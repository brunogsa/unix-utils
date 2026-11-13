---
# performance-check budget override, not plan-section content.
# Both plan reference files sat one word under the 1024w bundled default, so no rule can be
# added without deleting another. Doubled from that default.
words-budget: 2048
---
# Plan test design and appendix sections

Read alongside `plan-writing.md` when writing the Test Design, Task Breakdown, PR Breakdown, or Decision logs sections.

## Test Design

Test titles designed before implementation - bodies come during each RED-GREEN cycle. Review before coding starts.

Titles follow `test-standards`' title rules - domain language, no class, constant or field names - since implementation copies them verbatim.

**Integration tests (outer layer)** - the stable user-facing contract. Design all titles upfront, grouped by scenario class so a thin class is a visible gap:

- **Happy cases** - the expected success paths.
- **Corner cases** - boundary/edge inputs handled deliberately (off-by-one, empty, single-vs-many, precision residue, optional field present/absent).
- **Failure scenarios** - every way it fails: guard rejections, downstream errors, partial success, retry-vs-DLQ classification.

Annotate every `it()` with a trailing `// AC-<n>… T<n>… [on-demand]` comment: the ACs it proves, the tasks that write it, and `[on-demand]` when pulled mid-cycle. This section is the single source - the annotation replaces the AC-coverage list, so no test title is ever written twice.

- Cover a prose AC (hook or reminder wording) with no `it()`, only a standalone Test Design line: `// AC-<n> - prose, verified by direct-coder diff review, no test`.
  - Prose goes to `direct-coder`, never TDD, since tests over prose cost more than they catch; `check-ac-coverage.sh` accepts only this exact line.

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

**Unit tests for pre-known pure helpers** - only helpers we know will exist regardless of design or implementation choices (e.g., obvious normalizers, parsers, validators). Skip this subsection if none:

```
// <file>
describe("[obviousPureHelper]", () => {
  it("should [behavior] when [input]");                // AC-3 T2
});
```

Tests for helpers pulled on demand during RED-GREEN are designed at the moment the caller first needs them (test-first at the point of pull) - designing them eagerly would force premature signatures.

## Task Breakdown section

Load `task-breakdown` before authoring: it orders tasks (unblockers first, riskiest PoC next), extracts thin contract tasks, splits sub-steps, emits a `/tmp` artifact.

Populate from it: order becomes the numbering (execution order), links become each `**Depends on**:` (`none`, a lone `- none` bullet, or one `- Task N` bullet per dependency; never `- none` mixed with `- Task N`), sub-steps become the title breadcrumb and commit sketch.

Lead with a task-dependency DAG (mermaid, `mmdc`-validated) when a task names a real dependency; else `N/A - no task dependencies`.

Each task produces at least one base commit (tests, code, IaC/docs together; RED/GREEN lives inside it). At execution, a refactor/scout/drift/`/auto-review` follow-up becomes its own extra commit; a substantial addition becomes a new peer task. Refactors stay isolated tasks.

**Clarify task**: a question only an external party (another team, a vendor) can answer becomes `### N. [Clarify] <question to settle>`. It is the one exception to "Each task produces at least one base commit".

- Its body entry holds `**Depends on**:`, a `**Brief Description**:` naming who answers, `**Tests (planned)**: N/A - clarify task, no code`, and no commit sketch.

- Its body entry lists each question with the link to where it was asked, the premise the plan proceeds on, and what a contrary answer reopens (tasks and reads named).

- Its body entry also holds the backtick-wrapped `**Linear**:` field `sdd-to-linear` writes, like a PR's.

- List it under no PR's `**Tasks**:` - `check-pr-task-projection.py` rejects that, since the task has no commit.

- Each dependent lists it as a `- Task N` bullet under `**Depends on**:`; that dependency is satisfied outside the PR graph.

- Its Task Details entry holds only the acceptance criterion "the answer is recorded in the plan's Technical Decisions log" and the Verification "the Linear issue is closed with the answer".

- The block is enforced in Linear, not locally: `implement` treats a dependency outside the current PR as satisfied and never checks it.

**Gate task**: a task with no code - a Stage proof of concept, a read-only query, a team notice, a prod check - is the other exception to "Each task produces at least one base commit".

- [Instruction] Head a gate task `### N. [Gate] <check to run>`, with `**Tests (planned)**: N/A - gate task, no code`.
  - [Why] `check-pr-task-projection.py` exempts a task from "claimed by no PR" only by its `[Gate]` or `[Clarify]` heading tag.

- [Instruction] Name a gate task under the `**Gates**:` of each PR it guards, never under a PR's `**Tasks**:`.
  - [Why] It has no commit, so `check-pr-task-projection.py` rejects it under `**Tasks**:`.

Sub-step breadcrumb: optional, semicolon-separated parenthetical after the title - `### N. Title (sub-step; sub-step)`; keep ~4 items, else split the task.

**Brief Description**: a short paragraph of at most 4 sentences, or a bullet list of one sentence per bullet - never a longer prose block.

Commit sketch line: `` `<repo>` - `type(scope): subject` `` - repo path, Conventional Commits subject. Add a second line only when the task naturally produces two commits (e.g. "introduce helper" + "replace callers"), else omit.

## Task Details section

Lives in the Appendix, one `<details>` entry per task, in the template's shape. Never a `### N.` heading inside Task Details - the task's identity lives in the body's Task Breakdown entry; Task Details is keyed by its `Task N - ` summary line only.

Field placement:

- **Testable Acceptance criteria** (what "done" looks like for this task) and **Verification** (the command or test that proves it works) live only in Task Details, never in the body entry.

