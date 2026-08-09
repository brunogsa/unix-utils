# Wave 5 — Emit (local mode)

Read this only when Wave 1 resolved the run to **local mode**. The github-mode procedure lives in [`wave5-emit-github.md`](wave5-emit-github.md) and shares nothing with this one.

Write `${out_file}` (`${out_base}.md`) to the current CWD.

- `${out_base}` is set in Wave 1 to `./verdict_auto-review_YYYY-MM-DD_HH:MM`; the timestamp preserves ordering when the user runs several reviews in one CWD.

- The output follows the template at `references/local-review-template.md` — read it and expand its placeholders.

- Keep the template file as the single source of truth for the output shape; do not inline the template here.

**doc-standards check (after writing).** Run both `check-density.sh` and `check-bullet-gap.py` from `~/.claude/skills/doc-standards/scripts/` on `$out_file`, then fix any flagged lines yourself:

- Don't spawn a subagent — this pipeline keeps its fan-out flat so the run's token budget stays predictable, and local mode always runs isolated (SKILL.md's dispatch rule).

- Rewrite each over-cap line in place per `doc-standards/references/density-rules.md`, insert a blank line after each bullet `check-bullet-gap.py` flags, and re-run both until each exits 0.
