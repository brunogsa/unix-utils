---
name: test-sdd
description: "USE to check that every planned test a plan_<slug>.md declares actually exists in the repo — the standalone form of /implement's planned-test presence gate. Triggers: /test-sdd, 'are the planned tests there?', or another skill's dispatch."
disable-model-invocation: false
---

# Test-SDD — did the plan's planned tests actually land?

Check every `**Tests (planned)**` title a `plan_<slug>.md` declares against the tests that exist in the repo right now, and write the misses to a timestamped verdict file.

**Report only** — this skill never writes a test, never edits source, never commits.

Fixing what it finds is a separate step, run by hand or by `/quality-gate`, which writes these misses on every run that dispatches this leg.

## Usage

```
/test-sdd [plan-file] [task-ids]
```

- `plan-file` — the plan to check. Omit it, or pass the bare word `plan`, to discover `plan_*.md` in CWD.
- `task-ids` — comma-list of numeric task prefixes, `1,2,5`. Omit it to check **every** task in the plan.

Examples:

- `/test-sdd` — every task of the one plan in CWD.
- `/test-sdd plan_itgd-3374.md` — every task of that plan.
- `/test-sdd plan_itgd-3374.md 1, 4` — only tasks 1 and 4.

## When to invoke

Direct `/test-sdd` invocation, with phrases like "are the planned tests there?" / "did we write the tests the plan asked for?" / "check the plan's test coverage".
Or dispatch from another skill's flow, such as `/quality-gate`'s test leg.

## What it is, and what it is not

The search surface is the **repo's current working tree**, not a commit range.

A planned test written three branches ago still counts as present, because the question this skill answers is "does the repo have it", not "did this batch add it".

It is a **report**, not a gate: nothing halts, nothing retries, no exit code changes anyone's flow.

A caller that needs blocking semantics — a fix loop, a halt on missing titles — builds them around the verdict file this skill produces.

## 1. Resolve the plan

If the argument is a readable file path, use it as-is. Otherwise glob CWD, top-level only:

```bash
ls -1 plan_*.md 2>/dev/null
```

- **Exactly one match** → use it; print the resolved path, no prompt.
- **Multiple matches** → prompt with a numbered list and let the user pick one; never guess which plan was meant.
- **Zero matches** → stop with a clear message. There is nothing to check against, and inventing a plan would fabricate the whole verdict.

## 2. Resolve the task-ids

With no `task-ids` argument, the scope is every task heading in the plan:

```bash
grep -nE '^### [0-9]+\.' <plan-file>
```

With a `task-ids` argument, exact-match each id against those headings' numeric prefixes.

- An id matching **zero** headings → stop and say which id missed; a typo silently checking nothing is worse than no run.
- An id matching **more than one** heading → the plan is malformed. Stop and say so; never pick one.

Record each resolved task's status marker (`[Done]`, `[Blocked]`, `[Deferred]`, `[Dropped]`, or none) alongside its id.

The marker never changes whether a task is checked — it is carried into the report so a reader can tell an unwritten test from a deliberately postponed one.

## 3. Mint the verdict path

Run `date "+verdict_test-sdd_%Y-%m-%d_%H:%M.md"` once and treat the output as `$VERDICT_PATH` in CWD — never `/tmp/`, since the user reads it alongside the plan in their editor.

The `verdict_` prefix is load-bearing, not cosmetic: `~/.claude/hooks/deep-reviewer-write-guard.sh` auto-approves exactly that basename pattern and denies every other write.

One file per invocation; never reuse a prior run's path. Repeated runs accumulate as separate timestamped files, preserving their order.

## 4. Dispatch one deep-reviewer

Spawn a single `agent(subAgent=deep-reviewer, title=Planned-test presence check)`, in the **background** (the default).

Fresh context is the point: the invoking session often wrote the tests under check, and a same-session read carries the bias CLAUDE.md's fresh-context rule guards against.

Lead the prompt with the report-only preamble from [`code-review-pipeline/references/deep-reviewer-tail-pair.md`](../code-review-pipeline/references/deep-reviewer-tail-pair.md), substituting `$VERDICT_PATH`.
That file is the single source of truth for the contract wording.

Push into the prompt: the resolved plan path, the resolved task-ids with their status markers, `$VERDICT_PATH`, §5's matching procedure, and §6's report schema.

