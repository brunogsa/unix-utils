#!/usr/bin/env bash
# Plain-bash test file for claude-rm-guard.sh.
#
# Usage:
#   bash test-claude-rm-guard.sh
#
# Exits 0 when every assertion passes, non-zero
# otherwise. No bats dependency by design — three
# small scripts don't justify a new cross-platform
# test-runner dependency in install.sh.

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$script_dir/claude-rm-guard.sh"

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

bash_bin="$(command -v bash)"

# sandbox_dir - a throwaway git repo the hook's classify()
# step queries via `git ls-files` / `git check-ignore`. The
# hook reads its cwd via os.getcwd(), so run_hook below cd's
# into this dir for every invocation rather than passing cwd
# as a parameter.
sandbox_dir=""

setup_sandbox() {
  sandbox_dir=$(mktemp -d)
  (
    cd "$sandbox_dir" || exit 1
    git init -q
    git config user.email "test@example.com"
    git config user.name "Test"
    mkdir -p src
    printf 'export const x = 1;\n' > src/index.ts
    git add src/index.ts
    git commit -q -m "init"
    # Untracked-and-not-ignored fixture, reused by the "still BLOCKED" tests
    # below: this is the exact case the guard exists to catch (real work with
    # exactly one copy on disk, no git recovery).
    printf 'draft notes, never committed\n' > untracked.md
  )
}

teardown_sandbox() {
  [ -n "$sandbox_dir" ] && rm -rf "$sandbox_dir"
}

# run_hook - invokes the hook, cwd'd into the sandbox repo,
# with the given command string wrapped into the PreToolUse
# JSON shape. Captures exit code into HOOK_EXIT (0 = allowed,
# 2 = blocked); stderr is discarded, no test asserts on it.
run_hook() {
  local command="$1" stdin_json
  stdin_json=$(jq -n --arg c "$command" '{tool_input: {command: $c}}')
  (
    cd "$sandbox_dir" || exit 1
    printf '%s' "$stdin_json" | "$bash_bin" "$SCRIPT" >/dev/null 2>&1
  )
  HOOK_EXIT=$?
}

it_should_allow_a_plain_rm_of_a_tracked_file() {
  run_hook "rm src/index.ts"
  assert_eq "should allow a plain rm of a tracked file (sanity baseline)" "0" "$HOOK_EXIT"
}

# Bug 1 (real, hit live this session): split_segments() splits the ENTIRE raw
# command on newlines with no awareness that lines inside a `<<'EOF' ... EOF`
# heredoc body are literal data, not separate shell segments. A commit
# message body that merely mentions "rm -f" in prose (describing a past
# incident) shattered into many unparseable-looking segments, and the final
# fail-closed regex then found "rm" inside that inert body text and blocked
# a command that never actually invokes rm.
it_should_allow_a_commit_heredoc_whose_body_only_mentions_rm_dash_f_in_prose() {
  local cmd
  cmd=$(cat <<'OUTER'
git commit -m "$(cat <<'EOF'
fix(hook): guard against unrecoverable rm

Historical bug: a background agent once ran rm -f on an untracked file and
the file was gone for good. This commit fixes the root cause.
EOF
)"
OUTER
)
  run_hook "$cmd"
  assert_eq "should allow a git commit heredoc whose body text merely mentions rm -f in prose" "0" "$HOOK_EXIT"
}

# Bug 2 (real, hit live this session): split_segments() splits on a bare `|`
# with no quote-awareness, so an escaped pipe INSIDE a quoted string (e.g. a
# grep alternation pattern) still gets treated as a shell pipe operator. That
# shatters `grep -i "git-guard\|rm-guard"` into two segments, each with an
# unbalanced quote (unparseable). The final fail-closed regex then matched
# "rm" inside the substring "rm-guard" (a bare `\b` treats `-` as a
# word boundary), blocking a command that never invokes rm at all.
it_should_allow_a_hyphenated_identifier_that_merely_contains_rm() {
  run_hook 'grep -i "git-guard\|rm-guard"'
  assert_eq "should allow a command whose only 'rm' substring is inside a hyphenated identifier like rm-guard" "0" "$HOOK_EXIT"
}

# Regression guard: the heredoc-stripping fix for Bug 1 must not weaken the
# fail-closed property for a genuinely dangerous, genuinely unparseable rm.
# Here the REAL `rm -f` invocation is on the heredoc OPENER line (kept, not
# stripped) and that opener line itself has an unbalanced quote — so this
# must still be blocked after the fix.
it_should_still_block_a_real_rm_invocation_on_a_heredoc_opener_line() {
  local cmd
  cmd=$(cat <<'OUTER'
rm -f "$(cat <<'EOF'
/some/untracked/file.md
EOF
)"
OUTER
)
  run_hook "$cmd"
  assert_eq "should still block a real rm -f invocation that appears on a heredoc opener line" "2" "$HOOK_EXIT"
}

