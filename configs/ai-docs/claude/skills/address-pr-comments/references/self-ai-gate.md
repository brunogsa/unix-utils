# Self-AI gate

Step 3d of the fetch in `fetch-cluster-propose.md`: always applied, before user filters.

A candidate item - inline thread, top-level comment, or review-summary body - proceeds only if ALL hold:

- **Not resolved.** Inline threads need `isResolved == false`; top-level comments and review-summary bodies have no resolved concept, so they pass.

- **Self-flagged.** At least one comment in the item is authored by `ME` (`is_self == true`).
  - Its body has a line whose first non-blank, non-list-marker token starts with `AI!`, `AI?` or `AI:`.
  - The match is case-insensitive; the colon is optional after `AI!`/`AI?` and required on `AI:`, so "AI-generated" or "AIM" never matches.

- **Not already answered.** Find `ME`'s latest marked note in the item; the item is already answered, and dropped, when `ME` posted a comment after it:
  - Inline thread: a later comment by `ME` in the same thread (order by `createdAt`), signed or not. Step 9 posts dictated replies unsigned, and they are still answers.

  - Top-level comment or review summary: a later issue comment by `ME` (`created_at`) holding step 9's reply prefix from `reply-patterns.md`.

  - That prefix is `re: <that comment's html_url> - `, including the trailing ` - `.
    - Why: the delimiter keeps `re: ...#issuecomment-12` from matching a reply to `#issuecomment-123`.

  - A new marked note posted after that reply makes the item a candidate again, because the user is asking for more.
    - Why: a reply means a prior run addressed the marker, and the user resolving threads by hand must not be the only thing that stops a re-run.

Tag each such marker `command` for `AI!` and the legacy `AI:` alias, `question` for `AI?`. A comment holding several marked lines yields one tagged marker per line, each with its own sub-step and reply decision.

Drop anything failing a check before clustering: no reply is owed and no cluster entry exists. Failing the resolved or self-flagged check is silent; an item dropped as already answered is listed in the proposal block's `Dropped as already answered` section.

Why: a later `ME` comment is not proof the marker was handled - it may be the user's own hand-typed reply to the reviewer while their `AI!` command is still undone - so the drop stays visible and reversible.
