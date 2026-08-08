#!/usr/bin/env bash
# test-extract-session-feedback.sh - plain-bash test file
# for extract-session-feedback.py.
#
# Usage:
#   bash test-extract-session-feedback.sh
#
# Exits 0 when every assertion passes, nonzero otherwise.
# No pytest dependency, matching this skill's other test
# files.

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$script_dir/extract-session-feedback.py"

work_dir=$(mktemp -d)
trap 'rm -rf "$work_dir"' EXIT

pass_count=0
fail_count=0

# assert_eq - inline assert helper: compares expected vs
# actual, prints ok/not-ok.
assert_eq() {
  local description="$1" expected="$2" actual="$3"
  if [ "$expected" = "$actual" ]; then
    pass_count=$((pass_count + 1))
    printf 'ok - %s\n' "$description"
  else
    fail_count=$((fail_count + 1))
    printf 'not ok - %s\n  expected: %s\n  actual:   %s\n' "$description" "$expected" "$actual"
  fi
}

# run_script - invokes extract-session-feedback.py with the
# given args, capturing stdout/stderr/exit code into
# VERDICT_OUT/VERDICT_ERR/VERDICT_EXIT.
run_script() {
  local out_file="$work_dir/stdout.txt"
  local err_file="$work_dir/stderr.txt"
  python3 "$SCRIPT" "$@" >"$out_file" 2>"$err_file"
  VERDICT_EXIT=$?
  VERDICT_OUT=$(cat "$out_file")
  VERDICT_ERR=$(cat "$err_file")
}

it_should_reject_the_removed_session_id_project_dir_and_cwd_flags_with_a_nonzero_exit() {
  run_script --session-id fake-session --project-dir /nonexistent --cwd /nonexistent

  # Both must hold: a nonzero exit alone doesn't prove
  # argparse rejected the flags (the old resolve_transcript()
  # also failed nonzero, for a different reason), so this is
  # one behavior, asserted once.
  local rejected_via_argparse="false"
  if [ "$VERDICT_EXIT" -ne 0 ] && [[ "$VERDICT_ERR" == *"unrecognized arguments"* ]]; then
    rejected_via_argparse="true"
  fi
  assert_eq \
    "ExtractSessionFeedbackSweep > failure > should reject the removed --session-id, --project-dir, and --cwd flags with a nonzero exit" \
    "true" "$rejected_via_argparse"
}

# make_transcript - writes JSONL lines (read from stdin) into
# a fresh transcript file at $1, then sets its mtime to
# $2 seconds before now (default: 0, i.e. just-now).
make_transcript() {
  local path="$1" seconds_ago="${2:-0}"
  mkdir -p "$(dirname "$path")"
  cat > "$path"
  python3 -c "
import os, time
t = time.time() - $seconds_ago
os.utime('$path', (t, t))
"
}

DAY=86400

it_should_select_every_transcript_in_the_since_window_with_turns_gte_2() {
  local dir="$work_dir/select_window"

  make_transcript "$dir/qualifies.jsonl" "$DAY" <<'JSONL'
{"type":"user","timestamp":"2026-01-01T00:00:00","message":{"content":"first real user correction about the API contract"}}
{"type":"assistant","message":{"content":[{"type":"text","text":"ack"}]}}
{"type":"user","timestamp":"2026-01-01T00:01:00","message":{"content":"second real user correction about the same contract"}}
{"type":"assistant","message":{"content":[{"type":"text","text":"ack2"}]}}
JSONL

  make_transcript "$dir/too_old.jsonl" "$((10 * DAY))" <<'JSONL'
{"type":"user","timestamp":"2026-01-01T00:00:00","message":{"content":"an old correction outside the window"}}
{"type":"assistant","message":{"content":[{"type":"text","text":"ack"}]}}
{"type":"user","timestamp":"2026-01-01T00:01:00","message":{"content":"a second old correction outside the window"}}
{"type":"assistant","message":{"content":[{"type":"text","text":"ack2"}]}}
JSONL

  make_transcript "$dir/too_few_turns.jsonl" "$DAY" <<'JSONL'
{"type":"user","timestamp":"2026-01-01T00:00:00","message":{"content":"only one real user turn in this file"}}
{"type":"assistant","message":{"content":[{"type":"text","text":"ack"}]}}
JSONL

  run_script --since 7 --project-dirs "$dir"

  local selected_correctly="false"
  if [[ "$VERDICT_OUT" == *"qualifies.jsonl"* ]] \
     && [[ "$VERDICT_OUT" != *"too_old.jsonl"* ]] \
     && [[ "$VERDICT_OUT" != *"too_few_turns.jsonl"* ]]; then
    selected_correctly="true"
  fi

  assert_eq \
    "ExtractSessionFeedbackSweep > happy > should select every transcript whose mtime falls in the --since window and whose real-user-turn count is >= 2" \
    "true" "$selected_correctly"
}

