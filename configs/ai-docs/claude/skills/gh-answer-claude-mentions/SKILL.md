---
name: gh-answer-claude-mentions
description: "Answer PR review comments addressed to Claude. User-invoked only — drafts replies to unresolved @claude mentions on a PR."
user-invocable: true
disable-model-invocation: true
---

# Answer PR Comments as Claude

Fetch comments on a GitHub PR, filter those addressed to Claude, discuss each
with the user on terminal, and post approved replies with a `Claude:` prefix.

## Process

### 1. Fetch comments

Save the full response to `/tmp/` (slow command principle), then filter locally.

```bash
gh api repos/{owner}/{repo}/pulls/{number}/comments \
  > /tmp/pr-{number}-comments.json
```

If the user provides a PR URL, extract owner/repo/number from it.
If only a number, infer owner/repo from the current git remote.

### 2. Filter comments addressed to Claude

Search for comments containing `@claude`, `Claude:`, or questions clearly
directed at the AI assistant. Present each matching comment to the user with:
- The comment author
- The file and line it's on (if a review comment)
- The full comment body
- Any existing replies in the thread

Skip bot comments (Wiz, Dependabot, etc.) unless the user explicitly asks.

### 3. Discuss each comment on terminal

For each comment, brainstorm the answer with the user:
- Present trade-offs and alternatives
- Reference relevant code if needed
- Wait for the user to approve the conclusion

**NEVER post a reply without explicit user approval.** The user may want to
adjust the wording, skip a comment, or handle it themselves.

### 4. Post approved replies

After the user approves a conclusion, post it as a reply:

```bash
gh api repos/{owner}/{repo}/pulls/{number}/comments \
  -X POST \
  -F in_reply_to={comment_id} \
  -f body="Claude:

{approved conclusion}"
```

Every reply MUST be prefixed with `Claude:` followed by a blank line,
so reviewers immediately know it's AI-generated context, not the user
talking to themselves.

The reply should be a concise summary of the terminal discussion — not a
verbatim dump of everything discussed. Focus on the conclusion and reasoning.

### 5. Confirm

After posting, confirm to the user which comments were answered and link to the PR.

## Edge cases

- **No comments addressed to Claude:** Tell the user and stop.
- **Comment already has a Claude reply:** Show the existing reply and ask if the user wants to update it (PATCH) or add a new one.
- **PR URL vs number:** Accept both. Extract from URL or use current repo.
