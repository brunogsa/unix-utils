# Plan: [Title]

Spec: [link or reference to spec.md]

---
## Technical Approach & High Level Architecture

High-level technical approach. Architecture and Trade-offs considered.

A flowchart, C4L1 (context diagram) or anything else. Keep simple and readable.

Follow the `mermaid-diagrams` skill for conventions.

---
## General Flow

Where the code starts executing, having which data, which modules/class/functions/enums etc are required and in which order.

It should explain for the human, assuming do NOT know the codebase, what happens technically in the code at the high level AS SIMPLE as possible, without code.

A sequence diagram, flowchart or anything else. Keep simple and readable.

Follow the `mermaid-diagrams` skill for conventions.

---
## Reusage report

What have you considered to reusage or extend? Why did you discard it?

Something simple in bullets and sub-bullets, easy for user to scan.
The main goal is to create user awareness and enforce AI to exercise this.

---
## Side-effect report

Is something a breaking change? For who? Do we know the blast radius? Can it be retrocompatible?

Something simple in bullets and sub-bullets, easy for user to scan.
The main goal is to create user awareness and enforce AI to exercise this.

---
## Test Design

Test titles designed before implementation — bodies come during each RED-GREEN cycle. Review before coding starts.

**Integration tests (outer layer)** — the stable user-facing contract. Design all titles upfront:

```
// <file>
describe("[ComponentOrUseCase]", () => {
  it("should [behavior] when [condition]");
  it("should [behavior] when [condition]");
});
```

**Unit tests for pre-known pure helpers** — only helpers we know will exist regardless of design or implementation choices (e.g., obvious normalizers, parsers, validators). Skip this subsection if none:

```
// <file>
describe("[obviousPureHelper]", () => {
  it("should [behavior] when [input]");
});
```

Tests for helpers pulled on demand during RED-GREEN are designed at the moment the caller first needs them (test-first at the point of pull) — designing them eagerly would force premature signatures.

If this change is a pure refactor, config edit, or similar no-behavior-change work, mark this section "N/A" with a short reason.

**CRITICAL:** Include a table with the columns "Testable Acceptance Criteria" and "Covered by", that shows user ALL ACs from spec.md were covered by this plan.md tests. Not a single one left behind.

---
## Task Breakdown

Each task produces **at least one base commit** (related tests, code and even IaC and docs, if they exist, together; RED/GREEN cycles live inside that commit).

At execution, any refactor, scout finding, side quest worked on, separable drift, or `/auto-review` follow-up change becomes its own additional commit within the task.
Substantial scope additions still warrant a new peer task.

Refactors are isolated tasks by definition.

**Sub-step breadcrumb** — optional parenthetical at the end of the task title, semicolon-separated, to hint at the beats inside: `### N. Task title (sub-step; sub-step; sub-step)`.

Keep to ~4 items; if it grows longer, the task is probably two tasks in disguise, or require sub-steps on the TaskList.

### 1. [Task title] (optional: sub-step; sub-step; sub-step)

**Depends on**:
- Task X
- ...

**Brief Description**: What needs to be done.

**Testable Acceptance criteria**:
- What "done" looks like for this task.

**Verification**:
- Command or test that proves it works.

**Files (logical order)**:
- `path/to/file1.ts`
- `path/to/file2.ts`

**Commits (logical order)**:
  1. `~/repo` — `type(scope): subject`
  2. `~/repo` — `type(scope): subject` *(only when the task naturally produces two — e.g., "introduce helper" + "replace callers" — otherwise delete this line)*

### 2. [Task title]

...

---
## Open Questions

- **QUESTION:** ... ?

---
## Technical Decisions

Chronological log. Editable while planning.

Once the user approves the plan and signals execution start, insert the divider line below and switch to append-only.

Revisions become new entries with `**Supersedes:**` references rather than in-place edits.

- **DECISION:** __Chose__ <approach>, __because__ <reason>
  - __Discarded__ **<alternative>**: <reason>

<!-- ── execution begins below; entries above are frozen, append-only below ── -->

- **DECISION (Task N):** __Chose__ <approach>, __because__ <reason>
  - __Supersedes__ "<first ~60 chars of prior decision>" __because__ <reason>