it_should_print_the_corpus_survey_before_emitting_any_session_content() {
  local dir="$work_dir/survey_order"

  make_transcript "$dir/session_one.jsonl" "$DAY" <<'JSONL'
{"type":"user","timestamp":"2026-01-01T00:00:00","message":{"content":"first session first real user correction"}}
{"type":"assistant","message":{"content":[{"type":"text","text":"ack"}]}}
{"type":"user","timestamp":"2026-01-01T00:01:00","message":{"content":"first session second real user correction"}}
{"type":"assistant","message":{"content":[{"type":"text","text":"ack2"}]}}
JSONL

  make_transcript "$dir/session_two.jsonl" "$DAY" <<'JSONL'
{"type":"user","timestamp":"2026-01-01T00:00:00","message":{"content":"second session first real user correction"}}
{"type":"assistant","message":{"content":[{"type":"text","text":"ack"}]}}
{"type":"user","timestamp":"2026-01-01T00:01:00","message":{"content":"second session second real user correction"}}
{"type":"assistant","message":{"content":[{"type":"text","text":"ack2"}]}}
JSONL

  run_script --since 7 --project-dirs "$dir"

  local survey_line session_line
  survey_line=$(printf '%s\n' "$VERDICT_OUT" | grep -n '^# corpus survey' | head -1 | cut -d: -f1)
  session_line=$(printf '%s\n' "$VERDICT_OUT" | grep -n '^## Session' | head -1 | cut -d: -f1)

  local survey_before_content="false"
  if [ -n "$survey_line" ] && [ -n "$session_line" ] && [ "$survey_line" -lt "$session_line" ]; then
    survey_before_content="true"
  fi
  assert_eq \
    "ExtractSessionFeedbackSweep > happy > should print the corpus survey (file count, turn count, estimated tokens) before emitting any session content" \
    "true" "$survey_before_content"
}

it_should_group_learnings_and_turns_per_session_in_session_order() {
  local dir="$work_dir/session_order"

  make_transcript "$dir/session_early.jsonl" "$((2 * DAY))" <<'JSONL'
{"type":"user","timestamp":"2026-01-01T00:00:00","message":{"content":"alpha first real user correction"}}
{"type":"assistant","message":{"content":[{"type":"text","text":"[Learning] said=\"applied alpha fix\" | rule=\"alpha-rule\""}]}}
{"type":"user","timestamp":"2026-01-01T00:01:00","message":{"content":"alpha second real user correction"}}
{"type":"assistant","message":{"content":[{"type":"text","text":"ack2"}]}}
JSONL

  make_transcript "$dir/session_late.jsonl" "$DAY" <<'JSONL'
{"type":"user","timestamp":"2026-01-02T00:00:00","message":{"content":"beta first real user correction"}}
{"type":"assistant","message":{"content":[{"type":"text","text":"[Learning] said=\"applied beta fix\" | rule=\"beta-rule\""}]}}
{"type":"user","timestamp":"2026-01-02T00:01:00","message":{"content":"beta second real user correction"}}
{"type":"assistant","message":{"content":[{"type":"text","text":"ack2"}]}}
JSONL

  run_script --since 7 --project-dirs "$dir"

  local session1 alpha_learning session2 beta_learning
  session1=$(printf '%s\n' "$VERDICT_OUT" | grep -n '^## Session 1' | head -1 | cut -d: -f1)
  alpha_learning=$(printf '%s\n' "$VERDICT_OUT" | grep -n 'alpha-rule' | head -1 | cut -d: -f1)
  session2=$(printf '%s\n' "$VERDICT_OUT" | grep -n '^## Session 2' | head -1 | cut -d: -f1)
  beta_learning=$(printf '%s\n' "$VERDICT_OUT" | grep -n 'beta-rule' | head -1 | cut -d: -f1)

  local grouped_in_order="false"
  if [ -n "$session1" ] && [ -n "$alpha_learning" ] && [ -n "$session2" ] && [ -n "$beta_learning" ] \
     && [ "$session1" -lt "$alpha_learning" ] && [ "$alpha_learning" -lt "$session2" ] \
     && [ "$session2" -lt "$beta_learning" ]; then
    grouped_in_order="true"
  fi
  assert_eq \
    "ExtractSessionFeedbackSweep > happy > should group emitted [Learning] markers and verbatim turns per session, in session order" \
    "true" "$grouped_in_order"
}