# Bug 3 (Scout #45, real, hit live this session): split_segments() splits the
# raw command text on `;`, `|`, `&`, `&&`, `||`, and newline with no
# quote-awareness. The plain text "rm -rf" alone, with no separator-shaped
# character alongside it, never actually shattered split_segments() — this
# case already passed before the fix and is kept here as a regression guard,
# not a bug demonstration. The genuine break needs a separator character
# (`;`, `|`, ...) sitting INSIDE the quotes too, which is what the next test
# reproduces.
it_should_allow_a_grep_search_for_the_double_quoted_string_rm_dash_rf() {
  run_hook 'grep -rn "rm -rf" configs/'
  assert_eq "should allow a grep search whose double-quoted pattern text is 'rm -rf'" "0" "$HOOK_EXIT"
}

# The actual reproduction of bug 3: the "rm -rf" text alone (no shell
# metacharacter alongside it) never tripped split_segments — it takes a
# separator-shaped character (here, `;`) sitting INSIDE the quotes to make
# the quote-unaware regex split cut the command in two mid-string, which is
# what turned this into an unparseable, fail-closed block live this session.
it_should_allow_a_grep_pattern_containing_a_semicolon_inside_double_quotes() {
  run_hook 'grep -rn "rm -rf; keep looking" configs/'
  assert_eq "should allow a grep search whose double-quoted pattern contains a semicolon" "0" "$HOOK_EXIT"
}

it_should_allow_a_grep_alternation_pattern_containing_a_pipe_inside_double_quotes() {
  run_hook 'grep -E -n "rm -rf|delete now" configs/'
  assert_eq "should allow a grep -E search whose double-quoted alternation pattern contains a pipe" "0" "$HOOK_EXIT"
}

it_should_allow_a_grep_search_for_the_single_quoted_string_rm() {
  run_hook "grep -rn 'rm ' ."
  assert_eq "should allow a grep search whose single-quoted pattern text is 'rm '" "0" "$HOOK_EXIT"
}

it_should_allow_an_echo_of_a_sentence_that_mentions_rm() {
  run_hook 'echo "use rm carefully"'
  assert_eq "should allow an echo whose double-quoted argument merely mentions rm" "0" "$HOOK_EXIT"
}

it_should_block_rm_of_a_real_untracked_and_not_ignored_file() {
  run_hook "rm untracked.md"
  assert_eq "should block rm of a real untracked-and-not-ignored file (sanity baseline)" "2" "$HOOK_EXIT"
}

# The quoted "rm" in the grep clause must stay inert data (bug 3 above);
# the real rm after && must still be recognized and blocked (its target is
# the untracked, not-ignored fixture from setup_sandbox — no git copy).
it_should_block_a_real_rm_after_a_command_that_only_quotes_the_word_rm() {
  run_hook 'grep -rn "rm" . && rm untracked.md'
  assert_eq "should still block a real rm after && following a command that only quotes the word rm" "2" "$HOOK_EXIT"
}

it_should_block_an_unterminated_double_quote_that_contains_rm() {
  run_hook 'grep -rn "rm -rf configs/'
  assert_eq "should fail closed and block a command with an unterminated double quote mentioning rm" "2" "$HOOK_EXIT"
}

setup_sandbox

it_should_allow_a_plain_rm_of_a_tracked_file
it_should_allow_a_commit_heredoc_whose_body_only_mentions_rm_dash_f_in_prose
it_should_allow_a_hyphenated_identifier_that_merely_contains_rm
it_should_still_block_a_real_rm_invocation_on_a_heredoc_opener_line
it_should_allow_a_grep_search_for_the_double_quoted_string_rm_dash_rf
it_should_allow_a_grep_pattern_containing_a_semicolon_inside_double_quotes
it_should_allow_a_grep_alternation_pattern_containing_a_pipe_inside_double_quotes
it_should_allow_a_grep_search_for_the_single_quoted_string_rm
it_should_allow_an_echo_of_a_sentence_that_mentions_rm
it_should_block_rm_of_a_real_untracked_and_not_ignored_file
it_should_block_a_real_rm_after_a_command_that_only_quotes_the_word_rm
it_should_block_an_unterminated_double_quote_that_contains_rm

teardown_sandbox

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
