#!/usr/bin/env bash
# claude-stop-orchestrator - Run the Stop hooks in series so the "done"
#                            notification fires exactly once, on the real stop.
#
# Usage (Claude Code Stop hook):
#   stdin: hook event JSON ({ session_id, stop_hook_active, ... })
#   stdout: passed through from whichever child hook produces it
#
# Why this exists:
#   Claude Code runs all hooks on one event IN PARALLEL with no short-circuit
#   (one hook's block does not suppress a sibling's side effects). With the
#   markdown-standards gate and the tmux "done" notification both wired directly
#   to Stop, a turn that the gate blocks (to keep fixing the doc) still fires a premature
#   "done" ping — then a second, real ping after the fix. On a tmux window you
#   aren't watching, that's a misleading double-notify.
#
#   Sequencing them here fixes it: run the markdown-standards gate, then the session-scoped
#   implement gate, then the spec-driven coverage gate; only if NONE blocks (the
#   turn is genuinely over) do we run the notification. One ping, on the real stop.
#
# This does NOT merge the child scripts:
#   claude-markdown-standards-stop-hook.sh, claude-implement-stop-hook.sh,
#   claude-sdd-stop-hook.sh, and claude-tmux-notification.sh stay standalone,
#   independently testable, and
#   usable on their own events (the notification is still wired directly to the
#   Notification event elsewhere). This orchestrator only sequences them for the
#   Stop event and gates the notification on either gate's verdict.
#
# Safeguards (never break Claude on a tooling/child gap):
#   - stdin is read once and replayed to each child (children each read stdin).
#   - A missing or failing gate fails OPEN: treat as "no block" and move on to
#     the next stage — better a stray ping than a swallowed stop.
#   - Block detection is by a gate's JSON output, not its exit code (each gate
#     emits {decision:"block"} and exits 0).

input=$(cat)

dir=$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd) || dir="$HOME/.claude/hooks"
md_standards="$dir/claude-markdown-standards-stop-hook.sh"
implement_gate="$dir/claude-implement-stop-hook.sh"
sdd_gate="$dir/claude-sdd-stop-hook.sh"
notify="$dir/claude-tmux-notification.sh"

# 1. Markdown-standards gate first. It prints a {decision:"block"} JSON (and
#    nothing else) when changed markdown still violates a doc-standards line
#    rule (density cap or bullet gap); stays silent otherwise.
md_standards_out=""
if [ -f "$md_standards" ]; then
  md_standards_out=$(printf '%s' "$input" | bash "$md_standards" 2>/dev/null || true)
fi

# 2. Gate blocked → pass its decision straight through and STOP here. The turn
#    isn't really over (Claude will fix the markdown next), so do NOT notify.
case "$md_standards_out" in
  *'"decision"'*)
    printf '%s\n' "$md_standards_out"
    exit 0
    ;;
esac

# 3. Session-scoped implement gate. It prints a {decision:"block"} JSON when
#    THIS session has a /implement run still mid-batch; stays silent for every
#    other session (no state file for the session id).
implement_out=""
if [ -f "$implement_gate" ]; then
  implement_out=$(printf '%s' "$input" | bash "$implement_gate" 2>/dev/null || true)
fi

# 4. Gate blocked → pass its decision straight through and STOP here, same as
#    step 2: the batch isn't done, so do NOT notify.
case "$implement_out" in
  *'"decision"'*)
    printf '%s\n' "$implement_out"
    exit 0
    ;;
esac

# 5. Spec-driven coverage gate. Runs AFTER the implement gate on purpose: that
#    gate blocks every mid-batch stop, and the plan_/spec_ docs are the batch's
#    own WIP — gating their coverage earlier would churn on transient mid-batch
#    drift. It prints a {decision:"block"} JSON reporting the itemized drift for the
#    main session to reconcile when a spec-driven plan_<slug>.md in CWD has drifted;
#    stays silent when there's no such plan or it's clean.
sdd_out=""
if [ -f "$sdd_gate" ]; then
  sdd_out=$(printf '%s' "$input" | bash "$sdd_gate" 2>/dev/null || true)
fi

# 6. Gate blocked → pass its decision straight through and STOP here, same as
#    steps 2 and 4: coverage still needs reconciling, so do NOT notify.
case "$sdd_out" in
  *'"decision"'*)
    printf '%s\n' "$sdd_out"
    exit 0
    ;;
esac

# 7. All gates clean → this is the real stop → fire the "done" notification.
#    Its stdout (none today; forward-safe if a future variant emits JSON) flows
#    through as this hook's stdout.
if [ -f "$notify" ]; then
  printf '%s' "$input" | bash "$notify" "done" 2>/dev/null || true
fi

exit 0
