# Scout leg

The brief for the `code-reviewer` that `/quality-gate` §3 dispatches in the background when `export-open-scouts.py` printed a count above 0. You are one fresh-context judge of the open `[Scout]` tasks: you decide which ones belong to this branch, and turn those into findings.

Main hands you `<RUN_DIR>`, `<BASE_REF>`, the spec and plan paths (either may be missing), and the export path `<RUN_DIR>/open-scouts.md`, which holds one `## #<id> <subject>` section per open scout, with its description below.

## Rules

- You are report-only: write only the 2 files under "Output", never edit a source file, and never spawn a nested reviewer.
  - Reason: you have no task tools, so the TaskList stays main's to change, and a nested reviewer spends a spawn-depth level on a second opinion nobody asked for.

- Write both files in `<RUN_DIR>`, never in CWD.
  - Reason: `/address-verdicts` globs `verdict_scouts*.md` in CWD for an older workflow, and the `scout-leg_` prefix keeps it out of that glob, and on a merge fallback it stays in `<RUN_DIR>`, never moved to CWD.

- Read the whole export file, never a summary of it.

## Classify each scout

Read `git diff <BASE_REF>...HEAD`, then the spec and the plan when they resolved. Mark each exported scout in-goal or off-goal.

- **In-goal**: fixing it serves the branch's stated goal, taken from the spec, the plan or the PR description.
  - The fix touching a file the branch changes is supporting evidence, never enough alone.
  - Reason: a scout in a touched file may still be unrelated work, and an in-goal call is auto-applied.

- **Off-goal**: everything else.

- **When in doubt, off-goal.**
  - Reason: a wrong in-goal call is auto-applied and its task deleted, while a wrong off-goal call only waits for the human.

## Verify each in-goal scout

Read the code the scout names, at HEAD, before writing its finding.

- It still reproduces: write a finding.

- It no longer reproduces: write no finding. List it in the classification as in-goal and already fixed, with the evidence (the `path:line` at HEAD that shows the fix).

## Output

### `<RUN_DIR>/scout-leg_<ts>.md`

The source file main merges. `<ts>` is `date +%Y-%m-%d_%H:%M`.

```markdown
## Findings

### 1. [MEDIUM][scout] `path:start_line-line`

**[RECOMMENDED]**

<one-sentence summary>

**Suggestion**

<fix>

**Trade-off of not doing it**

- [-] <cost>
- [+] <benefit>

**Scout task**: #<id>
```

- One finding per in-goal scout that still reproduces, in the four-part body of [`local-review-template.md`](../../code-review-pipeline/references/local-review-template.md), with the lens tag `[scout]` right after the severity tag.

- Put the `**Scout task**: #<id>` line last, at column 0, after a blank line. Main reads it to delete the task, so never write the id in any other shape.

- Never write `[scout #<id>]` in the heading: the apply scripts match tags as an exact set.

- Number from `### 1.`, ordered by severity; main's merge agent renumbers.

- With no in-goal scout that reproduces, still write `## Findings`, then the line `No in-goal scout among <N> open scouts.`, with `<N>` the exported count.
  - Reason: an empty file triggers a re-dispatch.

- Run `python3 ~/.claude/skills/code-review-pipeline/scripts/check-finding-bodies.py <RUN_DIR>/scout-leg_<ts>.md` and rewrite any flagged finding, at most twice.

### `<RUN_DIR>/scout-classification.md`

One line per exported scout id, none omitted: `#<id> - in-goal|off-goal - <one-line reason>`. An already-fixed scout reads `#<id> - in-goal, already fixed - <path:line at HEAD that shows the fix>`, and gets no finding.

Main reads it for the final report and keeps it as the audit trail. It is never merged and never copied into a findings report.

## Return

The two paths written, the exported count, and the in-goal and off-goal counts.

## Settle the tasks

Main runs this right after §4.1's merge passes, never later, and never on the fallback.
  - Reason: on the fallback the scouts stay pending, so the next gate run exports them again, and no human run can apply one twice.

- **Delete** an id (`TaskUpdate` status `deleted`) only when all 3 hold: it has a `## #<id>` section in `<RUN_DIR>/open-scouts.md`, `<RUN_DIR>/scout-classification.md` lists it as in-goal, and the merged file carries its `**Scout task**: #<id>` line outside code fences.
  - Reason: a task that fails any check may be a mis-typed id or a finding the merge dropped, and deleting it loses the scout for good.

- **Complete** an id classified `in-goal, already fixed` (`TaskUpdate` status `completed`, never `deleted`), with the evidence in its description.
  - Reason: the branch did the work, so the task is done, and a deletion would read as the merge dropping it.

- **Keep** an id that fails a check, and every off-goal id.

- Write `<RUN_DIR>/scout-outcomes.md`, one line per id: `#<id> - deleted|completed|kept|off-goal - <reason>`. Main reads it at §7.
  - Reason: after a compaction main can no longer recall which ids it deleted.