it_should_exclude_the_running_sessions_own_transcript_even_when_it_qualifies() {
  local dir="$work_dir/exclude_running"

  make_transcript "$dir/current-session-id.jsonl" "$DAY" <<'JSONL'
{"type":"user","timestamp":"2026-01-01T00:00:00","message":{"content":"this run mining its own prompts, first turn"}}
{"type":"assistant","message":{"content":[{"type":"text","text":"ack"}]}}
{"type":"user","timestamp":"2026-01-01T00:01:00","message":{"content":"this run mining its own prompts, second turn"}}
{"type":"assistant","message":{"content":[{"type":"text","text":"ack2"}]}}
JSONL

  make_transcript "$dir/other-session-id.jsonl" "$DAY" <<'JSONL'
{"type":"user","timestamp":"2026-01-01T00:00:00","message":{"content":"an unrelated other session, first turn"}}
{"type":"assistant","message":{"content":[{"type":"text","text":"ack"}]}}
{"type":"user","timestamp":"2026-01-01T00:01:00","message":{"content":"an unrelated other session, second turn"}}
{"type":"assistant","message":{"content":[{"type":"text","text":"ack2"}]}}
JSONL

  CLAUDE_CODE_SESSION_ID="current-session-id" run_script --since 7 --project-dirs "$dir"

  local excluded_correctly="false"
  if [[ "$VERDICT_OUT" != *"current-session-id.jsonl"* ]] \
     && [[ "$VERDICT_OUT" == *"other-session-id.jsonl"* ]]; then
    excluded_correctly="true"
  fi

  assert_eq \
    "ExtractSessionFeedbackSweep > corner > should exclude the running session's own transcript even when it otherwise qualifies" \
    "true" "$excluded_correctly"
}

it_should_default_since_to_7_days_when_omitted() {
  local dir="$work_dir/default_since"

  make_transcript "$dir/within_default.jsonl" "$((6 * DAY))" <<'JSONL'
{"type":"user","timestamp":"2026-01-01T00:00:00","message":{"content":"six days ago first real user correction"}}
{"type":"assistant","message":{"content":[{"type":"text","text":"ack"}]}}
{"type":"user","timestamp":"2026-01-01T00:01:00","message":{"content":"six days ago second real user correction"}}
{"type":"assistant","message":{"content":[{"type":"text","text":"ack2"}]}}
JSONL

  make_transcript "$dir/outside_default.jsonl" "$((10 * DAY))" <<'JSONL'
{"type":"user","timestamp":"2026-01-01T00:00:00","message":{"content":"ten days ago first real user correction"}}
{"type":"assistant","message":{"content":[{"type":"text","text":"ack"}]}}
{"type":"user","timestamp":"2026-01-01T00:01:00","message":{"content":"ten days ago second real user correction"}}
{"type":"assistant","message":{"content":[{"type":"text","text":"ack2"}]}}
JSONL

  run_script --project-dirs "$dir"

  local default_window_correct="false"
  if [[ "$VERDICT_OUT" == *"within_default.jsonl"* ]] \
     && [[ "$VERDICT_OUT" != *"outside_default.jsonl"* ]]; then
    default_window_correct="true"
  fi

  assert_eq \
    "ExtractSessionFeedbackSweep > corner > should default --since to 7 days when the flag is omitted" \
    "true" "$default_window_correct"
}

it_should_report_zero_qualifying_sessions_without_a_survey_estimate_of_zero() {
  local dir="$work_dir/zero_qualifying"
  mkdir -p "$dir"

  run_script --since 7 --project-dirs "$dir"

  local zero_reported_without_estimate="false"
  if [[ "$VERDICT_OUT" == *"0 qualifying sessions"* ]] \
     && [[ "$VERDICT_OUT" != *"estimated tokens"* ]]; then
    zero_reported_without_estimate="true"
  fi

  assert_eq \
    "ExtractSessionFeedbackSweep > corner > should report zero qualifying sessions and stop, without printing a survey estimate of zero" \
    "true" "$zero_reported_without_estimate"
}

