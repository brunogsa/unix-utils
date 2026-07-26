# On failure or a block — record and obey the verdict (detail for /implement's verify-retry-advance step)

Load this only when a §5.1 verify fails, the §4 dispatch hit its 1-hour timeout, or the subagent self-reported `blocked` (§4.4). A task that verifies clean skips it (that path is §5.4).

## The full verdict set — for orientation

`implement-loop-state.sh` emits exactly six verdicts. This file only ever obeys three of them — the ones a failed or blocked attempt can produce —
but the table below is the whole set, so a verdict this file doesn't mention is never a gap, just one that belongs to §5.4 instead.

| Verdict | When | Routes to |
|---|---|---|
| `retry` | a `fail`/`timeout` attempt, under the attempt cap, not yet a repeating signature | re-dispatch the same task (§4) |
| `stuck` | a `blocked` attempt (first try), or a `fail`/`timeout` run that stopped converging | §5.3 — mark terminal, chain-abort dependents |
| `next-task` | a `pass` attempt, with another non-terminal task still pending | §3.4 — activate that task |
| `gates` | a `pass` attempt, every task now `done`, none `blocked` | §8's test-presence gate |
| `halted` | a `pass` attempt, every task terminal, but at least one ended `blocked` | §5.5 — halt for the human |
| `halt-budget` | total dispatches (`attempts` + `gate_dispatches`) hit the batch cap, checked before anything else | §5.5 — halt for the human |

`next-task`, `gates`, and `halted` only ever follow a `pass`, which is §5.4's own path, not this one — so the rest of this file
only ever needs to obey `retry`, `stuck`, and `halt-budget`.

## Record the attempt

All three outcomes record one attempt; only `result` and `signature` differ.

- **Verify failure** (diff mismatch, verification red, checklist items unchecked) → `result: "fail"`, `signature` set to the failure text verbatim — the error output as it was printed.
- **Timeout** → `result: "timeout"`, `signature` the literal string `timeout` — there's no diff to inspect, since the subagent never reported back.
- **Self-reported block** → `result: "blocked"`, `signature` the subagent's own blocker statement verbatim, so the batch-end package can quote what needs clearing.

## Obey the verdict

Run `~/.claude/skills/implement/scripts/implement-loop-state.sh <state-file>` and obey the verdict — the script alone decides how many retries a task gets; no cap is written here.

- **`retry`** → re-dispatch the **same task** as a fresh subagent, passing the recorded failure as feedback.
- **`stuck`** → go to §5.3, which marks the task terminal and chain-aborts its dependents.
  - A `fail`/`timeout` attempt earns this only once the script judges the failures aren't converging (too many attempts, or a repeating failure signature).
  - A `blocked` attempt always earns it on the first try: only the human can clear a real blocker, so retrying the same subagent just burns a dispatch.

- **`halt-budget`** → the batch's dispatch budget is exhausted. Go to §5.5 and halt — wait for the human.
  - This is the same backstop §5.4 can hit on a pass — it's checked before this call even looks at the attempt's result.
  - It does **not** route to §9: a batch that burned its dispatch budget didn't finish, so there is no batch to gate or review yet.

Load `debug-standards` to diagnose why a task keeps failing before its next retry. A `blocked` attempt needs no diagnosis — it goes straight to the human.
