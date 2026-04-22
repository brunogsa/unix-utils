# Local Review Output Template

Used by Wave 6 (local mode) to write `./auto-review.md` to the user's CWD.

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
