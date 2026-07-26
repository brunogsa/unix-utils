---
name: refactor
description: "USE for an end-of-branch refactoring sweep over unpushed/uncommitted changes — dispatches the deep-reviewer agent to write a report the user applies later. Triggers: 'refactor this', 'clean up', /refactor, or another skill's dispatch."
disable-model-invocation: false
---

# Simplify Unpushed & Uncommitted Code

Detect refactoring opportunities in unpushed/uncommitted code and write them to a report the user applies later.

**Report only** — this skill analyzes and reports; it never edits code. Applying selected findings is a separate step the user initiates.

## When to invoke

Direct `/refactor` invocation, phrases like "refactor this" / "clean this up" / "simplify what I just wrote", or dispatch from another skill's flow (e.g. `/implement`'s batch-end tail).

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

### 2. Dispatch deep-reviewer to detect opportunities

**Before dispatch, mint the report path.** Run `date "+verdict_refactor_%Y-%m-%d_%H:%M.md"` once and treat the output as `$VERDICT_PATH` in CWD (NOT `/tmp/` — the user reviews it alongside the diff in their editor).

- The `verdict_` prefix is mandatory, not cosmetic — see `~/.claude/hooks/deep-reviewer-write-guard.sh` for why (a reserved-prefix collision with the Claude Code harness itself, not our own guard).
- Use that exact filename in every reference below. One file per `/refactor` invocation; never reuse a prior run's path.

**Dispatch** `agent(subAgent=deep-reviewer, title=Refactor-lens review)` — report-only by construction. In the prompt:

- Run in the **background** (the default) -- the UI still surfaces progress, and the harness delivers the findings report on completion.
- List the target files identified in step 1.
- Include the analysis constraints below verbatim.
- Instruct it to **write the complete report to `$VERDICT_PATH`** (overwrite if exists) and make no other edits — the guard enforces this; stating it stops a wasted blocked-write attempt.

#### Analysis constraints (passed to deep-reviewer)

- Load and apply principles from `~/.claude/CLAUDE.md` and the `code-standards`, `test-standards`, `doc-standards` skills.
- Focus only on code touched by unpushed commits or uncommitted changes — the recently-modified surface, nothing beyond it.
- Preserve behavior exactly: propose changes to *how* the code reads, never *what* it does. No behavior changes, no formatting-only churn, no new features, no refactors outside the changed files.
- Simplify for clarity, not brevity: reduce needless complexity and nesting, eliminate redundant code and dead abstractions, consolidate related logic, and drop comments that only restate the code.
- Prefer explicit, readable code over compact code — avoid nested ternaries in favor of `if`/`else` or `switch` for multi-way branches.
- Keep the balance — do NOT over-simplify: no clever one-liners, no merging unrelated concerns into one function, no stripping helpful abstractions, no trading readability for fewer lines.
- Classify each finding as **subjective** or **mechanical**:
  - **Subjective**: naming, decomposition, architecture, layered-architecture violations, guideline alignment -- things only a context-aware reviewer can judge
  - **Mechanical**: unused imports/variables, dead code/exports, cyclomatic complexity, circular dependencies, missing type annotations -- things a linter could catch deterministically
  - For mechanical findings, prefix the **What** field with `[LINTER GAP]` to signal that the project's linter config should be improved to catch this automatically
- Write the complete findings report to `$VERDICT_PATH` (overwrite if exists) per the schema below.

#### Persist full findings to the file (avoid return-message truncation)

Subagent return messages are capped and **WILL truncate long lists** -- the user has hit this before. To make findings readable:

- The report file at `$VERDICT_PATH` is the source of truth (overwrite if exists).
- The subagent's return must contain only: total count, file path, and one title line per finding.
  - Format: `1. <file>:<lines> — <one-line title>`. No code blocks, no Before/After in the return.
- If the file is missing or empty after the agent returns, treat the run as failed and re-invoke (do not proceed from the truncated return alone).

#### Per-finding schema (inside `$VERDICT_PATH`)

Each finding is a `## N. <one-line title>` section. Inside, use these labeled blocks -- no field may be omitted. Empty / N/A is allowed but must be stated explicitly.

- **File**: absolute or repo-relative path
- **Lines**: precise line range (e.g. `42-67`), not approximate
- **Classification**: `subjective` or `mechanical` (prefix `[LINTER GAP]` on the title when mechanical)
- **Category**: suggested TaskList category for the eventual commit -- `[Refactor]`, `[Debt]`, `[Drift]`, `[Scout]`, `[Sub-Step]` (see CLAUDE.md "Leverage TaskList proactively")
- **What**: 2-4 sentences on the change. Name the construct (function, variable, type, test), what it does now, what it should become.
  - Avoid pronouns without antecedents ("it", "this") -- spell out the target.
- **Why**: which principle, skill rule, or smell this addresses. Quote the exact bullet from `~/.claude/CLAUDE.md` or a `*-standards` skill.
  - Example: `CLAUDE.md › "Centralize repeated artifacts"`. Generic "improves readability" is not acceptable.
- **Before** (fenced code block): the full current code with ≥3 lines of surrounding context above and below.
  - The reader shouldn't need to open the file. Mark target lines with a `// ← target` comment when helpful.
- **After** (fenced code block): the **full** proposed code with the same surrounding context, so a side-by-side compare is trivial.
- **Impact**: 1-2 sentences -- callers affected, tests that may need updating, blast radius. If isolated, say `isolated`.
- **Risk**: `low` / `medium` / `high` plus a 1-sentence reason (e.g. `medium — touches a public export; downstream callers in 3 packages`).
- **Effort**: rough size -- `trivial` (one-liner), `small` (single file, < 20 lines), `medium` (multi-file, < 100 lines), `large` (cross-cutting). If `large`, suggest splitting into sub-findings.

A finding that cannot fill every field above is not ready to surface -- the agent should either gather more context or drop it.

### 3. Present the report — report only, stop here

After the agent returns:

1. `Read` `$VERDICT_PATH` end-to-end — do **not** rely on the return summary, it is truncated by design.
2. Present a **compact index** in chat: numbered list, one line per finding.
   - Format: `<file>:<lines> — <one-line title> [classification, risk, effort]`.
   - Do not inline Before/After -- the user has the full file open.
3. Tell the user the full report is at `$VERDICT_PATH` and invite them to open it (`tail -f` or editor) for the rich detail.

**Stop here — this skill does not apply findings.** The user decides later which to act on.

That happens by hand, or by a follow-up ask that hands selected findings to the normal edit + TaskList + verification flow (the `test-standards` post-change suite gate applies then).

Do not create apply-tasks or edit code as part of `/refactor`.
