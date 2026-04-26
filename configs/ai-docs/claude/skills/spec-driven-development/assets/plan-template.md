# Plan: [Title]

Spec: [link or reference to spec.md]

> **Default: each task follows RED-GREEN-REFACTOR (TDD/BDD).** See the `test-driven-development` skill. Opt-out per task with `**DECISION:** skip TDD because <reason>`.

## Approach
High-level technical approach. Architecture decisions. Trade-offs considered.

## Test Design

Test titles designed before implementation — bodies come during each RED-GREEN cycle. Review before coding starts.

**Integration tests (outer layer)** — the stable user-facing contract. Design all titles upfront:

```
describe("[ComponentOrUseCase]", () => {
  it("should [behavior] when [condition]");
  it("should [behavior] when [condition]");
});
```

**Unit tests for pre-known pure helpers** — only helpers we know will exist regardless of design or implementation choices (e.g., obvious normalizers, parsers, validators). Skip this subsection if none:

```
describe("[obviousPureHelper]", () => {
  it("should [behavior] when [input]");
});
```

Tests for helpers pulled on demand during RED-GREEN are designed at the moment the caller first needs them (test-first at the point of pull) — designing them eagerly would force premature signatures.

If this change is a pure refactor, config edit, or similar no-behavior-change work, mark this section "N/A" with a short reason.

## Tasks

Each task produces **1-2 commits, never zero**. Sub-commit steps (RED/GREEN/REFACTOR cycles) live inside a task, not as sibling tasks. Scout findings, refactors, and scope increases become new peer tasks with their own commits.

**Sub-step breadcrumb** — optional parenthetical at the end of the task title, semicolon-separated, to hint at the beats inside: `### N. Task title (sub-step; sub-step; sub-step)`. Keep to ~4 items; if it grows longer, the task is probably two tasks in disguise.

### 0. Symlink plan to project directory
**What**: Create a symlink from this plan file to `./plan.md` in the current working directory. If spec.md exists in cwd, it was already used as input.
**Verify**: `readlink ./plan.md` points to this plan file.
**Commits**: none (scaffolding step).

### 1. [Task title] (optional: sub-step; sub-step; sub-step)
**Description**: What needs to be done.
**Files**: `path/to/file1.ts`, `path/to/file2.ts`
**Acceptance criteria**: What "done" looks like for this task.
**Verify**: Command or test that proves it works.
**Commits**:
  1. `~/repo` — `type(scope): subject`
  2. `~/repo` — `type(scope): subject` *(only when the task naturally produces two — e.g., "introduce helper" + "replace callers" — otherwise delete this line)*

### 2. [Task title]
...

## Decisions

Chronological log. Editable while planning. Once the user approves the plan and signals execution start, insert the divider line below and switch to append-only — revisions become new entries with `**Supersedes:**` references rather than in-place edits.

- **DECISION:** ..., because ...

<!-- ── execution begins below; entries above are frozen, append-only below ── -->

- **DECISION (Task N):** ..., because ... *(to revise an earlier decision, append a new entry ending with `**Supersedes:** "<first ~60 chars of prior>"`)*
