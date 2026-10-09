---
name: quality-gate
description: "Run the full quality sweep over a branch - refactor, auto-review, planned-test presence - in parallel, writing missing tests, optionally auto-solving the rest. Triggers: /quality-gate, 'run the quality gate', 'full review pass', batch-end dispatch."
disable-model-invocation: false
---

# Quality Gate

Run every review lens this setup has over one branch, in parallel, then write the planned tests the plan is missing. When asked, also apply whatever else is safely applicable.

Three legs, each a fresh-context reviewer writing a timestamped verdict file in CWD; §4.1 merges the first two into one:

| Leg | Lens | Verdict file |
|---|---|---|
| `refactor` | structure, duplication, dead code, naming | merged `verdict_quality-gate_<branch>_<ts>.md` |
| `auto-review` | correctness, edge cases, contract and spec conformance | merged `verdict_quality-gate_<branch>_<ts>.md` |
| `test-sdd` | planned tests the plan declared but the repo lacks | `verdict_test-sdd_<branch>_<ts>.md` |

The third leg runs only when a plan resolves.

## Usage

```
/quality-gate [spec] [plan] [--tasks <ids>] [--base-ref <ref>] [--auto-solve | --report-only]
```

- `spec` / `plan` - paths in either order, recognised by their `spec_`/`plan_` filename prefix. Omit either to discover it in CWD.

- `--tasks <ids>` - comma-list of plan task ids (`1,2,5`) forwarded to the `test-sdd` leg to narrow its scope; omitted, it checks every task.

- `--base-ref <ref>` - review from this ref instead of `origin/HEAD` (branch, tag, or SHA); a caller that already knows its range passes it here.

- `--auto-solve` - skip the opening interview and apply the `refactor`/`auto-review` findings this run judges safe. Doesn't govern `test-sdd` (§5.1).

- `--report-only` - skip the interview the other way: leave every `refactor`/`auto-review` finding unapplied.
  - A skill caller that already asked its human passes one of the two flags, never neither, so §1 never stalls a batch on a prompt nobody is watching.

  - Both flags at once is a contradiction, not a precedence puzzle - stop and say so.

See [`references/more-examples.md`](references/more-examples.md) for example invocations, opened only when the flags above leave a case unclear.

`/implement`'s batch-end tail runs this, passing `--auto-solve` only when its own interview asked for it.

## 1. Ask about auto-solve - first, before anything else

**The question covers only the `refactor` and `auto-review` lenses.**

**Skip this step entirely when either `--auto-solve` or `--report-only` was passed.** The flag is the answer.

Otherwise ask one `AskUserQuestion`, before resolving files or dispatching anything:

- **Report only** (recommended default) - verdict files land in CWD, no refactor/auto-review finding is touched; the human decides later, by hand or via `/address-verdicts`.

- **Auto-solve** - after reports land, this session triages both lenses and hands safe findings to `/address-verdicts`.

## 2. Resolve the spec and the plan

Use any path given in the arguments as-is. For each of `spec` and `plan` not given, glob CWD, top-level only:

```bash
ls -1 spec_*.md plan_*.md 2>/dev/null
```

- **Exactly one spec and one plan** → use both; print the resolved paths, no prompt.
- **Zero of a kind** → proceed without it, and say so plainly.
  - No spec: the `auto-review` leg runs without spec-conformance context.
  - No plan: the `test-sdd` leg does not run at all.

- **More than one of a kind** → prompt with a numbered list and let the user pick; never guess which spec or plan was meant.

- **Under `--auto-solve` or `--report-only`, never prompt on a multi-match** → proceed without that kind and say so, exactly as a zero match resolves.
  - Either flag means nobody is standing by; see [`references/dispatch-and-apply-rationale.md`](references/dispatch-and-apply-rationale.md).

Also resolve `<BASE_REF>` for the `auto-review` leg:

```bash
~/.claude/scripts/resolve-base-ref.sh
```

The script falls back from `origin/HEAD` to local `main` to local `master`.

If detection fails, ask which branch to diff against rather than guessing - but under either flag, stop and print what failed, since a missing base has no safe default.

`/implement`'s batch-end tail passes `BATCH_BASE_SHA` via `--base-ref`.

## 3. Dispatch the legs in parallel

