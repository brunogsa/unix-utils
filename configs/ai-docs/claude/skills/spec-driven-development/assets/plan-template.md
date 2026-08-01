---
# performance-check budget override — DELETE this whole frontmatter block when you copy
# this template into a real plan file. It is tooling metadata, not plan content.
# Both consumers read this file and populate every section in one run, so splitting it would
# only make the author read two files instead of one. Raised from the 1024w bundled default.
words-budget: 2048
---
# Plan: [Title]

Spec: [link or reference to the paired spec file — `N/A — plan-only run` when no spec was written]

---
## Technical Approach & High Level Architecture

**Lead with a diagram** — a flowchart or C4L1 context diagram is the primary artifact; a picture is faster for the reviewer to scan than prose. Keep it simple and readable.

Add prose only for the trade-offs and architecture decisions the diagram can't convey.

N/A escape: for a trivial or no-flow change, write "N/A — <reason>" and skip the diagram.

Follow the `mermaid-diagrams` skill for conventions.

---
## General Flow

**Lead with a diagram** — faster to scan than prose: a sequence diagram or flowchart showing where execution starts, what data it carries, and which modules/functions run in order.

For a reader who does NOT know the codebase, the diagram plus minimal prose should convey the high-level technical flow, as simply as possible, without code.

N/A escape: for a trivial or no-flow change, write "N/A — <reason>" and skip the diagram.

Follow the `mermaid-diagrams` skill for conventions.

---
## Test Design

Test titles designed before implementation — bodies come during each RED-GREEN cycle. Review before coding starts.

**Integration tests (outer layer)** — the stable user-facing contract. Design all titles upfront, grouped by scenario class so a thin class is a visible gap:

- **Happy cases** — the expected success paths.
- **Corner cases** — boundary/edge inputs handled deliberately (off-by-one, empty, single-vs-many, precision residue, optional field present/absent).
- **Failure scenarios** — every way it fails: guard rejections, downstream errors, partial success, retry-vs-DLQ classification.

```
// <file>
describe("[ComponentOrUseCase]", () => {
  // Happy cases
  it("should [behavior] when [nominal condition]");
  // Corner cases
  it("should [behavior] when [boundary condition]");
  // Failure scenarios
  it("should [fail/throw] when [failure condition]");
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

**AC → test coverage — an AC-grouped nested list, not a table:**

Each AC from the paired spec is a header; under it, the tests that prove it as sub-bullets, each written as a Test Design breadcrumb.

Format: `<describe> > <happy|corner|failure> > <it>`, or `<describe> > <it>` for a flat helper block with no class grouping:

```
- **AC-1** <AC title>
  - "SgeSyncUseCase > happy > verbatim it() title from Test Design"
  - "SgeSyncUseCase > failure > another verbatim it() title"

- **AC-2** <AC title>
  - "SomeHelper > verbatim helper it() title"
