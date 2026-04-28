---
name: gh-cli-usage
description: "GitHub operations using gh CLI. Use when creating PRs, reviewing code, managing issues, checking CI status, or any GitHub API interaction."
user-invocable: false
---

# gh CLI Usage

Use the `gh` CLI for all GitHub operations. Do NOT suggest installing the GitHub MCP server.

## Why gh CLI over GitHub MCP

- Zero context tokens at startup (MCP costs ~7-14k tokens loaded always)
- Stateless — works identically across multiple Claude Code processes
- Claude already knows the gh API deeply from training data

## Common Operations

### Pull Requests
```bash
gh pr create --title "..." --body "..." [--draft]
gh pr list [--state open|closed|merged] [--author @me]
gh pr view <number> [--json ...]
gh pr merge <number> [--squash|--merge|--rebase]
gh pr checks <number>
```

### Issues
```bash
gh issue create --title "..." --body "..."
gh issue list [--label "..." --assignee @me]
gh issue view <number>
```

### Reviews
```bash
gh pr review <number> --approve
gh pr review <number> --request-changes --body "..."
gh pr diff <number>
```

### CI / Actions
```bash
gh run list [--workflow <name>]
gh run view <run-id> [--log]
gh run watch <run-id>
```

### PR Comment Replies
```bash
# Fetch all review comments
gh api repos/{owner}/{repo}/pulls/{number}/comments

# Reply to a specific comment (in_reply_to = parent comment ID)
gh api repos/{owner}/{repo}/pulls/{number}/comments \
  -X POST -F in_reply_to={id} -f body="..."

# Update an existing comment
gh api repos/{owner}/{repo}/pulls/comments/{id} \
  -X PATCH -f body="..."
```

### Raw API (for anything not covered above)
```bash
gh api repos/{owner}/{repo}/... [--method GET|POST|PATCH]
```
