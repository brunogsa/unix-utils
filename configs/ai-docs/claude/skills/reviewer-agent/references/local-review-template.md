# Local Review Output Template

Used by Wave 5 (local mode) to write `${out_file}` (timestamped, e.g. `./auto-review_2026-04-26_14-32.md`) to the user's CWD. Timestamp preserves ordering across runs.

Placeholders resolved by the orchestrator:
- `<branch>`, `<base-branch>`: current and base branch names
- `<Review Guide from Wave 2's guide writer>`: the guide-writer's full markdown body, verbatim
- Findings are numbered sequentially, ordered by severity
- Action items are grouped by file, then severity

---

```markdown
# Auto Review: <branch> vs <base-branch>

<Review Guide from Wave 2's guide writer goes here verbatim>

## Findings

<for each finding, numbered sequentially by severity order>
**#N [SEVERITY]** `path:start_line-line`
<body>
```

No signature footer needed — the file belongs to the user.
