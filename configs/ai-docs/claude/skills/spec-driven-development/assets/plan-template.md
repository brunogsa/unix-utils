# Plan: [Title]

> Authoring rules live in `references/plan-writing.md` — read it once before filling this in. This file is a copyable skeleton only.

Spec: [link or reference to the paired spec file — `N/A — plan-only run` when no spec was written]

---
## Technical Approach & High Level Architecture

---
## Threat Model

- [ ] untrusted input enters (user input, webhooks, files, LLM output)
- [ ] permissions change (who can see/do what)
- [ ] personal data (PII/LGPD) is stored, logged, or shared
- [ ] a secret/credential is read, written, or could be logged
- [ ] code, shell, or SQL is built from input (injection)

---
## General Flow

---
## Test Design

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

```
// <file>
describe("[obviousPureHelper]", () => {
  it("should [behavior] when [input]");                // AC-3 T2
});
```

---
## Task Breakdown

### 1. [Task title] (optional: sub-step; sub-step; sub-step)

**Depends on**:
- Task X

**Brief Description**:

**Commits (sketch, minimum)**:
  1. `~/repo` — `type(scope): subject`

### 2. [Task title]

...

---
## PR Breakdown

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
# Appendix

## Task Details

<details>
<summary>Task N — </summary>

**Testable Acceptance criteria**:

**Verification**:

**Files (logical order)**:

</details>

## Technical Decisions

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
