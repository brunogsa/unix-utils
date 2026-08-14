---
name: quality-gate
description: "Run the full quality sweep over a branch — refactor, auto-review, planned-test presence — in parallel, writing missing tests, optionally auto-solving the rest. Triggers: /quality-gate, 'run the quality gate', 'full review pass', batch-end dispatch."
disable-model-invocation: false
---

# Quality Gate

Run every review lens this setup has over one branch, in parallel, then write the planned tests the plan is missing. When asked, also apply whatever else is safely applicable.

Three legs, each a fresh-context reviewer writing its own timestamped verdict file in CWD:

| Leg | Lens | Verdict file |
|---|---|---|
| `refactor` | structure, duplication, dead code, naming | `verdict_refactor_<ts>.md` |
| `auto-review` | correctness, edge cases, contract and spec conformance | `verdict_auto-review_<ts>.md` |
| `test-sdd` | planned tests the plan declared but the repo lacks | `verdict_test-sdd_<ts>.md` |

The third leg runs only when a plan resolves — without a plan there are no planned tests to check.

## Usage

```
/quality-gate [spec] [plan] [--tasks <ids>] [--base-ref <ref>] [--auto-solve | --report-only]
```

- `spec` / `plan` — paths in either order, recognised by their `spec_`/`plan_` filename prefix. Omit either to discover it in CWD.

- `--tasks <ids>` — comma-list of plan task ids (`1,2,5`) forwarded to the `test-sdd` leg to narrow its scope; omitted, it checks every task.

- `--base-ref <ref>` — review from this ref instead of `origin/HEAD` (branch, tag, or SHA); a caller that already knows its range passes it here.

- `--auto-solve` — skip the opening interview and apply the `refactor`/`auto-review` findings this run judges safe. Doesn't govern `test-sdd`, whose findings apply on every run that dispatches that leg (§5.1).

- `--report-only` — skip the interview the other way: leave every `refactor`/`auto-review` finding unapplied.
  - A skill caller that already asked its human passes one of the two flags, never neither, so §1 never stalls a batch on a prompt nobody is watching.

  - Both flags at once is a contradiction, not a precedence puzzle — stop and say so.

Examples:

- `/quality-gate` — discover spec/plan in CWD, ask before applying.
- `/quality-gate spec_itgd-3374.md plan_itgd-3374.md --auto-solve` — explicit paths, apply all three lenses.
- `/quality-gate --tasks 1,2 --auto-solve` — used by `/implement` to scope the `test-sdd` leg to its batch.
- `/quality-gate --base-ref abc1234 --report-only` — only the plan's missing tests get written.

## When to invoke

Direct `/quality-gate` invocation, phrases like "run the quality gate" / "full review pass" / "review and fix what's safe", or dispatch from another skill's flow.
`/implement`'s batch-end tail runs this, passing `--auto-solve` only when its own interview asked for it.

## 1. Ask about auto-solve — first, before anything else

**The question covers only the `refactor` and `auto-review` lenses** — `test-sdd` is outside it, see this section's closing note.

**Skip this step entirely when either `--auto-solve` or `--report-only` was passed.** The flag is the answer.

Otherwise ask one `AskUserQuestion`, before resolving files or dispatching anything:

- **Report only** (recommended default) — verdict files land in CWD, no refactor/auto-review finding is touched; the human decides later, by hand or via `/address-verdicts`.

- **Auto-solve** — after reports land, this session triages both lenses and hands safe findings to `/address-verdicts`.

Ask first, so a human wanting only a report is never surprised by commits, and one wanting fixes never has to re-invoke.

**The `test-sdd` lens is applied on every run that dispatches it, unconditionally** (§5.1) — a planned-test miss carries no design call, since the human already approved the plan that declared it.

## 2. Resolve the spec and the plan

Use any path given in the arguments as-is. For each of `spec` and `plan` not given, glob CWD, top-level only:

```bash
ls -1 spec_*.md plan_*.md 2>/dev/null
```

