---
name: quality-gate
description: "Run the quality sweep over a branch - refactor, auto-review, planned tests, scouts, metrics - in parallel, writing missing tests, optionally auto-solving the rest. Triggers: /quality-gate, 'run the quality gate', 'full review pass', batch-end."
disable-model-invocation: false
---

# Quality Gate

Run every review lens this setup has over one branch, in parallel, then write the planned tests the plan is missing. By default, also apply what a judge rules Fix.

Five legs, each a fresh-context reviewer; §4.1 merges them into one verdict in CWD, `verdict_quality-gate_<branch>_<ts>.md`:

| Leg | Lens | Entries in the merged file |
|---|---|---|
| `metrics` | measured size, complexity, coverage, dependency direction; judged splits and tests | first, tagged `[metrics]` |
| `refactor` | structure, duplication, dead code, naming | `[refactor]` |
| `auto-review` | correctness, edge cases, contract and spec conformance | `[auto-review]` |
| `test-sdd` | planned tests the plan declared but the repo lacks | `[test-sdd]` |
| `scout` | pending `[Scout]` tasks that belong to this branch, judged fresh | `[scout]` |

A whole run (§1 through §7, apply included) targets 20 minutes of wall-clock or less, never a reason to cut a gate short.

Main notes each phase's start and end (`date +%H:%M:%S`) in its scratchpad as it happens: each §3 leg with its own end, §4.1, §4.2, §6 with each `/address-verdicts` dispatch's start and end, and §7.

## Usage

```
/quality-gate [spec] [plan] [--tasks <ids>] [--base-ref <ref>] [--auto-solve | --report-only]
```

- `spec` / `plan` - paths in either order, recognised by their `spec_`/`plan_` filename prefix. Omit either to discover it in CWD.

- `--tasks <ids>` - comma-list of plan task ids (`1,2,5`) for the `test-sdd` leg.
  - Omitted, it takes the ids `get-plan-tasks-for-branch.py` derives from the plan's PR entry for the current branch, else every task when no entry names it.

- `--base-ref <ref>` - review from this ref instead of `origin/HEAD` (branch, tag, or SHA).

- `--auto-solve` - skip the interview; a judge rules each `refactor`, `auto-review`, `metrics` and `scout` finding Fix or Skip, and every Fix applies.

- `--report-only` - skip the interview the other way; only `test-sdd` findings apply.
  - A skill caller that already asked its human passes one flag, so §1 never stalls a batch.

  - Both flags at once is a contradiction - stop and say so.

See [`references/more-examples.md`](references/more-examples.md) for example invocations, only when the flags above leave a case unclear.

## 1. Ask about auto-solve - first, before anything else

**The question covers the `refactor`, `auto-review`, `metrics` and `scout` lenses.**

**Skip this step entirely when either `--auto-solve` or `--report-only` was passed.** The flag is the answer.

Otherwise ask one `AskUserQuestion`, before resolving files or dispatching anything:

- **Auto-solve** (recommended default) - a fresh judge rules each finding Fix or Skip, every Fix applies.

- **Report only** - only `test-sdd` findings apply; the human decides the rest, by hand or by tagging headings `[AI!]` for `/address-verdicts`.

## 2. Resolve the spec and the plan

Use any path given in the arguments as-is. For each of `spec` and `plan` not given, glob CWD, top-level only:

```bash
ls -1 spec_*.md plan_*.md 2>/dev/null
```

- **Exactly one spec and one plan** → use both; print the resolved paths, no prompt.
- **Zero of a kind** → proceed without it, and say so.
  - No spec: the `auto-review` leg runs without spec-conformance context.
  - No plan: the `test-sdd` leg does not run at all.

- **More than one of a kind** → prompt with a numbered list and let the user pick; never guess.

- **Under `--auto-solve` or `--report-only`, never prompt on a multi-match** → proceed without that kind, as a zero match resolves.
  - See [`references/dispatch-and-apply-rationale.md`](references/dispatch-and-apply-rationale.md).

Also resolve `<BASE_REF>`:

```bash
~/.claude/scripts/resolve-base-ref.sh
```

If detection fails, ask which branch to diff against; under either flag, stop and print what failed, since a missing base has no safe default.

**No git repo encloses CWD** → skip this resolution and never stop: see [`metrics-leg.md`](../metrics-review/references/metrics-leg.md) §3.

## 3. Dispatch the legs in parallel

First mint the run directory: `RUN_DIR=$(mktemp -d /tmp/quality-gate.XXXXXX)`. §4.1 reuses it.

`<SESSION_ID>` is the path segment just above `scratchpad` in the main session's scratchpad path.

Then export the pending scouts: `~/.claude/scripts/export-open-scouts.py <SESSION_ID> <RUN_DIR>/open-scouts.md`. It prints the count of pending `[Scout]` tasks.

With no git, skip the export. Settle each outcome per [`scout-leg.md`](references/scout-leg.md) "Export outcomes".

Spawn each leg as its own agent, all in the **same turn**, all in the background.

