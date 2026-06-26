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

**Tests (planned)**:
- "should [behavior] when [condition]"
- "should [behavior] when [condition]"

Subset of the global Test Design section that this task owns. The /implement
pre-commit gate (Gate 3) parses these titles via
`spec-driven-development/scripts/extract-planned-tests-for-task.sh` and a
fresh-context subagent verifies each one exists in the diff before allowing
the commit.

- Pure refactor / config edit with no behavior change: use
  `**Tests (planned)**: N/A — <one-line reason>`. The gate short-circuits.
- Helper test pulled in mid-task (test-first at point of pull, per
  `test-driven-development`): append the new title to this list in the
  same commit, tagged `[on-demand]`. The gate treats `[on-demand]` titles
  identically to originally planned ones.

**Verification**:
- Command or test that proves it works.

**Files (logical order)**:
- `path/to/file1.ts`
- `path/to/file2.ts`

**Commits (sketch, minimum)**:
  1. `~/repo` — `type(scope): subject`
  2. `~/repo` — `type(scope): subject` *(only when the task naturally produces two — e.g., "introduce helper" + "replace callers" — otherwise delete this line)*

Minimum count, not exact. Drift fixes, scout findings, refactor sub-steps,
and `/auto-review` follow-ups become their own additional commits within
the task, each carrying the matching `[Drift]` / `[Scout]` / `[Refactor]`
category tag in the message.

### 2. [Task title]

...

---
## PR Breakdown

Default: **one plan = one PR.** Most plans stop here — write "Single PR." and move on.

Split into a sequence of PRs only when the work is too large to review well in one sitting.

**Felt size anchor (a guide, not a gate)** — reviewer defect-detection drops sharply past ~400 lines of diff and falls off hard above ~600 (SmartBear/Cisco 2,500-review study; Google's small-CL guidance).

No code exists yet, so estimate by feel from the task and file counts above — never invent a line number.

**Splitting rules:**

- **Vertical, never horizontal** — each PR ships its own tests + code + docs + infra together. Never "PR-1 = all tests, PR-2 = all code."

- **Prefer independent PRs; a dependent sequence is fine** — a series of manageable PRs beats one big PR when full independence isn't feasible.

- **Each PR is independently reviewable and mergeable** — in order, if dependent.

- **Don't over-split** — a PR under ~50 lines usually lacks the context to review. The failure mode to catch is the one giant PR, not many tiny ones.

Partition the tasks above — one line per PR:

1. **PR-1** — <theme>. Tasks: <N, N>. Depends on: <none | PR-N>.

2. **PR-2** — <theme>. Tasks: <N, N>. Depends on: <none | PR-N>.

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
