# Pre-flight — existing task state & TaskList items

Detail for §1.5 in `/implement`. Fires only on a resume or dirty run — a clean first run skips it.

## Handle existing task state

- **Already `[Done]`** → ask: re-execute / skip / abort.
- **Already `[Doing]`** → ask: resume / restart / abort. Multiple `[Doing]` tasks at once is a smell — flag it.
- **Already `[Blocked]` / `[Deferred]`** → ask: resume / abort.
  - Resume re-dispatches the task.
  - The fresh subagent picks up from its checklist file (§3) + `plan_<slug>.md` context.
  - The `[Doing]` flip happens on resume.
- **Already `[Dropped]`** → ask: revive (clear status, restart) / abort.

## Existing TaskCreate items

Run TaskList. If any items exist, list them **ON CHAT** and ask:

- Keep all
- Delete `completed` only
- Delete all
- Cancel `/implement`

Apply the choice before continuing — long lists may not fully render in the UI, so listing them in chat for explicit confirmation is part of the safety net.

Sub-steps are not in the TaskList — they live in each task's `/tmp` checklist file (§3), which a re-dispatch resumes from rather than overwrites, so no TaskList cleanup touches them.
