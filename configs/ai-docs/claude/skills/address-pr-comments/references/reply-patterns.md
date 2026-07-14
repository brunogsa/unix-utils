# Reply Patterns: observed behaviors

Real edits the user has made to AI-generated replies, captured to justify the templates in `SKILL.md` Step 7.

## Apply replies — observed deletions

Reviewer wrote what they wrote. Acknowledge it landed, link the proof, move on. Anything more usually gets deleted post-post.

- "Pegada boa — exatamente o cenário..." — unsolicited praise reads as canned-bot empathy.
- "Cobertura adicionada em <sha>: <url>. summarize() reusa o mesmo X, mas sem cenário pinned..." — re-explaining the reviewer's own point is patronizing.

## Apply replies — examples that survived

- `Bem visto. Aplicado em <url>`
- `Cobertura adicionada em <url>`
- `Adicionado em <url>`

Ack is optional — bare URL works.

## Answer replies — no signature

Observed: user stripped the AI signature on cluster C3 of PR #2030 for an `answer` reply.

Tagging an `answer` as AI-assisted dilutes ownership; the reviewer discounts it. That's why `answer` replies omit the signature.

## Ownership rationale (inline threads)

`by <logins>` filters by thread-opener, not by participation:

- Why: the thread-opener raises the concern; replies are participation.
- Filtering by participation would surface threads the user only answered in (not theirs to address). Thread-opener matches the "my comments" mental model.

## jq ownership query

For an inline-thread filter on author "alice":

```bash
jq --arg author "alice" '
  [.data.repository.pullRequest.reviewThreads.nodes[]
    | select(.isResolved == false)
    | select(.comments.nodes[0].author.login == $author)
  ]' inline.json
```

`select(.comments.nodes[0].author.login == ...)` is the ownership check — `nodes[0]` is the thread-opener.

## Reuse note (fetch primitives)

This skill duplicates `gh api` fetch primitives from `improve-from-user` Mode B intentionally — that flow uses REST only; this one needs GraphQL for `isResolved`.
