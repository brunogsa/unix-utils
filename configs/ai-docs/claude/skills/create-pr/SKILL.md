---
description: "Create a GitHub PR with a rich description. Auto-detects spec.md and plan.md in cwd for context."
disable-model-invocation: true
---

# Create Pull Request

Create a GitHub PR with a rich description generated from
spec.md and plan.md context (when available).

## Usage

`/create-pr`

No flags needed. Auto-detects spec.md and plan.md in the current directory.

## Process

### 1. Gather context

- Check for spec.md and plan.md in cwd (optional -- works without them)
- Check for PR templates in `.github/` (e.g., `PULL_REQUEST_TEMPLATE.md`)
- Run git log to see commits on current branch vs base
- Run git diff against base branch
- Check if branch is pushed

### 2. Write rich-pr-description.md

Write `./rich-pr-description.md` in the directory where Claude Code is running.

If a PR template exists in `.github/`, use it as the base structure but NEVER
remove detail. All generated content must remain -- create a superset of the
template if necessary (add sections, keep all info).

If no PR template exists, use the default template below.

#### Default Template

```markdown
## Summary
[From spec.md: Background + Goals, condensed to 2-3 bullets.
 Without spec.md: summarize from git log and diff]

## Approach
[From plan.md: Approach section, condensed.
 Without plan.md: summarize from diff]

## Key Decisions
[From [DECISION: ...] markers in both files.
 Without files: omit section]

## Changes
[From git diff + plan.md tasks: what was actually implemented]

## Test Plan
[From plan.md task verify sections + acceptance criteria.
 Without plan.md: list tests added/modified]

## References
[Jira links, related PRs, etc.]
```

### 3. Review with user

Present the rich-pr-description.md content for review.
Wait for approval or edits before creating the PR.

### 4. Create the PR

- Push branch if needed (with -u)
- Create PR using `gh pr create` with the content from rich-pr-description.md
- Return the PR URL
