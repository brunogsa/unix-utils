---
name: quality-gate
description: "Run the full quality sweep over a branch - refactor, auto-review, planned tests, metrics - in parallel, writing missing tests, optionally auto-solving the rest. Triggers: /quality-gate, 'run the quality gate', 'full review pass', batch-end dispatch."
disable-model-invocation: false
---

# Quality Gate

Run every review lens this setup has over one branch, in parallel, then write the planned tests the plan is missing. When asked, also apply whatever else is safely applicable.

Four legs, each a fresh-context reviewer; §4.1 merges them into one verdict in CWD, `verdict_quality-gate_<branch>_<ts>.md`:

| Leg | Lens | Entries in the merged file |
|---|---|---|
| `metrics` | measured size, complexity, coverage, dependency direction; judged splits and tests | first, tagged `[metrics]` |
| `refactor` | structure, duplication, dead code, naming | `[refactor]` |
| `auto-review` | correctness, edge cases, contract and spec conformance | `[auto-review]` |
| `test-sdd` | planned tests the plan declared but the repo lacks | `[test-sdd]` |

The `test-sdd` leg runs only when a plan resolves. The `metrics` leg needs no plan.

## Usage

```
/quality-gate [spec] [plan] [--tasks <ids>] [--base-ref <ref>] [--auto-solve | --report-only]
```

- `spec` / `plan` - paths in either order, recognised by their `spec_`/`plan_` filename prefix. Omit either to discover it in CWD.

- `--tasks <ids>` - comma-list of plan task ids (`1,2,5`) forwarded to the `test-sdd` leg; omitted, it checks every task.

- `--base-ref <ref>` - review from this ref instead of `origin/HEAD` (branch, tag, or SHA).

- `--auto-solve` - skip the opening interview and apply the `refactor`/`auto-review` findings this run judges safe. Doesn't govern `test-sdd` or `metrics` (§5.1, §5.3).

- `--report-only` - skip the interview the other way: leave every `refactor`/`auto-review` finding unapplied.
  - A skill caller that already asked its human passes one of the two flags, never neither, so §1 never stalls a batch on a prompt nobody is watching.

  - Both flags at once is a contradiction - stop and say so.

See [`references/more-examples.md`](references/more-examples.md) for example invocations, opened only when the flags above leave a case unclear.

`/implement`'s batch-end tail runs this, always with `--report-only`.

## 1. Ask about auto-solve - first, before anything else

**The question covers only the `refactor` and `auto-review` lenses.**

**Skip this step entirely when either `--auto-solve` or `--report-only` was passed.** The flag is the answer.

Otherwise ask one `AskUserQuestion`, before resolving files or dispatching anything:

- **Report only** (recommended default) - no refactor/auto-review finding is touched; the human decides later, by hand or by tagging headings `[AI!]` for `/address-verdicts`.

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

- **More than one of a kind** → prompt with a numbered list and let the user pick; never guess.

- **Under `--auto-solve` or `--report-only`, never prompt on a multi-match** → proceed without that kind, as a zero match resolves.
  - See [`references/dispatch-and-apply-rationale.md`](references/dispatch-and-apply-rationale.md).

Also resolve `<BASE_REF>`:

```bash
~/.claude/scripts/resolve-base-ref.sh
```

If detection fails, ask which branch to diff against - but under either flag, stop and print what failed, since a missing base has no safe default.

**No git repo encloses CWD** → skip this resolution and never stop: see [`references/metrics-leg.md`](references/metrics-leg.md) §3.

`/implement`'s batch-end tail passes `BATCH_BASE_SHA` via `--base-ref`.

## 3. Dispatch the legs in parallel

First mint the run directory, before any dispatch: `RUN_DIR=$(mktemp -d /tmp/quality-gate.XXXXXX)`. §4.1 reuses it.

Spawn each leg as its own agent - `code-reviewer` for the refactor, auto-review and metrics legs, `test-reviewer` for the planned-test leg - all in the **same turn**, all in the background. They are independent report-only passes.

- `agent(subAgent=code-reviewer, title=Refactor-lens review)` - invokes and executes the `refactor` skill (via the Skill tool).

- `agent(subAgent=code-reviewer, title=Auto-review pipeline)` - invokes the `auto-review` skill with `<BASE_REF>`, the resolved spec/plan paths and `<SESSION_ID>` pushed in.

- `agent(subAgent=test-reviewer, title=Planned-test presence check)` - invokes and executes the `test-sdd` skill, with the plan path, `<BASE_REF>`, any `--tasks` ids, and `--out-dir <RUN_DIR>` pushed in; dispatch only when a plan resolved.