Spawn each leg as its own agent per role - `code-reviewer` for the refactor-lens and auto-review legs, `test-reviewer` for the planned-test-presence leg - all in the **same turn**, all in the background. They are independent report-only passes with no ordering dependency.

- `agent(subAgent=code-reviewer, title=Refactor-lens review)` - invokes and executes the `refactor` skill (via the Skill tool).

- `agent(subAgent=code-reviewer, title=Auto-review pipeline)` - invokes the `auto-review` skill, orchestrating from there with `<BASE_REF>` and the resolved spec/plan paths pushed in so it needs no interactive resolution.

- `agent(subAgent=test-reviewer, title=Planned-test presence check)` - invokes and executes the `test-sdd` skill, with the resolved plan path and any `--tasks` ids pushed in; dispatch only when a plan resolved.

**Each leg performs its skill's reviewer role itself and never spawns a nested reviewer.**

Tell each leg this explicitly, since the skills it invokes describe dispatching a reviewer. See [`references/dispatch-and-apply-rationale.md`](references/dispatch-and-apply-rationale.md) for why nesting is ruled out.

The `check-reviewer-writes.sh` hook backs the report-only contract at the tool layer - its exact terms live in [`code-reviewer-tail-pair.md`](../code-review-pipeline/references/code-reviewer-tail-pair.md).

Every leg mints its own `verdict_*.md` timestamp per its own skill, so repeated runs accumulate rather than collide.

Tell each leg the `/tmp` half too: a leg that believes only `verdict_*` is writable skips the `$work_dir` persistence its compaction-resume depends on.

## 4. Collect the reports

When each leg returns, confirm its verdict file exists in CWD and is non-empty.
- **A leg's file is missing or empty** → re-dispatch once; still missing → flag it in the summary, let the other legs' reports stand, and move on.
  - Never retry twice - a twice-failed leg is for the human.

- **Never report from a leg's return message** - messages truncate long lists; the file is the source of truth.

### 4.1. Merge the `refactor` and `auto-review` files into one verdict

**Neither file exists** → skip this step. **Only one exists** → still merge it, so the output shape and lens tags are uniform. It runs on report-only and auto-solve runs alike.

Record the resolved source paths. Mint the run directory `mktemp -d /tmp/quality-gate.XXXXXX` once, and the merged path in CWD: `date "+verdict_quality-gate_$(git branch --show-current | tr '/' '-')_%Y-%m-%d_%H:%M.md"`.

Before dispatching, count each source file's findings yourself, fence-aware, since a finding may quote a `### 1.` line inside a code fence: ``awk '/^[[:space:]]*[`][`][`]/{f=!f} !f && /^### [0-9]+\. /' <file> | wc -l``.

Dispatch ONE `code-reviewer` (fresh context, foreground) with exactly those source paths, never a glob that could pick up a stale file, plus the merged path and [`references/merge-review-verdicts.md`](references/merge-review-verdicts.md), which holds its rules. It merges reports only.

Verify without reading the file into main:

- It exists and is non-empty, and main's own run of `check-finding-bodies.py` on it exits 0.

- The finding count, counted the same way, equals main's per-lens input counts minus the findings absorbed (a group of k duplicates collapses into one and absorbs k-1).
  - An upper bound would let dropped findings pass, and the agent's own input counts would let it hide one; both vanish once the sources move.

- Every finding heading carries exactly one `[auto-review]` or `[refactor]` tag, so this prints 0: ``awk '/^[[:space:]]*[`][`][`]/{f=!f} !f && /^### [0-9]+\. /{if(gsub(/\[(auto-review|refactor)\]/,"&")!=1)b++} END{print b+0}' <file>``.

**Pass** → move (never delete) both source files into the run directory, so `/address-verdicts` can't apply one finding from both the merged file and its source. Record the moved paths for §7.

**Fail** → keep the source files in CWD as this run's output, move the failed merged file into the run directory instead, and say so in §7.

## 5. Assemble the apply list

Compose the whole list, and print it, before applying anything. The two groups below enter the list on different terms.

### 5.1. Every `test-sdd` finding goes in, without triage

When §4 collected a non-empty `test-sdd` file, every finding enters the apply list - report-only and auto-solve alike.

Each names a test the plan declared and the repo lacks, so the human's plan approval already answered "is this worth doing".

