# On failure or a block — record and obey the verdict (detail for /implement's verify-retry-advance step)

Load this only when a §5.1 verify fails, the §4 dispatch hit its 1-hour timeout, or the subagent self-reported `blocked` (§4.4). A task that verifies clean skips it (that path is §5.4).

## Record the attempt

All three outcomes record one attempt; only `result` and `signature` differ.

- **Verify failure** (diff mismatch, verification red, checklist items unchecked) → `result: "fail"`, `signature` set to the failure text verbatim — the error output as it was printed.
- **Timeout** → `result: "timeout"`, `signature` the literal string `timeout` — there's no diff to inspect, since the subagent never reported back.
- **Self-reported block** → `result: "blocked"`, `signature` the subagent's own blocker statement verbatim, so the batch-end package can quote what needs clearing.

Either way, also record the token count noted at dispatch (§4) — the run cost tokens even though it didn't pass.

## Obey the verdict

Run `~/.claude/skills/implement/scripts/implement-loop-state.sh <state-file>` and obey the verdict — the script alone decides how many retries a task gets; no cap is written here.

- **`retry`** → re-dispatch the **same task** as a fresh subagent, passing the recorded failure as feedback.
- **`stuck`** → go to §5.3, which marks the task terminal and chain-aborts its dependents.
  - A `fail`/`timeout` attempt earns this only once the script judges the failures aren't converging (too many attempts, or a repeating failure signature).
  - A `blocked` attempt always earns it on the first try: only the human can clear a real blocker, so retrying the same subagent just burns a dispatch.
- **`halt-budget`** → the batch's dispatch budget is exhausted. Halt the loop and go to §9's batch-end review with whatever work is done so far.
  - This is the same backstop §5.4 can hit on a pass — it's checked before this call even looks at the attempt's result.

Load `debug-standards` to diagnose why a task keeps failing before its next retry. A `blocked` attempt needs no diagnosis — it goes straight to the human.
