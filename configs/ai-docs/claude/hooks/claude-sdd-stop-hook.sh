#!/usr/bin/env bash
# claude-sdd-stop-hook - At review handoff, gate on spec-driven-development coverage
#                        drift in the CWD's spec_/plan_ docs, and report the itemized
#                        drift to the main session to reconcile.
#
# Usage (Claude Code Stop hook):
#   stdin:  hook event JSON ({ session_id, stop_hook_active, ... })
#   stdout: optional JSON ({ decision: "block", reason: "..." }) to keep Claude going
#
# What it gates (the spec-driven-development coverage scripts, on CWD docs):
#   For each plan_<slug>.md in the CWD that is a REAL spec-driven plan (has a
#   `## ...Test Design...` heading — the sniff that skips ad-hoc plan_ notes):
#     - check-test-distribution.sh <plan>    Test Design titles == union of per-task
#                                            `**Tests (planned)**` lists (set equality).
#     - check-ac-coverage.sh <plan> <spec>   run ONLY when spec_<slug>.md also exists
#                                            AND defines `### AC-N:` — spec AC ⊆ plan
#                                            headers (completeness) + cited ⊆ design
#                                            (honesty).
#   Density is deliberately NOT run here — the density Stop hook owns .md density.
#
# Why at Stop:
#   The Stop event is the review handoff. Spec/plan coverage drifts silently while ACs
#   and tests get uncovered during implementation (a real hit: Test Design edited,
#   per-task Tests-planned lists not — only a manual gate run caught it). Gating at Stop
#   keeps spec/plan continuously in sync, off the main thread.
#
# Reconcile contract — NOT the density fixer's "iterate to green":
#   Coverage gates assert set-equality/subset, so a fix CAN reach exit 0 by CORRUPTING
#   the doc (deleting a real planned test, or inventing a Test Design line). That is a
#   regression, not a fix. So the main session — which this hook hands the itemized drift
#   to — reconciles ONLY high-confidence renamed/typo'd twins, interviews the user on a
#   genuine gap, and never deletes/invents to force equality. The doc may still carry
#   drift after one pass — acceptable: the stop_hook_active guard means this sequence
#   won't re-block anyway.
#
# Enforcement vs. loop-safety:
#   Honors stop_hook_active=true → bows out, so this can never spin an infinite
#   stop-block loop. One reconcile pass per handoff: the main session fixes the twins it
#   can, interviews on genuine gaps, and re-runs the gates to confirm. The hook never
#   re-blocks in-cycle, so residual drift waits for the next clean handoff, not a loop.
#
# Safeguards (all silent no-ops — never break Claude on a tooling/context gap):
#   - jq missing, or the coverage scripts absent/not executable → exit 0.
#   - No plan_<slug>.md in CWD, none spec-driven, or all clean → exit 0.
#   - A gate exiting 2 (usage / file-not-found / missing sibling) is a TOOLING gap, not
#     drift → fail OPEN (skip that check). Only exit 1 (real content/structure drift)
#     counts as a block-worthy finding.
#
# NO env-var opt-out by design — a kill switch would let Claude silence its own
# coverage gate via a Bash call. To disable, remove this hook from the orchestrator.

set -eo pipefail

input=$(cat)

command -v jq >/dev/null 2>&1 || exit 0

stop_hook_active=$(printf '%s' "$input" | jq -r '.stop_hook_active // false' 2>/dev/null || true)
[ "$stop_hook_active" = "true" ] && exit 0

SCRIPTS="$HOME/.claude/skills/spec-driven-development/scripts"
DIST="$SCRIPTS/check-test-distribution.sh"
AC="$SCRIPTS/check-ac-coverage.sh"
[ -x "$DIST" ] || exit 0
[ -x "$AC" ] || exit 0

shopt -s nullglob

drift=""

for plan in plan_*.md; do
  [ -f "$plan" ] || continue

  # Sniff: only REAL spec-driven plans carry a `## ...Test Design...` heading. Ad-hoc
  # plan_<slug>.md notes (no Test Design, no `### N.` tasks) are skipped, so they never
  # false-block the gate. `^##[[:space:]]` matches the h2 heading only (not `### `).
  grep -qiE '^##[[:space:]].*test design' "$plan" || continue

  slug="${plan#plan_}"
  slug="${slug%.md}"

  # test-distribution: needs only the plan. Capture stdout+stderr — the FAIL diff prints
  # the offending titles to stderr — so the main session gets the itemized drift, not a
  # bare "mismatch" label. `|| dist_rc=$?` keeps the exit code reliable under set -e.
  dist_rc=0
  dist_out=$(bash "$DIST" "$plan" 2>&1) || dist_rc=$?
  if [ "$dist_rc" -eq 1 ]; then
    drift+="- ${plan}: Test Design <-> per-task Tests-planned set mismatch"$'\n'
    drift+="${dist_out}"$'\n'
  fi

  # ac-coverage: only when the same-slug spec exists AND defines `### AC-N:`.
  spec="spec_${slug}.md"
  if [ -f "$spec" ] && grep -qE '^### AC-[0-9]+' "$spec"; then
    ac_rc=0
    ac_out=$(bash "$AC" "$plan" "$spec" 2>&1) || ac_rc=$?
    if [ "$ac_rc" -eq 1 ]; then
      drift+="- ${plan} <-> ${spec}: AC coverage/honesty mismatch"$'\n'
      drift+="${ac_out}"$'\n'
    fi
  fi
done

drift=$(printf '%s' "$drift" | sed '/^$/d')
[ -z "$drift" ] && exit 0

# The itemized drift (captured from the gates' stderr above) plus the standing reconcile
# rules go straight to the MAIN session — no subagent. It is the stronger model and the
# only one that can interview the user on a genuine gap, so it reconciles here.
reason="Spec-driven coverage drift in CWD spec/plan docs — reconcile it, then re-run the gates to confirm:

${drift}

How to reconcile (Test Design is the source of truth for test titles):
- Twin — a FAIL line that is a clear rename/typo/whitespace variant of a real title on the \
other side: align the CITATION (a per-task Tests-planned entry or an AC citation) to the \
Test Design title. Only if Test Design is itself the lone dissenter is the typo there.
- Genuine gap — a cited/planned test that exists nowhere, a missing AC header, a designed \
test in no task: INTERVIEW the user before editing; it needs the plan author's intent.
- NEVER delete a planned test, invent a Test Design line, or fabricate an AC header/citation \
to force the gates green. Residual drift is fine — one honest pass, no looping (this handoff \
won't re-block).

Re-run to confirm: check-test-distribution.sh <plan> and check-ac-coverage.sh <plan> <spec> \
under ~/.claude/skills/spec-driven-development/scripts/."

jq -n --arg r "$reason" '{decision: "block", reason: $r}'
