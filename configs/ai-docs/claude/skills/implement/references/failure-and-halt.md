# Failure, stuck & halt - detail for /implement's §5.2, §5.3 and §5.5

Load this on an unresolvable reported commit (§5.1), a §4 timeout, a self-reported `blocked` (§4.4), or any route to a halt. An accepted `done` skips this file (§5.4).

## §5.2 - On failure or a block: record the attempt, obey the verdict

### The full verdict set - for orientation

`implement-loop-state.py` emits eight verdicts, all in the table below.

This file obeys only `retry`, `stuck`, and `halt-budget`, the ones a failed or blocked attempt can produce. The other five only follow a `pass` (§5.4).

| Verdict | When | Routes to |
|---|---|---|
| `retry` | a `fail`/`timeout` attempt, under the attempt cap, not yet a repeating signature | re-dispatch the same task (§4) |
| `stuck` | a `blocked` attempt (first try), or a `fail`/`timeout` run that stopped converging | §5.3 below |
| `next-chunk` | a `pass` attempt on a task still `in_progress` - more of its chunks remain | §4 - dispatch that task's next chunk |
| `next-task` | a `pass` attempt, with another non-terminal task still pending | §3.4 - activate that task |
| `wait` | a `pass` attempt, no pending task eligible yet, another task still `in_progress` | §5.4 - dispatch nothing until its report lands |
| `gates` | a `pass` attempt, every task now `done`, none `blocked` | [`batch-end-review.md`](batch-end-review.md)'s §8.1 |
| `halted` | a `pass` attempt, either every task terminal with at least one `blocked`, or pending tasks remain with none `depends_on`-eligible | §5.5 below |
| `halt-budget` | non-pass dispatches (`attempts` not `pass`, + `gate_dispatches`) hit the batch cap, checked before anything else | §5.5 below |

### Record the attempt

All three outcomes record one attempt; only `result` and `signature` differ.

- **A reported commit that doesn't resolve, or a `done` reporting none** (§5.1) → `result: "fail"`, `signature` the literal string `no-commits`.

  - The subagent reported success over absent commits - no failure text to quote.

- **Timeout** → `result: "timeout"`, `signature` the literal string `timeout` - the subagent never reported back.
- **Self-reported block** → `result: "blocked"`, `signature` the subagent's own blocker statement verbatim, so the batch-end package can quote what needs clearing.

### Obey the verdict

Run `~/.claude/skills/implement/scripts/implement-loop-state.py <state-file>` and obey the verdict - the script alone decides how many retries a task gets.

- **`retry`** → re-dispatch the **same task** as a fresh subagent (§4), passing the recorded failure as feedback.
- **`stuck`** → go to §5.3 below.
  - A `fail`/`timeout` attempt earns this only once the script judges the failures aren't converging (too many attempts, or a repeating failure signature).

  - Both checks count only non-pass attempts, so passing chunk dispatches never near the cap.

  - A `blocked` attempt always earns it on the first try: only the human can clear a blocker; retrying burns a dispatch.

- **`halt-budget`** → the batch's dispatch budget is exhausted. Go to §5.5 below.
  - This is the same backstop §5.4 can hit on a pass.
  - It does **not** route to §8: a batch that burned its budget isn't finished, so nothing to gate or review.

Load `debug-standards` to diagnose a repeatedly failing task before its next retry; a `blocked` attempt goes straight to the human.

## §5.3 - On `stuck`: mark terminal, chain-abort dependents, advance

Set that task to `status: "blocked"` - `reason: "blocked"` for a self-reported block, `reason: "stuck"` for repeated failures.

`status` drives flow (blocked tasks skip the next pick); `reason` keeps the stuck-vs-blocked label for the batch-end report.

`TaskUpdate` its TaskList status to `completed` (the tool has no `blocked` state; the state file's `reason` distinguishes it).

**Chain-abort the task's dependents, before picking what runs next.** Read each task's `depends_on` from the state file (§2.3) and walk them transitively. It's the field the script uses, so the two never disagree.

Any task depending on the one just marked terminal also gets `status: "blocked"`, `reason: "blocked-upstream"`, and TaskList status `completed`. Flip the plan to `[Blocked]` for the terminal task and every chain-aborted dependent (§6).

**Pick the next task yourself - the script can't.** `next-task` only follows a `pass` (§5.4) and this task didn't pass. Run `implement-loop-state.py --next-eligible <state-file>` instead - same DAG-eligibility rule as §5.4's `next-task`, without needing a `pass` attempt.

A `task` id in the result → re-run §3.4 on it.

`task: "none"` - nothing runnable remains: this task is terminal-without-`[Done]` with no open dependency path around it, or the batch's dispatch budget is exhausted; `reason` names which. **Do not go to the gates** - go to §5.5 below.

## §5.5 - Halt: stop where you stand and wait for the human

The single exit for every dead end in the run. Entry, from anywhere:

- A `halted` or `halt-budget` verdict (§5.2 above, or §5.4).
- §5.3's scan above finding nothing runnable while some task is terminal-without-`[Done]`.
- [`batch-end-review.md`](batch-end-review.md)'s §8.3 repo-green gate exhausting its fix attempts with a batch-caused failure still red.
- [`batch-end-review.md`](batch-end-review.md)'s §8.1 push failing - no remote, a rejected non-fast-forward, missing credentials.
- [`batch-end-review.md`](batch-end-review.md)'s §8.1 PR dispatch failing when a PR was requested.

Regardless of entry:

- Set `phase: "halted"` in this unit's state file, and every remaining unit's file too - the Stop hook globs the whole session and blocks on any unit still at `tasks`.

- Write into `<scratchpad>/notes.md`, per blocked task, **exactly what a human must do to clear it**.

- Leave this unit's remaining batch-end `[Reminder]` entries `pending` - they didn't run.
- **Run nothing further** - the quality-gate tail, the repo-green gate, the push, the package, and the PR all presuppose a finished batch.
  - A mid-batch quality gate flags planned tests that don't exist yet; a package invites review of unfinished work.

- On a PR-label run, the remaining PRs stay untouched - no branch, no dispatch.
- Say it in one short message: which tasks are blocked and what each needs. Nothing else.

Then stop - the Stop hook releases on `phase: "halted"`.

Clearing the blocker is a fresh `/implement`, not a resume: delete this unit's state file first (§2.3).
