# Failure, stuck & halt — detail for /implement's §5.2, §5.3 and §5.5

Load this on an unresolvable reported commit (§5.1), a §4 timeout, a self-reported `blocked` (§4.4), or any route to a halt. An accepted `done` skips this file (§5.4).

## §5.2 — On failure or a block: record the attempt, obey the verdict

### The full verdict set — for orientation

`implement-loop-state.sh` emits six verdicts; the table below is the whole set.

This file obeys only `retry`, `stuck`, and `halt-budget` — the ones a failed or blocked attempt can produce. The other three only ever follow a `pass`, so they belong to §5.4.

| Verdict | When | Routes to |
|---|---|---|
| `retry` | a `fail`/`timeout` attempt, under the attempt cap, not yet a repeating signature | re-dispatch the same task (§4) |
| `stuck` | a `blocked` attempt (first try), or a `fail`/`timeout` run that stopped converging | §5.3 below — mark terminal, chain-abort dependents |
| `next-task` | a `pass` attempt, with another non-terminal task still pending | §3.4 — activate that task |
| `gates` | a `pass` attempt, every task now `done`, none `blocked` | [`batch-end-review.md`](batch-end-review.md)'s §8.1 |
| `halted` | a `pass` attempt, either every task terminal with at least one `blocked`, or pending tasks remain with none `depends_on`-eligible | §5.5 below |
| `halt-budget` | total dispatches (`attempts` + `gate_dispatches`) hit the batch cap, checked before anything else | §5.5 below |

### Record the attempt

All three outcomes record one attempt; only `result` and `signature` differ.

- **A reported commit that doesn't resolve, or a `done` reporting none** (§5.1) → `result: "fail"`, `signature` the literal string `no-commits`.
  The subagent reported success over commits this repo doesn't have — no failure text to quote.

- **Timeout** → `result: "timeout"`, `signature` the literal string `timeout` — there's no diff to inspect, since the subagent never reported back.
- **Self-reported block** → `result: "blocked"`, `signature` the subagent's own blocker statement verbatim, so the batch-end package can quote what needs clearing.

### Obey the verdict

Run `~/.claude/skills/implement/scripts/implement-loop-state.sh <state-file>` and obey the verdict — the script alone decides how many retries a task gets.

- **`retry`** → re-dispatch the **same task** as a fresh subagent (§4), passing the recorded failure as feedback.
- **`stuck`** → go to §5.3 below.
  - A `fail`/`timeout` attempt earns this only once the script judges the failures aren't converging (too many attempts, or a repeating failure signature).

  - A `blocked` attempt always earns it on the first try: only the human can clear a real blocker, so retrying just burns a dispatch.

- **`halt-budget`** → the batch's dispatch budget is exhausted. Go to §5.5 below.
  - This is the same backstop §5.4 can hit on a pass.
  - It does **not** route to §8: a batch that burned its budget isn't finished — nothing to gate or review yet.

Load `debug-standards` to diagnose why a task keeps failing before its next retry — a `blocked` attempt needs no diagnosis, straight to the human.

## §5.3 — On `stuck`: mark terminal, chain-abort dependents, advance

Set that task to `status: "blocked"` — `reason: "blocked"` for a self-reported block, `reason: "stuck"` for repeated failures.

`status` drives flow — blocked tasks are excluded from the next pick — while `reason` keeps the stuck-vs-blocked label for the batch-end report.

`TaskUpdate` its TaskList status to `completed`; the tool has no `blocked` state, and the state file's `reason` is what distinguishes it.

**Chain-abort the task's dependents, before picking what runs next.** Read each task's `depends_on` from the state file (§2.3) and walk them transitively.
It's the same field the script uses, so this scan and `implement-loop-state.sh` never disagree.
Any task depending on the one just marked terminal also gets `status: "blocked"`, `reason: "blocked-upstream"`, and TaskList status `completed`.
Flip the plan to `[Blocked]` for the terminal task and every dependent this just chain-aborted (§6).

**Pick the next task yourself — the script can't.** `next-task` only comes out of a `pass` attempt (§5.4), and this task didn't pass.
Run `implement-loop-state.sh --next-eligible <state-file>` instead — it answers with the same DAG-eligibility rule §5.4's `next-task` uses, just without requiring a `pass` attempt to ask it.
A `task` id in the result → re-run §3.4 on it.

`task: "none"` — nothing runnable remains: this task is terminal-without-`[Done]` with no open dependency path around it, or the batch's dispatch budget is exhausted; `reason` names which.
**Do not go to the gates** — go to §5.5 below.

## §5.5 — Halt: stop where you stand and wait for the human

This is the single exit every dead end in the run routes to. Entry, from anywhere:

- A `halted` or `halt-budget` verdict (§5.2 above, or §5.4).
- §5.3's scan above finding nothing runnable while some task is terminal-without-`[Done]`.
- [`batch-end-review.md`](batch-end-review.md)'s §8.2 repo-green gate exhausting its fix attempts with a batch-caused failure still red.
- [`batch-end-review.md`](batch-end-review.md)'s §8.3 push failing — no remote, a rejected non-fast-forward, missing credentials.
- [`batch-end-review.md`](batch-end-review.md)'s §8.3 PR dispatch failing when a PR was requested.

Regardless of entry:

- Set `phase: "halted"` in this unit's state file, and every remaining unit's file too — the Stop hook globs the whole session and blocks on any unit still at `tasks`.

- Write into the scratchpad, per blocked task, **exactly what a human must do to clear it** — the whole point of stopping here.

- Leave this unit's remaining batch-end `[Reminder]` entries `pending` — they didn't run, and pending is the honest record of that.
- **Run nothing further** — the quality-gate tail, the repo-green gate, the push, the package, and the PR all presuppose a finished batch.
  - A quality gate run mid-batch flags planned tests that don't exist yet, and a package would invite review of unfinished work.

- On a PR-label run, the remaining PRs stay untouched — no branch, no dispatch.
- Say it in one short message: which tasks are blocked, and what each one needs. Nothing else.

Then stop — the Stop hook releases on `phase: "halted"`, so the session may end and wait.

Clearing the blocker is a fresh `/implement`, not a resume: delete this unit's state file first (§2.3).
