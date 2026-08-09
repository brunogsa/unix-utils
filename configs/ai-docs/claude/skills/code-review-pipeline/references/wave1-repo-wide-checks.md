# Wave 1 — Repo-wide static checks + tests + coverage (local mode)

Detail for the Wave 1 context-prep step that gathers repo-wide signal for Wave 2 specialists. Referenced from `SKILL.md` Wave 1.

## What runs

After the diff files are on disk, gather repo-wide signal that specialists in Wave 2 consume alongside the diff.

CWD is the branch under review, so the project's own commands run directly.

Discover commands from the repo: `package.json` scripts, `Makefile`, `justfile`, repo CLAUDE.md.

- Prefer "agentic" / "ci" variants when present — they exit non-zero cleanly.
- If a check does not exist, write `not-available: <reason>` to its output file so Wave 2 can tell "ran clean" from "did not run".
- Never skip silently.

Apply CLAUDE.md `"Save slow command output, verify from the file"`: each command writes to `$work_dir/`, then `echo "exit: $?"`, then `tail -<N>` to keep the parent-session context lean.

Run independent commands in parallel.

## Outputs

| Output file | Source |
|---|---|
| `static-lint.txt` | Project's full lint task (workspace-wide, not scoped) |
| `static-typecheck.txt` | Strictest typecheck/build — `tsc --noEmit`, `next build`, `cargo check`, `mypy`, equivalent |
| `static-dead-code.txt` | `knip`, `ts-prune`, equivalent (unused exports) |
| `static-circular.txt` | `madge --circular`, equivalent (dependency cycles) |
| `tests-unit.txt` | Full unit suite |
| `tests-integration.txt` | Every integration tier (router/API, service, contract, ...) |
| `tests-e2e.txt` | Browser / e2e tests **if** the diff touches UI, hooks, or anything rendered |
| `coverage.txt` | Branch + line coverage on the changed files if the runner emits it |
| `discovered-commands.txt` | One line per check: `<name>: <command-used>` or `<name>: not-available` |

## Mode scope

This collection is **local mode only** today.

github mode's clone is `--depth=50 --filter=blob:none` with no dependency install, so the project's own lint, typecheck, and test commands can't run there.

Extending would need an install step — out of scope; revisit if github reviews need the same signal.
