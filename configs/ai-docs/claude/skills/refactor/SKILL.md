---
name: refactor
description: "USE for end-of-branch refactoring sweep over unpushed changes. DEFAULT: explicit trigger ('refactor this' / 'clean up' / /refactor). AUTONOMOUS: first step of end-of-branch wrap-up (refactor → auto-review + fixes → create-pr)."
disable-model-invocation: false
---

# Simplify Unpushed & Uncommitted Code

Detect refactoring opportunities in unpushed/uncommitted code, then apply them one-by-one in the main conversation for user review.

## When to invoke

**Default mode (interactive):** only on explicit user trigger.

- Direct `/refactor` invocation or phrases like "refactor this" / "clean this up" / "simplify what I just wrote".
- Do NOT auto-trigger from "user just finished editing some code" or similar; the user reserves this command.

**Autonomous mode:** run as the FIRST step of the end-of-branch wrap-up sequence:

1. `/refactor` — sweep + apply approved opportunities
2. final `/auto-review` — quality gate; fix MANDATORY findings
3. `/create-pr` — generate the PR description

This ordering matters: refactor first so auto-review sees the polished code; auto-review second so create-pr's description reflects the final state.

**NOT for in-task cleanup.**

- RED-GREEN-REFACTOR already covers in-task local cleanup (rename a variable, extract a helper, restructure within the task).
- Invoking `/refactor` mid-task is both more expensive and more likely to over-abstract on partial visibility.

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

- Run in **foreground** (never `run_in_background`) -- the user must see analysis progress and the main session needs full visibility into findings

- List the files identified above
- Instruct it to **only analyze and report** -- it must NOT make any edits (no Edit, no Write)
- Instruct it to load and apply principles from:
  - `~/.claude/CLAUDE.md` (global guidelines)
  - `code-standards` skill (code patterns)
  - `test-standards` skill (test patterns)
  - `doc-standards` skill (doc / comment patterns)
- Instruct it to focus only on code touched by unpushed commits or uncommitted changes
- Instruct it to NOT propose changes that alter behavior, change formatting only, add features beyond what exists, or refactor code outside the changed files
- Instruct it to classify each finding as **subjective** or **mechanical**:
  - **Subjective**: naming, decomposition, architecture, layered-architecture violations, guideline alignment -- things only a context-aware reviewer can judge
  - **Mechanical**: unused imports/variables, dead code/exports, cyclomatic complexity, circular dependencies, missing type annotations -- things a linter could catch deterministically
- For mechanical findings, prefix the **What** field with `[LINTER GAP]` to signal that the project's linter config should be improved to catch this automatically

#### Persist full findings to a file (avoid return-message truncation)

Subagent return messages are capped and **WILL truncate long lists** -- the user has hit this before. To make findings readable:

- Instruct the subagent to **write the complete report to `/tmp/refactor-findings.md`** (overwrite if exists).
- The subagent's return must contain only: total count, file path, and one title line per finding.
  - Format: `1. <file>:<lines> — <one-line title>`. No code blocks, no Before/After in the return.
  - The file is the source of truth.
- If the file is missing or empty after the agent returns, treat the run as failed and re-invoke (do not proceed from the truncated return alone).

#### Per-finding schema (in the `/tmp/refactor-findings.md` file)

Each finding is a `## N. <one-line title>` section. Inside, use these labeled blocks -- no field may be omitted. Empty / N/A is allowed but must be stated explicitly.

- **File**: absolute or repo-relative path
- **Lines**: precise line range (e.g. `42-67`), not approximate
- **Classification**: `subjective` or `mechanical` (prefix `[LINTER GAP]` on the title when mechanical)
- **Category**: suggested TaskList category for the eventual commit -- `[Refactor]`, `[Debt]`, `[Drift]`, `[Scout]`, `[Sub-Step]` (see CLAUDE.md "Leverage TaskList proactively")
- **What**: 2-4 sentences on the change. Name the construct (function, variable, type, test), what it does now, what it should become.
  - Avoid pronouns without antecedents ("it", "this") -- spell out the target.
- **Why**: which principle, skill rule, or smell this addresses. Quote the exact bullet from `~/.claude/CLAUDE.md` or a `*-standards` skill.
  - Example: `code-standards › "Centralize repeated artifacts"`. Generic "improves readability" is not acceptable.
- **Before** (fenced code block): the full current code with ≥3 lines of surrounding context above and below.
  - The reader shouldn't need to open the file. Mark target lines with a `// ← target` comment when helpful.
- **After** (fenced code block): the **full** proposed code with the same surrounding context, so a side-by-side compare is trivial.
- **Impact**: 1-2 sentences -- callers affected, tests that may need updating, blast radius. If isolated, say `isolated`.
- **Risk**: `low` / `medium` / `high` plus a 1-sentence reason (e.g. `medium — touches a public export; downstream callers in 3 packages`).
- **Effort**: rough size -- `trivial` (one-liner), `small` (single file, < 20 lines), `medium` (multi-file, < 100 lines), `large` (cross-cutting). If `large`, suggest splitting into sub-findings.

A finding that cannot fill every field above is not ready to surface -- the agent should either gather more context or drop it.

### 3. Present Findings to User

After the agent returns:

1. `Read` `/tmp/refactor-findings.md` end-to-end (do **not** rely on the agent's return summary -- it is truncated by design).
2. Present a **compact index** in chat: numbered list, one line per finding.
   - Format: `<file>:<lines> — <one-line title> [classification, risk, effort]`.
   - Do not inline Before/After -- the user has the full file open.
3. Tell the user the full report is at `/tmp/refactor-findings.md` and invite them to open it (`tail -f` or editor) for the rich detail.
4. Ask which items to proceed with (all, specific numbers, none, or a range like `1-3,7`).

Once the user selects items, emit *"Selected N findings. Leveraging tasklist."*

- Create one task per approved finding, using the **Category** field from the report as the prefix.
  - Defaults: `[Refactor]` for typical changes, `[Scout]` for agent-flagged pre-existing issues.
- The trigger phrase activates the rest of the TaskList protocol from CLAUDE.md — do not restate it here.

### 4. Apply Refactors in Main Conversation

For each approved item, **you** (not the agent) perform the edit directly in the main conversation using the Edit tool.

- This keeps the user in the loop.
- They can provide guidance, corrections, or reject individual changes as they happen.

All CLAUDE.md principles plus the code-standards, test-standards, and doc-standards skills apply to the resulting code.

- Stay within the approved refactor's *intent*.
- Structural formatting changes implied by the refactor are expected (an extracted method has different indentation than its inlined version, etc.).
- But tangential reformatting the user did not approve (quote-style swaps, blank-line shuffles, surrounding-code reflows) is not.

Work through the TaskList created in step 3 in order, one finding per edit.
