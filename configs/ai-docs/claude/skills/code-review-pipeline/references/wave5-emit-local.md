# Wave 5 — Emit (local mode)

Read this only when Wave 1 resolved the run to **local mode**. The github-mode procedure lives in [`wave5-emit-github.md`](wave5-emit-github.md) and shares nothing with this one.

Consult the `html-artifacts` skill's decision tree, then write `${out_file}` — `${out_base}.md` or `${out_base}.html` per its verdict — to the current CWD.

- The routing table's fixed verdict for this artifact type counts as standing approval — skip html-artifacts' propose-first gate here.
  - Why: the pipeline may run unattended (isolated subagent, `/implement`'s batch-end tail), where no per-instance OK is possible; pausing to propose would stall the async run.

- `${out_base}` is set in Wave 1 to `./verdict_auto-review_YYYY-MM-DD_HH:MM`; the timestamp preserves ordering when the user runs several reviews in one CWD. Only the extension is the router's call.

- Either format follows the template at `references/local-review-template.md` — read it and expand its placeholders; an `.html` output renders those same sections under html-artifacts' non-negotiables.

- Keep the template file as the single source of truth for the output shape; do not inline the template here.

**Density check (after writing, `.md` output only).** Run `~/.claude/skills/doc-standards/scripts/check-density.sh "$out_file"`, then fix flagged lines by how this Wave 5 runs:

- **Calling session (you were NOT spawned as a subagent):** delegate to `agent(subAgent=markdown-standards-fixer, title=Fix review-output markdown)`, passing it `$out_file`; wait for it to report exit 0.
  - It splits over-cap lines and re-runs the script itself, without rewording or dropping content.
  - Unreachable in practice here — local mode always dispatches isolated (SKILL.md's dispatch rule), so only the isolated branch below ever runs.

- **Isolated (`Mode: local`, or `--isolate` passed):** do NOT spawn — this pipeline keeps its fan-out flat so the run's token budget stays predictable.
  - Rewrite each violation in place per `doc-standards/references/density-rules.md` and re-run until exit 0.