One exception: a planned test whose target is prose is never written, because CLAUDE.md forbids tests over non-code artifacts.

It still enters the list, and `/address-verdicts` §4 annotates it `SKIPPED`.

With no plan resolved (§2), this sub-step contributes nothing.

### 5.2. `refactor` and `auto-review` findings go in only on an auto-solve run

**Report-only** (§1 resolved to it, or `--report-only`) → neither lens contributes anything, including trivially-safe-looking findings - the opt-in came from §1.

**Auto-solve** (§1 resolved to it, or `--auto-solve`) → read the merged file **in full** (the two source files on §4.1's fallback path), never the legs' return summaries, sorting each finding into addressable or not.

- **Addressable** - small, well-scoped, clearly evidenced, low blast radius: a local simplification, a correctness fix with an obvious forcing case.
- **Not addressable** - design tradeoffs, cross-cutting risk, anything a leg flagged as uncertain, anything whose fix needs a product decision.

Print the accepted list before applying anything, one line per finding: `quality-gate#N [<lens>] (<file>:<lines>) - <one-line recap> - accepted because <reason>`.

Print the rejected list in the same shape, carrying the rejection reason instead.

On the fallback path use `<lens>#N (<file>:<lines>)`. The relevance call is judgment, so it gets shown, not just its result.

## 6. Hand the apply list to `/address-verdicts`

**An empty apply list skips straight to §7** - a report-only run with no plan resolved has nothing to apply.

**Applying is not this skill's job** - `/address-verdicts` is the apply step for every `verdict_*.md` on disk, whoever wrote it.

Resolve the repo's test command first - a `package.json` script, a Makefile target, the repo's own CLAUDE.md - then invoke, **in this session**:

```
/address-verdicts <every finding identifier §5 assembled, with their verdict file paths - the merged file's path for merged findings> --no-ask --test-cmd <cmd>
```

**Pass the whole list in one invocation**, never one call per lens. That skill groups the list by lens itself, so a second call would only re-seed a TaskList it already owns.

- **The list is explicit** - naming each finding as its report does, so nothing re-derives §5.2's triage from a severity floor and widens scope.

- **`--no-ask` is mandatory here**, report-only or auto-solve alike.
  - §1 already asked this run's one question, so a prompt now would either re-ask it or stall a `/implement` tail with nobody standing by.

- **`--test-cmd` is passed** so its inference step has nothing left to prompt for.

It runs in this session, never wrapped in a subagent, because it commits and a permission prompt only renders in main.

See [`references/dispatch-and-apply-rationale.md`](references/dispatch-and-apply-rationale.md) for why applying is its job.

It returns the ledger §7 reports from: applied findings with SHAs, skipped findings with reasons, failures with retry needs.

## 7. Close with a report

Compose this from the ledger `/address-verdicts` returned, not from a second reading of the verdict files. A human reading the report should never have to open a verdict file to know what was decided.

- Every verdict file path this run produced: the merged file, the source paths §4.1 moved, and the fallback when it happened.
  - Also any leg that failed to produce a file, and the `test-sdd` leg when §2 resolved no plan.

- **Every finding below carries its `quality-gate#N [<lens>] (<file>:<lines>)` reference (`<lens>#N (...)` for `test-sdd` and the fallback) plus a one-line recap - never a bare id, count, or SHA alone.**
  - §5.2 already composed this; reuse it.

- Applied findings, with commit SHA.
- Findings judged not addressable by §5.2, with the reason - they stay unmarked in their verdict files.

- **On a report-only run, every `refactor` and `auto-review` finding, under a heading naming them as never triaged.**
  - Nothing read them for addressability, so reporting them as "not addressable" would claim a judgment this run never made.
  - Close that section by naming both ways to work them: `/address-verdicts`, or a re-run as `/quality-gate --auto-solve`.

- Findings `/address-verdicts` skipped, with the reason - an ambiguity or a missing test command under `--no-ask`.
- Findings whose apply failed, with what it needs to retry.
- The plain statement that unmarked findings are untouched, and that a later `/address-verdicts` run - this time with a human answering - is how they get worked.

## Flowchart (human-facing)

[`assets/flowchart.md`](assets/flowchart.md) diagrams this skill's flow for the human. Don't load it - non-authoritative, the steps above win; regenerate it whenever the flow changes.
