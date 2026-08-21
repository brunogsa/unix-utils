# Direct-coder lane — §4.0's non-TDD dispatch

Loaded whenever §4.0's extractor call returns empty stdout for a task: no test to write, so `direct-coder` replaces `tdd-coder` as this task's subagent.

## Context contract

**Push** — embed a `Change`/`Files`/`Verification`/`Optional` block verbatim, using `direct-coder.md`'s Inputs field names; the subagent pulls nothing from CWD.

- **Change**: the task's heading, description, and acceptance criteria, in the plan's own words — enough detail to apply with no test to write against.
- **Files**: the task's **Files (logical order)** list, same starting-set rule as §4.1.
- **Verification**: same rule as §4.1 — task-scoped commands only, when the plan names any; omit when it names none.
- **Optional**: the same `references:` / `base:` / `<run-label>` fields as §4.1.

Everything else is baked into `direct-coder.md`. Don't re-push any of it.

## Report back

`~/.claude/agents/direct-coder.md` authors the report's full shape — `Status`, `Commits`, `Changes`, `Verification`, `Needs-TDD`, `Deviations`, `Scouts`, `Blocked on`.

A report carrying **Needs-TDD** re-dispatches that named part through §4.1's tdd-coder lane, same task, same `<run-label>`. `direct-coder.md`'s Boundaries carve non-code artifacts out of the bounce entirely, so a
`Needs-TDD` here always names a genuine, code-only falsifiable input the extractor's empty stdout missed — not a doc, spec, or plan edit.
