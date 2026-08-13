#!/usr/bin/env bash
# Plain-bash test file for
# claude-comment-format-stop-hook.sh.
#
# Usage:
#   bash test-claude-comment-format-stop-hook.sh
#
# Exits 0 when every assertion passes, non-zero
# otherwise.
#
# Same no-bats rationale as the sibling test files.
#
# How the hook is exercised: it reads a transcript
# path out of its stdin JSON and asks git what
# changed, so each case builds its own throwaway
# repo plus a transcript naming a subset of it.
#
# That makes all three filters observable: the
# working-tree filter, the session filter, and the
# tracked-vs-untracked rule split.
#
# The orchestrator's own test stubs this gate out
# entirely, so nothing else covers them.
#
# The checker itself is NOT stubbed: these tests
# assert the hook's filtering, and a stub that
# always reports a violation would assert the
# filters away.
#
# This hook also carries per-file decision memory at
# /tmp/claude-comment-fixer-decisions-<session_id>, the
# same mechanism the markdown-standards sibling has.
#
# So this file also covers new-file-asks, skip-drops,
# delegate-skips-the-ask, a mixed skip+new file set, and
# the session-id-disables-memory corner.

set -uo pipefail

hooks_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOK="$hooks_dir/claude-comment-format-stop-hook.sh"

# pwd -P resolves /var -> /private/var on macOS.
#
# The hook compares transcript paths against
# `git rev-parse --show-toplevel`, always physical.
#
# An unresolved work_dir would match nothing, so
# every block case would become a false pass.
work_dir=$(cd "$(mktemp -d)" && pwd -P)

# Decision-memory files live at a fixed /tmp path
# keyed only by session_id (the hook does not accept
# an override), so every test that writes one picks
# its own session_id.
#
# This list is swept both before and after the run —
# a leftover file from an interrupted earlier run
# would silently change "no recorded answer" into
# "already decided" for the same session_id.
decision_session_ids=(
  new skip delegate mixed
)
sweep_decision_files() {
  local sid
  for sid in "${decision_session_ids[@]}"; do
    rm -f "/tmp/claude-comment-fixer-decisions-${sid}"
  done
}
cleanup() {
  rm -rf "$work_dir"
  sweep_decision_files
}
trap cleanup EXIT
sweep_decision_files

pass_count=0
fail_count=0

# assert_eq - inline assert helper: compares
# expected vs actual, prints ok/not-ok.
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

# assert_contains - inline assert helper: passes
# when needle is a substring of haystack (used for
# reason-text checks, where the exact string is long
# and mostly not the point of the assertion).
assert_contains() {
  local description="$1" haystack="$2" needle="$3"
  case "$haystack" in
    *"$needle"*)
      pass_count=$((pass_count + 1))
      printf 'ok - %s\n' "$description"
      ;;
    *)
      fail_count=$((fail_count + 1))
      printf 'not ok - %s\n  expected to contain: %s\n  actual:              %s\n' "$description" "$needle" "$haystack"
      ;;
  esac
}

# assert_not_contains - the inverse of assert_contains
# (used to prove a reason text does NOT re-ask or
# re-mention record instructions once a decision is
# already known).
assert_not_contains() {
  local description="$1" haystack="$2" needle="$3"
  case "$haystack" in
    *"$needle"*)
      fail_count=$((fail_count + 1))
      printf 'not ok - %s\n  expected to NOT contain: %s\n  actual:                  %s\n' "$description" "$needle" "$haystack"
      ;;
    *)
      pass_count=$((pass_count + 1))
      printf 'ok - %s\n' "$description"
      ;;
  esac
}

# new_repo - creates an empty git repo under
# work_dir and prints its path. Identity is set
# locally so the fixture commit never depends on
# the machine's global git config.
new_repo() {
  local dir="$work_dir/$1"
  mkdir -p "$dir"
  git -C "$dir" init -q .
  git -C "$dir" config user.email test@example.com
  git -C "$dir" config user.name test
  printf '%s' "$dir"
}

# write_clean_base - writes a violation-free source
# file and commits it, so a later append is the
# only thing git reports as added.
write_clean_base() {
  local repo="$1" name="$2"
  printf '#!/usr/bin/env bash\n\necho one\n' > "$repo/$name"
  git -C "$repo" add "$name"
  git -C "$repo" commit -q -m base
}

# append_wide_comment - appends a comment line over
# the 64-char cap, which the checker reports as
# WIDTH: a line-local rule, so it gates on a
# tracked file's added lines.
append_wide_comment() {
  printf '\n# This appended comment line is definitely longer than the sixty-four cap.\n' >> "$1/$2"
}

