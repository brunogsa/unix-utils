# Local Review Output Template

Used by Wave 5 (local mode) to write `${out_file}` (branch + timestamp, e.g. `./verdict_auto-review_feat-my-branch_2026-04-26_14-32.md`) to the user's CWD. The branch segment distinguishes runs across branches; the timestamp preserves
ordering across runs within a branch.

Placeholders resolved by the orchestrator:
- `<branch>`, `<base-branch>`: current and base branch names
- Findings are numbered sequentially, ordered by severity
- Action items are grouped by file, then severity

- `[SEVERITY]`: the finding's ordinal rank — `HIGH` / `MEDIUM` / `LOW` — or `QUESTION` for a finding that carries no rank
  - Read it off the priority tag via the "Priority tags" section of [`review-principles.md`](review-principles.md), which owns that mapping.
  - Emit the ordinal, never the priority tag: `/address-verdicts`' severity floor compares ranks, and a tag it cannot rank drops this lens out of every floored selection.

Local mode carries no Review Guide block — Wave 2's guide-writer step doesn't run for `Mode: local` (see `SKILL.md`'s Wave 2).

The guide only exists to post as a standalone PR comment in github mode.

---

```markdown
# Auto Review: <branch> vs <base-branch>

## Findings

<for each finding, numbered sequentially by severity order>
### N. [SEVERITY] `path:start_line-line`
<body>
```

No signature footer needed — the file belongs to the user.
