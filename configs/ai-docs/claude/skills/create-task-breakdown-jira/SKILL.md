---
description: "Create Task Breakdown in Jira"
disable-model-invocation: true
---

# Create Task Breakdown in Jira

This command creates Jira issues from a structured task breakdown markdown file.

## Invocation

```
/create-task-breakdown-jira <path-to-markdown-file>
```

Example:
```
/create-task-breakdown-jira ~/workspace/project/task-breakdown.md
```

## Prerequisites

1. **Environment variables** must be set:
   ```bash
   export JIRA_URL='https://yourcompany.atlassian.net'
   export JIRA_EMAIL='your.email@company.com'
   export JIRA_API_TOKEN='your-api-token'
   ```

2. **jira-utilities.sh** must be available:
   ```bash
   source ~/oh-my-zsh/commands/jira-utilities.sh
   ```

---

## Link Syntax (Intuitive Order)

The `link-jira-issues` function uses intuitive parameter order:

```bash
link-jira-issues <source> <link-type> <target>
```

The link reads naturally: **SOURCE --[link-type]--> TARGET**

### Examples

```bash
# "Design 101 blocks Task 102"
link-jira-issues "ITGD-101" "Blocks" "ITGD-102"

# "Story 100 is parent of Task 101"
link-jira-issues "ITGD-100" "Parent-Child" "ITGD-101"
```

### Verification

After creating links, verify with:
```bash
get-jira-links ITGD-102
```

**Correct Blocks output** (Task 102 is blocked by Design 101):
```json
{"id":"12345","type":"Blocks","inwardIssue":"ITGD-101","outwardIssue":null}
```

**Correct Parent-Child output** (Task 101 is child of Story 100):
```json
{"id":"12346","type":"Parent-Child","inwardIssue":"ITGD-100","outwardIssue":null}
```

---

## Task Breakdown File Format

The markdown file should follow this structure:

```markdown
## Section Name

[Epic] Epic Name (or link to existing Epic: https://...atlassian.net/browse/PROJ-123)

  [User Story][Label1][Label2] Story title
    [Dependency][Label1] Dependency title
      [Design][Label1] Design title
        [Task][Label1] Task title
          [Test] E2E: Test description
```

### Rules