- `agent(subAgent=code-reviewer, title=Metrics-lens review)` - follows [`references/metrics-lens.md`](references/metrics-lens.md), with `<RUN_DIR>`, `<BASE_REF>`, HEAD and `<SESSION_ID>` pushed in; dispatch whether or not a plan resolved.
  - `<SESSION_ID>` is main's own, the last segment of its scratchpad path.
  - Read [`references/metrics-leg.md`](references/metrics-leg.md) first: main dispatches the inspector, relays tooling asks, and handles a failed leg.

**Each leg performs its skill's reviewer role itself and never spawns a nested reviewer.**

Tell each leg this, since its skill describes dispatching a reviewer. See [`references/dispatch-and-apply-rationale.md`](references/dispatch-and-apply-rationale.md).

The `check-reviewer-writes.sh` hook backs report-only; its terms are in [`code-reviewer-tail-pair.md`](../code-review-pipeline/references/code-reviewer-tail-pair.md).

Tell each leg the `/tmp` half too: a leg that believes only `verdict_*` is writable skips the `$work_dir` persistence its compaction-resume needs.

## 4. Collect the reports

When each leg returns, confirm its file exists and is non-empty: `refactor` and `auto-review` in CWD, `test-sdd` and `metrics` in `<RUN_DIR>` (`verdict_{metrics,quality-gate_no-git}_*.md` plus `metrics-judge_*.md`).
- **A leg's file is missing or empty** → re-dispatch once; still missing → flag it in the summary and let the other legs stand.
  - Never retry twice - a twice-failed leg is for the human.

- **Never report from a leg's return message** - messages truncate long lists; the file is the source of truth.

### 4.1. Merge the legs' files into one verdict

**No leg produced a file** → skip this step. Otherwise merge whatever exists, so shape and tags are uniform, on report-only and auto-solve runs alike.

Record the source paths, and the merged path in CWD: `date "+verdict_quality-gate_$(git branch --show-current | tr '/' '-')_%Y-%m-%d_%H:%M.md"`, or `verdict_quality-gate_no-git_<ts>.md` with no git. Sources are the `refactor`, `auto-review` and `test-sdd` files, the judge file, and `<RUN_DIR>/detector-edits.md` when main wrote one.

Count findings yourself, fence-aware, since a finding may quote a `### 1.` line inside a code fence: ``awk '/^[[:space:]]*[`][`][`]/{f=!f} !f && /^### [0-9]+\. /' <file> | wc -l``.
- Run it on each source, and on the rendered metrics verdict to get k (0 with none).

Dispatch ONE `code-reviewer` (fresh context, foreground) with exactly those source paths (never a glob), k, `<RUN_DIR>/merged-findings.md`, and [`references/merge-review-verdicts.md`](references/merge-review-verdicts.md). It writes only that file, numbered from k+1, and merges reports only.

Then assemble: `cat <rendered> <RUN_DIR>/merged-findings.md | ~/.claude/scripts/write-atomically.py <merged path>`. See [`references/dispatch-and-apply-rationale.md`](references/dispatch-and-apply-rationale.md) for why main assembles.

Verify without reading the merged file into main:

- It exists and is non-empty, and `check-finding-bodies.py` exits 0 on `<RUN_DIR>/merged-findings.md` alone.

- The merged count, counted the same way, equals k plus the sources' summed findings minus those absorbed (a group of k duplicates absorbs k-1).

- Every heading carries exactly one of `auto-review|refactor|test-sdd|metrics`, so this prints 0: ``awk '/^[[:space:]]*[`][`][`]/{f=!f} !f && /^### [0-9]+\. /{if(gsub(/\[(auto-review|refactor|test-sdd|metrics)\]/,"&")!=1)b++} END{print b+0}' <merged path>``.

**Pass** → move (never delete) the `refactor` and `auto-review` files into `<RUN_DIR>`, so `/address-verdicts` can't apply one finding from both the merged file and its source. Record the moved paths for §7.

**Fail** → move the failed merged file into `<RUN_DIR>`, and move every source file back into CWD as this run's output. Say so in §7.

## 5. Assemble the apply list

Compose and print the whole list before applying anything. The groups below enter on different terms.

### 5.1. Every missing-planned-test finding goes in, without triage