- **Exactly one spec and one plan** → use both; print the resolved paths, no prompt.
- **Zero of a kind** → proceed without it, and say so plainly.
  - No spec: the `auto-review` leg runs without spec-conformance context.
  - No plan: the `test-sdd` leg does not run at all, and the run has two legs instead of three.

- **More than one of a kind** → prompt with a numbered list and let the user pick; never guess which spec or plan was meant.

- **Under `--auto-solve` or `--report-only`, never prompt on a multi-match** → proceed without that kind and say so, exactly as a zero match resolves.
  - Either flag marks a run dispatched by a skill with nobody standing by —
    - the same premise §6 uses to force `--no-ask` — so a prompt here stalls the `/implement` tail indefinitely.

Also resolve `<BASE_REF>` for the `auto-review` leg:

```bash
~/.claude/scripts/resolve-base-ref.sh
```

The script falls back from `origin/HEAD` to local `main` to local `master`; a failed detection means none of the three exist.

If detection fails, ask which branch to diff against rather than guessing.

Under either flag, stop and print what failed instead, since a missing base has no safe default and proceeding would review the wrong range.

A caller may pass its own base ref via `--base-ref` instead — `/implement`'s batch-end tail passes `BATCH_BASE_SHA` that way.

## 3. Dispatch the legs in parallel

Spawn every leg as `agent(subAgent=deep-reviewer, …)`, all in the **same turn**, all in the background. They are independent report-only passes with no ordering dependency.

- `agent(subAgent=deep-reviewer, title=Refactor-lens review)` — invokes and executes the `refactor` skill (via the Skill tool).
- `agent(subAgent=deep-reviewer, title=Auto-review pipeline)` — invokes the `auto-review` skill, orchestrating from there with `<BASE_REF>` and the resolved spec/plan paths pushed in so it needs no interactive resolution.
- `agent(subAgent=deep-reviewer, title=Planned-test presence check)` — invokes and executes the `test-sdd` skill, with the resolved plan path and any `--tasks` ids pushed in; dispatch only when a plan resolved.

**Each leg performs its skill's reviewer role itself and never spawns a nested reviewer.**

It already *is* the fresh-context reviewer those skills would otherwise dispatch, and nesting would spend one of the harness's three levels on a second opinion nobody asked for.

Tell each leg this explicitly: the skills it invokes describe dispatching a reviewer, and without the override it would follow that literally.

Every leg mints its own `verdict_*.md` timestamp per its own skill, so repeated runs accumulate rather than collide.

The `deep-reviewer-write-guard.sh` hook backs the report-only contract at the tool layer — its exact terms live in [`deep-reviewer-tail-pair.md`](../code-review-pipeline/references/deep-reviewer-tail-pair.md), the single home for that wording.

Tell each leg the `/tmp` half too — the `auto-review` leg's waves persist there, and a leg that believes only `verdict_*` is writable skips the `$work_dir` persistence its compaction-resume depends on.

## 4. Collect the reports

When each leg returns, confirm its verdict file exists in CWD and is non-empty. Record the three resolved paths.

- **A leg's file is missing or empty** → re-dispatch once; still missing → flag it in the summary, let the other legs' reports stand, and move on.
  - Never retry twice — a leg that fails twice is for the human to look at, not a retry loop to grind on.

- **Never report from a leg's return message** — messages are capped and truncate long finding lists; the file is the source of truth.

## 5. Assemble the apply list

The two groups below enter the list on different terms. Compose the whole list before invoking anything, and print it before applying anything.

### 5.1. Every `test-sdd` finding goes in, unconditionally

Whenever §3 dispatched the `test-sdd` leg and §4 collected a non-empty file for it, every finding enters the apply list — report-only and auto-solve alike, with no triage.

Each names a test the plan declared and the repo lacks, so "is this worth doing" was already answered when the human approved the plan.

When §2 resolved no plan, that leg never dispatched and this sub-step contributes nothing.

### 5.2. `refactor` and `auto-review` findings go in only on an auto-solve run

