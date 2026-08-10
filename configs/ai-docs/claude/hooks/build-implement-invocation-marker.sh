#!/usr/bin/env bash
# build-implement-invocation-marker - Record that /implement was invoked in this
#                                     session, so claude-implement-stop-hook.sh
#                                     can tell "no run" apart from "run that
#                                     never wrote its §2.3 state file".
#
# Usage (Claude Code UserPromptSubmit hook):
#   stdin:  hook event JSON ({ session_id, prompt, ... })
#   stdout: NOTHING, ever — a UserPromptSubmit hook's stdout is injected into
#           the conversation as context, so any output here would silently
#           rewrite the human's prompt.
#   exit:   0, always — see "Fail-closed is not an option" below.
#
# Side effect, and the only one: touches /tmp/implement_<session_id>.expected
# when the submitted prompt is a /implement slash-command invocation.
#
# Rationale:
#   implement/SKILL.md §2.3 requires writing /tmp/implement_<session_id>.json
#   before the first task dispatch. On 2026-08-10 an entire six-task batch ran
#   with no state file at all and nothing detected it — it had to be
#   reconstructed by hand at batch close. Every downstream guard was blind:
#   implement-loop-state.py errors correctly on a missing path but nothing
#   called it, and claude-implement-stop-hook.sh's session scoping reads an
#   empty state-file glob as "no /implement in this session" and exits silently.
#
#   That empty glob has two causes the Stop hook structurally cannot separate on
#   its own, and it must NOT stop treating one of them as silence: the silent
#   exit is what keeps every unrelated session on this machine free. This hook
#   supplies the missing bit from the one place the orchestrator cannot forget —
#   the literal prompt text, written by the harness before Claude reads it.
#
# Marker lifecycle (deliberately asymmetric — this hook only ever arms):
#   - Written here, on every /implement invocation, truncating any earlier
#     marker so its mtime always tracks the CURRENT invocation. The Stop hook
#     compares the §2.3 scratchpad against that mtime, so a stale marker would
#     let an earlier run's leftovers disarm a later run.
#   - Removed by claude-implement-stop-hook.sh, in gate mode only, the moment it
#     witnesses §2.3 (a state file exists, or the scratchpad is newer than this
#     marker). Removing it there and nowhere else is what stops a marker from
#     outliving its run: §8.3 trashes the state file at batch end, so a marker
#     still armed afterwards would false-block every later Stop in the session.
#   - NEVER consumed by a block. A batch whose orchestrator ends no turn
#     mid-flight stops exactly once — at batch end — so a marker that a first
#     block cleared would miss the very failure this guard exists for.
#   - Escape hatch for a marker with no run behind it (pre-flight aborted at
#     §1.1/§1.3, or the invocation never started the skill): the Stop hook's
#     block reason names `trash /tmp/implement_<session_id>.expected`. It says
#     trash rather than rm because claude-rm-guard.sh blocks rm on /tmp paths.
#
# Coverage limits — real gaps, stated so no reader assumes this is total:
#   - Only a TYPED slash command reaches UserPromptSubmit. A programmatic Skill
#     tool invocation of /implement never fires this event, so it stays
#     unguarded. The typed path is the one that actually failed, which is what
#     makes the partial guard worth shipping.
#   - Natural-language invocation ("let's implement that", which the skill's
#     own description accepts) is deliberately NOT matched. Matching it would
#     mean arming the guard from ordinary prose, and a false block is a worse
#     failure here than a missed one.
#
# Fail-closed is not an option:
#   A UserPromptSubmit hook that exits non-zero interferes with the human's
#   prompt (exit 2 blocks it outright). So this script must be structurally
#   incapable of a non-zero exit — hence `trap 'exit 0' EXIT`, no `set -e`
#   (one unexpected non-zero would otherwise eat the prompt), and `|| true` on
#   every command that can fail. `claude-implement-stop-hook.sh` sets the house
#   precedent for trimming this line for the same fail-open reason: it runs
#   `set -eo pipefail`, dropping -u on purpose.
#
# Safeguards (every one a silent no-op — this hook never breaks a prompt, and
# every path either writes the marker or is one of these enumerated gaps):
#   - jq missing → no marker, exit 0.
#   - stdin empty or unreadable → no marker, exit 0.
#   - stdin not valid JSON → no marker, exit 0.
#   - No session_id in the payload → no marker (there is no path to key it to),
#     exit 0.
#   - No prompt field → no marker, exit 0.
#   - Marker path unwritable (read-only /tmp, or something already occupying
#     the path) → no marker, exit 0. This one IS a silent skip of the guard
#     itself; it is enumerated rather than fixed because the alternative —
#     failing loudly — costs the human their prompt.
#
# NO env-var opt-out by design, matching claude-implement-stop-hook.sh: a kill
# switch would let Claude silence its own accountability mechanism via a Bash
# call. To disable, remove the UserPromptSubmit entry from settings.json.

set -uo pipefail
trap 'exit 0' EXIT

input=$(cat 2>/dev/null || true)
[ -n "$input" ] || exit 0

command -v jq >/dev/null 2>&1 || exit 0

session_id=$(printf '%s' "$input" | jq -r '.session_id // empty' 2>/dev/null || true)
[ -n "$session_id" ] || exit 0

prompt=$(printf '%s' "$input" | jq -r '.prompt // empty' 2>/dev/null || true)
[ -n "$prompt" ] || exit 0

# Anchored at the start of the prompt and terminated by whitespace or end of
# string. Both halves are load-bearing:
#   - unanchored, the word "implement" in ordinary prose would arm the guard;
#   - unterminated, /implement-something (a different command) would too.
# The [[:space:]] character class rather than \b: \b matches before a hyphen,
# so \b would accept /implement-something — and the class behaves the same on
# BSD and glibc, which the repo's cross-platform MUST requires.
if [[ ! "$prompt" =~ ^[[:space:]]*/implement([[:space:]]|$) ]]; then
  exit 0
fi

marker="/tmp/implement_${session_id}.expected"

# Truncating write, not `touch`: a second /implement in the same session must
# reset the mtime the Stop hook compares the scratchpad against. The content is
# for a human who finds the file in /tmp — never the prompt itself, which can
# carry anything the human typed.
printf '%s\n' \
  "/implement was invoked in session ${session_id}; implement/SKILL.md §2.3 must write /tmp/implement_${session_id}.json" \
  >"$marker" 2>/dev/null || true

exit 0