it_should_silently_skip_a_malformed_trailing_jsonl_line() {
  local dir="$work_dir/malformed_trailing"

  make_transcript "$dir/live_appending.jsonl" "$DAY" <<'JSONL'
{"type":"user","timestamp":"2026-01-01T00:00:00","message":{"content":"first real user correction before truncation"}}
{"type":"assistant","message":{"content":[{"type":"text","text":"ack"}]}}
{"type":"user","timestamp":"2026-01-01T00:01:00","message":{"content":"second real user correction before truncation"}}
{"type":"assistant","message":{"content":[{"type":"text","text":"ack2"}]}}
{"type":"user","timestamp":"2026-01-01T00:02:00","message":{"content":"trunc
JSONL

  run_script --since 7 --project-dirs "$dir"

  local skipped_malformed_line_cleanly="false"
  if [ "$VERDICT_EXIT" -eq 0 ] \
     && [[ "$VERDICT_OUT" == *"second real user correction before truncation"* ]]; then
    skipped_malformed_line_cleanly="true"
  fi

  assert_eq \
    "ExtractSessionFeedbackSweep > corner > should silently skip a malformed trailing JSONL line from a live-appending transcript" \
    "true" "$skipped_malformed_line_cleanly"
}

it_should_truncate_a_user_turn_at_the_char_cap_while_still_counting_it() {
  local dir="$work_dir/char_cap"
  local long_text
  long_text=$(python3 -c "print('x' * 7000)")

  {
    printf '{"type":"user","timestamp":"2026-01-01T00:00:00","message":{"content":"%s"}}\n' "$long_text"
    printf '{"type":"assistant","message":{"content":[{"type":"text","text":"ack"}]}}\n'
    printf '{"type":"user","timestamp":"2026-01-01T00:01:00","message":{"content":"a short second real user turn"}}\n'
    printf '{"type":"assistant","message":{"content":[{"type":"text","text":"ack2"}]}}\n'
  } | make_transcript "$dir/oversized_turn.jsonl" "$DAY"

  run_script --since 7 --project-dirs "$dir"

  local truncated_and_still_qualified="false"
  if [[ "$VERDICT_OUT" == *"…[truncated, 7000 chars total]"* ]] \
     && [[ "$VERDICT_OUT" == *"oversized_turn.jsonl"* ]]; then
    truncated_and_still_qualified="true"
  fi

  assert_eq \
    "ExtractSessionFeedbackSweep > corner > should truncate a single user turn at USER_TURN_CHAR_CAP while still counting it toward the >=2-turn filter" \
    "true" "$truncated_and_still_qualified"
}

it_count_real_user_turns_should_count_only_real_user_prose_turns() {
  local fixture="$work_dir/mixed_turns.jsonl"
  cat > "$fixture" <<'JSONL'
{"type":"user","message":{"content":"a real prose correction about the API contract"}}
{"type":"user","isMeta":true,"message":{"content":"meta housekeeping turn"}}
{"type":"user","message":{"content":[{"type":"tool_result","content":"tool output"}]}}
{"type":"user","message":{"content":"<command-name>improve-from-user</command-name>\n<command-message>run it</command-message>"}}
{"type":"user","isCompactSummary":true,"message":{"content":"compaction summary text"}}
{"type":"assistant","message":{"content":[{"type":"text","text":"ack"}]}}
JSONL

  local count
  count=$(python3 - "$SCRIPT" "$fixture" <<'PY'
import sys, importlib.util
spec = importlib.util.spec_from_file_location("extract_session_feedback", sys.argv[1])
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
print(mod.count_real_user_turns(sys.argv[2]))
PY
)
  assert_eq \
    "count_real_user_turns > should count a real user prose turn but not a tool_result, meta, slash-command, or compaction-summary turn" \
    "1" "$count"
}

it_should_reject_the_removed_session_id_project_dir_and_cwd_flags_with_a_nonzero_exit
it_should_select_every_transcript_in_the_since_window_with_turns_gte_2
it_should_print_the_corpus_survey_before_emitting_any_session_content
it_should_group_learnings_and_turns_per_session_in_session_order
it_should_exclude_the_running_sessions_own_transcript_even_when_it_qualifies
it_should_default_since_to_7_days_when_omitted
it_should_report_zero_qualifying_sessions_without_a_survey_estimate_of_zero
it_should_silently_skip_a_malformed_trailing_jsonl_line
it_should_truncate_a_user_turn_at_the_char_cap_while_still_counting_it
it_count_real_user_turns_should_count_only_real_user_prose_turns

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
