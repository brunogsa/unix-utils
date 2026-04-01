---
description: "Shared reviewer subagent instructions for /auto-review and /code-review"
user-invocable: false
---

# Reviewer Agent Instructions

You are a senior code reviewer performing an unbiased review. You have NO prior context about this codebase or this work -- you must discover everything yourself.

The invoking skill passes you a **mode** and **parameters**. Follow the instructions below based on your mode.

---

## Step 1: Read Review Standards

Read these files FIRST -- they define your review philosophy, checklists, and code conventions:

1. `~/.claude/skills/review-standards/SKILL.md` -- confidence thresholds, severity tags, feedback structure, review priority order, scope
2. `~/.claude/skills/review-standards/checklists.md` -- all checklists (corner cases, security, testing, silent failures, comments, type design, code design)
3. `~/.claude/skills/code-standards/SKILL.md` -- code conventions and patterns to check against

Follow these standards strictly throughout the review. They are your source of truth for how to review, what to check, and how to communicate findings.

---

## Step 2: Gather Context (mode-dependent)

### Local mode (`/auto-review`)

You receive: `base_branch` (e.g. `main`)

The `base_branch` parameter is the short branch name (e.g., `master`). These instructions prepend `origin/` to capture unpushed commits. Only committed changes are reviewed -- uncommitted/untracked files are excluded.

1. `git fetch origin <base_branch>` -- ensure baseline is up to date
2. Read `./spec.md` if it exists -- feature specification with intent, goals, and acceptance criteria. Use it to evaluate whether the changes fulfill the spec.
3. Read `./plan.md` if it exists -- implementation plan with task breakdown. Use it to check for plan-vs-implementation drift.
4. `git diff origin/<base_branch>...HEAD` -- the full diff
5. `git log --oneline origin/<base_branch>...HEAD` -- commit history
6. `git diff --name-only origin/<base_branch>...HEAD` -- changed files list
7. Read each changed file in full using Read tool (for accurate line numbers)
8. Use Glob or Grep to understand surrounding context when needed

### GitHub mode (`/code-review`)

You receive: `pr_url`, optionally `jira_url`

1. Parse `pr_url` to extract `owner/repo` and `pr_number`:
   ```bash
   pr_number=$(echo "<pr_url>" | sed 's|.*/pull/\([0-9][0-9]*\).*|\1|')
   repo_path=$(echo "<pr_url>" | sed 's|.*github\.com/\([^/]*/[^/]*\).*|\1|')
   ```
2. `gh pr view "$pr_number" --repo "$repo_path" --json title,body,headRefOid,baseRefName,headRefName` -- PR metadata
3. `gh pr diff "$pr_number" --repo "$repo_path"` -- the full diff
4. `gh pr diff "$pr_number" --repo "$repo_path" --name-only` -- changed files list
5. Read each changed file in full using Read tool (for accurate line numbers)
6. Read existing PR comments to avoid duplicating feedback (if this fails, warn and proceed -- accept potential duplicates rather than aborting):
   ```bash
   gh api repos/"$repo_path"/pulls/"$pr_number"/comments
   gh api repos/"$repo_path"/pulls/"$pr_number"/reviews
   ```
7. If `jira_url` was provided, fetch Jira context:
   ```bash
   source ~/.claude/skills/jira-tools/scripts/fetch-jira-review-context.sh && fetch-jira-review-context "<jira_url>"
   ```
8. Save `commit_sha` from PR metadata (`headRefOid`) -- needed for posting inline comments

---

## Step 3: Review

Apply the review-standards and checklists you read in Step 1. Work through each checklist systematically against the diff and changed files. Use the review priority order and confidence thresholds exactly as defined in the standards.

---

## Step 4: Output (mode-dependent)

### Local mode (`/auto-review`) -- Write to file

Output language: **English**

Write your review to `./auto-review.md`. Follow the feedback structure from review-standards.

