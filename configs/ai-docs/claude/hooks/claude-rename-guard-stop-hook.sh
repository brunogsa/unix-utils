#!/usr/bin/env bash
# claude-rename-guard-stop-hook - Block a session Stop when
#                            check-rename-references.py finds a dangling
#                            script reference.
#
# Usage (Claude Code Stop hook):
#   stdin:  hook event JSON ({ session_id, stop_hook_active, ... })
#   stdout: optional JSON ({ decision: "block", reason: "..." }) to keep Claude going
#   args:   forwarded verbatim to check-rename-references.py, so a test can
#           pin --repo/--settings to an isolated fixture instead of this
#           machine's real corpus.
#
# One checker, one gate:
#   check-rename-references.py resolves every full script path referenced
#   from settings.json, every covered install.sh, and every markdown file
#   in both covered repos, and prints a FAIL/WARN line per dangling
#   reference. This wrapper is the "later task" that checker's own header
#   docstring names -- it turns the checker's plain exit code into this
#   event's {decision:"block"} JSON contract and wires it in.
#
# Not a session-scoped diff filter, unlike the markdown/agent-contract/
# comment-format gates it sits beside in the orchestrator: the checker
# scans a fixed corpus (settings.json + install.sh + markdown across both
# covered repos), not "what this session touched", so there is no
# transcript filter to apply the same way. A dangling reference anywhere
# blocks every session's stop, including one that never touched the
# offending file -- that width is what the plan's own "a gate every
# session finishes through" asks for. The severity split the checker
# already makes (FAIL only on settings.json/install.sh, WARN on markdown)
# is what keeps that survivable: the real corpus carries ~240 markdown WARN
# findings today and none of them block.
#
# Enforcement vs. loop-safety:
#   Honors stop_hook_active=true -> bows out, so this can never spin an
#   infinite stop-block loop, matching every sibling gate. Because the
#   guard bails on the post-fix stop, this hook cannot re-verify its own
#   fix -- the block reason tells the main session to re-run the checker
#   directly.
#
# Safeguards (all silent no-ops -- never break Claude on a tooling gap):
#   - jq missing -> exit 0.
#   - The checker script missing beside this wrapper, or python3 missing -> exit 0.
#   - Checker exits 0 (clean, or WARN-only) -> silent, exit 0.
#   - Checker exits anything other than 0 or 1 (its own usage error is 2)
#     -> fail open, silent, exit 0 -- a usage error is this wrapper's bug
#     to fix, never the session's block.
#
# NO env-var opt-out by design, matching the agent-contract gate: a kill
# switch would let Claude silence its own rename guard via a Bash call.

set -eo pipefail

input=$(cat)

command -v jq >/dev/null 2>&1 || exit 0

stop_hook_active=$(printf '%s' "$input" | jq -r '.stop_hook_active // false' 2>/dev/null || true)
[ "$stop_hook_active" = "true" ] && exit 0

dir=$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd) || dir="$HOME/.claude/hooks"
CHECKER="$dir/check-rename-references.py"
[ -f "$CHECKER" ] || exit 0
command -v python3 >/dev/null 2>&1 || exit 0

set +e
output=$(python3 "$CHECKER" "$@" 2>/dev/null)
status=$?
set -e

[ "$status" -eq 0 ] && exit 0
[ "$status" -eq 1 ] || exit 0

fail_lines=$(printf '%s\n' "$output" | grep '^FAIL:' || true)
[ -n "$fail_lines" ] || exit 0

reason="check-rename-references.py found a dangling script reference -- ${fail_lines}. \
Fix the reference, then confirm with: check-rename-references.py (exit 0 = clean)."

jq -n --arg r "$reason" '{decision: "block", reason: $r}'
