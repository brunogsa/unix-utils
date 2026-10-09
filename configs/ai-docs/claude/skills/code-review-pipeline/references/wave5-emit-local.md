# Wave 5 - Emit (local mode)

Read this only when Wave 1 resolved the run to **local mode**. The github-mode procedure lives in [`wave5-emit-github.md`](wave5-emit-github.md) and shares nothing with this one.

Write `${out_file}` (`${out_base}.md`) to the current CWD.

- `${out_base}` is set in Wave 1 to `./verdict_auto-review_<branch>_YYYY-MM-DD_HH:MM`.
  - The branch segment keeps runs from different branches distinguishable, and the timestamp preserves ordering within a branch when the user runs several reviews in one CWD.

- The output follows the template at `references/local-review-template.md` - read it and expand its placeholders.

- Keep the template file as the single source of truth for the output shape; do not inline the template here.

- Each finding's body is the Wave-4 JSON `body` copied verbatim - never re-composed or annotated at emit.
  - Provenance, counts, drop logs, and deviations belong in the Wave 6 terminal summary ([`wave6-summary-template.md`](wave6-summary-template.md)), not in the verdict file.

- After writing `${out_file}`, run `python3 ~/.claude/skills/code-review-pipeline/scripts/check-finding-bodies.py "${out_file}"`.
  - On exit 1, rewrite only the flagged bodies to fit (cut prose, never drop Suggestion or Trade-off) and re-run, at most twice.
  - Report any violations still remaining in Wave 6 rather than looping.