- `agent(subAgent=code-reviewer, title=Refactor-lens review)` - invokes and executes the `refactor` skill with `<BASE_REF>` as its `--base-ref`.

- `agent(subAgent=code-reviewer, title=Auto-review pipeline)` - invokes the `auto-review` skill with `<BASE_REF>`, the resolved spec/plan paths and `<SESSION_ID>` pushed in.

- **Scope the test-sdd leg** (plan resolved, no `--tasks`): main runs `~/.claude/scripts/get-plan-tasks-for-branch.py <plan> "$(git branch --show-current)"`.
  - **Non-empty output** → pass it as the leg's `--tasks`.
  - **Empty output, exit 0** → no `--tasks`; §7 reads `test-sdd: every plan task (no PR entry names <branch>)`.
  - **Non-zero exit** → dispatch no test-sdd leg; §7 reads `test-sdd leg: FAIL (task scoping exited <rc>: <its stderr>)`, a failing outcome, never a clean one.

- `agent(subAgent=test-reviewer, title=Planned-test presence check)` - invokes and executes the `test-sdd` skill, with the plan path, `<BASE_REF>`, its `--tasks` ids, and `--out-dir <RUN_DIR>` pushed in; dispatch only when a plan resolved.

- `agent(subAgent=code-reviewer, title=Scout-lens review)` - follows [`references/scout-leg.md`](references/scout-leg.md), with `<RUN_DIR>`, `<BASE_REF>`, the spec and plan paths, and the export path pushed in.
  - Dispatch it only when the export printed a count above 0.

- Run the `metrics-review` skill ([`../metrics-review/SKILL.md`](../metrics-review/SKILL.md)) in this session, in parallel with the other legs, with `<RUN_DIR>`, `<BASE_REF>`, HEAD and `<SESSION_ID>` pushed in; dispatch whether or not a plan resolved.
  - Main runs it, since the inspector dispatch and the tooling asks are main's, and the skill dispatches the `code-reviewer` that follows [`metrics-lens.md`](../metrics-review/references/metrics-lens.md) in the background.

  - Never pass the `refactor` and `auto-review` legs a `--metrics` flag: this leg already measures, and a second measurement is the duplicate that flag exists to avoid.

**Each leg performs its skill's reviewer role itself and never spawns a nested reviewer.** Carve-out: the auto-review leg's `code-review-pipeline` run may spawn its own lens agents (`agents/code-reviewer.md`).

Tell each leg this, since its skill describes dispatching a reviewer ([`references/dispatch-and-apply-rationale.md`](references/dispatch-and-apply-rationale.md)).

The `check-reviewer-writes.sh` hook backs report-only; its terms are in [`code-reviewer-tail-pair.md`](../code-review-pipeline/references/code-reviewer-tail-pair.md).

Tell each leg the `/tmp` half too: a leg that believes only `verdict_*` is writable skips the `$work_dir` persistence its compaction-resume needs.

## 4. Collect the reports

When each leg returns, confirm its file exists and is non-empty: `refactor` and `auto-review` in CWD, `test-sdd`, `scout` (`scout-leg_<ts>.md` and `scout-classification.md`, each counting) and `metrics` in `<RUN_DIR>` (`verdict_{metrics,quality-gate_no-git}_*.md` plus `metrics-judge_*.md`).
- **A leg's file is missing or empty** → re-dispatch once; still missing → flag it in the summary and let the other legs stand.

- **Never report from a leg's return message** - it truncates long lists.

### 4.1. Merge the legs' files into one verdict

**No leg produced a file** → skip this step. Otherwise merge whatever exists, so shape and tags are uniform on every run.

Record the source paths and the merged path in CWD: `date "+verdict_quality-gate_$(git branch --show-current | tr '/' '-')_%Y-%m-%d_%H:%M.md"`, or `verdict_quality-gate_no-git_<ts>.md` with no git. Sources are the `refactor`, `auto-review`, `test-sdd` and `scout` files, the judge file, and `<RUN_DIR>/detector-edits.md` when main wrote one.

Count findings fence-aware, since a finding may quote a `### 1.` line in a fence: ``awk '/^[[:space:]]*[`][`][`]/{f=!f} !f && /^### [0-9]+\. /' <file> | wc -l``.
- Run it on each source, and on `<tooling>` for k (0 with none): the `tooling_metrics_*.md` beside the rendered verdict, numbered as it numbers its deferred, tooling-ask and exception entries.

Dispatch ONE `code-reviewer` (fresh context, foreground) with exactly those source paths (never a glob), k, `<RUN_DIR>/merged-findings.md`, and [`references/merge-review-verdicts.md`](references/merge-review-verdicts.md). It writes only that file, numbered from k+1.

Then assemble: `cat <tooling> <RUN_DIR>/merged-findings.md | ~/.claude/scripts/write-atomically.py <merged path>`, so the human reads only tooling problems above `## Findings`. See [`references/dispatch-and-apply-rationale.md`](references/dispatch-and-apply-rationale.md) for why main assembles.

Verify without reading the merged file into main:

