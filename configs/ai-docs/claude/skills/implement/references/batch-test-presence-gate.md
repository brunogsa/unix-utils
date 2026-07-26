# Batch test-presence gate — did every planned test actually land?

Loaded by `implement`'s orchestrator when the state file's `phase` reaches `gates` — once per batch, after the task loop and before §9's tails.

Verifies every planned test the plan declared actually landed in the batch's commits.

## Why the check lands here and nowhere else

This is the run's only planned-test check, and it reads the batch's **final state**.

A per-task check would verify each task at its own commit point and still miss what a later task did to those tests afterward.
That means renaming, gutting, or deleting an earlier task's tests.

Use a fresh-context `deep-reviewer` dispatch: semantic title-matching across the whole batch diff deserves eyes carrying none of the loop's accumulated assumptions.

## Entry

Run this when `phase` is `gates` — the state §5.3's queue-empty scan and §5.4's `gates` verdict both set.

A `halt-budget` verdict never reaches here: it routes straight to §9 from §5.2/§5.4, upstream of this gate, so the gate has no budget branch of its own.

## Dispatch

Spawn ONE `deep-reviewer` subagent via the Agent tool — fresh context, that agent type's pinned model and effort (no override needed).

Pass it the resolved `plan_<slug>.md` path, the diff range `<BATCH_BASE_SHA>..HEAD`, and the batch's task IDs, read from the state file's `tasks[]`.

`BATCH_BASE_SHA` here is this run's own base — the current PR's, captured fresh per §1.4 — never the whole PR-label list's start.

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

**Any missing — run one fix round, try-once.**
For each task with missing titles, re-dispatch THAT task's subagent (fresh, per §4) with missing titles as feedback.
The same 1-hour Monitor cap from §4 applies here too — every tdd-coder dispatch, including this gate-fix re-dispatch, gets it.
The subagent owns writing them (RED → GREEN), never hand-write tests.
Increment `gate_dispatches` in the state file by one per fix dispatch.
Add each dispatch's token count into `.tails.tokens.gate` — the metrics script sums it.
Then re-gate ONCE — a second `deep-reviewer` pass, same contract.

- Re-gate all found → pass; set `phase: "tails"` and go to §9.
- Re-gate still missing → record the still-missing titles for §9's package, set `phase: "tails"`, go to §9 so the package surfaces them.
  Do NOT loop, do NOT hand-fix.

## Budget note

This gate never calls `implement-loop-state.sh` — nor does §9, which runs linearly to the package.

The `gate_dispatches` it increments feed the script's phase-independent budget backstop.
It fires on its next call (in practice, a resumed run's first verdict) returning `halt-budget` before anything else.

A gate-fix overflow never halts the current batch — the gate is try-once, so overshoot is bounded at one dispatch per task.

Keeping the accounting in the script is the invariant — do not "helpfully" add a script call here.