```

A nested list, not a table, because one AC maps to many tests — a table jams N titles into one cell, forcing `…` truncation.
Truncation is exactly where a gamed citation hides.
One test per line keeps each line short and verbatim.
The human cross-checks each against the Test Design by exact string.

Spell out the AC title, not only its `AC-N` mnemonic, so the human verifies each group without a legend.

The breadcrumb prefix (describe + class) makes each citation self-describing — its exact home in Test Design is visible without hunting.

It keeps two same-named `it()` titles distinct, which a bare title would collapse under de-duplication, silently hiding a coverage gap.

Don't hand-type breadcrumbs — the prefix is derived from Test Design, so typing it in the lists duplicates a source and drifts.

Author the AC and task lists with bare `it()` titles, then run `spec-driven-development/scripts/normalize-list-breadcrumbs.sh <plan>` to upgrade every list bullet to its breadcrumb in place.

It is idempotent and only rewrites titles that match a real Test Design test.

**Both coverage axes are verified by script, not by hand:**

- `spec-driven-development/scripts/check-ac-coverage.sh <plan> <spec>`:
  - COMPLETENESS: every `AC-N` defined in the spec's Acceptance-Criteria section has a header.
  - HONESTY: every cited breadcrumb exists verbatim among the Test Design breadcrumbs; a `…`-truncated or invented citation won't match → flagged.
  - The semantic "does this test prove this AC?" stays the human's read — the script only kills the two gaming vectors around it.

- `spec-driven-development/scripts/check-test-distribution.sh <plan>` — SET EQUALITY between the Test Design breadcrumbs (A) and the union of all tasks' Tests (planned) lists (B).
  Fails on `A \ B` (a designed test in no task) or `B \ A` (a task inventing a test).
  Don't maintain a hand-written Test → task table — it becomes a third verbatim copy that drifts.
  Set-equality (not a naive "title appears ≥2 times" count) is needed because the AC coverage list also quotes titles, so a bare count passes without the title ever reaching a task.

- Both gates reconstruct the Test Design breadcrumbs via the shared `spec-driven-development/scripts/extract-design-tests.sh`, so the breadcrumb format lives in one place.

  Each gate scans only its relevant sections — Test Design, the AC-coverage list, the per-task Tests (planned) lists, and the spec's Acceptance-Criteria section — never the whole file.

Both gates are fail-closed and run before the first human review, then again on every test change (add / remove / title edit).
See the gate process in the `spec-driven-development` SKILL.md for when and how they run.

---
## Task Breakdown

**Read `~/.claude/skills/task-breakdown/SKILL.md` before authoring this section** — it owns task ordering (unblockers first, riskiest with a proof of concept next), thin contract-task extraction for parallel work, and sub-step splitting.

Number the tasks in that priority order — the numbering is the intended execution order, not the order the feature narrates itself.

**Task-dependency DAG diagram** — lead the section with a mermaid flowchart when any task's `Depends on:` names a real task (not empty/`none`): one node per task, edges following each `Depends on:` link.
Validate with `mmdc` before pasting, per the `mermaid-diagrams` skill.

N/A escape: when every task is independent, or there's only one task, write `N/A — no task dependencies` in place of the diagram and skip it.

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

Subset of the global Test Design section that this task owns. After the task's
subagent commits, the /implement post-commit planned-test check parses these titles
via `spec-driven-development/scripts/extract-planned-tests-for-task.sh` and the
orchestrator — fresh-context relative to the subagent's work — verifies each one
exists in the committed diff before the task is marked done.

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

`/implement` hands this list to the task's subagent as its grounding starting-set, so it doesn't re-discover the file map from scratch.

Keep it accurate; the subagent may still touch more when execution requires it.

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

- **Sequence PRs by the `task-breakdown` skill's priorities** — the earliest PRs carry the contract/unblocker tasks and the riskiest proof of concept; feature slices stack behind them on the de-risked base.

- **Don't over-split** — a PR under ~50 lines usually lacks the context to review. The failure mode to catch is the one giant PR, not many tiny ones.

**PR-level status marker** — `[<status>]` prefixes the PR-N label, mirroring the Task Breakdown's `### N. [<status>] Title` convention one level up: `[Doing]`, `[Done]`, `[Blocked]`, `[Deferred]`, `[Dropped]`.
Absent for the pending/not-started state — a PR that hasn't started yet carries no bracket at all.
Written inline by the orchestrating agent at PR batch-end, never scripted — same precedent as the task-level marker.

**PR branch record** — a trailing `Branch:` clause on the same line, naming the branch that PR's commits live on, with the name wrapped in backticks:

```
1. **[Done] PR-1** — Extract the parser. Tasks: 1, 2. Depends on: none. Branch: `feat/parser/pr1`.
```

Written inline by the orchestrating agent when that PR's batch pushes, never by the plan author.
Absent until that push happens — the absence is how tooling tells a PR that already ran from one that never did.
The backticks are load-bearing: `parse-pr-breakdown.sh` reads the name between them, so a branch holding periods (`release/1.2`) survives a clause grammar that otherwise stops at the next period.

**PR-dependency DAG diagram** — lead the numbered list below with a mermaid flowchart when any PR's `Depends on:` names a real PR (not `none`).
One node per PR, edges following each `Depends on:` link — one abstraction level up from the Task Breakdown's own diagram.
Validate with `mmdc` before pasting, per the `mermaid-diagrams` skill.

N/A escape: for a "Single PR." plan, or a multi-PR plan where every PR is independent, write `N/A — no PR dependencies` in place of the diagram and skip it.

Partition the tasks above — one line per PR:

1. **[<status>] PR-1** — <title>. Tasks: <N, N>. Depends on: <none | PR-N, PR-M, ...>.

2. **[<status>] PR-2** — <title>. Tasks: <N, N>. Depends on: <none | PR-N, PR-M, ...>.

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
