# Reply Patterns: templates, API, and observed behaviors

Step 7's reply mechanics — templates, the `gh api` call per reply-target kind, and the signature rule — plus the real user edits that justify them.

## Templates, by action

**Apply** — optional one-word ack + commit URL, nothing more. No praise, no re-explaining, no double-anchoring the SHA.

```
<optional one-word ack> https://github.com/<OWNER_REPO>/pull/<n>/commits/<FULL_SHA>

_via Claude Code (`address-pr-comments`)_
```

**Answer** — the user-supplied answer text, in the user's voice, no signature (see "Signature rule" below).

```
<answer_body>
```

**Drop** — minimal drop reason.

```
Dropping this one — <drop_reason>

_via Claude Code (`address-pr-comments`)_
```

## API call, by reply-target kind

**Inline** — one GraphQL mutation per `thread_id`, mutating a thread rather than a comment so the duplicate-reply mistake is unrepresentable, not merely forbidden:

```bash
gh api graphql -f query='
mutation($tid: ID!, $body: String!) {
  addPullRequestReviewThreadReply(
    input: { pullRequestReviewThreadId: $tid, body: $body }
  ) { comment { url } }
}' -f tid="<thread_id>" -f body="<reply_body>"
```

**Top-level and review-summary** — REST, since GitHub exposes no thread object for either:

| Source | gh command |
|---|---|
| top-level | `gh api -X POST repos/$OWNER_REPO/issues/<n>/comments -f body='@<author> re: <comment_url> — <body>'` |
| review-summary | same as top-level (no per-review reply API) |

That `@<author> re: <link>` prefix pings the commenter and preserves thread context. Both post a fresh comment rather than threading — GitHub's model, not a shortcut; no API threads either kind.

## Signature rule

`apply` and `drop` replies carry the AI signature **mandatorily**; `answer` replies carry **none** — an answer is the user's reasoning in the user's voice, and an AI tag
dilutes that ownership (see "Answer replies — no signature" below).

The inverse case — a comment addressed to Claude, answered in Claude's own voice — belongs to `gh-answer-claude-mentions`, not here.

Signature literal: `_via Claude Code (`address-pr-comments`)_`. Plain text only — no emoji, same as any posted reply.

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
