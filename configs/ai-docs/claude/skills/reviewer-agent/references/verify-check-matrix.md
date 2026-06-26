# Verify the full check matrix — MANDATORY

Shared post-change verification gate. Loaded by `auto-review` and `refactor` after a batch of fixes/refactors is applied — run every gate the project exposes, fix what you caused, file what you didn't.

This is distinct from `wave1-repo-wide-checks.md`: that file gathers pre-review signal into output files for specialists; this one is the post-change green-gate that callers run on their own edits.

After ALL approved changes are applied (at the end of the batch, not after each), run every gate the project exposes — in parallel where independent.

The changes look mechanical, but renames, contract changes, removed code still used elsewhere, and broken type narrowing all surface failures here — not at edit time.

Run, at minimum:

- **Lint** (project's full lint task — workspace-wide, not scoped).
- **Type-check / build** (the strictest available — prefer `tsc --noEmit` or a full build over scoped variants).
- **Dead code / unused exports** (e.g. `knip`, `ts-prune`).
- **Circular dependencies** (e.g. `madge --circular`).
- **Unit tests** (full suite — a change's blast radius is bigger than its diff).
- **Integration tests** — every tier the project has (router/API, service, contract, etc.).
- **Browser / e2e tests** if the project has them and a change touched UI, hooks, or anything rendered.

Discover the actual commands from the repo (`package.json` scripts, `Makefile`, `justfile`, repo CLAUDE.md). Prefer the project's "agentic" / "ci" variants when they exist — they exit non-zero cleanly.

If a check doesn't exist for this project, say so explicitly instead of skipping silently.

Apply CLAUDE.md `"Save slow command output, verify from the file"`: redirect each long-running command to `/tmp/`, check exit + tail in one shot. Run independent checks in parallel.

**Fix what you find.**

- Failures your change caused are part of the change — resolve before declaring done.
- Pre-existing failures your branch did NOT introduce are reported AND filed: per CLAUDE.md's hard-contract Scout rule, **every distinct pre-existing finding gets a TaskCreate in the same response** that surfaces it.
- Covers cycles, failing tests, skipped/disabled tests, dead-code findings in untouched modules, etc. Filing is non-negotiable; whether to execute later is the user's call.

A passing lint with failing tests is NOT done. Only after every gate is green (or pre-existing failures are explicitly acknowledged) may the work be declared complete.
