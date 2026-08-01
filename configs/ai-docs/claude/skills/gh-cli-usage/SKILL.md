---
name: gh-cli-usage
description: "GitHub operations using gh CLI. Use when creating PRs (including stacked PRs), reviewing code, managing issues, checking CI status, or any GitHub API interaction."
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

### Stacked PRs

```bash
# A child PR targets its PARENT branch, never the default branch
gh pr create --head <child-branch> --base <parent-branch> ...

# Retarget a child after its parent merges (REST — gh pr edit --base shares
# the projectCards hazard documented in the fallback section below)
gh api -X PATCH repos/{owner}/{repo}/pulls/<n> -F base=<default-branch>

# Direct children of a branch
gh pr list --base <branch>
```

Read [`references/stacked-prs.md`](references/stacked-prs.md) before creating or restacking a stack — it owns the full workflow: bottom-up chain build, `--update-refs` restacks, merge order, and post-merge cleanup.

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

## Fallback: REST `gh api` when high-level subcommands fail

If a high-level `gh` subcommand fails with a GraphQL deprecation warning, don't fight it — drop to the REST API directly via `gh api`.

- Examples: GitHub deprecates a field used by `gh pr view --json X`, `gh issue list ...`, etc.
- REST endpoints are versioned independently and rarely break.

Symptoms that warrant the fallback:
- `gh: GraphQL: Field 'X' is deprecated` or `... will be removed on YYYY-MM-DD`
- `gh: failed to read JSON output: ...` after a recent gh upgrade
- A subcommand silently returning an empty list while the web UI shows results

Common REST equivalents:

```bash
# Instead of:  gh pr view <num> --json mergeStateStatus,mergeable,...
gh api repos/{owner}/{repo}/pulls/<num>

# Instead of:  gh pr edit <num> --body-file ./body.md (fails on projectCards GraphQL deprecation)
gh api -X PATCH "repos/{owner}/{repo}/pulls/<num>" -F body=@./body.md
# Same shape for title:
gh api -X PATCH "repos/{owner}/{repo}/pulls/<num>" -F title="New title"

# Instead of:  gh pr list --json ... (when filters fail)
gh api "repos/{owner}/{repo}/pulls?state=open&per_page=50"

# Instead of:  gh issue list --json labels,...
gh api "repos/{owner}/{repo}/issues?labels=bug&state=open"

# Instead of:  gh run list --json ... (failing field)
gh api "repos/{owner}/{repo}/actions/runs?per_page=20"

# Pagination (REST defaults to 30/page, max 100):
gh api --paginate "repos/{owner}/{repo}/pulls?state=closed"
```

Use `--jq` for projection when the response is large:

```bash
gh api repos/{owner}/{repo}/pulls/123 --jq '{title, mergeable, mergeable_state}'
```

Reach for GraphQL (`gh api graphql -f query='...'`) only when REST genuinely cannot express the query (deeply joined fields, cross-resource aggregation). For routine reads, REST is the more stable fallback.
