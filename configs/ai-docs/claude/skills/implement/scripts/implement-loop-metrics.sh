#!/usr/bin/env bash
# implement-loop-metrics.sh - pure run-metrics script for the /implement task loop.
#
# Usage:
#   implement-loop-metrics.sh <state-file> [transcript-jsonl]
#
# Reads a /implement run's JSON state file (and optionally its session
# transcript JSONL) and prints one JSON summary on stdout:
#   {
#     "duration_seconds": <int or null>,
#     "tokens": {
#       "per_task": {"<task-id>": <int>, ...},
#       "subagent_total": <int>,
#       "orchestrator_total": <int>,
#       "total": <int>
#     },
#     "over_budget_tasks": ["<task-id>", ...]
#   }
#
# Examples:
#   implement-loop-metrics.sh /tmp/implement_abc123.json
#   implement-loop-metrics.sh /tmp/implement_abc123.json ~/.claude/projects/-foo/abc123.jsonl
#   implement-loop-metrics.sh --help
#
# Pure: no writes, no clock reads. `duration_seconds` is arithmetic over the
# `started_at`/`presented_at` strings already recorded in the state file, not
# a read of the wall clock — the orchestrator can't observe its own token
# usage in-session, so this script is the deterministic place to sum it.
#
# Contract for the optional transcript arg: each line is a Claude Code
# transcript JSONL record; a record contributes to `orchestrator_total` when
# it has a `.message.usage` object, summing `input_tokens`, `output_tokens`,
# `cache_creation_input_tokens`, and `cache_read_input_tokens` (missing
# fields treated as 0). Lines without that shape contribute 0.
#
# Exit codes:
#   0 - summary printed on stdout.
#   1 - usage error, missing/invalid state file, or a transcript path given
#       that doesn't exist. Fail-loud, same rationale as implement-loop-state.sh.

set -eo pipefail

# Tunable constant.
TASK_TOKEN_BUDGET=200000

usage() {
  cat <<'EOF'
usage: implement-loop-metrics.sh <state-file> [transcript-jsonl]

Reads a /implement run's JSON state file (and optionally its session
transcript JSONL) and prints one JSON summary: wall-clock duration, summed
subagent + orchestrator tokens, and the list of over-budget tasks.

Examples:
  implement-loop-metrics.sh /tmp/implement_abc123.json
  implement-loop-metrics.sh /tmp/implement_abc123.json ~/.claude/projects/-foo/abc123.jsonl
EOF
}

if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
  usage
  exit 0
fi

if [ $# -lt 1 ] || [ $# -gt 2 ]; then
  usage >&2
  exit 1
fi

state_file="$1"
transcript_file="${2:-}"

if ! command -v jq >/dev/null 2>&1; then
  echo "error: jq is required but not found on PATH" >&2
  exit 1
fi

if [ ! -f "$state_file" ]; then
  echo "error: state file not found: $state_file" >&2
  exit 1
fi

if ! jq empty "$state_file" >/dev/null 2>&1; then
  echo "error: state file is not valid JSON: $state_file" >&2
  exit 1
fi

if [ -n "$transcript_file" ] && [ ! -f "$transcript_file" ]; then
  echo "error: transcript file not found: $transcript_file" >&2
  exit 1
fi

# iso_to_epoch - converts an ISO-8601 UTC timestamp ("...Z") to epoch seconds,
# cross-platform (GNU date on Linux, BSD date on macOS).
iso_to_epoch() {
  local iso="$1"
  if date --version >/dev/null 2>&1; then
    date -u -d "$iso" +%s
  else
    date -u -j -f '%Y-%m-%dT%H:%M:%SZ' "$iso" +%s
  fi
}

started_at=$(jq -r '.started_at // ""' "$state_file")
presented_at=$(jq -r '.presented_at // ""' "$state_file")

duration_json="null"
if [ -n "$started_at" ] && [ -n "$presented_at" ]; then
  start_epoch=$(iso_to_epoch "$started_at")
  end_epoch=$(iso_to_epoch "$presented_at")
  duration_json=$((end_epoch - start_epoch))
fi

per_task_json=$(jq -c \
  '(.attempts // []) | group_by(.task) | map({(.[0].task): ((map(.tokens // 0) | add) // 0)}) | add // {}' \
  "$state_file")

subagent_total=$(jq \
  '((.attempts // []) | map(.tokens // 0) | add // 0) + (((.tails.tokens // {}) | to_entries | map(.value) | add) // 0)' \
  "$state_file")

orchestrator_total=0
if [ -n "$transcript_file" ]; then
  orchestrator_total=$(jq -s \
    '[.[] | (.message.usage // {}) | ((.input_tokens // 0) + (.output_tokens // 0) + (.cache_creation_input_tokens // 0) + (.cache_read_input_tokens // 0))] | add // 0' \
    "$transcript_file")
fi

over_budget_tasks=$(printf '%s' "$per_task_json" | jq --argjson budget "$TASK_TOKEN_BUDGET" \
  '[to_entries[] | select(.value > $budget) | .key]')

jq -n \
  --argjson duration "$duration_json" \
  --argjson per_task "$per_task_json" \
  --argjson subagent_total "$subagent_total" \
  --argjson orchestrator_total "$orchestrator_total" \
  --argjson over_budget_tasks "$over_budget_tasks" \
  '{
    duration_seconds: $duration,
    tokens: {
      per_task: $per_task,
      subagent_total: $subagent_total,
      orchestrator_total: $orchestrator_total,
      total: ($subagent_total + $orchestrator_total)
    },
    over_budget_tasks: $over_budget_tasks
  }'