- It exists and is non-empty, and `check-finding-bodies.py` and the [`merge-review-verdicts.md`](references/merge-review-verdicts.md) prose checkers exit 0 on `<RUN_DIR>/merged-findings.md` alone.
  - A prose hit first re-dispatches the merge agent once with that output.

- The merged count, fence-aware, equals k plus the sources' summed findings minus those absorbed.

- Every heading carries exactly one of `auto-review|refactor|test-sdd|metrics|scout`, so this prints 0: ``awk '/^[[:space:]]*[`][`][`]/{f=!f} !f && /^### [0-9]+\. /{if(gsub(/\[(auto-review|refactor|test-sdd|metrics|scout)\]/,"&")!=1)b++} END{print b+0}' <merged path>``.

**Pass** → move (never delete) the `refactor` and `auto-review` files into `<RUN_DIR>`, so `/address-verdicts` can't apply one finding from both the merged file and its source. Record the moved paths for §7.

Then settle the scout tasks as [`scout-leg.md`](references/scout-leg.md) "Settle the tasks" says: delete each in-goal one the merged file carries, complete each already fixed, keep the rest, and write `<RUN_DIR>/scout-outcomes.md`.

**Fail** → move the merged file into `<RUN_DIR>`, and move every source file except the scout files, and the rendered metrics verdict, back into CWD. Leave `scout-leg_<ts>.md` in `<RUN_DIR>` and change no scout task: they stay pending for the next gate run. Say so in §7.

### 4.2. Judge each finding Fix or Skip - auto-solve only

Runs on auto-solve when §4.1 passed. Report-only and §4.1's fallback skip it.

Main copies the merged file to `<RUN_DIR>/pre-judge.md`. Then it dispatches ONE `agent(subAgent=code-reviewer, title=Fix-or-Skip judge)` in the foreground with [`references/fix-judge.md`](references/fix-judge.md) §1, and runs that file's §3 checks.

The judge rules `[scout]` findings exactly like `refactor`, `auto-review` and `metrics` ones, so an in-goal scout is judged, and under auto-solve applied, with no human step.

On §4.1's fallback under auto-solve, apply `test-sdd` only and report `judge: not run (merge fell back)`.

## 5. Assemble the apply list

### 5.1. Every missing-planned-test finding goes in, without triage

Every finding `~/.claude/scripts/get-test-sdd-dispatch-list.py <merged file>` prints enters the apply list (the `test-sdd` file on §4.1's fallback), report-only and auto-solve alike; §7 reports the unplanned-tests finding it omits.

One exception: a planned test whose target is prose is never written, because CLAUDE.md forbids tests over non-code artifacts. It still enters the list, and `/address-verdicts` §4 annotates it `SKIPPED`.

### 5.2. Fix-ruled findings go in on an auto-solve run

Auto-solve adds the numbers `~/.claude/scripts/get-fix-apply-list.py <merged>` prints, per [`references/fix-judge.md`](references/fix-judge.md) §2. The tooling entries above `## Findings` never enter; only the judge's `[metrics]` findings do.

Report-only adds nothing else.

Print the composed list, one line per finding, before applying.

## 6. Hand the apply list to `/address-verdicts`

**An empty apply list skips straight to §7.**

**Applying is not this skill's job** - `/address-verdicts` is the apply step for every `verdict_*.md` on disk, whoever wrote it.

Resolve the repo's test command first, then invoke, **in this session**:

```
/address-verdicts <every finding identifier §5 assembled, with their verdict file paths - the merged file's path for merged findings> --no-ask --test-cmd <cmd>
```

**Pass the whole list in one invocation**, never one call per lens.

- **The list is explicit** - each finding named as its report names it.

- **`--no-ask` is mandatory here**, report-only or auto-solve alike.

- **Pass `--test-cmd`**, so it has nothing to infer.

- **A scout found while applying goes to the TaskList** like any other, and the next gate run exports it; the scout leg never re-runs in this run.

### 6.1. One fix review over every applied commit

**Disabled since 2026-11-17: skip this step, and §7 reports `fix review: disabled`.** The user disabled it while finding out what makes a run slow. Delete this notice once the user has reviewed §7's per-phase timings and turns the review back on.

Skipped when the merged file has no unfenced `APPLIED (` line, or with no git.

Otherwise dispatch ONE `agent(subAgent=code-reviewer, title=Fix review)` in the foreground with [`references/fix-judge.md`](references/fix-judge.md) §4, then run main's checks and the append from that section. Its findings are reported, never applied.

## 7. Close with a report

**Open with a timing table** from the notes above: phase, start, end, minutes. Its last row is the total against the 20-minute target, and the report names the slowest phase.

Then read [`references/final-report.md`](references/final-report.md) and report every item it lists: the verdict file paths, metrics results, findings by outcome, judge and fix-review status, the scout leg, and what `/address-verdicts` skipped or failed.

## Flowchart (human-facing)

[`assets/flowchart.md`](assets/flowchart.md) diagrams this skill's flow for the human. Don't load it: the steps above win; regenerate it when the flow changes.
