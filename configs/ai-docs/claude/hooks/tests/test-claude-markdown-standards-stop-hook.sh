#!/usr/bin/env bash
# Plain-bash test file for
# claude-markdown-standards-stop-hook.sh.
#
# Usage:
#   bash test-claude-markdown-standards-stop-hook.sh
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
# That makes the shared filters observable: the
# working-tree filter, the session filter, and the
# tracked-vs-untracked scope split — the same three
# the comment-format sibling covers.
#
# This hook adds one more surface the sibling does
# not have: per-file decision memory at
# /tmp/claude-md-fixer-decisions-<session_id>.
#
# So this file also covers the Scout the reason asks
# for, skip-drops, a stale delegate line staying
# inert, a mixed skip+new file set, and the
# no-place-to-record corner.
#
# The checkers themselves are NOT stubbed: these
# tests assert the hook's filtering and memory
# logic, and a stub that always reports a violation
# would assert both away.

set -uo pipefail

hooks_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOK="$hooks_dir/claude-markdown-standards-stop-hook.sh"

# pwd -P resolves /var -> /private/var on macOS.
#
# The hook compares transcript paths against
# `git rev-parse --show-toplevel`, always physical.
#
# An unresolved work_dir would match nothing, so
# every block case would become a false pass.
work_dir=$(cd "$(mktemp -d)" && pwd -P)

