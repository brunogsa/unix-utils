# Ticket ID — resolving the Jira/Linear prefix

Read this on every `create-pr` run (step 1), and from any skill that dispatches `pr-creator` — the one rule for which ticket names the PR.

The resolved ID prefixes the PR title as `[<ID>] <Title>` (`pr-finalizer`) and fills the body's `## Jira link` bullet (`pr-writer`), so both come from one answer and never disagree.

## Candidates

- An ID the caller passed, an ID stated in this session, a key in the branch name (`feat/itgd-2947_x` → `ITGD-2947`), or a key/URL in any globbed spec/plan.

- Grep the spec/plan for keys and URLs (`atlassian.net/browse/KEY-N`, `linear.app/.../issue/KEY-N`); never read them in full, since step 2's agent does.

- Never tickets: the `<parent>` arg, and `AC-N`/`PR-N`/`UTF-8`-style tokens, which fill every spec and plan.

## Resolution

- Caller passed an ID or "none" → resolved; never ask.

- Exactly one confident ID → auto-resolved. Zero, 2+, or unsure → open question **(D) Ticket ID** in step 1's pre-flight call.

- (D) with candidates: up to 3 IDs, the strongest marked `(Recommended)`, plus `No ticket`. The user types an unlisted ID in Other.

- (D) with none: `No ticket (Recommended)` and `Has one, add it later` (plain title now, renamed on GitHub).

## Subagent callers

- `pr-creator` runs `create-pr` as a subagent that cannot ask, so its caller resolves the ID up front and passes it, or "none".

- `implement` does so in its §1.2 interview on a draft-PR yes, asking (D) in a follow-up call only when the rule above leaves it open.

- A stacked run passes the same ID to every layer's PR.