- **Files (logical order)** lives only in Task Details - it grounds the subagent's starting set, skipping re-discovery; keep it accurate, though the subagent may touch more.

- Title, **Depends on**, **Brief Description**, and **Commits (sketch, minimum)** live only in the body's Task Breakdown entry.

Adding a task writes both entries - a task with only one is incomplete.

**Tests (planned)**: dropped everywhere except one opt-out - when a task's tests are fully covered elsewhere, state `**Tests (planned)**: N/A - <reason>` inside that task's body entry.

A task whose deliverable is prose or markdown (a prompt file, a markdown template, a doc) gets `**Tests (planned)**: N/A - prose deliverable, no test`, never a planned test.

- Why: the global CLAUDE.md forbids routing a document or prose edit through TDD, so a test planned over one can never be written and the AC-to-test gate would demand the impossible.

- A script the same task ships is still tested; only the prose part gets the N/A line.

A plan-only run (no spec) carries each task's acceptance criteria inline in Task Details, since there's no spec AC to point back to.

`Commits (sketch, minimum)` is a floor - drift fixes, scout findings, refactor sub-steps, `/auto-review` follow-ups become extra commits, each tagged `[Drift]`/`[Scout]`/`[Refactor]`.

## PR Breakdown section

Split past one-plan-one-PR when the work is too large to review well in one sitting. Felt size (guide, not gate): defect-detection drops sharply past ~400 diff lines, falls off above ~600 (SmartBear/Cisco, Google). No code exists yet - estimate by feel, never a line number.

Splitting rules:
- Vertical, never horizontal - each PR ships its own tests+code+docs+infra; never "PR-1 = tests, PR-2 = code."
- Sequence by `task-breakdown`'s priorities - unblockers and riskiest PoC first.
- Don't over-split (~50-line floor) - catch one giant PR, not many tiny ones.

PR slicing (set by the user on 2026-11-06; replaces the earlier "prefer independent PRs; a dependent sequence is fine" and "each PR independently reviewable/mergeable, in order if dependent" bullets). `plan-reviewer` checks each:

- [Instruction] Make each PR one deliverable the author can explain to their team in one paragraph, stated as what changes for the team or the systems, not as code.
  - [Why] In the `sf-account-hierarchy` plan, PR-2 held 5 unrelated deliverables, so no one paragraph described it; regrouping by deliverable gave 13 PRs, each the same size or smaller.

- [Instruction] Add no code that has no caller until a later PR; ship a constant, type, or schema in the PR that first uses it.
  - [Why] In the `sf-account-hierarchy` plan, PR-1 shipped constants and an OpenAPI schema with no caller until later PRs, so its review judged code with no behavior to check it against.

  - [Example] Bad: PR-1 adds a constant and an OpenAPI schema, and PR-3 first calls them. Good: PR-3 adds the constant, the schema, and the call.

- [Instruction] Make each PR deployable to prod by itself once its gate has run, and merge it into the main branch, never into a long-lived feature branch that ships at once.
  - [Why] A feature branch that ships at once turns a 7-PR chain into one all-or-nothing release, so a blocked PR holds every PR stacked on it.

- [Instruction] Make a PR depend only on PRs whose code it calls; never chain PRs in sequence for ordering alone.
  - [Why] In the `sf-account-hierarchy` plan, a PDP answer gating PR-2 blocked every PR stacked after it; regrouping cut the longest dependency chain from 8 to 4.

- [Instruction] Treat a task with no code as a gate on the PR whose behavior it guards, never as a member of a PR.
  - [Why] In the `sf-account-hierarchy` plan, prod gates sat on the last PR although they guarded the first ones, so the first PRs reached prod unguarded.

  - [Example] No-code tasks: a Stage proof of concept, a read-only query, a question to another team, a team notice, a prod check.

- [Instruction] Run each gate before the PR it guards merges or deploys.
  - [Why] A gate that runs after the merge can no longer stop the behavior it was meant to check.

One `### PR-N.` heading per PR, one level above Task Breakdown's `### N.`.

Only the orchestrating agent writes two inline fields, absent until then:
- `[<status>]` (`[Doing]`/`[Done]`/`[Blocked]`/`[Deferred]`/`[Dropped]`) after `PR-N.`, at batch-end.
- Backtick-wrapped `**Branch**:`, once that PR's batch pushes - `parse-pr-breakdown.sh` reads the branch name between backticks.

Only `sdd-to-linear` writes `**Linear**:`, at export time, its issue URL wrapped in backticks like `**Branch**:`. The awk parser's `field()` ends a value at the first period, so a bare `https://linear.app/...` truncates at `https://linear`.

Each field is its own line; parsers read the first found per PR. Free prose after is for the reviewer.

`**Tasks**:` the task numbers shipped (`1, 2`). `**Depends on**:` `none` or the PR numbers (`PR-1, PR-2`).

`**Gates**:` the no-code `[Gate]` task numbers and the pre-merge or pre-deploy checks this PR waits on (`3`), else `none`.

Lead the PR headings with a PR-dependency DAG (mermaid, `mmdc`-validated) when any PR names a real dependency; else `N/A - no PR dependencies`.

## Decision logs

Both the Functional Decisions (spec) and Technical Decisions (plan) logs live in the Appendix, chronological, editable until the user approves and signals execution start.

At that point, insert the divider line already present in the template and switch to append-only: entries above stay frozen, revisions become new entries appended below with `**Supersedes:**` references rather than in-place edits.

Each decision is its own collapsed `<details>`, with the summary carrying a one-line gist of the choice.

`__Chose__`: approach taken. `__because__`: the reason. `__Discarded__`: the alternative plus why it lost. `__Supersedes__`: first ~60 chars of the prior entry replaced.