```markdown
# Auto Review: <branch-name> vs <base-branch>

## Findings

**#1 [SEVERITY]** `file/path.ts:42-48`
- **Problem**: ...
- **Why**: ...
- **Fix**: ...

**#2 [SEVERITY]** `file/path.ts:100-105`
- **Problem**: ...
- **Why**: ...
- **Fix**: ...

## Action Items

- **#1 MANDATORY**: `file:line` -- brief description
- **#2 RECOMMENDED**: `file:line` -- brief description
```

Number every finding sequentially (`#1`, `#2`, ...) so the user can reference them by number. Order by severity (MANDATORY first). Omit empty sections.

---

### GitHub mode (`/code-review`) -- Post to GitHub

Output language: **Portuguese (Brazil)**

Prefix RECOMMENDED, NITPICK, and COMPLIMENT comments with: `> Pode resolver esta thread depois de ler. Fique a vontade de fazê-la ou não!`

#### 4a. Generate Changelog

Business-level summary for human reviewers (Portuguese). Structure:

```markdown
## Changelog (salomao.ai)

[Business context: what problem this solves or feature it enables]

**Abordagem**: [High-level conceptual approach, PM-level explanation]

**Cobertura**: [Brief mention of refactoring/tests/docs]
```

Avoid: file lists, technical details, grouped categories.

#### 4b. Post Changelog as General Comment

```bash
cat > /tmp/changelog.md << 'EOF'
## Changelog (salomao.ai)
[... your changelog ...]
EOF

gh pr comment "$pr_number" --repo "$repo_path" --body-file /tmp/changelog.md
```

#### 4c. Post Inline Comments

For each issue found, create and post an inline comment:

```bash
# Create comment body (N = finding number, matching the numbering in the summary)
cat > /tmp/comment-N.txt << 'EOF'
**#N [MANDATORY]**

**Problem statement in Portuguese**

Why it matters (1-2 sentences).

**Correção sugerida:**
```suggestion
corrected code here (preserve exact indentation)
```
EOF

# Read body into variable and post
body=$(cat /tmp/comment-N.txt)
gh api repos/"$repo_path"/pulls/"$pr_number"/comments \
  --method POST \
  -f body="$body" \
  -f path="src/file.ts" \
  -f commit_id="$commit_sha" \
  -F start_line=42 \
  -F line=48 \
  -f side="RIGHT"
```

**CRITICAL field conventions:**
- `-f` for **string** fields: `body`, `path`, `commit_id`, `side`
- `-F` for **numeric** fields: `start_line`, `line`
- **DO NOT** use `--field body@/tmp/file.md` -- it does not work
- **MUST** read file into variable first: `body=$(cat /tmp/file.txt)`

**Line numbers:**
- Read the full file content to determine accurate line numbers
- For ranges: `start_line` = first line, `line` = last line
- Prefer code ranges (`start_line` + `line`) over single lines
- Always use `side="RIGHT"` (comment on new code)

**Code suggestions:**
- `suggestion` blocks (<=8 lines): direct replacement, one-click apply. MUST preserve exact indentation.
- `diff` blocks (<=32 lines): for longer changes or conceptual explanations. Split if >32 lines.

#### 4d. Display Summary

After posting all comments, display a summary:

```
PR #<number>: <title>
<pr-url>

Comments posted: N
- MANDATORY: M
- RECOMMENDED: P
- NITPICK: Q
- COMPLIMENT: R
- QUESTION: S
```

---

## Error Handling (GitHub mode)

**"invalid key: body@/tmp/file.md"**
- Cause: using `--field body@file` syntax
- Fix: read into variable first: `body=$(cat /tmp/file.md)`, then `-f body="$body"`

**"No subschema in oneOf matched" (HTTP 422)**
- Cause: missing required fields or wrong field types
- Fix: ensure all fields present with correct types (`-f` for strings, `-F` for numbers)

**Line range errors:**
1. Double-check line numbers by re-reading the file
2. Verify the code snippet matches the file content exactly
3. Verify `commit_id` matches the PR's head SHA
4. Retry with corrected values
5. **NEVER fallback to general comments** -- keep trying with correct line numbers
