#!/usr/bin/env bash
# claude-implement-stop-hook - Block a Stop while ANY unit of a /implement run
#                              is mid-batch in THIS session; allow the stop
#                              once every unit has left tasks|gates|tails.
#
# Usage (Claude Code Stop hook — "gate mode", the default):
#   stdin:  hook event JSON ({ session_id, stop_hook_active, ... })
#   stdout: optional JSON ({ decision: "block", reason: "..." }) to keep Claude going
#
# Usage (--check, "query mode" — for claude-stop-orchestrator.sh only, never
# wired to a hook event):
#   stdin:  the same hook event JSON
#   stdout: nothing
#   exit 0: at least one unit of this session is mid-flight
#   exit 1: nothing is mid-flight (also the fail-open answer on any tooling gap)
#   exit 2: usage error — an argument other than --check
#
# Why query mode exists:
#   Gate mode answers "should I block this stop?", which is NOT the same
#   question as "is the batch still running". The stop_hook_active guard below
#   makes gate mode stay silent on every stop that a previous block caused, so
#   the orchestrator — which suppresses its "done" ping only when a gate blocks
#   — pinged success once per task, mid-batch. Query mode answers the plain
#   mid-flight question with no loop guard in the way, so the ping can be
#   decided on the batch's real state instead of on the gate's block decision.
#   The loop guard stays where it belongs: it suppresses the block, not the truth.
#
#   Exit 1 rather than 0 carries "not mid-flight" so the shell's own convention
#   reads right at the call site (`if hook --check; then skip the ping; fi`),
#   which leaves exit 2 for a usage error — conflating that with a real answer
#   would silently notify or silently mute on a typo'd flag.
#
# Rationale:
#   /implement's task loop (the implement skill) writes ONE state file PER
#   UNIT, all created upfront: /tmp/implement_<session_id>.json for a plain
#   <task-ids> run, or /tmp/implement_<session_id>_pr<N>.json per PR on a
#   PR-label run. A natural Stop before every unit reaches a stopping phase
#   would leave the batch abandoned mid-way with no re-prompt. This hook
#   globs every state file for the session and blocks the stop while ANY
#   unit's phase is still tasks|gates|tails — session-scoped, so it never
#   affects any session without an active /implement run.
#
# Session scoping — the entire mechanism is one existence check:
#   State file paths are keyed by session_id. No file matching this session
#   id → silent exit 0 immediately, before any other check. Every other
#   session on this machine (no /implement run, or a different session id)
#   pays the cost of one failed glob and nothing else.
#
# Escape hatch: deleting the session's state files instantly un-scopes the
# session (the next Stop attempt finds no files and allows the stop).
#
# §2.3-skip guard — telling the two empty-glob cases apart:
#   An empty glob used to mean one thing here, and it silently covered two. On
#   2026-08-10 a whole six-task batch ran with NO state file: §2.3 was skipped,
#   every downstream guard read the empty glob as "no /implement here", and the
#   run had to be reconstructed by hand at batch close.
#
#   The session-scoping silence above is CORRECT and stays exactly as it was —
#   it is what keeps unrelated sessions free. What was missing is the bit that
#   separates the cases, and it cannot be recovered from state this hook owns.
#   build-implement-invocation-marker.sh (UserPromptSubmit) supplies it: on a
#   typed /implement it writes /tmp/implement_<session_id>.expected, from the
#   literal prompt text, before Claude reads the prompt — so the orchestrator
#   cannot forget it the way it forgot §2.3.
#
#   - Marker absent → unchanged: silent exit 0, one failed glob and nothing else.
#   - Marker present, and no §2.3 witness → block, naming the exact missing path
#     and both fixes (write the state file; or trash the marker if no run is
#     actually in flight).
#
#   Two artifacts count as a §2.3 witness, because §2.3 writes two:
#   - Any /tmp/implement_<session_id>*.json state file.
#   - /tmp/implement_<session_id>.md, the scratchpad — NEWER than the marker.
#     §8.3 trashes the state file but nothing disposes of the scratchpad, so it
#     is the only witness left at the batch-end Stop of a run that ended no turn
#     mid-flight. The newer-than test is what stops a leftover scratchpad from
#     an earlier /implement in the same session from disarming a later one.
#
#   No grace stop, on purpose: a design that let the first qualifying Stop pass
#   would eat the only Stop such a batch ever makes, and miss the exact failure
#   this guard exists for. The one-extra-turn cap comes from stop_hook_active,
#   like every other block here.
#
#   Marker removal happens here and nowhere else, in GATE MODE ONLY, the moment
#   a witness appears. A marker outliving its run would false-block every later
#   Stop in the session; query mode stays read-only because the orchestrator
#   calls it after the gate, and it must not mutate what the gate decided on.
#
#   Query mode is deliberately untouched by all of this: a run with no state
#   file is not mid-flight, which is what --check answers. The orchestrator
#   calls the gate first (claude-stop-orchestrator.sh:129) and a block
#   short-circuits the chain before the --check call ever runs.
#
# Safeguards (all silent no-ops — never break Claude on a tooling/state gap;
# each answers "nothing is mid-flight", which is exit 0 in gate mode and exit 1
# under --check):
#   - jq missing.
#   - No session_id.
#   - No state files match it AND no marker is armed (an armed marker is the
#     one case that is NOT a no-op — see the §2.3-skip guard above).
#   - A marker path that is not a regular file (a directory left there, say) is
#     ignored rather than treated as armed: no hook wrote it, so blocking on it
#     would be a false block whose disarm could never succeed.
#   - The marker removal is best-effort (`rm -f ... || true`); a removal that
#     fails costs at most one more armed Stop, never a broken hook.
#   - stop_hook_active=true → exit 0, GATE MODE ONLY (mirrors
#     claude-markdown-standards-stop-hook.sh's guard: an always-on hook must
#     never spin an infinite stop-block loop). --check skips it on purpose —
#     see "Why query mode exists" above.
#   - A state file that is corrupt JSON is skipped (fail-open per-file), not
#     treated as blocking.
#   - A unit's phase other than tasks|gates|tails — including presented,
#     halted, and blocked — releases that unit; the stop is allowed once no
#     unit is left mid-flight. halted and blocked deliberately release the
#     stop: a run that stopped for the human (a failed gate, a triage
#     decision) must be allowed to stop, otherwise this hook would spin
#     against a wall only the human can clear.
#
# This hook supersedes claude-tasklist-stop-hook.sh (deleted as dormant —
# it was never wired into settings.json). Its safeguard style (stdin parse,
# stop_hook_active guard, jq guard, fail-open) is the template this hook
# follows, adapted to read per-unit state files instead of a tasks dir.
#
# NO env-var opt-out by design — a kill switch would let Claude silence its
# own accountability mechanism via a Bash call. To disable, remove this
# hook's chaining from claude-stop-orchestrator.sh (or delete the session's
# state files to un-scope this one session).

