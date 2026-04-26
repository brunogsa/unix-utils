---
description: "USE for end-of-branch refactoring sweep over unpushed/uncommitted changes (naming, decomposition, dead code, dense expressions, layered-architecture violations). DEFAULT mode: only on explicit user trigger ('refactor this' / 'clean this up' / 'simplify what I just wrote' / direct /refactor invocation). AUTONOMOUS mode: at end-of-branch as the FIRST step of the wrap-up sequence (refactor → final auto-review + fixes → create-pr). NOT for in-task cleanup — GREEN-REFACTOR within the task already handles that. Reports a numbered opportunity list; user picks which to apply."
disable-model-invocation: false
---

# Simplify Unpushed & Uncommitted Code

Detect refactoring opportunities in unpushed/uncommitted code, then apply them one-by-one in the main conversation for user review.

## When to invoke

**Default mode (interactive):** only on explicit user trigger — direct `/refactor` invocation or phrases like "refactor this" / "clean this up" / "simplify what I just wrote". Do NOT auto-trigger from "user just finished editing some code" or similar; the user reserves this command.

**Autonomous mode:** run as the FIRST step of the end-of-branch wrap-up sequence:

1. `/refactor` — sweep + apply approved opportunities
2. final `/auto-review` — quality gate; fix MANDATORY findings
3. `/create-pr` — generate the PR description

This ordering matters: refactor first so auto-review sees the polished code; auto-review second so create-pr's description reflects the final state.

**NOT for in-task cleanup.** RED-GREEN-REFACTOR already covers in-task local cleanup (rename a variable, extract a helper, restructure within the task). Invoking `/refactor` mid-task is both more expensive and more likely to over-abstract on partial visibility.

**Exceptions where mid-branch is OK:**
- The branch produced an obvious large duplication and you want to dedup before adding more on top.
- A naming choice in an early task turned out wrong and is propagating; rename now before the cost compounds.

## Usage

`/refactor` or `/refactor <path-or-glob>`

- No argument: scan all unpushed + uncommitted files
- With argument: scan only the specified path(s)

## Process

### 1. Identify Target Files

If the user provided a path/glob argument, use that directly.

Otherwise, collect files from both unpushed commits and uncommitted changes:

```bash
# Unpushed commits
git diff --name-only @{upstream}..HEAD

# Uncommitted changes (staged + unstaged)
git diff --name-only HEAD

# Untracked files
git ls-files --others --exclude-standard
```

Deduplicate and merge the lists. If no files are found, inform the user and stop.

### 2. Detect Refactoring Opportunities (Agent -- foreground, read-only)

Use the **Agent tool** with `subagent_type=code-simplifier:code-simplifier`. In the prompt:

- Run in **foreground** (never `run_in_background`) -- the user must see analysis progress and the main session needs full visibility into findings for the learning loop (`improve-principles-and-skills-from-session-learnings`)

- List the files identified above
- Instruct it to **only analyze and report** -- it must NOT make any edits (no Edit, no Write)
- Instruct it to read and apply principles from:
  - `~/.claude/CLAUDE.md` (global guidelines)
  - `~/.claude/skills/code-standards/SKILL.md` (code patterns)
  - `~/.claude/skills/test-standards/SKILL.md` (test patterns)
  - `~/.claude/skills/doc-standards/SKILL.md` (doc / comment patterns)
- Instruct it to focus only on code touched by unpushed commits or uncommitted changes
- Instruct it to NOT propose changes that alter behavior, change formatting only, add features beyond what exists, or refactor code outside the changed files
- Instruct it to classify each finding as **subjective** or **mechanical**:
  - **Subjective**: naming, decomposition, architecture, layered-architecture violations, guideline alignment -- things only a context-aware reviewer can judge
  - **Mechanical**: unused imports/variables, dead code/exports, cyclomatic complexity, circular dependencies, missing type annotations -- things a linter could catch deterministically
- For mechanical findings, prefix the **What** field with `[LINTER GAP]` to signal that the project's linter config should be improved to catch this automatically

The agent must return a **numbered list** of refactoring opportunities, each with:
- **File** and approximate line range
- **What**: `[LINTER GAP]` prefix if mechanical, then one-sentence description of the change
- **Why**: which guideline or principle it addresses
- **Before/After sketch**: brief code snippet showing the current state and proposed improvement

### 3. Present Findings to User

After the agent returns, present the numbered list to the user and ask which items to proceed with (all, specific numbers, or none).

### 4. Apply Refactors in Main Conversation

For each approved item, **you** (not the agent) perform the edit directly in the main conversation using the Edit tool. This keeps the user in the loop -- they can provide guidance, corrections, or reject individual changes as they happen.

All CLAUDE.md principles plus the code-standards, test-standards, and doc-standards skills apply to the resulting code. Stay within the approved refactor's *intent*: structural formatting changes implied by the refactor are expected (an extracted method has different indentation than its inlined version, etc.) -- but tangential reformatting the user did not approve (quote-style swaps, blank-line shuffles, surrounding-code reflows) is not.

Work through items sequentially. After each edit, move to the next item.