# Decision-memory files live at a fixed /tmp path keyed
# only by session_id (the hook does not accept an
# override), so every test that writes one picks its
# own session_id.
#
# This list is swept both before and after the run — a
# leftover file from an interrupted earlier run would
# silently change "no recorded answer" into "already
# decided" for the same session_id.
decision_session_ids=(
  new skip delegate mixed
)
sweep_decision_files() {
  local sid
  for sid in "${decision_session_ids[@]}"; do
    rm -f "/tmp/claude-md-fixer-decisions-${sid}"
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
# reason-text checks, where the exact string is
# long and mostly not the point of the assertion).
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

# write_clean_base - writes a violation-free
# markdown file and commits it, so a later append is
# the only thing git reports as added.
write_clean_base() {
  local repo="$1" name="$2"
  printf '# Title\n\nA short clean line.\n' > "$repo/$name"
  git -C "$repo" add "$name"
  git -C "$repo" commit -q -m base
}

# write_base_with_violation - writes a markdown file
# whose base commit ALREADY contains a density
# violation.
#
# A later clean append is the only thing git reports
# as added, while the violation itself predates this
# session.
write_base_with_violation() {
  local repo="$1" name="$2"
  printf '# Title\n\n%s\n' "$(wide_line)" > "$repo/$name"
  git -C "$repo" add "$name"
  git -C "$repo" commit -q -m base
}

# wide_line - 40 words / 200 chars, over the
# density checker's 32-word cap (its default is
# 256 chars / 32 words; either alone trips it).
wide_line() {
  printf 'word %.0s' $(seq 1 40)
}

# append_wide_line - appends a density violation,
# with a blank line on each side so it reads as its
# own paragraph and never merges with neighboring
# content.
append_wide_line() {
  printf '\n%s\n' "$(wide_line)" >> "$1/$2"
}

# append_clean_line - appends a short, non-violating
# paragraph line.
append_clean_line() {
  printf '\nAnother short clean line.\n' >> "$1/$2"
}

# write_bullet_gap_violation - writes a markdown file
# whose only violation is a nested sub-bullet flush
# against its parent's sibling — the bullet-gap
# checker's own rule, not the density checker's.
#
# No line here is over the density cap, so only
# check-bullet-gap.py can make this fixture block —
# proving the hook's second checker is actually wired
# in, not just present in the script.
write_bullet_gap_violation() {
  local repo="$1" name="$2"
  printf '# Doc\n\n- parent\n  - child\n- next parent\n' > "$repo/$name"
}

# write_lazy_continuation_violation - writes a
# markdown file whose only violation is prose indented
# for the numbered item but swallowed by the bullet
# above it — the lazy-continuation checker's own rule.
#
# Every line is short and no bullet sits flush against
# a sibling, so neither check-density.sh nor
# check-bullet-gap.py fires here.
#
# Verified directly against both before writing this
# fixture — only check-lazy-continuation.py can
# make it block.
write_lazy_continuation_violation() {
  local repo="$1" name="$2"
  printf '# Doc\n\n1. numbered item\n   - pointer bullet\n   absorbed prose line\n' > "$repo/$name"
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
  printf '/tmp/claude-md-fixer-decisions-%s\n' "$1"
}

# run_hook - runs the hook from inside the given
# repo, capturing stdout in HOOK_OUT and the decoded
# reason (empty when it stayed silent) in
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

# An untracked file is new in full, so every line in
# it counts as written this session.
it_should_block_on_an_untracked_markdown_file_this_session_wrote() {
  local repo; repo=$(new_repo untracked)
  write_clean_base "$repo" base.md
  printf '# New doc\n\n%s\n' "$(wide_line)" > "$repo/new.md"
  local t; t=$(write_transcript "$repo/transcript.jsonl" "$repo/new.md")
  run_hook "$repo" "{\"session_id\":\"untracked-case\",\"stop_hook_active\":false,\"transcript_path\":\"$t\"}"

  assert_eq "should block on an untracked markdown file this session wrote (decision)" \
    "block" "$(printf '%s' "$HOOK_OUT" | jq -r '.decision // empty')"
  assert_eq "should block on an untracked markdown file this session wrote (names the file)" \
    "1" "$(printf '%s' "$HOOK_REASON" | grep -c 'new\.md')"
}

# Two checkers feed one gate: this proves
# check-bullet-gap.py alone can trigger a block, on a
# fixture the density checker stays clean on (verified
# directly against both checkers before writing this).
it_should_block_on_a_bullet_gap_violation_the_density_checker_would_miss() {
  local repo; repo=$(new_repo bullet-gap)
  write_clean_base "$repo" base.md
  write_bullet_gap_violation "$repo" new.md
  local t; t=$(write_transcript "$repo/transcript.jsonl" "$repo/new.md")
  run_hook "$repo" "{\"session_id\":\"bullet-gap-case\",\"stop_hook_active\":false,\"transcript_path\":\"$t\"}"

  assert_eq "should block on a bullet-gap violation the density checker would miss" \
    "block" "$(printf '%s' "$HOOK_OUT" | jq -r '.decision // empty')"
}

# Three checkers feed one gate: this proves
# check-lazy-continuation.py alone can trigger a
# block, on a fixture the other two stay clean on.
#
# The defect it guards inverts a sentence's meaning
# rather than merely reading long, so an unwired
# checker here ships a rendered lie.
it_should_block_on_a_lazy_continuation_the_other_checkers_would_miss() {
  local repo; repo=$(new_repo lazy-continuation)
  write_clean_base "$repo" base.md
  write_lazy_continuation_violation "$repo" new.md
  local t; t=$(write_transcript "$repo/transcript.jsonl" "$repo/new.md")
  run_hook "$repo" "{\"session_id\":\"lazy-continuation-case\",\"stop_hook_active\":false,\"transcript_path\":\"$t\"}"

  assert_eq "should block on a lazy continuation the other checkers would miss" \
    "block" "$(printf '%s' "$HOOK_OUT" | jq -r '.decision // empty')"
}

# The diff filter's positive case: a violation the
# session actually added to a tracked file is in
# git's added-lines set, so it gates.
it_should_block_on_a_violation_added_to_a_tracked_markdown_file() {
  local repo; repo=$(new_repo tracked-added)
  write_clean_base "$repo" tracked.md
  append_wide_line "$repo" tracked.md
  local t; t=$(write_transcript "$repo/transcript.jsonl" "$repo/tracked.md")
  run_hook "$repo" "{\"session_id\":\"tracked-added-case\",\"stop_hook_active\":false,\"transcript_path\":\"$t\"}"

  assert_eq "should block on a violation added to a tracked markdown file (decision)" \
    "block" "$(printf '%s' "$HOOK_OUT" | jq -r '.decision // empty')"
  assert_eq "should block on a violation added to a tracked markdown file (names the file)" \
    "1" "$(printf '%s' "$HOOK_REASON" | grep -c 'tracked\.md')"
}

# The diff filter's negative case: the violation
# already sat in HEAD before this session touched the
# file.
#
# Intersecting it with git's added-lines set for the
# session's own (clean) append drops it — a
# pre-existing long line in a file you merely touched
# must never block.
it_should_stay_silent_on_a_preexisting_violation_the_session_did_not_add() {
  local repo; repo=$(new_repo tracked-preexisting)
  write_base_with_violation "$repo" tracked.md
  append_clean_line "$repo" tracked.md
  local t; t=$(write_transcript "$repo/transcript.jsonl" "$repo/tracked.md")
  run_hook "$repo" "{\"session_id\":\"preexisting-case\",\"stop_hook_active\":false,\"transcript_path\":\"$t\"}"

  assert_eq "should stay silent on a preexisting violation the session did not add" "" "$HOOK_OUT"
}

# Without the session filter, every concurrent
# session would see the same shared working-tree
# violations and each spawn its own fixer for files
# it never touched.
it_should_not_block_on_a_violating_file_this_session_never_touched() {
  local repo; repo=$(new_repo untouched)
  write_clean_base "$repo" tracked.md
  append_wide_line "$repo" tracked.md
  printf '# Unrelated\n\nClean.\n' > "$repo/edited.md"
  local t; t=$(write_transcript "$repo/transcript.jsonl" "$repo/edited.md")
  run_hook "$repo" "{\"session_id\":\"untouched-case\",\"stop_hook_active\":false,\"transcript_path\":\"$t\"}"

  assert_eq "should not block on a violating file this session never touched" "" "$HOOK_OUT"
}

# Loop guard: the hook cannot re-verify its own fix,
# so it must bow out on the stop its own block caused
# — otherwise an always-on gate spins forever.
it_should_stay_silent_when_its_own_block_caused_this_stop() {
  local repo; repo=$(new_repo loop-guard)
  write_clean_base "$repo" tracked.md
  append_wide_line "$repo" tracked.md
  local t; t=$(write_transcript "$repo/transcript.jsonl" "$repo/tracked.md")
  run_hook "$repo" "{\"session_id\":\"loop-guard-case\",\"stop_hook_active\":true,\"transcript_path\":\"$t\"}"

  assert_eq "should stay silent when its own block caused this stop" "" "$HOOK_OUT"
}

# A missing session signal must fail open to "no
# block", NOT widen the scope to the whole working
# tree.
it_should_stay_silent_when_the_transcript_is_missing() {
  local repo; repo=$(new_repo no-transcript)
  write_clean_base "$repo" tracked.md
  append_wide_line "$repo" tracked.md
  run_hook "$repo" '{"session_id":"no-transcript-case","stop_hook_active":false}'

  assert_eq "should stay silent when the transcript is missing" "" "$HOOK_OUT"
}

it_should_stay_silent_when_the_session_touched_no_markdown_file() {
  local repo; repo=$(new_repo non-md-only)
  write_clean_base "$repo" tracked.md
  append_wide_line "$repo" tracked.md
  printf '#!/usr/bin/env bash\necho hi\n' > "$repo/script.sh"
  local t; t=$(write_transcript "$repo/transcript.jsonl" "$repo/script.sh")
  run_hook "$repo" "{\"session_id\":\"non-md-case\",\"stop_hook_active\":false,\"transcript_path\":\"$t\"}"

  assert_eq "should stay silent when the session touched no markdown file" "" "$HOOK_OUT"
}

# Decision memory, case 1: a file with no recorded
# answer this session is reported as a [Scout].
#
# The user alone decides if and when a Scout runs, so
# the reason must file one and dispatch nothing — it
# must not ask at hook time either, since a Stop hook
# has no interactive channel to ask through.
#
# A valid session_id gives the hook a place to persist
# the suppression, so the reason also names it.
it_should_tell_the_session_to_file_a_scout_for_a_file_with_no_recorded_decision() {
  local repo; repo=$(new_repo new-file)
  write_clean_base "$repo" tracked.md
  append_wide_line "$repo" tracked.md
  local t; t=$(write_transcript "$repo/transcript.jsonl" "$repo/tracked.md")
  run_hook "$repo" "{\"session_id\":\"new\",\"stop_hook_active\":false,\"transcript_path\":\"$t\"}"

  assert_eq "should tell the session to file a Scout for a file with no recorded decision (decision)" \
    "block" "$(printf '%s' "$HOOK_OUT" | jq -r '.decision // empty')"
  assert_contains "should tell the session to file a Scout for a file with no recorded decision (names the Scout category)" \
    "$HOOK_REASON" "[Scout]"
  assert_not_contains "should tell the session to file a Scout for a file with no recorded decision (never asks the user)" \
    "$HOOK_REASON" "Ask the user"
  assert_not_contains "should tell the session to file a Scout for a file with no recorded decision (never says delegate)" \
    "$HOOK_REASON" "delegate"
  assert_contains "should tell the session to file a Scout for a file with no recorded decision (forbids dispatching now)" \
    "$HOOK_REASON" "Dispatch nothing now"
  assert_contains "should tell the session to file a Scout for a file with no recorded decision (tells where to append the skip)" \
    "$HOOK_REASON" "append 'skip:<abs path>' for each file to $(decisions_file_path new)"
}

# Decision memory, case 2: a file the user already
# declined this session is dropped from violations
# outright — a company doc declined once must never
# be re-blocked for the rest of the session.
it_should_stay_silent_on_a_file_recorded_as_skip_this_session() {
  local repo; repo=$(new_repo skip-file)
  write_clean_base "$repo" tracked.md
  append_wide_line "$repo" tracked.md
  local t; t=$(write_transcript "$repo/transcript.jsonl" "$repo/tracked.md")
  printf 'skip:%s/tracked.md\n' "$repo" > "$(decisions_file_path skip)"
  run_hook "$repo" "{\"session_id\":\"skip\",\"stop_hook_active\":false,\"transcript_path\":\"$t\"}"

  assert_eq "should stay silent on a file recorded as skip this session" "" "$HOOK_OUT"
}

# Decision memory, case 3: `delegate:` was the
# approval flow's verb, and nothing writes it any
# more.
#
# A line left over from a session that ran the old
# hook must be inert: `skip:` is now the only verb
# that suppresses, so a `delegate:` file still gets
# its Scout filed.
it_should_ignore_a_stale_delegate_line_left_by_the_removed_approval_flow() {
  local repo; repo=$(new_repo delegate-file)
  write_clean_base "$repo" tracked.md
  append_wide_line "$repo" tracked.md
  local t; t=$(write_transcript "$repo/transcript.jsonl" "$repo/tracked.md")
  printf 'delegate:%s/tracked.md\n' "$repo" > "$(decisions_file_path delegate)"
  run_hook "$repo" "{\"session_id\":\"delegate\",\"stop_hook_active\":false,\"transcript_path\":\"$t\"}"

  assert_eq "should ignore a stale delegate line left by the removed approval flow (still blocks)" \
    "block" "$(printf '%s' "$HOOK_OUT" | jq -r '.decision // empty')"
  assert_not_contains "should ignore a stale delegate line left by the removed approval flow (never says already approved)" \
    "$HOOK_REASON" "Already approved"
  assert_contains "should ignore a stale delegate line left by the removed approval flow (still tells to file a Scout)" \
    "$HOOK_REASON" "[Scout]"
}

# Decision memory, case 4: a skip decision is
# per-file, not per-session — one already-reported
# doc must not silence the gate for a second file
# with no recorded answer.
it_should_only_file_a_scout_for_the_undecided_file_when_one_of_two_is_skipped() {
  local repo; repo=$(new_repo mixed-file)
  write_clean_base "$repo" skipped.md
  append_wide_line "$repo" skipped.md
  write_clean_base "$repo" pending.md
  append_wide_line "$repo" pending.md
  local t; t=$(write_transcript "$repo/transcript.jsonl" "$repo/skipped.md" "$repo/pending.md")
  printf 'skip:%s/skipped.md\n' "$repo" > "$(decisions_file_path mixed)"
  run_hook "$repo" "{\"session_id\":\"mixed\",\"stop_hook_active\":false,\"transcript_path\":\"$t\"}"

  assert_eq "should only file a Scout for the undecided file when one of two is skipped (decision)" \
    "block" "$(printf '%s' "$HOOK_OUT" | jq -r '.decision // empty')"
  assert_eq "should only file a Scout for the undecided file when one of two is skipped (names the pending file)" \
    "1" "$(printf '%s' "$HOOK_REASON" | grep -c 'pending\.md')"
  assert_eq "should only file a Scout for the undecided file when one of two is skipped (never names the skipped file)" \
    "0" "$(printf '%s' "$HOOK_REASON" | grep -c 'skipped\.md')"
}

# A missing session_id leaves the hook nowhere to
# persist the `skip:` record (case "" in its own
# guard).
#
# `skip:` is the only thing that stops a block from
# repeating, so blocking without it would re-file the
# same Scout on every later Stop. The gate goes
# silent instead.
it_should_stay_silent_when_session_id_gives_it_nowhere_to_record_the_skip() {
  local repo; repo=$(new_repo no-session-id)
  write_clean_base "$repo" tracked.md
  append_wide_line "$repo" tracked.md
  local t; t=$(write_transcript "$repo/transcript.jsonl" "$repo/tracked.md")
  run_hook "$repo" "{\"stop_hook_active\":false,\"transcript_path\":\"$t\"}"

  assert_eq "should stay silent when session_id gives it nowhere to record the skip" "" "$HOOK_OUT"
}

it_should_block_on_an_untracked_markdown_file_this_session_wrote
it_should_block_on_a_bullet_gap_violation_the_density_checker_would_miss
it_should_block_on_a_lazy_continuation_the_other_checkers_would_miss
it_should_block_on_a_violation_added_to_a_tracked_markdown_file
it_should_stay_silent_on_a_preexisting_violation_the_session_did_not_add
it_should_not_block_on_a_violating_file_this_session_never_touched
it_should_stay_silent_when_its_own_block_caused_this_stop
it_should_stay_silent_when_the_transcript_is_missing
it_should_stay_silent_when_the_session_touched_no_markdown_file
it_should_tell_the_session_to_file_a_scout_for_a_file_with_no_recorded_decision
it_should_stay_silent_on_a_file_recorded_as_skip_this_session
it_should_ignore_a_stale_delegate_line_left_by_the_removed_approval_flow
it_should_only_file_a_scout_for_the_undecided_file_when_one_of_two_is_skipped
it_should_stay_silent_when_session_id_gives_it_nowhere_to_record_the_skip

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