**Report-only** (§1 resolved to it, or `--report-only`) → neither lens contributes anything, including trivially-safe-looking findings — the opt-in came from §1, and its absence is an answer.

**Auto-solve** (§1 resolved to it, or `--auto-solve`) → read both verdict files **in full**, never the legs' return summaries, sorting each finding into addressable or not.

- **Addressable** — small, well-scoped, clearly evidenced, low blast radius: a local simplification, a correctness fix with an obvious forcing case.
- **Not addressable** — design tradeoffs, cross-cutting risk, anything a leg flagged as uncertain, anything whose fix needs a product decision.

Print the accepted list before applying anything, one line per finding: `<lens>#N (<file>:<lines>) — <one-line recap> — accepted because <reason>`.
Print the rejected list in the same shape, carrying the rejection reason instead.
The relevance call is judgment, so it gets shown, not just its result.

## 6. Hand the apply list to `/address-verdicts`

**An empty apply list skips straight to §7** — a report-only run with no plan resolved has nothing to apply.

**Applying is not this skill's job** — `/address-verdicts` is the apply step for every `verdict_*.md` on disk, whoever wrote it.

This skill decides *which* findings deserve a fix, that one owns *how* every fix lands.

Duplicating its loop here would drift two copies of the lens routing, commit rule, and annotation format apart, leaving a human unable to tell which one their report followed.

Resolve the repo's test command first — a `package.json` script, a Makefile target, the repo's own CLAUDE.md — then invoke, **in this session**:

```
/address-verdicts <every finding identifier §5 assembled, with their verdict file paths> --no-ask --test-cmd <cmd>
```

**Pass the whole list in one invocation**, never one call per lens. That skill groups the list by lens itself, so a second call would only re-seed a TaskList it already owns.

- **The list is explicit** — naming each finding as its report does, so nothing re-derives §5.2's triage from a severity floor and widens scope.

- **`--no-ask` is mandatory here**, report-only or auto-solve alike.
  - §1 already asked this run's one question, so a prompt now would either re-ask it or stall a `/implement` tail with nobody standing by.

- **`--test-cmd` is passed** so its inference step has nothing left to guess — the one thing it would otherwise prompt for.

It runs in this session rather than a subagent, the same reason this skill sits in `/implement`'s main session.

It commits the `refactor` agent's work (a permission prompt only renders in main), and its per-lens apply agents are already fresh-context subagents.

So wrapping it would spend one of the harness's three nesting levels on a layer that decides nothing.

It returns the ledger §7 reports from: applied findings with SHAs, skipped findings with reasons, failures with retry needs.

## 7. Close with a report

Compose this from the ledger `/address-verdicts` returned, not from a second reading of the verdict files:

- Every verdict file path this run produced, plus any leg that failed to produce one, and the `test-sdd` leg when §2 resolved no plan to dispatch it with.

- **Every finding below carries its `<lens>#N (<file>:<lines>)` reference plus a one-line recap — never a bare id, count, or SHA alone.**

§5.2 already composed this for the accepted/rejected lines; reuse it.

A human reading the report should never have to open a verdict file to know what was decided.

- Applied findings, with commit SHA.
- Findings judged not addressable by §5.2, with the reason — they stay unmarked in their verdict files.

- **On a report-only run, every `refactor` and `auto-review` finding, under a heading naming them as never triaged.**
  - Nothing read them for addressability, so reporting them as "not addressable" would claim a judgment this run never made.
  - Close that section by naming both ways to work them: `/address-verdicts`, or a re-run as `/quality-gate --auto-solve`.

- Findings `/address-verdicts` skipped, with the reason — an ambiguity or a missing test command under `--no-ask`.
- Findings whose apply failed, with what it needs to retry.
- The plain statement that unmarked findings are untouched, and that a later `/address-verdicts` run — this time with a human answering — is how they get worked.

## Flowchart (human-facing)

[`assets/flowchart.md`](assets/flowchart.md) diagrams this skill's flow for the human. Don't load it — non-authoritative, the steps above win; regenerate it whenever the flow changes.
