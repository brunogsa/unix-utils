# Status markers — plan.md task title

Detail for §6 in `/implement`. The orchestrator owns these edits — the subagent never touches plan.md status.

Status sits **right after the number, before any pre-existing tag** (e.g., Jira IDs).

| State | Title format |
|---|---|
| Initial | `### N. Title (...)` |
| In progress | `### N. [Doing] Title (...)` |
| Done | `### N. [Done] Title (...)` |
| Blocked | `### N. [Blocked] Title (...)` |
| Deferred | `### N. [Deferred] Title (...)` |
| Dropped | `### N. [Dropped] Title (...)` |
| With pre-existing tag | `### N. [Doing][JIRA-123] Title (...)` |

Single value, mutually exclusive — `[Blocked]` *replaces* `[Doing]`, never stacks.

`plan.md` is session-scoped (gitignored per `spec-driven-development`). Status updates are file edits only, **never committed**.

## Semantics

- `[Doing]` — actively in progress this session (dispatched, not yet verified-done).
- `[Done]` — finished, verified by the orchestrator, committed by the subagent.
- `[Blocked]` — external dependency unresolvable in this session (e.g., upstream API down, missing access). Pair with a `**QUESTION:**` marker that names what's needed to unblock.
- `[Deferred]` — deliberately postponed to a later session, but still planned.
- `[Dropped]` — decided not to do at all (scope reduction). Pair with `**DECISION (Task N):**` capturing the reason.

In all non-`[Done]` terminal states, do NOT leave partial code committed under a misleading status.

Either the subagent's commits stand as coherent work (status is a separate concern) or the WIP is reverted first.