# append_long_paragraph - appends a 5-line comment
# paragraph of short lines, which the checker
# reports as PARAGRAPH alone.
#
# The surrounding blank lines keep CODE-GAP from
# firing too, since that one IS line-local and
# would mask the rule split this fixture exposes.
append_long_paragraph() {
  printf '\n# One.\n# Two.\n# Three.\n# Four.\n# Five.\n\necho two\n' >> "$1/$2"
}

# write_transcript - writes a transcript naming the
# given absolute paths as this session's own Edit
# tool calls. Prints the transcript path.
write_transcript() {
  local out="$1"; shift
  : > "$out"
  local p
  for p in "$@"; do
    printf '{"message":{"content":[{"type":"tool_use","name":"Edit","input":{"file_path":"%s"}}]}}\n' "$p" >> "$out"
  done
  printf '%s' "$out"
}

# decisions_file_path - the fixed /tmp path the hook
# reads and writes for a given session_id.
#
# Tests write directly to it to simulate "the main
# session already recorded an answer for this file",
# since the hook itself never writes this file — only
# reads it.
decisions_file_path() {
  printf '/tmp/claude-comment-fixer-decisions-%s\n' "$1"
}

# run_hook - runs the hook from inside the given
# repo, capturing stdout in HOOK_OUT and the
# decoded reason (empty when it stayed silent) in
# HOOK_REASON.
#
# The cd matters: the hook resolves its own repo
# root from the caller's working directory, so
# running it from anywhere else would measure this
# repo instead of the fixture.
run_hook() {
  local repo="$1" stdin_json="$2"
  HOOK_OUT=$(cd "$repo" && printf '%s' "$stdin_json" | bash "$HOOK" 2>/dev/null)
  HOOK_REASON=$(printf '%s' "$HOOK_OUT" | jq -r '.reason // empty' 2>/dev/null || true)
}

# An untracked file is new in full, so every line
# in it counts as written this session.
it_should_block_on_an_untracked_source_file_this_session_wrote() {
  local repo; repo=$(new_repo untracked-width)
  write_clean_base "$repo" base.sh
  printf '#!/usr/bin/env bash\n\n# This new comment line is longer than the sixty-four character cap.\necho hi\n' > "$repo/new.sh"
  local t; t=$(write_transcript "$repo/transcript.jsonl" "$repo/new.sh")
  run_hook "$repo" "{\"session_id\":\"s\",\"stop_hook_active\":false,\"transcript_path\":\"$t\"}"

  assert_eq "should block on an untracked source file this session wrote (decision)" \
    "block" "$(printf '%s' "$HOOK_OUT" | jq -r '.decision // empty')"
  assert_eq "should block on an untracked source file this session wrote (names the file)" \
    "1" "$(printf '%s' "$HOOK_REASON" | grep -c 'new\.sh')"
}

# The other half of the rule split: no line in an
# untracked file predates this session, so the
# range rule PARAGRAPH gates there even though the
# tracked case below drops it.
it_should_block_on_a_paragraph_violation_in_an_untracked_file() {
  local repo; repo=$(new_repo untracked-paragraph)
  write_clean_base "$repo" base.sh
  printf '#!/usr/bin/env bash\n\n# One.\n# Two.\n# Three.\n# Four.\n# Five.\n\necho hi\n' > "$repo/new.sh"
  local t; t=$(write_transcript "$repo/transcript.jsonl" "$repo/new.sh")
  run_hook "$repo" "{\"session_id\":\"s\",\"stop_hook_active\":false,\"transcript_path\":\"$t\"}"

  assert_eq "should block on a paragraph violation in an untracked file" \
    "block" "$(printf '%s' "$HOOK_OUT" | jq -r '.decision // empty')"
}

# WIDTH's fix stays on the flagged line, so it is
# one of the four rules a tracked file admits.
it_should_block_on_a_width_violation_added_to_a_tracked_file() {
  local repo; repo=$(new_repo tracked-width)
  write_clean_base "$repo" tracked.sh
  append_wide_comment "$repo" tracked.sh
  local t; t=$(write_transcript "$repo/transcript.jsonl" "$repo/tracked.sh")
  run_hook "$repo" "{\"session_id\":\"s\",\"stop_hook_active\":false,\"transcript_path\":\"$t\"}"

  assert_eq "should block on a width violation added to a tracked file (decision)" \
    "block" "$(printf '%s' "$HOOK_OUT" | jq -r '.decision // empty')"
  assert_eq "should block on a width violation added to a tracked file (names the file)" \
    "1" "$(printf '%s' "$HOOK_REASON" | grep -c 'tracked\.sh')"
}