Every finding `~/.claude/scripts/get-test-sdd-dispatch-list.py <merged file>` prints enters the apply list (the `test-sdd` file on §4.1's fallback), report-only and auto-solve alike; §7 reports the unplanned-tests finding it omits.

One exception: a planned test whose target is prose is never written, because CLAUDE.md forbids tests over non-code artifacts. It still enters the list, and `/address-verdicts` §4 annotates it `SKIPPED`.

### 5.2. `refactor` and `auto-review` findings go in only on an auto-solve run

**Report-only** → neither lens contributes anything, including trivially-safe-looking findings - the opt-in came from §1.

**Auto-solve** → read the merged file **in full** (the source files on §4.1's fallback), never the legs' return summaries, sorting each finding into addressable or not.

- **Addressable** - small, well-scoped, clearly evidenced, low blast radius.
- **Not addressable** - design tradeoffs, cross-cutting risk, anything a leg flagged as uncertain, anything whose fix needs a product decision.

Print the accepted list before applying, one line per finding: `quality-gate#N [<lens>] (<file>:<lines>) - <one-line recap> - accepted because <reason>`.

Print the rejected list the same way, with the rejection reason. On the fallback use `<lens>#N (...)`.

### 5.3. Every open metrics violation goes in, on report-only and auto-solve alike

The plan approval already asked for measured quality, so no triage runs. Enter every entry under the rendered file's `## Open violations`, plus every `[metrics]` judge finding.

Ranked lists, exceptions and deferred entries stay out: they repeat a violation or are rulings. List the numbers with the awk in [`references/metrics-leg.md`](references/metrics-leg.md) §5.

An entry the fix cannot clear, or a rejected exception, stays unmarked, open and first, and nothing blocks the PR.

## 6. Hand the apply list to `/address-verdicts`

**An empty apply list skips straight to §7.**

**Applying is not this skill's job** - `/address-verdicts` is the apply step for every `verdict_*.md` on disk, whoever wrote it.

Resolve the repo's test command first - a `package.json` script, a Makefile target, the repo's own CLAUDE.md - then invoke, **in this session**:

```
/address-verdicts <every finding identifier §5 assembled, with their verdict file paths - the merged file's path for merged findings> --no-ask --test-cmd <cmd>
```

**Pass the whole list in one invocation**, never one call per lens. That skill groups the list by lens itself.

- **The list is explicit** - naming each finding as its report does, so nothing re-derives §5.2's triage from a severity floor.

- **`--no-ask` is mandatory here**, report-only or auto-solve alike.
  - §1 already asked this run's one question, so a prompt now would re-ask it or stall a `/implement` tail.

- **`--test-cmd` is passed** so its inference step has nothing left to prompt for.

It runs in this session, never wrapped in a subagent, because it commits and a permission prompt only renders in main.

See [`references/dispatch-and-apply-rationale.md`](references/dispatch-and-apply-rationale.md) for why applying is its job.

It returns the ledger §7 reports from: applied findings with SHAs, skipped findings with reasons, failures with retry needs.

## 7. Close with a report

Compose this from the ledger `/address-verdicts` returned, not from a second reading of the verdict files.

- Every verdict file path this run produced: the merged file, the rendered metrics verdict and judge file (now in `<RUN_DIR>`), the source paths §4.1 moved, and the fallback when it happened.
  - Also any leg that failed to produce a file, and the `test-sdd` leg when §2 resolved no plan.

- **A failed metrics leg reads `metrics: not measured (<reason>)`, never as clean.**

- Any deferred tooling ask, with its reading: `pessimistic, tooling deferred` or `not measured: no language entry`.

- Metrics apply outcomes: each open violation fixed with its SHA, and each still open, including rejected exceptions.

- **Every finding below carries its `quality-gate#N [<lens>] (<file>:<lines>)` reference (`<lens>#N (...)` on the fallback) plus a one-line recap - never a bare id, count, or SHA alone.**

- Applied findings, with commit SHA.
- Findings judged not addressable by §5.2, with the reason - they stay unmarked in their verdict files.

- **On a report-only run, every `refactor` and `auto-review` finding, under a heading naming them as never triaged.**
  - No one judged them addressable, so "not addressable" would claim a judgment never made.
  - Close that section by naming both ways to work them: tag the chosen headings `[AI!]` and run `/address-verdicts`, or re-run as `/quality-gate --auto-solve`.

- The `test-sdd` `Unplanned tests added by the branch` finding, its tests listed, never dispatched, for the human to mark `[Done]`.

- Findings `/address-verdicts` skipped, with the reason, and findings whose apply failed, with what it needs to retry.
- The plain statement that unannotated findings are untouched, and that tagging them `[AI!]` for a later `/address-verdicts` run - this time with a human answering - is how they get worked.

## Flowchart (human-facing)

[`assets/flowchart.md`](assets/flowchart.md) diagrams this skill's flow for the human. Don't load it - non-authoritative, the steps above win; regenerate it whenever the flow changes.
