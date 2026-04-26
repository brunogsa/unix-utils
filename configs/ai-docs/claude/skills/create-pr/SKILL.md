---
description: "Create a GitHub PR with a rich description. User-invoked only — auto-detects spec.md/plan.md for context."
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

**CRITICAL: Always check for a PR template** in `.github/` (e.g., `pull_request_template.md`,
`PULL_REQUEST_TEMPLATE.md`). If one exists, it is the **base structure** -- keep every section
and checkbox from the template. Fill in each section with the rich content generated from
spec/plan/commits/diff. Add extra sections (Approach, Key Decisions, Findings, etc.) AFTER or
WITHIN the template structure, never replacing it. Mark checklist items as `[x]` when applicable.

If no PR template exists, use the default template below.

#### Writing Style

- **Separate planned from incidental** -- group items under `**Planned:**` and `**Incidental:**`. For incidental items, briefly explain why they had to be fixed now (e.g., "blocked green CI on this branch")
- **Bold topic prefix on every bullet** -- start each bullet with `**Topic** --` so reviewers can scan the bold words and skip details they don't need
- **Be concise** -- one short sentence per bullet. Sub-bullets only when essential.
- **No blank lines between bullets** -- keep lists tight. GitHub adds extra spacing with blank lines.
- **Max ~100 chars per line** -- break longer lines into top-level bullet + sub-bullets
- **Explain the "how is it different"** -- when mentioning a new method/function, briefly say what makes it different from existing ones. Don't just name it.
- **Don't list types/interfaces** -- type names are visible in the diff. Listing them in the PR is noise.
- **Coarse-grained incidental items** -- group small fixes (typos, error messages, log levels) into a single bullet. Don't give each its own line.
- **Collapsible sections for large content** -- use `<details><summary>` for reference payloads, long examples, or API responses.
- **Always include business context** -- every PR must explain the business problem being solved. Extract from spec.md Background section when available, or from commit messages. Reviewers who don't know the ticket need this to evaluate correctness.
- **Always include decisions** -- every PR must have a decisions section. Reviewers need to understand the trade-offs made, not just the code. When using a PR template, place decisions as a subsection of the solution (e.g., `##### Decisões tomadas` under `#### Sobre a solução`). Only include reviewer-facing decisions, not implementation details.
- **Don't repeat links across sections** -- if a Jira link or PR link appears in "Link do Jira" or "Contexto do PR", don't repeat it in "Referências". The references section is for follow-up tasks, external docs, or links not already present elsewhere in the PR.
- **Drop implementation jargon from planned items** -- don't say "(injectable NestJS)" or "(pure function)". Describe what it does for the reviewer, not the DI framework details.

Example:
```markdown
# Hard to scan:
- Fix lib test failures by changing build:deps from selective to full tsc -b
- Auto-create .env from .env.local.example for seamless git worktree support
  - New setup:env script in core/package.json
- Apply Prisma migrations to test DB (port 5433)
  - Fixes 40 pre-existing failures (test DB was never migrated)

# Better:
- **Lib test fix** -- `build:deps` → full `tsc -b`
- **Worktree support** -- `setup:env` auto-creates `.env` from example
- **Test DB migrations** -- new `dbtest:migrate` for port 5433
  - Fixes 40 pre-existing failures (test DB was never migrated)
```

#### Default Template

```markdown
[Review guide goes FIRST, before any content, collapsed by default:]

<details>
<summary><strong>Guia de review</strong> (tempo estimado: {min}-{max} min)</summary>
[Generated per `~/.claude/skills/reviewer-agent/references/reading-order-template.md` (Portuguese variant)]
</details>

## Summary
[From spec.md Background + Goals (when available), cross-referenced with
 commit messages and diff to confirm what was actually delivered.
 Condensed to 2-3 bullets. Always ground in commits, not just docs.]

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

The Guia de review template, time-estimate heuristic, and file-role inference live in `~/.claude/skills/reviewer-agent/references/reading-order-template.md` (Portuguese variant).

### 3. Review with user

Present the rich-pr-description.md content for review.
Wait for approval or edits before creating the PR.

### 3.5. Learn from user edits

After the user edits rich-pr-description.md, diff the original against their version.
Identify patterns in what was added, removed, or reworded. Present proposed improvements
to THIS skill's writing style guidelines (step 2) for user approval -- similar to
`improve-principles-and-skills-from-session-learnings`. Apply approved improvements before
creating the PR. This makes the skill self-improving over time.

### 4. Create the PR

- Push branch if needed (with -u)
- Create PR as **draft** using `gh pr create --draft` with the content from rich-pr-description.md
- Return the PR URL