# PARAGRAPH carries a line RANGE, so honoring it on
# a tracked file would demand rewriting lines the
# session never wrote.
#
# The paragraph's anchor line IS among git's added
# lines here, so only the rule split - not the diff
# filter - can keep this silent.
it_should_stay_silent_on_a_paragraph_violation_added_to_a_tracked_file() {
  local repo; repo=$(new_repo tracked-paragraph)
  write_clean_base "$repo" tracked.sh
  append_long_paragraph "$repo" tracked.sh
  local t; t=$(write_transcript "$repo/transcript.jsonl" "$repo/tracked.sh")
  run_hook "$repo" "{\"session_id\":\"s\",\"stop_hook_active\":false,\"transcript_path\":\"$t\"}"

  assert_eq "should stay silent on a paragraph violation added to a tracked file" "" "$HOOK_OUT"
}

# Without the session filter, every concurrent
# session would see the same shared working-tree
# violations and each spawn its own fixer for files
# it never touched.
it_should_not_block_on_a_violating_file_this_session_never_touched() {
  local repo; repo=$(new_repo untouched)
  write_clean_base "$repo" tracked.sh
  append_wide_comment "$repo" tracked.sh
  printf '#!/usr/bin/env bash\n\necho unrelated\n' > "$repo/edited.sh"
  local t; t=$(write_transcript "$repo/transcript.jsonl" "$repo/edited.sh")
  run_hook "$repo" "{\"session_id\":\"s\",\"stop_hook_active\":false,\"transcript_path\":\"$t\"}"

  assert_eq "should not block on a violating file this session never touched" "" "$HOOK_OUT"
}

# Loop guard: the hook cannot re-verify its own
# fix, so it must bow out on the stop its own block
# caused - otherwise an always-on gate spins
# forever.
it_should_stay_silent_when_its_own_block_caused_this_stop() {
  local repo; repo=$(new_repo loop-guard)
  write_clean_base "$repo" tracked.sh
  append_wide_comment "$repo" tracked.sh
  local t; t=$(write_transcript "$repo/transcript.jsonl" "$repo/tracked.sh")
  run_hook "$repo" "{\"session_id\":\"s\",\"stop_hook_active\":true,\"transcript_path\":\"$t\"}"

  assert_eq "should stay silent when its own block caused this stop" "" "$HOOK_OUT"
}

# A missing session signal must fail open to "no
# block", NOT widen the scope to the whole working
# tree.
it_should_stay_silent_when_the_transcript_is_missing() {
  local repo; repo=$(new_repo no-transcript)
  write_clean_base "$repo" tracked.sh
  append_wide_comment "$repo" tracked.sh
  run_hook "$repo" '{"session_id":"s","stop_hook_active":false}'

  assert_eq "should stay silent when the transcript is missing" "" "$HOOK_OUT"
}

it_should_stay_silent_when_the_session_touched_no_source_file() {
  local repo; repo=$(new_repo docs-only)
  write_clean_base "$repo" tracked.sh
  append_wide_comment "$repo" tracked.sh
  printf 'not a source file\n' > "$repo/README.md"
  local t; t=$(write_transcript "$repo/transcript.jsonl" "$repo/README.md")
  run_hook "$repo" "{\"session_id\":\"s\",\"stop_hook_active\":false,\"transcript_path\":\"$t\"}"

  assert_eq "should stay silent when the session touched no source file" "" "$HOOK_OUT"
}

# Decision memory, case 1: a file with no recorded
# answer this session is asked about.
#
# Because a valid session_id gives the hook a place to
# persist the answer, the reason also tells the main
# session where to record it.
it_should_ask_about_a_file_with_no_recorded_decision_this_session() {
  local repo; repo=$(new_repo new-file)
  write_clean_base "$repo" tracked.sh
  append_wide_comment "$repo" tracked.sh
  local t; t=$(write_transcript "$repo/transcript.jsonl" "$repo/tracked.sh")
  run_hook "$repo" "{\"session_id\":\"new\",\"stop_hook_active\":false,\"transcript_path\":\"$t\"}"

  assert_eq "should ask about a file with no recorded decision (decision)" \
    "block" "$(printf '%s' "$HOOK_OUT" | jq -r '.decision // empty')"
  assert_contains "should ask about a file with no recorded decision (asks the user)" \
    "$HOOK_REASON" "Ask the user whether to delegate"
  assert_contains "should ask about a file with no recorded decision (tells where to record the answer)" \
    "$HOOK_REASON" "append 'delegate:<abs path>' or 'skip:<abs path>' to $(decisions_file_path new)"
}

# Decision memory, case 2: a file the user already
# declined this session is dropped from violations
# outright.
#
# A vendored/generated source file declined once must
# never be re-blocked for the rest of the session.
it_should_stay_silent_on_a_file_recorded_as_skip_this_session() {
  local repo; repo=$(new_repo skip-file)
  write_clean_base "$repo" tracked.sh
  append_wide_comment "$repo" tracked.sh
  local t; t=$(write_transcript "$repo/transcript.jsonl" "$repo/tracked.sh")
  printf 'skip:%s/tracked.sh\n' "$repo" > "$(decisions_file_path skip)"
  run_hook "$repo" "{\"session_id\":\"skip\",\"stop_hook_active\":false,\"transcript_path\":\"$t\"}"

  assert_eq "should stay silent on a file recorded as skip this session" "" "$HOOK_OUT"
}

