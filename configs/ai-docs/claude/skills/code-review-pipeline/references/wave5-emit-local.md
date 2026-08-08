# Wave 5 — Emit (local mode)

Read this only when Wave 1 resolved the run to **local mode**. The github-mode procedure lives in [`wave5-emit-github.md`](wave5-emit-github.md) and shares nothing with this one.

Write `${out_file}` (`${out_base}.md`) to the current CWD.

- `${out_base}` is set in Wave 1 to `./verdict_auto-review_YYYY-MM-DD_HH:MM`; the timestamp preserves ordering when the user runs several reviews in one CWD.

- The output follows the template at `references/local-review-template.md` — read it and expand its placeholders.

- Keep the template file as the single source of truth for the output shape; do not inline the template here.

**doc-standards check (after writing).** Run both `check-density.sh` and `check-bullet-gap.py` from `~/.claude/skills/doc-standards/scripts/` on `$out_file`, then fix flagged lines by how this Wave 5 runs:

- **Calling session (you were NOT spawned as a subagent):** delegate to `agent(subAgent=markdown-standards-fixer, title=Fix review-output markdown)`, passing it `$out_file`; wait for it to report exit 0.
  - It splits over-cap lines, gaps bullets missing their blank line, and re-runs both scripts itself, without rewording or dropping content.
  - Unreachable in practice here — local mode always dispatches isolated (SKILL.md's dispatch rule), so only the isolated branch below ever runs.

- **Isolated (`Mode: local`, or `--isolate` passed):** do NOT spawn — this pipeline keeps its fan-out flat so the run's token budget stays predictable.
  - Rewrite each over-cap line in place per `doc-standards/references/density-rules.md`, insert a blank line after each bullet `check-bullet-gap.py` flags, and re-run both until each exits 0.
