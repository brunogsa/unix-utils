# Batch test-presence gate — did every planned test actually land?

Loaded by `implement`'s orchestrator when the state file's `phase` reaches `gates` — once per batch, after the task loop and before §9's tails.

Verifies every planned test the plan declared actually landed in the batch's commits.

## Why the check lands here and nowhere else

This is the run's only planned-test check, and it reads the batch's **final state**.

A per-task check would verify each task at its own commit point and still miss what a later task did to those tests afterward.
That means renaming, gutting, or deleting an earlier task's tests.

Use a fresh-context `deep-reviewer` dispatch: semantic title-matching across the whole batch diff deserves eyes carrying none of the loop's accumulated assumptions.

## Entry

Run this when `phase` is `gates` — set **only** by §5.4's `gates` verdict from `implement-loop-state.sh`, and only when every task in the unit is `done`.
§5.3's own dead-end scan never sets it: finding no runnable task there is a chain-abort, and that path goes to §5.5, not here.

Neither `halted` nor `halt-budget` ever reaches here: both verdicts route straight to §5.5's halt, before this gate would ever dispatch.

## Dispatch

Spawn ONE `agent(subAgent=deep-reviewer, title=Test-presence gate for batch)` — fresh context.

Pass it the resolved plan path, the diff range `<BATCH_BASE_SHA>..HEAD`, and the batch's task IDs, read from the state file's `tasks[]`.

`BATCH_BASE_SHA` here is this run's own base — the current PR's, captured fresh per §3.2 — never the whole PR-label list's start.

## What the deep-reviewer does

Iterate exactly the batch task IDs it was handed — never every `### N.` heading in the plan, which lists tasks other runs owned.

For each ID `<N>`, first check that task's own plan entry for a `**DECISION:** Skip planned-test check because <reason>` marker.

- Present → skip that task entirely and report it as opted out.
  - Reserved for a task whose deliverable has no runtime to test against, such as a prompt-markdown skill or agent file.
  - Test Design and the authoring-time coverage gates (`check-test-distribution.sh`, `check-ac-coverage.sh`) still apply in full; only this runtime check is bypassed.

- Absent → run `~/.claude/skills/spec-driven-development/scripts/extract-planned-tests-for-task.sh <plan-path> <N>` for that task's planned-test titles.

Handle its exit codes exactly this way — never fall back to inline AI judgment on a parse failure:

- **Exit 2** (usage / parse error) → abort the gate: record the failure for §9's package, do not mark the gate passed.
- **Exit 1** (plan malformed: missing `### N.` heading or missing `**Tests (planned)**:` bullet) → abort the same way; the plan must be fixed before a re-run.
- **Exit 0, empty stdout** → that task declared `**Tests (planned)**: N/A`; skip it and report it in the N/A list.
- **Exit 0, non-empty stdout** → titles captured; continue to the grep pass.

Grep the `<BATCH_BASE_SHA>..HEAD` diff for each title as a deterministic pre-pass.

Apply an AI semantic check ONLY to titles grep didn't match.

Return a per-title `found`/`missing` verdict plus the list of tasks that declared `**Tests (planned)**: N/A`.

## Outcomes

**All found, or every task N/A — the gate passes.**
If every task was N/A, note the explicit TDD opt-out so §9's package can state it.
Set `phase` to `tails` and proceed to §9.

**Any missing — fix in a loop, not once.**
For each task with missing titles, re-dispatch THAT task's subagent (fresh, per §4) with the missing titles as feedback.
The same 1-hour Monitor cap from §4 applies here too — every tdd-coder dispatch, including a gate-fix re-dispatch, gets it.
The subagent owns writing them (RED → GREEN), never hand-write tests.
Increment `gate_dispatches` in the state file by one per fix dispatch.
Then re-gate — another `deep-reviewer` pass, same contract.

- Re-gate all found (or N/A) → pass; set `phase: "tails"` and go to §9.
- Re-gate still missing → repeat: re-dispatch the same task again with the still-missing titles, then re-gate again.
  A planned test the plan declared is not optional, so one failed fix round is no reason to accept its absence — only its own task's attempt cap is.

Bound each task's fix-dispatch count by the same per-task cap the task loop enforces (`MAX_ATTEMPTS = 3` in `implement-loop-state.sh`).
Track it yourself: the script can't verdict this — it only judges phase `"tasks"`, and by now phase is `"gates"` (see Budget note).

**Attempts exhausted with titles still missing is a block, not a pass-through to §9.**
Go to §5.5 and halt — record, per task, exactly which titles are still missing, so the human knows what to finish.
There is no "proceed to §9 anyway so the package surfaces them" path any more: a batch that can't produce its own planned tests isn't ready for tails or a PR.

## Budget note

This gate never calls `implement-loop-state.sh` itself — nor does §9, which runs linearly to the package.
The script only verdicts phase `"tasks"`; by the time this gate runs, phase is already `"gates"`, so a call here would just fail loud.

`gate_dispatches` still feeds the script's phase-independent budget backstop: `total_dispatches` sums `attempts` and `gate_dispatches`
**before** the script even reads `phase`, so every fix dispatch here raises that count for the whole state file, not only for this gate.

`halt-budget` itself — when the script emits it, during the task loop, before this gate is ever reached — now routes to §5.5, never to §9.
A budget-exhausted unit halts for the human the same as any other blocked unit; it does not fall through to the batch-end flow.

The fix loop here is bounded by the per-task attempt cap above, not by being try-once — overshoot on a single task is what halts it, not a shared dispatch count.

Keeping the accounting in the script is the invariant — do not "helpfully" add a script call here.
