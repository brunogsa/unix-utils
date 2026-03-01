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
- Run git log to see commits on current branch vs base -- **primary source**: mine commit messages for decisions, rationale, and scope changes regardless of whether spec/plan exist
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
[From spec.md Background + Goals (when available), cross-referenced with
 commit messages and diff to confirm what was actually delivered.
 Condensed to 2-3 bullets. Always ground in commits, not just docs.]

## Approach
[From plan.md Approach section (when available), confirmed against diff.
 Without plan.md: infer from commit messages and diff.]

## Key Decisions
[Primary: [DECISION: ...] markers from spec.md and plan.md.
 Always also: mine commit messages for decision rationale, trade-off
 explanations, and "why" context -- even when spec/plan exist.
 Merge both sources, deduplicate.]

## Changes
[Compare git diff against plan.md tasks (when available).
 Two groups:
 - **Planned changes**: tasks from the plan that were implemented
 - **Incidental changes**: modifications not in the plan -- side-effects,
   cleanup, fixes discovered during implementation, scope adjustments.
 Without plan.md: organize changes from diff and commit messages.]

## Test Plan
[From plan.md task verify sections + acceptance criteria.
 Cross-reference with test files in the diff.
 Mark items [x] if verification was performed in this session.
 Without plan.md: list tests added/modified from diff.]

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
