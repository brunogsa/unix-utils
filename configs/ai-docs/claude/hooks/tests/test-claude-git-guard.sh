#!/usr/bin/env bash
# Plain-bash test file for claude-git-guard.sh.
#
# Usage:
#   bash test-claude-git-guard.sh
#
# Exits 0 when every assertion passes, non-zero
# otherwise. No bats dependency by design — three
# small scripts don't justify a new cross-platform
# test-runner dependency in install.sh.

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$script_dir/claude-git-guard.sh"

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

# run_hook - invokes the hook with the given command
# string, wrapped into the PreToolUse JSON shape.
# Captures exit code into HOOK_EXIT (0 = allowed, 2 =
# blocked); stderr is discarded, no test asserts on it.
bash_bin="$(command -v bash)"

run_hook() {
  local command="$1" stdin_json
  stdin_json=$(jq -n --arg c "$command" '{tool_input: {command: $c}}')
  printf '%s' "$stdin_json" | "$bash_bin" "$SCRIPT" >/dev/null 2>&1
  HOOK_EXIT=$?
}

it_should_allow_a_plain_git_status() {
  run_hook "git status"
  assert_eq "should allow a plain git status" "0" "$HOOK_EXIT"
}

it_should_block_git_push_force() {
  run_hook "git push --force"
  assert_eq "should block git push --force" "2" "$HOOK_EXIT"
}

it_should_block_git_reset_hard() {
  run_hook "git reset --hard"
  assert_eq "should block git reset --hard" "2" "$HOOK_EXIT"
}

it_should_block_git_branch_capital_d() {
  run_hook "git branch -D foo"
  assert_eq "should block git branch -D" "2" "$HOOK_EXIT"
}

it_should_block_git_clean_fd() {
  run_hook "git clean -fd"
  assert_eq "should block git clean -fd" "2" "$HOOK_EXIT"
}

it_should_block_a_direct_aigitcommit_invocation() {
  run_hook "aigitcommit -m foo"
  assert_eq "should block a direct aigitcommit invocation" "2" "$HOOK_EXIT"
}

it_should_block_commit_without_attribution() {
  run_hook "git commit -m fixbug"
  assert_eq "should block a commit without Co-Authored-By attribution" "2" "$HOOK_EXIT"
}

it_should_allow_commit_with_attribution() {
  local msg
  msg=$(printf 'git commit -m "fix bug\n\nCo-Authored-By: Claude Fable 5 <noreply@anthropic.com>"')
  run_hook "$msg"
  assert_eq "should allow a commit whose message carries Co-Authored-By" "0" "$HOOK_EXIT"
}

it_should_allow_a_cat_heredoc_that_only_mentions_a_git_phrase() {
  local cmd
  cmd=$(printf "cat >> /tmp/scratch.md <<'EOF'\nRemember to always add Co-Authored-By when running git commit.\nEOF\n")
  run_hook "$cmd"
  assert_eq "should allow a cat heredoc whose payload text merely mentions git commit" "0" "$HOOK_EXIT"
}

it_should_allow_a_python_heredoc_that_only_mentions_a_git_phrase() {
  local cmd
  cmd=$(printf "python3 - <<'PYEOF'\nprint(\"remember: git commit needs attribution\")\nPYEOF\n")
  run_hook "$cmd"
  assert_eq "should allow a python3 heredoc whose payload text merely mentions git commit" "0" "$HOOK_EXIT"
}

it_should_allow_a_cat_heredoc_fed_through_a_command_substitution() {
  local cmd
  cmd=$(cat <<'OUTER'
echo "$(cat <<'EOF'
fix(x): mentions git push --force in prose
EOF
)"
OUTER
)
  run_hook "$cmd"
  assert_eq "should allow a cat heredoc opened inside a command substitution" "0" "$HOOK_EXIT"
}

it_should_allow_a_dangerous_phrase_inside_a_quoted_argument() {
  run_hook 'echo "the word aigitcommit appears here"'
  assert_eq "should allow a dangerous phrase that only appears inside a quoted argument" "0" "$HOOK_EXIT"
}

it_should_still_block_a_dangerous_git_op_smuggled_through_a_bash_heredoc() {
  local cmd
  cmd=$(printf "bash <<'EOF'\ngit push --force\nEOF\n")
  run_hook "$cmd"
  assert_eq "should still block git push --force smuggled inside a bash-executed heredoc" "2" "$HOOK_EXIT"
}

it_should_allow_a_plain_git_status
it_should_block_git_push_force
it_should_block_git_reset_hard
it_should_block_git_branch_capital_d
it_should_block_git_clean_fd
it_should_block_a_direct_aigitcommit_invocation
it_should_block_commit_without_attribution
it_should_allow_commit_with_attribution
it_should_allow_a_cat_heredoc_that_only_mentions_a_git_phrase
it_should_allow_a_python_heredoc_that_only_mentions_a_git_phrase
it_should_allow_a_cat_heredoc_fed_through_a_command_substitution
it_should_allow_a_dangerous_phrase_inside_a_quoted_argument
it_should_still_block_a_dangerous_git_op_smuggled_through_a_bash_heredoc

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