## 5. The matching procedure (pushed into the dispatch)

Iterate exactly the task-ids handed over — never every `### N.` heading in the plan, which may list tasks this run was told to skip.

For each id `<N>`, first check that task's plan entry for a `**DECISION:** Skip planned-test check because <reason>` marker.

- **Present** → skip the task entirely and report it as opted out, quoting the stated reason.
  - Reserved for a task whose deliverable has no runtime to test against, such as a prompt-markdown skill or an agent file.

- **Absent** → extract that task's planned-test titles:

```bash
~/.claude/skills/spec-driven-development/scripts/extract-planned-tests-for-task.sh <plan-path> <N>
```

Handle its exit codes exactly this way — never fall back to inline AI judgment on a parse failure:

- **Exit 2** (usage / parse error) → record the failure in the report and mark the whole run inconclusive.
- **Exit 1** (plan malformed — missing `### N.` heading or missing `**Tests (planned)**:` bullet) → same treatment; the plan must be fixed before a re-run means anything.

- **Exit 0, empty stdout** → the task declared `**Tests (planned)**: N/A`. Report it in the N/A list; it is not a finding.
- **Exit 0, non-empty stdout** → titles captured; continue to the grep pass.

Run a deterministic grep pre-pass per title, over tracked and untracked files:

```bash
git grep -nF --untracked -- "<title>"
```

Apply an AI semantic check **only** to titles grep did not match — a title reworded, split across lines by a formatter, or assembled from a template string still counts as present.

A semantic match must cite `path:line`; a match nobody can point at is a miss, not a match.

Classify every title as `found` (with its `path:line`) or `missing`.

## 6. Report schema

Write the complete report to `$VERDICT_PATH`. Every missing title is one numbered finding.

```markdown
# Test-SDD Verdict: <plan-file>

- **Plan:** `<plan-file>`
- **Tasks checked:** <ids>, of <total> in the plan
- **Result:** <M> of <T> planned tests present — <K> missing

## Summary

| Task | Status | Planned | Found | Missing |
|------|--------|---------|-------|---------|
| 3    | [Done] | 4       | 3     | 1       |

Tasks declaring `**Tests (planned)**: N/A`: <ids, or "none">.
Tasks opted out via `**DECISION:** Skip planned-test check`: <ids with reasons, or "none">.

## Findings

### 1. [HIGH] Missing planned test — task <N>: "<planned title>"

- **Task:** <N> — <task heading title> <status marker, or "no status marker">
- **Planned title:** the title verbatim, as `extract-planned-tests-for-task.sh` printed it
- **Searched:** the grep command run, and what the semantic pass looked for after it
- **Nearest existing test:** `path:line` of the closest match, or `none found`
- **Why it is a miss:** why the nearest match does not cover the planned title
```

Rules the schema depends on:

- Severity is fixed at `[HIGH]` for every missing title — a test the plan declared is not optional, so there is no judgment call to make and none to get wrong.

- Findings are numbered from `1`, sequentially, with the number in the heading.

- Keep that exact heading shape — `### N. [SEVERITY] <title>`.
  `/quality-gate`'s apply step stamps `[Done]` right after the number, giving `### 1. [Done][HIGH] …`.
  This follows the same prefix-after-the-number convention `plan-status-markers` defines for plan headings.

- **Zero missing titles** → write the file anyway, with a `## Findings` section reading `None — every planned test is present.`
  A run that produces no artifact leaves nothing to point at later.

The subagent's return message must carry only the counts, the file path, and one title line per finding — return messages are capped and truncate long lists.

## 7. Present the report, then stop

After the agent returns:

1. `Read` `$VERDICT_PATH` end-to-end — the return summary is truncated by design, so never report from it.
2. Print the resolved plan path, the checked task-ids, the found/missing counts, and one line per finding.
3. Tell the user the full report is at `$VERDICT_PATH`.

If the file is missing or empty after the agent returns, treat the run as failed and re-dispatch once; do not report from the truncated return alone.

**Stop here.** Writing the missing tests is not part of this flow — that is `/quality-gate`, or a direct ask.

## Flowchart (human-facing)

[`assets/flowchart.md`](assets/flowchart.md) diagrams this skill's flow for the human. Don't load it — non-authoritative, the steps above win; regenerate it whenever the flow changes.