1. **First tag** = Issue type (Epic, User Story, Dependency, Design, Task, Test)
2. **Remaining tags** = Labels (e.g., `[SAS][B2B]` becomes labels `["SAS", "B2B"]`)
3. **Indentation** indicates hierarchy (2 spaces per level)
4. **Epic** is the parent of all cards (via Jira's parent field)
5. **Existing Epics** can be referenced via URL or issue key

### Issue Type Mapping

| Tag | Jira Issue Type | Required Fields |
|-----|-----------------|-----------------|
| `[Epic]` | Epic | - |
| `[User Story]` or `[Story]` | Story | - |
| `[Dependency]` or `[Dependencies]` | Dependency | `duedate` |
| `[Tech Design]` or `[Design]` | Tech Design | `duedate` |
| `[Task]` | Task | - |
| `[Test]` | Test | `labels` (e.g., `["E2E"]`) |

---

## Workflow

### Step 1: Read and Parse the Task Breakdown File

Read the provided markdown file and identify:
- Existing Epics (by URL or key)
- Cards to create (by indentation level)
- Labels (from tags after the first one)
- Hierarchy relationships

### Step 2: Create Issues (Without Links)

Create all issues first, recording their keys. Use `create-jira-issue` from jira-utilities.sh:

```bash
source ~/oh-my-zsh/commands/jira-utilities.sh

# Story
create-jira-issue PROJ Story "[Label1] Story title" '{"parent":{"key":"PROJ-123"},"labels":["Label1"]}'

# Dependency (requires duedate)
create-jira-issue PROJ Dependency "[Label1] Dependency title" '{"parent":{"key":"PROJ-123"},"labels":["Label1"],"duedate":"2026-03-31"}'

# Tech Design (requires duedate)
create-jira-issue PROJ "Tech Design" "[Label1] Design title" '{"parent":{"key":"PROJ-123"},"labels":["Label1"],"duedate":"2026-03-31"}'

# Task
create-jira-issue PROJ Task "[Label1] Task title" '{"parent":{"key":"PROJ-123"},"labels":["Label1"]}'

# Test (requires labels)
create-jira-issue PROJ Test "E2E: Test description" '{"parent":{"key":"PROJ-123"},"labels":["E2E"]}'
```

### Step 3: Create Parent-Child Links

All cards that are children of a User Story should have "is child of" link:

```bash
# Story 100 is parent of Task 101
link-jira-issues "ITGD-100" "Parent-Child" "ITGD-101"
```

### Step 4: Create Blocks Links

Cards are blocked by cards one level above them in the same paragraph.

**Direct children of User Stories do NOT need "is blocked by" to the User Story.**

```bash
# Design 101 blocks Task 102
link-jira-issues "ITGD-101" "Blocks" "ITGD-102"
```

### Step 5: Verify in Jira UI

Check that:
- Blocker card shows "blocks" relationship
- Blocked card shows "is blocked by" relationship

---

## Link Hierarchy Examples

### Simple hierarchy

```
[User Story] ITGD-100
  [Task] ITGD-101
    [Test] ITGD-102
```

Links to create:
```bash
# Parent-Child (Story 100 is parent of 101, 102)
link-jira-issues "ITGD-100" "Parent-Child" "ITGD-101"
link-jira-issues "ITGD-100" "Parent-Child" "ITGD-102"

# Blocks: Task 101 blocks Test 102
link-jira-issues "ITGD-101" "Blocks" "ITGD-102"
```

### Complex hierarchy (Dependency chain)

```
[User Story] ITGD-100
  [Dependency] ITGD-101
    [Design] ITGD-102
      [Task] ITGD-103
        [Test] ITGD-104
```

Links to create:
```bash
# Parent-Child (Story 100 is parent of all)
link-jira-issues "ITGD-100" "Parent-Child" "ITGD-101"
link-jira-issues "ITGD-100" "Parent-Child" "ITGD-102"
link-jira-issues "ITGD-100" "Parent-Child" "ITGD-103"
link-jira-issues "ITGD-100" "Parent-Child" "ITGD-104"

# Blocks chain (source blocks target)
link-jira-issues "ITGD-101" "Blocks" "ITGD-102"  # Dep blocks Design
link-jira-issues "ITGD-102" "Blocks" "ITGD-103"  # Design blocks Task
link-jira-issues "ITGD-103" "Blocks" "ITGD-104"  # Task blocks Test
```

### Multiple items at same level

```
[User Story] ITGD-100
  [Design] ITGD-101
    [Task] ITGD-102
    [Task] ITGD-103
      [Test] ITGD-104
```

Links to create:
```bash
# Parent-Child (Story 100 is parent of all)
link-jira-issues "ITGD-100" "Parent-Child" "ITGD-101"
link-jira-issues "ITGD-100" "Parent-Child" "ITGD-102"
link-jira-issues "ITGD-100" "Parent-Child" "ITGD-103"
link-jira-issues "ITGD-100" "Parent-Child" "ITGD-104"

# Blocks (source blocks target)
link-jira-issues "ITGD-101" "Blocks" "ITGD-102"  # Design blocks Task 1
link-jira-issues "ITGD-101" "Blocks" "ITGD-103"  # Design blocks Task 2
link-jira-issues "ITGD-102" "Blocks" "ITGD-104"  # Task 1 blocks Test
link-jira-issues "ITGD-103" "Blocks" "ITGD-104"  # Task 2 blocks Test
```

### Parallel items at same level (no block between them)

```
[User Story] ITGD-100
  [Dependency] ITGD-101
  [Task] ITGD-102
    [Test] ITGD-103
```

Here, Dependency and Task are at the same level (parallel work). Only the Test is blocked by the Task:

```bash
# Parent-Child (Story 100 is parent of all)
link-jira-issues "ITGD-100" "Parent-Child" "ITGD-101"
link-jira-issues "ITGD-100" "Parent-Child" "ITGD-102"
link-jira-issues "ITGD-100" "Parent-Child" "ITGD-103"

# Blocks: Task 102 blocks Test 103
link-jira-issues "ITGD-102" "Blocks" "ITGD-103"
```

---

## Managing Links

```bash
source ~/oh-my-zsh/commands/jira-utilities.sh

# Get all links for an issue
get-jira-links ITGD-101

# Get raw JSON response
get-jira-links ITGD-101 --raw

# Delete a link by ID
delete-jira-link 12345

# Bulk link (source to multiple targets)
bulk-link-jira-issues "Parent-Child" ITGD-100 ITGD-101 ITGD-102 ITGD-103
# Makes: Story 100 is parent of 101, 102, 103
```

---

## Common Issues

| Issue | Solution |
|-------|----------|
| Dependency/Tech Design creation fails | Add `"duedate":"YYYY-MM-DD"` to fields JSON |
| Test creation fails | Add `"labels":["E2E"]` to fields JSON |
| Blocks link appears inverted in UI | Delete and recreate: `link-jira-issues "<blocked>" "Blocks" "<blocker>"` |
| Link already exists error | Use `get-jira-links` to check existing links first |
| "Field 'issuelinks' not supported" | Cannot add links during issue creation; add them after |

---

## Quick Reference Card

```
CREATING ISSUES:
  create-jira-issue <project> <type> <summary> '<json-fields>'

CREATING LINKS (intuitive order):
  link-jira-issues <source> <link-type> <target>

  Parent-Child:
    link-jira-issues "STORY-100" "Parent-Child" "TASK-101"
    # Story 100 is parent of Task 101

  Blocks:
    link-jira-issues "DESIGN-100" "Blocks" "TASK-101"
    # Design 100 blocks Task 101

  Bulk (one source to many targets):
    bulk-link-jira-issues "Parent-Child" STORY-100 TASK-101 TASK-102 TASK-103

VERIFYING LINKS:
  get-jira-links <issue-key>
  # Correct: inwardIssue = source (parent or blocker)

FIXING WRONG LINKS:
  delete-jira-link <link-id>
  link-jira-issues "<source>" "<link-type>" "<target>"
```
