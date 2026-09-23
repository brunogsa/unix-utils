# Plan test design and appendix sections

Read alongside `plan-writing.md` when writing the Test Design, Task Breakdown, PR Breakdown, or Decision logs sections.

## Test Design

Test titles designed before implementation — bodies come during each RED-GREEN cycle. Review before coding starts.

**Integration tests (outer layer)** — the stable user-facing contract. Design all titles upfront, grouped by scenario class so a thin class is a visible gap:

- **Happy cases** — the expected success paths.
- **Corner cases** — boundary/edge inputs handled deliberately (off-by-one, empty, single-vs-many, precision residue, optional field present/absent).
- **Failure scenarios** — every way it fails: guard rejections, downstream errors, partial success, retry-vs-DLQ classification.

Annotate every `it()` with a trailing `// AC-<n>… T<n>… [on-demand]` comment: the ACs it proves, the tasks that write it, and `[on-demand]` when pulled mid-cycle. This section is the single source — the annotation replaces both the AC-coverage list and the per-task `Tests (planned)` field, so no test title is ever written twice.

Group each `describe()` block by scenario class, one comment per class:

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

## Task Breakdown section

Load `task-breakdown` before authoring: it orders tasks (unblockers first, riskiest PoC next), extracts thin contract tasks, splits sub-steps, emits a `/tmp` artifact.

Populate from it: order becomes the numbering (execution order), links become each `Depends on:`, sub-steps become the title breadcrumb and commit sketch.

Lead with a task-dependency DAG (mermaid, `mmdc`-validated) when a task names a real dependency; else `N/A — no task dependencies`.

Each task produces at least one base commit (tests, code, IaC/docs together; RED/GREEN lives inside it). At execution, a refactor/scout/drift/`/auto-review` follow-up becomes its own extra commit; a substantial addition becomes a new peer task. Refactors stay isolated tasks.

Sub-step breadcrumb: optional, semicolon-separated parenthetical after the title — `### N. Title (sub-step; sub-step)`; keep ~4 items, else split the task.

**Brief Description**: a short paragraph of at most 4 sentences, or a bullet list of one sentence per bullet — never a longer prose block.

Commit sketch line: `` `<repo>` — `type(scope): subject` `` — repo path, Conventional Commits subject. Add a second line only when the task naturally produces two commits (e.g. "introduce helper" + "replace callers"), else omit.

## Task Details section

Lives in the Appendix, one `<details>` entry per task, in the exact shape the template shows. Never a `### N.` heading inside Task Details — the task's identity lives in the body's Task Breakdown entry; Task Details is keyed by its `Task N —` summary line only.

Field placement:

- **Testable Acceptance criteria** (what "done" looks like for this task) and **Verification** (the command or test that proves it works) live only in Task Details, never in the body entry.

- **Files (logical order)** lives only in Task Details — it grounds the subagent's starting set, skipping re-discovery; keep it accurate, though the subagent may touch more.

- Title, **Depends on**, **Brief Description**, and **Commits (sketch, minimum)** live only in the body's Task Breakdown entry.

Adding a task writes both entries — a task with only one is incomplete.

**Tests (planned)**: dropped everywhere except one opt-out — when a task's tests are fully covered elsewhere, state `**Tests (planned)**: N/A — <reason>` inside that task's body entry. The one surviving use of the field.

A plan-only run (no spec) carries each task's acceptance criteria inline in Task Details, since there's no spec AC to point back to.

`Commits (sketch, minimum)` is a floor — drift fixes, scout findings, refactor sub-steps, `/auto-review` follow-ups become extra commits, each tagged `[Drift]`/`[Scout]`/`[Refactor]`.

## PR Breakdown section

Split past one-plan-one-PR when the work is too large to review well in one sitting. Felt size (guide, not gate): defect-detection drops sharply past ~400 diff lines, falls off above ~600 (SmartBear/Cisco, Google). No code exists yet — estimate by feel, never a line number.

Splitting rules:
- Vertical, never horizontal — each PR ships its own tests+code+docs+infra; never "PR-1 = tests, PR-2 = code."
- Prefer independent PRs; a dependent sequence is fine.
- Each PR independently reviewable/mergeable, in order if dependent.
- Sequence by `task-breakdown`'s priorities — unblockers and riskiest PoC first.
- Don't over-split (~50-line floor) — catch one giant PR, not many tiny ones.

One `### PR-N.` heading per PR, one level above Task Breakdown's `### N.`.

Only the orchestrating agent writes two inline fields, absent until then:
- `[<status>]` (`[Doing]`/`[Done]`/`[Blocked]`/`[Deferred]`/`[Dropped]`) after `PR-N.`, at batch-end.
- Backtick-wrapped `**Branch**:`, once that PR's batch pushes — `parse-pr-breakdown.sh` reads the branch name between backticks.

Each field is its own line; parsers read the first found per PR. Free prose after is for the reviewer.

`**Tasks**:` the task numbers shipped (`1, 2`). `**Depends on**:` `none` or the PR numbers (`PR-1, PR-2`). `**Branch**:` the backtick-wrapped branch name once created.

Lead the PR headings with a PR-dependency DAG (mermaid, `mmdc`-validated) when any PR names a real dependency; else `N/A — no PR dependencies`.

## Decision logs

Both the Functional Decisions (spec) and Technical Decisions (plan) logs live in the Appendix, chronological, editable until the user approves and signals execution start.

At that point, insert the divider line already present in the template and switch to append-only: entries above stay frozen, revisions become new entries appended below with `**Supersedes:**` references rather than in-place edits.

Each decision is its own collapsed `<details>`, with the summary carrying a one-line gist of the choice.

`__Chose__`: approach taken. `__because__`: the reason. `__Discarded__`: the alternative plus why it lost. `__Supersedes__`: first ~60 chars of the prior entry replaced.