set -eo pipefail

mode="gate"
if [ "${1:-}" = "--check" ]; then
  mode="check"
elif [ $# -gt 0 ]; then
  echo "claude-implement-stop-hook: unknown argument '$1' (expected no argument, or --check)" >&2
  exit 2
fi

# leave_not_mid_flight - exit with this mode's "no unit is mid-flight" answer.
# Every safeguard below routes through it so a tooling gap fails open in both
# modes at once: gate mode allows the stop, query mode lets the ping through.
leave_not_mid_flight() {
  [ "$mode" = "check" ] && exit 1
  exit 0
}

input=$(cat)

command -v jq >/dev/null 2>&1 || leave_not_mid_flight

# Loop guard, gate mode only: query mode is answering what is true, not deciding
# whether to block, so it can never spin a stop-block loop of its own.
if [ "$mode" = "gate" ]; then
  stop_hook_active=$(printf '%s' "$input" | jq -r '.stop_hook_active // false' 2>/dev/null || true)
  [ "$stop_hook_active" = "true" ] && exit 0
fi

session_id=$(printf '%s' "$input" | jq -r '.session_id // empty' 2>/dev/null || true)
[ -z "$session_id" ] && leave_not_mid_flight

shopt -s nullglob
state_files=(/tmp/implement_"$session_id"*.json)
shopt -u nullglob

# The two §2.3 witnesses, and the marker that makes them meaningful. See the
# "§2.3-skip guard" block in the header for why each one is here.
marker="/tmp/implement_${session_id}.expected"
scratchpad="/tmp/implement_${session_id}.md"

if [ "${#state_files[@]}" -eq 0 ]; then
  # Marker absent → no /implement was invoked in this session: the original
  # behavior, one failed glob and nothing else. Query mode never blocks, so it
  # takes this path too.
  if [ "$mode" != "gate" ] || [ ! -f "$marker" ]; then
    leave_not_mid_flight
  fi

  # §8.3 trashes the state file but leaves the scratchpad, so a completed run
  # whose only Stop is the batch-end one still has a witness. It must be NEWER
  # than the marker: a leftover scratchpad from an earlier /implement in the
  # same session would otherwise disarm this run permanently.
  if [ -f "$scratchpad" ] && [ "$scratchpad" -nt "$marker" ]; then
    rm -f "$marker" 2>/dev/null || true
    exit 0
  fi

  reason="Implement run (session $session_id): /implement was invoked in this \
session, but no state file exists at /tmp/implement_${session_id}.json (nor any \
/tmp/implement_${session_id}_pr<N>.json). The implement skill's §2.3 was \
skipped, so implement-loop-state.sh, this Stop gate and the compact reminder \
are all blind and the batch can run to the end unrecorded. Write the §2.3 state \
file now — its version-3 shape is in the implement skill — before doing anything \
else. If /implement is NOT running here (pre-flight aborted at §1.1 or §1.3, or \
the invocation never started the skill), clear the guard instead with: trash \
/tmp/implement_${session_id}.expected"
  jq -n --arg r "$reason" '{decision: "block", reason: $r}' 2>/dev/null || exit 0
  exit 0
fi

# A real state file witnesses §2.3: the guard has done its job for this run, and
# every later Stop is driven by the phase logic below. Gate mode only — query
# mode is a read-only question the orchestrator asks after the gate has already
# decided, so it must not mutate what that decision was based on.
if [ "$mode" = "gate" ] && [ -f "$marker" ]; then
  rm -f "$marker" 2>/dev/null || true
fi

mid_flight_count=0
first_unit_desc=""
first_phase=""

for f in "${state_files[@]}"; do
  jq empty "$f" >/dev/null 2>&1 || continue   # corrupt JSON: skip, fail-open

  phase=$(jq -r '.phase // empty' "$f" 2>/dev/null || true)
  case "$phase" in
    tasks|gates|tails) ;;
    *) continue ;;
  esac

  mid_flight_count=$((mid_flight_count + 1))
  if [ -z "$first_phase" ]; then
    pr_label=$(jq -r '.pr_label // empty' "$f" 2>/dev/null || true)
    if [ -n "$pr_label" ]; then
      first_unit_desc="PR '$pr_label'"
    else
      first_unit_desc="the plain run"
    fi
    first_phase="$phase"
  fi
done

[ "$mid_flight_count" -eq 0 ] && leave_not_mid_flight

# Query mode answers with the exit code alone — naming the unit and its phase is
# the block reason's job, and the orchestrator has nothing to print it into.
[ "$mode" = "check" ] && exit 0

remaining=$((mid_flight_count - 1))
remaining_note=""
[ "$remaining" -gt 0 ] && remaining_note=" ($remaining more unit(s) still mid-flight)"

reason="Implement run (session $session_id): $first_unit_desc is still in phase \
'$first_phase'$remaining_note — the batch isn't done yet. Keep working the task \
loop (see the implement skill and implement-loop-state.sh) instead of stopping; \
each unit finishes on its own once its phase reaches presented, or halts for the \
human (halted/blocked)."
jq -n --arg r "$reason" '{decision: "block", reason: $r}'

exit 0
