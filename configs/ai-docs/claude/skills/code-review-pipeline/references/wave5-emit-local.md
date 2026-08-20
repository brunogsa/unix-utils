# Wave 5 — Emit (local mode)

Read this only when Wave 1 resolved the run to **local mode**. The github-mode procedure lives in [`wave5-emit-github.md`](wave5-emit-github.md) and shares nothing with this one.

Write `${out_file}` (`${out_base}.md`) to the current CWD.

- `${out_base}` is set in Wave 1 to `./verdict_auto-review_<branch>_YYYY-MM-DD_HH:MM`; the branch segment keeps runs from different branches distinguishable, and the timestamp preserves ordering within a branch when the user runs several reviews in one CWD.

- The output follows the template at `references/local-review-template.md` — read it and expand its placeholders.

- Keep the template file as the single source of truth for the output shape; do not inline the template here.
