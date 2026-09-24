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
# string, wrapped into the PreToolUse JSON shape. An
# optional second arg sets .cwd in that JSON (Claude
# Code's own payload field) to the given directory.
#
# Captures exit code into HOOK_EXIT (0 = allowed, 2 =
# blocked); stderr is discarded, no test asserts on it.
bash_bin="$(command -v bash)"

run_hook() {
  local command="$1" cwd="${2:-}" stdin_json
  if [ -n "$cwd" ]; then
    stdin_json=$(jq -n --arg c "$command" --arg d "$cwd" '{tool_input: {command: $c}, cwd: $d}')
  else
    stdin_json=$(jq -n --arg c "$command" '{tool_input: {command: $c}}')
  fi
  printf '%s' "$stdin_json" | "$bash_bin" "$SCRIPT" >/dev/null 2>&1
  HOOK_EXIT=$?
}

# CLEANUP_DIRS - throwaway repos built by
# make_repo/make_bare_origin, removed on exit regardless of
# pass/fail.
CLEANUP_DIRS=()
cleanup_dirs() {
  local d
  for d in "${CLEANUP_DIRS[@]}"; do
    rm -rf "$d"
  done
}
trap cleanup_dirs EXIT

# make_repo <branch> - creates a throwaway git repo checked out
# on <branch> with one commit, prints its path on stdout.
make_repo() {
  local branch="$1" dir
  dir=$(mktemp -d)
  CLEANUP_DIRS+=("$dir")
  git init -q -b "$branch" "$dir" >/dev/null
  git -c user.name=t -c user.email=t@t -C "$dir" commit -q --allow-empty -m init
  printf '%s' "$dir"
}

