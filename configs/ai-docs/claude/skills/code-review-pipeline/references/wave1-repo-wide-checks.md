# Wave 1 - Repo-wide static checks + tests + coverage (local mode)

Detail for the Wave 1 context-prep step that gathers repo-wide signal for Wave 2. Referenced from `SKILL.md` Wave 1.

## What runs

After the diff files are on disk, gather repo-wide signal that Wave 2 consumes alongside the diff.

CWD is the branch under review, so the project's own commands run directly.

Discover commands from the repo: `package.json` scripts, `Makefile`, `justfile`, repo CLAUDE.md.

- Prefer "agentic" / "ci" variants when present - they exit non-zero cleanly.
- If a check does not exist, write `not-available: <reason>` to its output file so Wave 2 can tell "ran clean" from "did not run".
- Never skip silently.

Apply CLAUDE.md `"Save slow command output, verify from the file"`: each command writes to `$work_dir/`, then `echo "exit: $?"`, then `tail -<N>` to keep the parent-session context lean.

Run independent commands in parallel.

## Outputs

| Output file | Source |
|---|---|
| `static-lint.txt` | Project's full lint task (workspace-wide, not scoped) |
| `static-typecheck.txt` | Strictest typecheck/build - `tsc --noEmit`, `next build`, `cargo check`, `mypy`, equivalent |
| `static-dead-code.txt` | `knip`, `ts-prune`, equivalent (unused exports) |
| `static-circular.txt` | `madge --circular`, equivalent (dependency cycles) |
| `tests-unit.txt` | Full unit suite |
| `tests-integration.txt` | Every integration tier (router/API, service, contract, ...) |
| `tests-e2e.txt` | Browser / e2e tests **if** the diff touches UI, hooks, or anything rendered |
| `coverage.txt` | Branch + line coverage on the changed files if the runner emits it |
| `quality-metrics.json` | `measure-quality-metrics.py --diff` on the diff only (see "Measured quality metrics") |
| `discovered-commands.txt` | One line per check: `<name>: <command-used>` or `<name>: not-available` |

## Measured quality metrics

Run `base_rev=$(cat "$work_dir/base-rev.txt") && ~/.claude/scripts/measure-quality-metrics.py --diff "$base_rev...HEAD" --session-id <session id> > $work_dir/quality-metrics.json`, once, from the repo root (`prep-local-context.sh` writes that file).

- `<session id>` is the header's `Session id`; omit the flag when the header has none.
  - [Why] Only the main session's id keys the per-session tool map, so without it every metric uses global tools.

- `--diff` measures only the code the diff changes, adds or removes, so an untouched over-limit function never appears.

- A function the diff removes is listed under `resolved` with its last score; no limit applies to removed code, so it is never a violation.

- Exit 0 is clean and exit 1 is a violation with valid JSON. On exit 2 or any other failure, write `not-available: <reason>` to `quality-metrics.json`, per "What runs".

Wave 2's `code-design-clarity` lens reads this file and cites its values.

Wave 6 lists each `resolved` entry on its own line, `resolved: <function> (<path>), last <metric> <value>`, never as a finding or a violation.

### Tool map

The first check that needs the per-session tool map builds it, and the `code-reviewer` orchestrator running this wave does that itself, since every wave runs inside it and it can dispatch agents.

Follow section 1 of [`metrics-leg.md`](../../quality-gate/references/metrics-leg.md): dispatch the read-only inspector only when `/tmp/quality-metrics_<session id>.json` has no entry for this repo and base ref.

Raise tooling problems as that file's section 2 and [`coder-metrics-check.md`](../../implement/references/coder-metrics-check.md) describe.

## Mode scope

This collection is **local mode only** today.

github mode's clone is `--depth=50 --filter=blob:none` with no dependency install, so the project's own lint, typecheck, and test commands can't run there.

Extending would need an install step - out of scope; revisit if github reviews need the same signal.
