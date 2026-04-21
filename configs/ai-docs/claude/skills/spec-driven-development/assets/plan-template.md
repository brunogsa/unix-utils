# Plan: [Title]

Spec: [link or reference to spec.md]

## Approach
High-level technical approach. Architecture decisions. Trade-offs considered.

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
