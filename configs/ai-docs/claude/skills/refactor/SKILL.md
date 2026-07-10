---
name: refactor
description: "USE for end-of-branch refactoring sweep over unpushed changes — batch report → approve → apply (direct-apply cleanup of just-written code → native /simplify). Triggers: 'refactor this' / 'clean up' / /refactor, or another skill's dispatch."
disable-model-invocation: false
---

# Simplify Unpushed & Uncommitted Code

Detect refactoring opportunities in unpushed/uncommitted code, then apply the user-approved batch in the main conversation.

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

### 2. Detect Refactoring Opportunities

**Before analysis, mint the report path.** Run `date "+refactor_%Y-%m-%d_%H:%M.md"` once and treat the output as `$REPORT_PATH` in CWD (NOT `/tmp/` — the user reviews it alongside the diff in their editor).

Use that exact filename in every reference below. One file per `/refactor` invocation; never reuse a prior run's path.

**Default**: run analysis in the main context yourself — the user sees every file read and every reasoning step inline.

**Opt-in subagent**: ask the user first:

> "Run refactor analysis in this main context (default — you see every read and reasoning step inline) or offload to a subagent (saves tokens, hides intermediate output; returns may truncate)?"

Only spawn the subagent on explicit user opt-in.

The subagent path is faster on token budget but the user loses visibility into intermediate decisions, and subagent return messages have hit truncation limits before.

#### Analysis constraints (both flows)

- Load and apply principles from `~/.claude/CLAUDE.md` and the `code-standards`, `test-standards`, `doc-standards` skills.
- Focus only on code touched by unpushed commits or uncommitted changes.
- Do NOT propose changes that alter behavior, change formatting only, add features beyond what exists, or refactor code outside the changed files.
- Classify each finding as **subjective** or **mechanical**:
  - **Subjective**: naming, decomposition, architecture, layered-architecture violations, guideline alignment -- things only a context-aware reviewer can judge
  - **Mechanical**: unused imports/variables, dead code/exports, cyclomatic complexity, circular dependencies, missing type annotations -- things a linter could catch deterministically
  - For mechanical findings, prefix the **What** field with `[LINTER GAP]` to signal that the project's linter config should be improved to catch this automatically
- Write the complete findings report to `$REPORT_PATH` (overwrite if exists) per the schema below.

#### Main-context flow (default)

Apply the analysis constraints directly yourself — the user sees every file read and reasoning step inline.

#### Subagent flow (opt-in)

Use the **Agent tool** with `subagent_type=code-simplifier:code-simplifier`. In the prompt:

- Run in the **background** (the default) -- the UI still surfaces progress, and the harness delivers the findings report on completion
- List the files identified above
- Include the analysis constraints above verbatim
- Instruct it to **only analyze and report** -- it must NOT make any edits (no Edit, no Write)

#### Persist full findings to a file (avoid return-message truncation)

Subagent return messages are capped and **WILL truncate long lists** -- the user has hit this before. To make findings readable:

- Instruct the subagent to **write the complete report to `$REPORT_PATH`** (overwrite if exists).
- The subagent's return must contain only: total count, file path, and one title line per finding.
  - Format: `1. <file>:<lines> — <one-line title>`. No code blocks, no Before/After in the return.
  - The file is the source of truth.
- If the file is missing or empty after the agent returns, treat the run as failed and re-invoke (do not proceed from the truncated return alone).

#### Per-finding schema (inside `$REPORT_PATH`)

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

### 3. Present Findings to User

After the analysis completes (either flow):

1. `Read` `$REPORT_PATH` end-to-end (in the subagent flow, do **not** rely on the return summary -- it is truncated by design).
2. Present a **compact index** in chat: numbered list, one line per finding.
   - Format: `<file>:<lines> — <one-line title> [classification, risk, effort]`.
   - Do not inline Before/After -- the user has the full file open.
3. Tell the user the full report is at `$REPORT_PATH` and invite them to open it (`tail -f` or editor) for the rich detail.
4. Ask which items to proceed with (all, specific numbers, none, or a range like `1-3,7`).

Once the user selects items, emit *"Selected N findings. Leveraging tasklist."*

- Create one task per approved finding, using the **Category** field from the report as the prefix.
  - Defaults: `[Refactor]` for typical changes, `[Scout]` for agent-flagged pre-existing issues.
- The trigger phrase activates the rest of the TaskList protocol from CLAUDE.md — do not restate it here.

### 4. Apply Refactors in Main Conversation

For each approved item, **you** (not the agent) perform the edit directly in the main conversation using the Edit tool.

- Step 3's batch selection IS the one-pass review (CLAUDE.md's async-iteration rule): apply every approved finding without pausing for per-item confirmation.
- The user may interject at any point; fold their corrections into one numbered batch — never wait for a per-edit go-ahead.

All CLAUDE.md principles plus the code-standards, test-standards, and doc-standards skills apply to the resulting code.

- Stay within the approved refactor's *intent*.
- Structural formatting changes implied by the refactor are expected (an extracted method has different indentation than its inlined version, etc.).
- But tangential reformatting the user did not approve (quote-style swaps, blank-line shuffles, surrounding-code reflows) is not.

Work through the TaskList created in step 3 in order, one finding per edit.

### 5. Verify the full check matrix — MANDATORY

After ALL approved refactors are applied (at the end of the batch, not after each), run the full post-change verification gate — load and follow `~/.claude/skills/reviewer-agent/references/verify-check-matrix.md`.

Refactors look mechanical, but rename collisions, missed callers, removed exports still in use elsewhere, and broken type narrowing all surface here — not at edit time.
