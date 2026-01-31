---
description: "Jira issue hierarchy model, link syntax conventions, and task breakdown workflow"
user-invocable: false
---

# Jira Workflow

Reusable Jira conventions extracted from the `/create-task-breakdown-jira` command. Auto-loaded when discussing Jira.

## Issue Type Hierarchy

| Tag | Jira Issue Type | Notes |
|-----|-----------------|-------|
| `[Epic]` | Epic | Top-level parent |
| `[User Story]` or `[Story]` | Story | |
| `[Dependency]` or `[Dependencies]` | Dependency | Requires `duedate` |
| `[Tech Design]` or `[Design]` | Tech Design | Requires `duedate` |
| `[Task]` | Task | |
| `[Test]` | Test | Requires `labels` (e.g., `["E2E"]`) |

## Link Conventions

Links use intuitive order: `SOURCE --[type]--> TARGET`

```bash
# "Design 101 blocks Task 102"
link-jira-issues "PROJ-101" "Blocks" "PROJ-102"

# "Story 100 is parent of Task 101"
link-jira-issues "PROJ-100" "Parent-Child" "PROJ-101"
```

## Hierarchy Rules

- **Indentation** indicates hierarchy (2 spaces per level)
- **Epic** is parent of all cards (via Jira's parent field)
- **Parent-Child links**: all cards are children of their User Story
- **Blocks links**: cards are blocked by cards one level above in the same paragraph
- **Direct children of User Stories** do NOT need "is blocked by" to the User Story
- **Parallel items at same level** (no indentation difference) do NOT block each other

## Workflow

1. Parse markdown task breakdown file
2. Create all issues first (without links), recording keys
3. Create Parent-Child links (Story -> all descendants)
4. Create Blocks links (parent level blocks child level)
5. Verify in Jira UI

## Bulk Operations

```bash
source ~/oh-my-zsh/func-utilities/jira-utilities.sh
bulk-link-jira-issues "Parent-Child" PROJ-100 PROJ-101 PROJ-102 PROJ-103
```