# Decision memory, case 3: a file already approved for
# delegation this session is delegated directly — the
# reason must not ask again.
it_should_delegate_directly_for_a_file_recorded_as_delegate_this_session() {
  local repo; repo=$(new_repo delegate-file)
  write_clean_base "$repo" tracked.sh
  append_wide_comment "$repo" tracked.sh
  local t; t=$(write_transcript "$repo/transcript.jsonl" "$repo/tracked.sh")
  printf 'delegate:%s/tracked.sh\n' "$repo" > "$(decisions_file_path delegate)"
  run_hook "$repo" "{\"session_id\":\"delegate\",\"stop_hook_active\":false,\"transcript_path\":\"$t\"}"

  assert_eq "should delegate directly for a file recorded as delegate this session (decision)" \
    "block" "$(printf '%s' "$HOOK_OUT" | jq -r '.decision // empty')"
  assert_contains "should delegate directly for a file recorded as delegate this session (says already approved)" \
    "$HOOK_REASON" "Already approved this session — delegate directly, no need to ask again"
  assert_not_contains "should delegate directly for a file recorded as delegate this session (does not ask again)" \
    "$HOOK_REASON" "Ask the user whether to delegate"
}

# Decision memory, case 4: a skip decision is
# per-file, not per-session — one declined vendored
# file must not silence the gate for a second file
# with no recorded answer.
it_should_only_ask_about_the_undecided_file_when_one_of_two_is_skipped() {
  local repo; repo=$(new_repo mixed-file)
  write_clean_base "$repo" skipped.sh
  append_wide_comment "$repo" skipped.sh
  write_clean_base "$repo" pending.sh
  append_wide_comment "$repo" pending.sh
  local t; t=$(write_transcript "$repo/transcript.jsonl" "$repo/skipped.sh" "$repo/pending.sh")
  printf 'skip:%s/skipped.sh\n' "$repo" > "$(decisions_file_path mixed)"
  run_hook "$repo" "{\"session_id\":\"mixed\",\"stop_hook_active\":false,\"transcript_path\":\"$t\"}"

  assert_eq "should only ask about the undecided file when one of two is skipped (decision)" \
    "block" "$(printf '%s' "$HOOK_OUT" | jq -r '.decision // empty')"
  assert_eq "should only ask about the undecided file when one of two is skipped (names the pending file)" \
    "1" "$(printf '%s' "$HOOK_REASON" | grep -c 'pending\.sh')"
  assert_eq "should only ask about the undecided file when one of two is skipped (never names the skipped file)" \
    "0" "$(printf '%s' "$HOOK_REASON" | grep -c 'skipped\.sh')"
}

# A missing session_id disables the memory feature
# entirely (case "" in the hook's own guard).
#
# The gate still fires every time, it just never
# learns a file was already decided and never tells
# the main session where to persist an answer.
it_should_never_reference_decision_memory_when_session_id_is_missing() {
  local repo; repo=$(new_repo no-session-id)
  write_clean_base "$repo" tracked.sh
  append_wide_comment "$repo" tracked.sh
  local t; t=$(write_transcript "$repo/transcript.jsonl" "$repo/tracked.sh")
  run_hook "$repo" "{\"stop_hook_active\":false,\"transcript_path\":\"$t\"}"

  assert_eq "should never reference decision memory when session_id is missing (still blocks)" \
    "block" "$(printf '%s' "$HOOK_OUT" | jq -r '.decision // empty')"
  assert_contains "should never reference decision memory when session_id is missing (still asks)" \
    "$HOOK_REASON" "Ask the user whether to delegate"
  assert_not_contains "should never reference decision memory when session_id is missing (no record instruction)" \
    "$HOOK_REASON" "Record the answer"
}

it_should_block_on_an_untracked_source_file_this_session_wrote
it_should_block_on_a_paragraph_violation_in_an_untracked_file
it_should_block_on_a_width_violation_added_to_a_tracked_file
it_should_stay_silent_on_a_paragraph_violation_added_to_a_tracked_file
it_should_not_block_on_a_violating_file_this_session_never_touched
it_should_stay_silent_when_its_own_block_caused_this_stop
it_should_stay_silent_when_the_transcript_is_missing
it_should_stay_silent_when_the_session_touched_no_source_file
it_should_ask_about_a_file_with_no_recorded_decision_this_session
it_should_stay_silent_on_a_file_recorded_as_skip_this_session
it_should_delegate_directly_for_a_file_recorded_as_delegate_this_session
it_should_only_ask_about_the_undecided_file_when_one_of_two_is_skipped
it_should_never_reference_decision_memory_when_session_id_is_missing

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