# make_bare_origin - creates a throwaway bare repo (an "origin"
# a throwaway repo can push to / track), prints its path on
# stdout.
make_bare_origin() {
  local dir
  dir=$(mktemp -d)
  CLEANUP_DIRS+=("$dir")
  git init -q --bare -b main "$dir" >/dev/null
  printf '%s' "$dir"
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

### Block: explicit refspec variants targeting main/master

it_should_block_git_push_origin_main() {
  run_hook "git push origin main"
  assert_eq "should block git push origin main" "2" "$HOOK_EXIT"
}

it_should_block_git_push_origin_master() {
  run_hook "git push origin master"
  assert_eq "should block git push origin master" "2" "$HOOK_EXIT"
}

it_should_block_git_push_origin_head_colon_main() {
  run_hook "git push origin HEAD:main"
  assert_eq "should block git push origin HEAD:main" "2" "$HOOK_EXIT"
}

it_should_block_git_push_origin_feat_colon_refs_heads_master() {
  run_hook "git push origin feat:refs/heads/master"
  assert_eq "should block git push origin feat:refs/heads/master" "2" "$HOOK_EXIT"
}

it_should_block_git_push_origin_plus_master() {
  run_hook "git push origin +master"
  assert_eq "should block git push origin +master" "2" "$HOOK_EXIT"
}

### Block: remote-delete variants of main/master

it_should_block_git_push_origin_colon_master() {
  run_hook "git push origin :master"
  assert_eq "should block git push origin :master (remote delete)" "2" "$HOOK_EXIT"
}

it_should_block_git_push_origin_delete_master() {
  run_hook "git push origin --delete master"
  assert_eq "should block git push origin --delete master" "2" "$HOOK_EXIT"
}

it_should_block_git_push_origin_dash_d_master() {
  run_hook "git push origin -d master"
  assert_eq "should block git push origin -d master" "2" "$HOOK_EXIT"
}

### Block: bulk-push forms

it_should_block_git_push_all() {
  run_hook "git push --all origin"
  assert_eq "should block git push --all origin" "2" "$HOOK_EXIT"
}

it_should_block_git_push_mirror() {
  run_hook "git push --mirror origin"
  assert_eq "should block git push --mirror origin" "2" "$HOOK_EXIT"
}

### Block: HEAD / implicit pushes resolved against a real repo

it_should_block_push_origin_head_while_on_master() {
  local repo
  repo=$(make_repo master)
  run_hook "git push origin HEAD" "$repo"
  assert_eq "should block git push origin HEAD while the repo is on master" "2" "$HOOK_EXIT"
}

it_should_block_bare_push_via_cwd_while_on_master() {
  local repo
  repo=$(make_repo master)
  run_hook "git push" "$repo"
  assert_eq "should block bare git push while the repo's current branch is master" "2" "$HOOK_EXIT"
}

it_should_block_bare_push_origin_via_cwd_while_on_main() {
  local repo
  repo=$(make_repo main)
  run_hook "git push origin" "$repo"
  assert_eq "should block bare git push origin while the repo's current branch is main" "2" "$HOOK_EXIT"
}

it_should_block_bare_push_whose_upstream_resolves_to_origin_main() {
  local origin repo
  origin=$(make_bare_origin)
  repo=$(mktemp -d)
  CLEANUP_DIRS+=("$repo")
  git init -q -b feat "$repo" >/dev/null
  git -c user.name=t -c user.email=t@t -C "$repo" commit -q --allow-empty -m init
  git -C "$repo" remote add origin "$origin"
  git -C "$repo" push -q origin feat:main
  git -C "$repo" config push.default upstream
  git -C "$repo" branch --set-upstream-to=origin/main feat
  run_hook "git push" "$repo"
  assert_eq "should block a bare git push whose @{push} resolves to origin/main" "2" "$HOOK_EXIT"
}

it_should_block_git_dash_c_push_while_repo_on_master() {
  local repo
  repo=$(make_repo master)
  run_hook "git -C $repo push"
  assert_eq "should block git -C <repo-on-master> push" "2" "$HOOK_EXIT"
}

it_should_block_cd_then_bare_push_while_repo_on_master() {
  local repo
  repo=$(make_repo master)
  run_hook "cd $repo && git push"
  assert_eq "should block cd <repo-on-master> && git push" "2" "$HOOK_EXIT"
}

### Block: shell-fed and prefixed invocations

it_should_block_git_push_main_smuggled_through_bash_heredoc() {
  local cmd
  cmd=$(printf "bash <<'EOF'\ngit push origin main\nEOF\n")
  run_hook "$cmd"
  assert_eq "should block git push origin main smuggled through a bash heredoc" "2" "$HOOK_EXIT"
}

it_should_block_bash_dash_c_push_to_main() {
  run_hook 'bash -c "git push origin main"'
  assert_eq 'should block bash -c "git push origin main"' "2" "$HOOK_EXIT"
}

it_should_block_sh_dash_c_push_to_main() {
  run_hook 'sh -c "git push origin main"'
  assert_eq 'should block sh -c "git push origin main"' "2" "$HOOK_EXIT"
}

it_should_block_rtk_prefixed_push_to_main() {
  run_hook "rtk git push origin main"
  assert_eq "should block rtk git push origin main (transparent prefix)" "2" "$HOOK_EXIT"
}

it_should_block_env_prefixed_push_to_main() {
  run_hook "env FOO=1 git push origin main"
  assert_eq "should block env FOO=1 git push origin main" "2" "$HOOK_EXIT"
}

it_should_block_bare_env_assignment_push_to_main() {
  run_hook "FOO=1 git push origin main"
  assert_eq "should block FOO=1 git push origin main" "2" "$HOOK_EXIT"
}

it_should_block_command_prefixed_push_to_main() {
  run_hook "command git push origin main"
  assert_eq "should block command git push origin main" "2" "$HOOK_EXIT"
}

it_should_block_git_dash_c_config_push_to_main() {
  run_hook "git -c foo=bar push origin main"
  assert_eq "should block git -c foo=bar push origin main" "2" "$HOOK_EXIT"
}

### Block: unresolvable implicit push (fail closed)

it_should_block_implicit_push_with_unresolvable_cwd() {
  run_hook 'cd "$SOMEVAR" && git push'
  assert_eq "should block an implicit push whose cd target cannot be resolved" "2" "$HOOK_EXIT"
}

### Block: unparseable segment naming git and push (fail closed)

it_should_block_unparseable_segment_naming_git_and_push() {
  run_hook 'git push origin "unterminated'
  assert_eq "should block a segment shlex cannot parse that names git and push" "2" "$HOOK_EXIT"
}

### Allow: exact branch-name match only, never substring

it_should_allow_git_push_origin_feature_main_fix() {
  run_hook "git push origin feature/main-fix"
  assert_eq "should allow git push origin feature/main-fix" "0" "$HOOK_EXIT"
}

it_should_allow_git_push_origin_main_v2() {
  run_hook "git push origin main-v2"
  assert_eq "should allow git push origin main-v2" "0" "$HOOK_EXIT"
}

### Allow: feature-branch pushes, with and without upstream

it_should_allow_push_u_origin_feat_from_feature_branch() {
  local repo
  repo=$(make_repo feat)
  run_hook "git push -u origin feat" "$repo"
  assert_eq "should allow git push -u origin feat from a repo on a feature branch" "0" "$HOOK_EXIT"
}

it_should_allow_bare_push_with_no_upstream_from_feature_branch() {
  local repo
  repo=$(make_repo feat)
  run_hook "git push" "$repo"
  assert_eq "should allow a bare git push from a feature branch with no upstream" "0" "$HOOK_EXIT"
}

# ## Allow: value-taking push options must not be miscounted as
# refspecs

it_should_allow_push_option_short_form_to_feature_branch() {
  run_hook "git push -o ci.skip origin feat"
  assert_eq "should allow git push -o ci.skip origin feat" "0" "$HOOK_EXIT"
}

it_should_allow_push_option_long_form_to_feature_branch() {
  run_hook "git push --push-option=x origin feat"
  assert_eq "should allow git push --push-option=x origin feat" "0" "$HOOK_EXIT"
}

it_should_allow_repo_option_to_feature_branch() {
  run_hook "git push --repo=origin feat"
  assert_eq "should allow git push --repo=origin feat" "0" "$HOOK_EXIT"
}

it_should_allow_receive_pack_option_to_feature_branch() {
  run_hook "git push --receive-pack git-receive-pack origin feat"
  assert_eq "should allow git push --receive-pack git-receive-pack origin feat" "0" "$HOOK_EXIT"
}

it_should_allow_push_option_value_named_main_not_counted_as_refspec() {
  run_hook "git push -o main origin feat"
  assert_eq "should allow git push -o main origin feat (main is the -o value, not a refspec)" "0" "$HOOK_EXIT"
}

### Allow: data that merely mentions a push-to-main phrase

it_should_allow_echo_of_push_to_main_as_quoted_data() {
  run_hook 'echo "git push origin main"'
  assert_eq "should allow echo of a quoted git push origin main string" "0" "$HOOK_EXIT"
}

it_should_allow_cat_heredoc_mentioning_push_to_main_as_inert_data() {
  local cmd
  cmd=$(printf "cat <<'EOF'\npush to main later\ngit push origin main\nEOF\n")
  run_hook "$cmd"
  assert_eq "should allow a cat heredoc body that merely mentions git push origin main" "0" "$HOOK_EXIT"
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
it_should_block_git_push_origin_main
it_should_block_git_push_origin_master
it_should_block_git_push_origin_head_colon_main
it_should_block_git_push_origin_feat_colon_refs_heads_master
it_should_block_git_push_origin_plus_master
it_should_block_git_push_origin_colon_master
it_should_block_git_push_origin_delete_master
it_should_block_git_push_origin_dash_d_master
it_should_block_git_push_all
it_should_block_git_push_mirror
it_should_block_push_origin_head_while_on_master
it_should_block_bare_push_via_cwd_while_on_master
it_should_block_bare_push_origin_via_cwd_while_on_main
it_should_block_bare_push_whose_upstream_resolves_to_origin_main
it_should_block_git_dash_c_push_while_repo_on_master
it_should_block_cd_then_bare_push_while_repo_on_master
it_should_block_git_push_main_smuggled_through_bash_heredoc
it_should_block_bash_dash_c_push_to_main
it_should_block_sh_dash_c_push_to_main
it_should_block_rtk_prefixed_push_to_main
it_should_block_env_prefixed_push_to_main
it_should_block_bare_env_assignment_push_to_main
it_should_block_command_prefixed_push_to_main
it_should_block_git_dash_c_config_push_to_main
it_should_block_implicit_push_with_unresolvable_cwd
it_should_block_unparseable_segment_naming_git_and_push
it_should_allow_git_push_origin_feature_main_fix
it_should_allow_git_push_origin_main_v2
it_should_allow_push_u_origin_feat_from_feature_branch
it_should_allow_bare_push_with_no_upstream_from_feature_branch
it_should_allow_push_option_short_form_to_feature_branch
it_should_allow_push_option_long_form_to_feature_branch
it_should_allow_repo_option_to_feature_branch
it_should_allow_receive_pack_option_to_feature_branch
it_should_allow_push_option_value_named_main_not_counted_as_refspec
it_should_allow_echo_of_push_to_main_as_quoted_data
it_should_allow_cat_heredoc_mentioning_push_to_main_as_inert_data

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
