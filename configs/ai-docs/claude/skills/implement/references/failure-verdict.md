# On failure — record and obey the verdict (§5.3 detail)

Load this only when a §5.1/§5.2 verify fails or the §4 dispatch hit its 1-hour timeout. A task that verifies clean skips it (that path is §5.5).

## Record the attempt

If §5.1 or §5.2 fails (diff mismatch, verification red, planned tests missing), or the dispatch hit the 1-hour timeout (§4), record the attempt.

- On a verify failure, set `result` to `fail` and `signature` to the failure text verbatim — the error output, or the list of missing planned tests.
- On a timeout, set `result` to `timeout` and `signature` to the literal string `timeout` — there's no diff to inspect, since the subagent never reported back.
- Either way, also record the token count noted at dispatch (§4) — the run cost tokens even though it didn't pass.

## Obey the verdict

Run `~/.claude/skills/implement/scripts/implement-loop-state.sh <state-file>` and obey the verdict — the script alone decides how many retries a task gets; no cap is written here.

- **`retry`** → re-dispatch the **same task** as a fresh subagent, passing the recorded failure as feedback.
- **`stuck`** → the script judged this task's failures aren't converging (too many attempts, or a repeating failure signature) — go to §5.4, which marks it terminal.
- **`halt-budget`** → the batch's dispatch budget is exhausted. Halt the loop and go to §9's batch-end review with whatever work is done so far.
  - This is the same backstop §5.5 can hit on a pass — it's checked before this call even looks at the fail/timeout result.

Load `debug-standards` to diagnose why a task keeps failing before its next retry.
