# Wave 5 — Emit (local mode)

Read this only when Wave 1 resolved the run to **local mode**. The github-mode procedure lives in [`wave5-emit-github.md`](wave5-emit-github.md) and shares nothing with this one.

Write `${out_file}` (`${out_base}.md`) to the current CWD.

- `${out_base}` is set in Wave 1 to `./verdict_auto-review_YYYY-MM-DD_HH:MM`; the timestamp preserves ordering when the user runs several reviews in one CWD.

- The output follows the template at `references/local-review-template.md` — read it and expand its placeholders.

- Keep the template file as the single source of truth for the output shape; do not inline the template here.

**doc-standards check (after writing).** Run both `check-density.sh` and `check-bullet-gap.py` from `~/.claude/skills/doc-standards/scripts/` on `$out_file`, then report what they flag:

- Report what they flag; never repair it, and never dispatch `markdown-standards-fixer`.
  - Reflowing prose is a judgment call that has already split sentences mid-phrase across bullet boundaries and damaged a document.

- Local mode always runs isolated (SKILL.md's dispatch rule), so this step can neither ask the user nor file the `[Scout]` those flags earn.
  - A subagent's TaskList write never reaches the user who triages it.

- Carry every flagged line into your Wave 6 summary's doc-standards-flags block instead, naming `$out_file` and what is off standard. The calling session files the `[Scout]` from there.

- Either way, `${out_file}` ships exactly as written. An over-cap verdict file still stands, because the user alone decides if and when that Scout runs.
