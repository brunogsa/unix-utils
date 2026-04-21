# Plan: [Title]

Spec: [link or reference to spec.md]

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

### 0. Symlink plan to project directory
**What**: Create a symlink from this plan file to `./plan.md` in the current working directory. If spec.md exists in cwd, it was already used as input.
**Verify**: `readlink ./plan.md` points to this plan file.

### 1. [Task title]
**Description**: What needs to be done.
**Files**: `path/to/file1.ts`, `path/to/file2.ts`
**Acceptance criteria**: What "done" looks like for this task.
**Verify**: Command or test that proves it works.

### 2. [Task title]
...

## Decisions
- [DECISION: ... because ...]
