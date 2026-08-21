---
# performance-check budget override — DELETE this whole frontmatter block when you copy
# this template into a real plan file. It is tooling metadata, not plan content.
# Both consumers read this file and populate every section in one run, so splitting it would
# only make the author read two files instead of one. Raised from the 1024w bundled default.
words-budget: 4096
---
# Plan: [Title]

> Authoring rules (diagram conventions, Task/PR Breakdown population, threat vocabulary,
> PR splitting, etc.) live in `references/plan-writing.md` — read it once before filling
> this in. This file is a copyable skeleton only.

Spec: [link or reference to the paired spec file — `N/A — plan-only run` when no spec was written]

---
## Technical Approach & High Level Architecture

N/A escape: for a trivial or no-flow change, write "N/A — `<reason>`" and skip the diagram.

---
## Threat Model

N/A escape: no trust boundary crossed → `N/A — <reason>`.

Mark boundaries on the Technical Approach diagram as dashed subgraphs — never a second diagram:

```
subgraph trust_public["trust: public internet"]
subgraph trust_db["trust: service account"]
```

Tick every boundary this change touches, or N/A:

- [ ] untrusted input enters
- [ ] privilege changes
- [ ] data leaves the system
- [ ] a secret is read or written
- [ ] dynamic execution / deserialization

One line per ticked box:

- `<asset>` ← `<threat>` ⇒ `<mitigation>` → AC-N

Unmitigated threat → Open Question, never a bullet.

---
## General Flow

N/A escape: for a trivial or no-flow change, write "N/A — `<reason>`" and skip the diagram.

---
## Test Design

Test titles designed before implementation — bodies come during each RED-GREEN cycle. Review before coding starts.

**Integration tests (outer layer)** — the stable user-facing contract. Design all titles upfront, grouped by scenario class so a thin class is a visible gap:

- **Happy cases** — the expected success paths.
- **Corner cases** — boundary/edge inputs handled deliberately (off-by-one, empty, single-vs-many, precision residue, optional field present/absent).
- **Failure scenarios** — every way it fails: guard rejections, downstream errors, partial success, retry-vs-DLQ classification.

Annotate every `it()` with a trailing `// AC-<n>… T<n>… [on-demand]` comment: the ACs it proves, the tasks that write it, and `[on-demand]` when the test is pulled mid-cycle rather than upfront.

This section is the single source — the annotation replaces both the AC-coverage list and the per-task `Tests (planned)` field, so no test title is ever written twice.

```
// <file>
describe("[ComponentOrUseCase]", () => {
  // Happy cases
  it("should [behavior] when [nominal condition]");    // AC-1 T3
  // Corner cases
  it("should [behavior] when [boundary condition]");   // AC-1 AC-2 T3
  // Failure scenarios
  it("should [fail/throw] when [failure condition]");  // AC-4 T5 [on-demand]
});
```

**Unit tests for pre-known pure helpers** — only helpers we know will exist regardless of design or implementation choices (e.g., obvious normalizers, parsers, validators). Skip this subsection if none:

```
// <file>
describe("[obviousPureHelper]", () => {
  it("should [behavior] when [input]");                // AC-3 T2
});
```

Tests for helpers pulled on demand during RED-GREEN are designed at the moment the caller first needs them (test-first at the point of pull) — designing them eagerly would force premature signatures.

If this change is a pure refactor, config edit, or similar no-behavior-change work, mark this section "N/A" with a short reason.

---
## Task Breakdown

N/A escape: when every task is independent, or there's only one task, write `N/A — no task dependencies` in place of the diagram and skip it.

### 1. [Task title] (optional: sub-step; sub-step; sub-step)

**Depends on**:
- Task X
- ...

**Brief Description**: What needs to be done. Either a short paragraph of at most 4 sentences, or a bullet list of one sentence per bullet — never a longer prose block.

**Testable Acceptance criteria**:
- What "done" looks like for this task.

**Verification**:
- Command or test that proves it works.

**Files (logical order)**:
- `path/to/file1.ts`
- `path/to/file2.ts`

**Commits (sketch, minimum)**:
  1. `~/repo` — `type(scope): subject`
  2. `~/repo` — `type(scope): subject` *(only when the task naturally produces two — e.g., "introduce helper" + "replace callers" — otherwise delete this line)*

### 2. [Task title]

...

---
## PR Breakdown

Default: **one plan = one PR.** Most plans stop here — write "Single PR." and move on.

N/A escape: for a "Single PR." plan, or a multi-PR plan where every PR is independent, write `N/A — no PR dependencies` in place of the diagram and skip it.

Partition the tasks above — one heading per PR:

### PR-1. [<status>] <title>

**Tasks**: <N, N>

**Depends on**: <none | PR-N, PR-M, ...>

**Branch**: `<branch-name>`

### PR-2. [<status>] <title>

**Tasks**: <N, N>

**Depends on**: <none | PR-N, PR-M, ...>

**Branch**: `<branch-name>`

---
## Open Questions

- **QUESTION:** ... ?

---
## Technical Decisions

Chronological log. Editable while planning.

Once the user approves the plan and signals execution start, insert the divider line below and switch to append-only.

Revisions become new entries with `**Supersedes:**` references rather than in-place edits.

Each decision is its own collapsed `<details>`, with the summary carrying a one-line gist.

<details>
<summary><strong>DECISION:</strong> &lt;one-line gist of the choice&gt;</summary>

- **DECISION:** __Chose__ `<approach>`, __because__ `<reason>`
  - __Discarded__ **`<alternative>`**: `<reason>`

</details>

<!-- ── execution begins below; entries above are frozen, append-only below ── -->

<details>
<summary><strong>DECISION (Task N):</strong> &lt;one-line gist of the choice&gt;</summary>

- **DECISION (Task N):** __Chose__ `<approach>`, __because__ `<reason>`
  - __Supersedes__ "`<first ~60 chars of prior decision>`" __because__ `<reason>`

</details>
