# GitHub Workflow via gh CLI

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

### Raw API (for anything not covered above)
```bash
gh api repos/{owner}/{repo}/... [--method GET|POST|PATCH]
```

## Project Conventions

[TODO: Add your specific conventions here]
- Branch naming: ...
- PR title format: ...
- Required labels: ...
- Review process: ...
