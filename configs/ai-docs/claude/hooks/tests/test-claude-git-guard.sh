#!/usr/bin/env bash
# Plain-bash test file for claude-git-guard.sh.
#
# Usage:
#   bash test-claude-git-guard.sh
#
# Exits 0 when every assertion passes, non-zero
# otherwise. No bats dependency by design - three
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

# make_hook_without_lib - copies claude-git-guard.sh alone
# into a throwaway directory with no lib/ subdirectory.
#
# CLAUDE_HOOKS_DIR (resolved from BASH_SOURCE) then points at
# a location where lib/parse-shell-command.py cannot be
# imported. Prints the copied script's path on stdout.
make_hook_without_lib() {
  local dir
  dir=$(mktemp -d)
  CLEANUP_DIRS+=("$dir")
  cp "$SCRIPT" "$dir/claude-git-guard.sh"
  printf '%s' "$dir/claude-git-guard.sh"
}

# make_hook_without_format_gate - like make_hook_without_lib,
# but keeps the python libs the attribution check reads the
# message with, so only the comment-format gate is missing.
make_hook_without_format_gate() {
  local hook
  hook=$(make_hook_without_lib)
  mkdir "$(dirname "$hook")/lib"
  cp "$(dirname "$SCRIPT")/lib/parse-shell-command.py" "$(dirname "$SCRIPT")/lib/check-commit-subject-length.py" \
    "$(dirname "$SCRIPT")/lib/shell-stage-lexer.py" "$(dirname "$SCRIPT")/lib/commit-stage-reader.py" "$(dirname "$hook")/lib/"
  printf '%s' "$hook"
}

# run_hook_with_script - like run_hook, but against an
# explicit script path instead of the real hook, for exercising
# the copy make_hook_without_lib built.
run_hook_with_script() {
  local script="$1" command="$2" cwd="${3:-}" stdin_json
  if [ -n "$cwd" ]; then
    stdin_json=$(jq -n --arg c "$command" --arg d "$cwd" '{tool_input: {command: $c}, cwd: $d}')
  else
    stdin_json=$(jq -n --arg c "$command" '{tool_input: {command: $c}}')
  fi
  printf '%s' "$stdin_json" | "$bash_bin" "$script" >/dev/null 2>&1
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
  local msg dir
  dir=$(make_repo main)
  msg=$(printf 'git commit -m "fix bug\n\nCo-Authored-By: Claude Fable 5 <noreply@anthropic.com>"')
  run_hook "$msg" "$dir"
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

it_should_block_a_cat_heredoc_naming_git_push_fed_through_a_command_substitution_since_any_substitution_fails_closed() {
  local cmd
  cmd=$(cat <<'OUTER'
echo "$(cat <<'EOF'
fix(x): mentions git push --force in prose
EOF
)"
OUTER
)
  run_hook "$cmd"
  assert_eq "should deny a cat heredoc naming git push opened inside a command substitution, since a substitution in a command naming git push is never parsed" "2" "$HOOK_EXIT"
}

it_should_allow_a_dangerous_phrase_inside_a_quoted_argument() {
  run_hook 'echo "the word aigitcommit appears here"'
  assert_eq "should allow a dangerous phrase that only appears inside a quoted argument" "0" "$HOOK_EXIT"
}

# Inside "$(...)" bash opens a fresh quoting context, so the
# '"'"' idiom there pairs as three strings, not as a closing ".
it_should_allow_quoted_prose_in_a_command_substitution_that_uses_the_apostrophe_idiom() {
  local cmd
  cmd=$(cat <<'CMD'
echo "x: $(wc -w 'it'"'"'s a commit')"
CMD
)
  run_hook "$cmd"
  assert_eq "should allow prose naming commit, quoted with the '\"'\"' apostrophe idiom inside a double-quoted command substitution" "0" "$HOOK_EXIT"
}

it_should_allow_multi_line_quoted_prose_that_names_git_show_and_commit() {
  local cmd
  cmd=$(cat <<'CMD'
c(){ printf "%s\n" "$1" | wc -w | tr -d ' '; }
echo "s8: $(c 'Main dispatches you with their commit SHAs.

For each SHA, read `git show <sha>` and the finding it fixed.
- **Hollow split**, by section 4'"'"'s signs.')"
CMD
)
  run_hook "$cmd"
  assert_eq "should allow a word count of multi-line quoted prose that names git show and commit" "0" "$HOOK_EXIT"
}

it_should_allow_a_here_string_of_multi_line_prose_that_names_commit() {
  run_hook "$(printf "wc -w <<< 'first line\nthe commit SHAs'")"
  assert_eq "should allow a word count of a multi-line here-string whose prose names commit" "0" "$HOOK_EXIT"
}

it_should_block_an_unattributed_commit_after_a_multi_line_quoted_argument() {
  run_hook "$(printf "echo 'first line\nsecond line'; git commit -m 'fix bug'")"
  assert_eq "should block an unattributed commit that follows a multi-line quoted argument on its closing line" "2" "$HOOK_EXIT"
}

it_should_block_an_unattributed_commit_inside_a_double_quoted_command_substitution() {
  run_hook "echo \"done: \$(git commit -m 'fix bug')\""
  assert_eq "should block an unattributed commit run inside a command substitution within double quotes" "2" "$HOOK_EXIT"
}

it_should_block_an_unattributed_commit_in_a_function_called_from_a_command_substitution() {
  local cmd
  cmd=$(cat <<'CMD'
c(){ git commit -m "$1"; }
echo "result: $(c 'fix bug
second line')"
CMD
)
  run_hook "$cmd"
  assert_eq "should block an unattributed commit inside a function body called with multi-line quoted text" "2" "$HOOK_EXIT"
}

# Bash starts a comment after ")", "<" and ">" too, so the
# apostrophe in that comment opens no quote, and the commit on
# the next line runs.
it_should_block_an_unattributed_commit_after_a_comment_that_follows_a_closing_paren() {
  local cmd
  cmd=$(cat <<'CMD'
(true)#'
git commit -m 'fix bug'
#'
CMD
)
  run_hook "$cmd"
  assert_eq "should block an unattributed commit on the line after a comment that starts right after a closing paren" "2" "$HOOK_EXIT"
}

it_should_block_an_unattributed_commit_after_a_comment_that_follows_a_redirect() {
  local cmd
  cmd=$(cat <<'CMD'
echo hi >#'
git commit -m 'fix bug'
#'
CMD
)
  run_hook "$cmd"
  assert_eq "should block an unattributed commit on the line after a comment that starts right after a redirect" "2" "$HOOK_EXIT"
}

# An escaped metacharacter is part of the word, so a # right
# after it opens no comment. The apostrophe after it then opens
# a quote that closes on the next line, before the commit.
it_should_block_an_unattributed_commit_after_a_hash_that_follows_an_escaped_semicolon() {
  run_hook "$(printf "echo x\\\\;#'\n'; git commit -m 'fix bug'")"
  assert_eq "should block an unattributed commit after a hash glued to a backslash-escaped semicolon" "2" "$HOOK_EXIT"
}

# Bash drops a backslash-newline before it splits words, so a #
# on the next line still starts a word and opens a comment. The
# commit goes through a variable, which no line-by-line reading
# of git commands catches.
it_should_block_an_unattributed_commit_after_a_comment_that_follows_a_line_continuation() {
  run_hook "$(printf 'echo x;\\\n#%s\ng=git; $g commit -m y\n#%s' "'" "'")"
  assert_eq "should block an unattributed commit after a comment on the line after a backslash-newline" "2" "$HOOK_EXIT"
}

# Bash runs a backtick substitution inside double quotes as a
# command, so its contents are no quoted text.
it_should_block_an_unattributed_commit_in_backticks_inside_double_quotes() {
  run_hook "echo \"\`git commit -m 'fix bug'\`\""
  assert_eq "should block an unattributed commit in a backtick substitution inside double quotes" "2" "$HOOK_EXIT"
}

# A case pattern's ")" inside "$(...)" does not close the
# substitution, so the commit in the case branch runs.
it_should_block_an_unattributed_commit_in_a_case_branch_inside_a_double_quoted_command_substitution() {
  run_hook "echo \"\$(case x in x) git commit -m 'fix bug';; esac)\""
  assert_eq "should block an unattributed commit in a case branch inside a command substitution within double quotes" "2" "$HOOK_EXIT"
}

# Either reading of the quotes can be wrong, so a guarded git
# command seen by the line-by-line reading blocks even when the
# whole-command reading puts it inside a quoted string.
it_should_block_a_guarded_git_command_that_only_the_line_by_line_reading_sees() {
  local cmd
  cmd=$(cat <<'CMD'
echo 'first line
git reset --hard
last line'
CMD
)
  run_hook "$cmd"
  assert_eq "should block a hard reset that the line-by-line reading sees, even when the whole-command reading puts it inside quotes" "2" "$HOOK_EXIT"
}

# A stray apostrophe that bash never reads as a quote must not
# hide the commit on the next line.
it_should_block_an_unattributed_commit_after_a_comment_holding_an_apostrophe() {
  run_hook "$(printf "# don't skip this\ngit commit -m 'fix bug'")"
  assert_eq "should block an unattributed commit on the line after a comment holding an apostrophe" "2" "$HOOK_EXIT"
}

it_should_block_an_unattributed_commit_after_an_escaped_apostrophe() {
  run_hook "$(printf "echo don\\\\'t\ngit commit -m 'fix bug'")"
  assert_eq "should block an unattributed commit on the line after a backslash-escaped apostrophe" "2" "$HOOK_EXIT"
}

it_should_block_an_unattributed_commit_after_an_ansi_c_string_with_an_escaped_quote() {
  run_hook "$(printf "echo \$'it\\\\'s'\ngit commit -m 'fix bug'\necho 'done'")"
  assert_eq "should block an unattributed commit on the line after a \$'...' string holding an escaped quote" "2" "$HOOK_EXIT"
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

it_should_block_an_unparseable_push_after_an_attributed_heredoc_commit() {
  local dir cmd
  dir=$(make_repo feat)
  cmd=$(printf '%s\n' \
    "git commit --allow-empty -F - <<'EOF'" \
    "docs(readme): it's the since-last-push diff now" \
    '' \
    'Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>' \
    'EOF' \
    'git push origin "main')
  run_hook "$cmd" "$dir"
  assert_eq "should block an unparseable git push segment that runs after a commit message heredoc" "2" "$HOOK_EXIT"
}

### Allow: "push" only inside a commit message

# stdin_heredoc_commit - prints a commit command that reads
# its message from a quoted heredoc on stdin, with the given
# body line between the subject and the attribution.
stdin_heredoc_commit() {
  printf '%s\n' \
    "git commit --allow-empty -q -F - <<'EOF'" \
    'docs(open-in-tmux): drop stale "matches <leader>tD" claims' \
    '' \
    "$1" \
    '' \
    'Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>' \
    'EOF'
}

it_should_allow_a_stdin_heredoc_commit_message_with_an_apostrophe_naming_git_and_push() {
  local dir
  dir=$(make_repo feat)
  run_hook "$(stdin_heredoc_commit "neovim's <leader>tD now shows the since-last-push diff git computes.")" "$dir"
  assert_eq "should allow a commit whose stdin heredoc message has an apostrophe and names git and push" "0" "$HOOK_EXIT"
}

it_should_allow_a_stdin_heredoc_commit_message_line_that_reads_as_a_push_to_main() {
  local dir
  dir=$(make_repo feat)
  run_hook "$(stdin_heredoc_commit 'git push origin main stays blocked by the guard.')" "$dir"
  assert_eq "should allow a commit whose stdin heredoc message has a line reading git push origin main" "0" "$HOOK_EXIT"
}

it_should_allow_a_stdin_heredoc_commit_message_that_names_a_force_push() {
  local dir
  dir=$(make_repo feat)
  run_hook "$(stdin_heredoc_commit 'The guard still blocks git push --force here.')" "$dir"
  assert_eq "should allow a commit whose stdin heredoc message names git push --force" "0" "$HOOK_EXIT"
}

### Block: a real push next to a commit

it_should_block_a_push_to_master_chained_after_a_commit() {
  local dir
  dir=$(make_repo feat)
  run_hook 'git commit --allow-empty -m "docs: x" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" && git push origin master' "$dir"
  assert_eq "should block git push origin master chained after an attributed commit" "2" "$HOOK_EXIT"
}

it_should_block_a_force_push_after_a_commit_whose_message_is_push() {
  local dir
  dir=$(make_repo feat)
  run_hook 'git commit --allow-empty -m "push" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" ; git push -f' "$dir"
  assert_eq "should block git push -f run after a commit whose message is the word push" "2" "$HOOK_EXIT"
}

it_should_block_a_push_to_main_on_the_line_after_a_heredoc_commit_message() {
  local dir cmd
  dir=$(make_repo feat)
  cmd=$(printf '%s\n' \
    "git commit --allow-empty -F - <<'EOF'" \
    'docs(readme): mention push' \
    '' \
    'Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>' \
    'EOF' \
    'git push origin main')
  run_hook "$cmd" "$dir"
  assert_eq "should block git push origin main on the line after a commit message heredoc closes" "2" "$HOOK_EXIT"
}

# The commit and the heredoc share a line, but bash, not the
# commit, reads the heredoc, so its body runs.
it_should_block_a_push_to_main_in_a_bash_heredoc_opened_after_a_commit() {
  local dir cmd
  dir=$(make_repo feat)
  cmd=$(printf '%s\n' \
    "git commit --allow-empty -F - -m x -m 'Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>'; bash <<'EOF'" \
    'git push origin main' \
    'EOF')
  run_hook "$cmd" "$dir"
  assert_eq "should block git push origin main in a bash heredoc opened on the same line as a commit" "2" "$HOOK_EXIT"
}

# The << sits inside a quoted -m value, so no heredoc opens and
# the next line runs as a command.
it_should_block_a_push_to_main_after_a_quoted_heredoc_marker_in_a_commit_message() {
  local dir cmd
  dir=$(make_repo feat)
  cmd=$(printf '%s\n' \
    "git commit --allow-empty -F - -m \"<<'EOF'\"" \
    'git push origin main' \
    'EOF')
  run_hook "$cmd" "$dir"
  assert_eq "should block git push origin main on the line after a commit message quoting a heredoc marker" "2" "$HOOK_EXIT"
}

it_should_block_git_dash_c_absolute_path_push_to_main() {
  run_hook "git -C /some/repo push origin main"
  assert_eq "should block git -C /some/repo push origin main, whatever the directory" "2" "$HOOK_EXIT"
}

### Block: a commit-looking heredoc whose body still runs

# push_in_heredoc_opened_by - prints the given opener line,
# then a body that pushes to main, then the attribution.
push_in_heredoc_opened_by() {
  printf '%s\n' \
    "$1" \
    'git push origin main' \
    '' \
    'Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>' \
    'EOF'
}

# bash reads $'\' ; ... \'' as one argument, so `bash -s`,
# not the commit, reads the heredoc and runs its body.
it_should_block_a_push_to_main_in_a_heredoc_that_ansi_c_quoting_hands_to_bash() {
  local dir
  dir=$(make_repo feat)
  run_hook "$(push_in_heredoc_opened_by "bash -s \$'\\' ; git commit -F - '\\' <<'EOF'")" "$dir"
  assert_eq "should block git push origin main in a heredoc that ANSI-C quoting hands to bash -s" "2" "$HOOK_EXIT"
}

it_should_block_a_push_to_main_after_a_heredoc_marker_inside_a_comment() {
  local dir
  dir=$(make_repo feat)
  run_hook "$(push_in_heredoc_opened_by "echo done #; git commit -F - <<'EOF'")" "$dir"
  assert_eq "should block git push origin main on the line after a heredoc marker that sits in a comment" "2" "$HOOK_EXIT"
}

it_should_block_a_push_to_main_in_a_commit_message_that_an_env_set_editor_runs() {
  local dir
  dir=$(make_repo feat)
  run_hook "$(push_in_heredoc_opened_by "GIT_EDITOR=sh git commit -e -F - <<'EOF'")" "$dir"
  assert_eq "should block git push origin main in a commit message that GIT_EDITOR=sh runs as a script" "2" "$HOOK_EXIT"
}

it_should_block_a_push_to_main_in_a_commit_message_that_a_dash_c_editor_runs() {
  local dir
  dir=$(make_repo feat)
  run_hook "$(push_in_heredoc_opened_by "git -c core.editor=sh commit --edit -F - <<'EOF'")" "$dir"
  assert_eq "should block git push origin main in a commit message that git -c core.editor=sh runs as a script" "2" "$HOOK_EXIT"
}

it_should_block_a_push_to_main_on_the_lines_after_a_here_string() {
  local dir
  dir=$(make_repo feat)
  run_hook "$(push_in_heredoc_opened_by "git commit -F - <<<'EOF'")" "$dir"
  assert_eq "should block git push origin main on the lines after a here-string, which bash runs as commands" "2" "$HOOK_EXIT"
}

# The attribution check can deny these shapes on its own, so
# each test reads the push guard's own denial from stderr.
PUSH_GUARD_DENIAL='git push to main/master is never allowed'

# run_hook_reading_push_verdict - like run_hook, but sets
# PUSH_GUARD_DENIED to yes when the push guard denied.
run_hook_reading_push_verdict() {
  local command="$1" cwd="${2:-}" stdin_json stderr_text
  if [ -n "$cwd" ]; then
    stdin_json=$(jq -n --arg c "$command" --arg d "$cwd" '{tool_input: {command: $c}, cwd: $d}')
  else
    stdin_json=$(jq -n --arg c "$command" '{tool_input: {command: $c}}')
  fi
  stderr_text=$(printf '%s' "$stdin_json" | "$bash_bin" "$SCRIPT" 2>&1 >/dev/null)
  HOOK_EXIT=$?
  case "$stderr_text" in
    *"$PUSH_GUARD_DENIAL"*) PUSH_GUARD_DENIED=yes ;;
    *) PUSH_GUARD_DENIED=no ;;
  esac
}

it_should_block_a_push_to_main_in_a_commit_message_whose_unquoted_variable_splits_into_an_editor_flag() {
  local dir
  dir=$(make_repo feat)
  run_hook_reading_push_verdict "$(push_in_heredoc_opened_by "export GIT_EDITOR=sh; e=-e; git commit \$e -F - <<'EOF'")" "$dir"
  assert_eq "should deny, as a push, a commit message that an unquoted \$e splitting into -e hands to the editor" "yes" "$PUSH_GUARD_DENIED"
}

it_should_block_a_push_to_main_in_a_commit_message_whose_unquoted_directory_variable_splits_into_git_options() {
  local dir
  dir=$(make_repo feat)
  run_hook_reading_push_verdict "$(push_in_heredoc_opened_by "d='x -c core.editor=sh'; git -C \$d commit -F - <<'EOF'")" "$dir"
  assert_eq "should deny, as a push, a commit message whose unquoted -C \$d splits into git -c core.editor=sh" "yes" "$PUSH_GUARD_DENIED"
}

it_should_block_a_push_to_main_in_a_commit_message_after_a_git_config_that_can_set_its_hooks() {
  local dir
  dir=$(make_repo feat)
  run_hook_reading_push_verdict "$(push_in_heredoc_opened_by "git config core.hooksPath /tmp/hooks && git commit -F - <<'EOF'")" "$dir"
  assert_eq "should deny, as a push, a commit message after a git config that can point the commit at hooks running it" "yes" "$PUSH_GUARD_DENIED"
}

it_should_block_a_push_to_main_in_a_commit_message_whose_double_dash_directory_hides_an_editor_flag_variable() {
  local dir
  dir=$(make_repo feat)
  run_hook_reading_push_verdict "$(push_in_heredoc_opened_by "export GIT_EDITOR=sh; e=-e; git -C -- commit \$e -F - <<'EOF'")" "$dir"
  assert_eq "should deny, as a push, a commit message whose -C -- puts the unquoted \$e after a double dash that is no pathspec separator" "yes" "$PUSH_GUARD_DENIED"
}

it_should_block_a_push_to_main_in_a_commit_message_after_an_env_run_git_config() {
  local dir
  dir=$(make_repo feat)
  run_hook_reading_push_verdict "$(push_in_heredoc_opened_by "env git config core.hooksPath /tmp/hooks && git commit -F - <<'EOF'")" "$dir"
  assert_eq "should deny, as a push, a commit message after env runs a git config that can point the commit at hooks running it" "yes" "$PUSH_GUARD_DENIED"
}

it_should_block_a_push_to_main_in_a_commit_message_after_a_zsh_lowercase_path_assignment() {
  local dir
  dir=$(make_repo feat)
  run_hook_reading_push_verdict "$(push_in_heredoc_opened_by "path=/tmp/evil && git commit -q -F - <<'EOF'")" "$dir"
  assert_eq "should deny, as a push, a commit message after path=/tmp/evil, which zsh ties to PATH so git can resolve to a fake binary" "yes" "$PUSH_GUARD_DENIED"
}

it_should_block_a_push_to_main_in_a_commit_message_after_a_mixed_case_assignment() {
  local dir
  dir=$(make_repo feat)
  run_hook_reading_push_verdict "$(push_in_heredoc_opened_by "GIT_dir=/tmp/evil && git commit -q -F - <<'EOF'")" "$dir"
  assert_eq "should deny, as a push, a commit message after a GIT_dir= assignment that is not all lowercase" "yes" "$PUSH_GUARD_DENIED"
}

it_should_allow_a_stdin_heredoc_commit_whose_variables_sit_only_in_pathspecs_after_the_double_dash() {
  local dir cmd
  dir=$(make_repo feat)
  cmd=$(printf '%s\n' \
    "cd $dir && d=docs && git commit -q -F - -- \"\$d/SKILL.md\" \"\$d/scripts/diffview-in-tmux.sh\" <<'EOF'" \
    'docs(open-in-tmux): name the since-last-push diff' \
    '' \
    'Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>' \
    'EOF')
  run_hook "$cmd" "$dir"
  assert_eq "should allow a stdin heredoc commit whose \$d variables appear only in pathspecs after --" "0" "$HOOK_EXIT"
}

it_should_allow_a_commit_whose_inline_message_mentions_git_push() {
  local dir
  dir=$(make_repo feat)
  run_hook 'git commit --allow-empty -m "docs: mention git push in readme" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"' "$dir"
  assert_eq "should allow a commit whose -m message only mentions git push" "0" "$HOOK_EXIT"
}

it_should_block_a_commit_whose_message_is_a_cat_heredoc_substitution_naming_a_push_to_main_since_any_substitution_fails_closed() {
  local dir cmd
  dir=$(make_repo feat)
  cmd=$(printf '%s\n' \
    "git commit --allow-empty -m \"\$(cat <<'EOF'" \
    'docs(readme): git push origin main stays blocked' \
    '' \
    'Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>' \
    'EOF' \
    ')"')
  run_hook_reading_push_verdict "$cmd" "$dir"
  assert_eq "should deny a commit whose \$(cat <<'EOF') message names git push origin main, since a substitution in a command naming git push is never parsed" "yes" "$PUSH_GUARD_DENIED"
}

it_should_block_a_push_to_main_in_an_unquoted_cat_heredoc_body_command_substitution() {
  local cmd
  cmd=$(printf '%s\n' 'cat <<EOF' 'pushed: $(git push origin main)' 'EOF')
  run_hook_reading_push_verdict "$cmd"
  assert_eq "should deny a \$(git push origin main) that an unquoted cat heredoc body expands and runs" "yes" "$PUSH_GUARD_DENIED"
}

it_should_block_a_push_to_main_in_a_bash_heredoc_after_an_earlier_cat_stage() {
  local cmd
  cmd=$(printf '%s\n' "cat notes.txt; bash <<'EOF'" 'git push origin main' 'EOF')
  run_hook_reading_push_verdict "$cmd"
  assert_eq "should deny git push origin main in a bash heredoc even when cat ran in an earlier stage of the line" "yes" "$PUSH_GUARD_DENIED"
}

it_should_block_a_push_to_main_in_a_dollar_paren_substitution() {
  run_hook_reading_push_verdict 'echo $(git push origin main)'
  assert_eq "should deny echo \$(git push origin main)" "yes" "$PUSH_GUARD_DENIED"
}

it_should_block_a_push_to_main_in_backticks() {
  run_hook_reading_push_verdict 'echo `git push origin main`'
  assert_eq "should deny a git push origin main run in backticks" "yes" "$PUSH_GUARD_DENIED"
}

it_should_block_a_push_to_main_after_another_statement_inside_a_substitution() {
  run_hook_reading_push_verdict 'echo $(cd /tmp; git push origin main)'
  assert_eq "should deny git push origin main after a cd inside one \$(...) substitution" "yes" "$PUSH_GUARD_DENIED"
}

it_should_block_a_push_to_main_in_a_nested_substitution() {
  run_hook_reading_push_verdict 'echo $(echo $(git push origin main))'
  assert_eq "should deny git push origin main in a substitution nested inside another" "yes" "$PUSH_GUARD_DENIED"
}

it_should_block_even_a_push_to_a_feature_branch_in_a_substitution_since_any_substitution_fails_closed() {
  run_hook_reading_push_verdict 'echo $(git push origin feature/login)'
  assert_eq "should deny echo \$(git push origin feature/login), since a substitution in a command naming git push is never parsed" "yes" "$PUSH_GUARD_DENIED"
}

it_should_block_a_push_to_main_after_a_closing_paren_inside_a_comment_in_a_substitution() {
  local cmd
  cmd=$(printf '%s\n' 'echo $(: # )' 'git push origin main)')
  run_hook_reading_push_verdict "$cmd"
  assert_eq "should deny git push origin main after a ) that a # comment inside the substitution holds" "yes" "$PUSH_GUARD_DENIED"
}

it_should_block_a_push_to_main_after_a_case_pattern_closing_paren_in_a_substitution() {
  run_hook_reading_push_verdict 'echo $(case a in a) true;; esac; git push origin main)'
  assert_eq "should deny git push origin main after a case pattern ) inside the substitution, whose refspec then reads main)" "yes" "$PUSH_GUARD_DENIED"
}

it_should_block_a_push_to_main_after_an_unbalanced_closing_paren_in_a_parameter_default_in_a_substitution() {
  run_hook_reading_push_verdict 'echo $(echo ${x:-)}; git push origin main)'
  assert_eq "should deny git push origin main after the lone ) of a \${x:-)} default inside the substitution" "yes" "$PUSH_GUARD_DENIED"
}

it_should_block_a_push_to_main_after_an_ansi_c_quoted_escaped_quote_in_a_substitution() {
  run_hook_reading_push_verdict "echo \$(echo \$'\\''; git push origin main)"
  assert_eq "should deny git push origin main after a \$'\\'' quote inside the substitution" "yes" "$PUSH_GUARD_DENIED"
}

it_should_block_a_push_to_main_in_an_input_process_substitution() {
  run_hook_reading_push_verdict 'cat <(git push origin main)'
  assert_eq "should deny git push origin main run in a <(...) process substitution" "yes" "$PUSH_GUARD_DENIED"
}

it_should_block_a_push_to_main_in_an_output_process_substitution() {
  run_hook_reading_push_verdict 'tee >(git push origin main) < notes.txt'
  assert_eq "should deny git push origin main run in a >(...) process substitution" "yes" "$PUSH_GUARD_DENIED"
}

it_should_block_a_push_to_main_in_escaped_backticks_nested_inside_backticks() {
  run_hook_reading_push_verdict 'echo `echo \`git push origin main\` `'
  assert_eq "should deny git push origin main in escaped backticks nested inside backticks" "yes" "$PUSH_GUARD_DENIED"
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

it_should_block_force_push_when_shared_lib_is_missing() {
  local hook
  hook=$(make_hook_without_lib)
  run_hook_with_script "$hook" "git push --force"
  assert_eq "should fail closed and block git push --force when the shared parsing lib cannot be imported" "2" "$HOOK_EXIT"
}

it_should_block_push_to_main_when_shared_lib_is_missing() {
  local hook
  hook=$(make_hook_without_lib)
  run_hook_with_script "$hook" "git push origin main"
  assert_eq "should fail closed and block git push origin main when the push-target check itself crashes" "2" "$HOOK_EXIT"
}

it_should_allow_git_status_when_shared_lib_is_missing() {
  local hook
  hook=$(make_hook_without_lib)
  run_hook_with_script "$hook" "git status"
  assert_eq "should still allow git status when the shared parsing lib cannot be imported" "0" "$HOOK_EXIT"
}

it_should_block_commit_whose_file_breaks_comment_format() {
  local dir cmd
  dir=$(make_repo main)
  printf '%s\n' '# this standalone comment line runs well past the sixty-four character cap' > "$dir/f.sh"
  cmd=$(printf 'git add f.sh && git commit -m "add f.sh\n\nCo-Authored-By: Claude Opus 5 <noreply@anthropic.com>"')
  run_hook "$cmd" "$dir"
  assert_eq "should block a commit whose file carries a comment-format violation" "2" "$HOOK_EXIT"
}

it_should_allow_commit_whose_file_respects_comment_format() {
  local dir cmd
  dir=$(make_repo main)
  printf '%s\n' '# short comment' > "$dir/f.sh"
  cmd=$(printf 'git add f.sh && git commit -m "add f.sh\n\nCo-Authored-By: Claude Opus 5 <noreply@anthropic.com>"')
  run_hook "$cmd" "$dir"
  assert_eq "should allow a commit whose file respects comment format" "0" "$HOOK_EXIT"
}

it_should_allow_commit_with_violation_when_format_gate_is_missing() {
  local dir hook cmd
  dir=$(make_repo main)
  printf '%s\n' '# this standalone comment line runs well past the sixty-four character cap' > "$dir/f.sh"
  hook=$(make_hook_without_format_gate)
  cmd=$(printf 'git add f.sh && git commit -m "add f.sh\n\nCo-Authored-By: Claude Opus 5 <noreply@anthropic.com>"')
  run_hook_with_script "$hook" "$cmd" "$dir"
  assert_eq "should fail open and allow the commit when the comment-format gate cannot be run" "0" "$HOOK_EXIT"
}

# run_hook discards stderr, and this case must prove the deny
# came from the subject length, not from another rule.
it_should_block_a_commit_whose_subject_runs_past_64_characters() {
  local dir cmd payload stderr_text
  dir=$(make_repo main)
  cmd=$(printf 'git commit --allow-empty -m "fix(git-guard): stop a commit whose subject is longer than a cap.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"')
  payload=$(jq -n --arg c "$cmd" --arg d "$dir" '{tool_input: {command: $c}, cwd: $d}')
  stderr_text=$(printf '%s' "$payload" | "$bash_bin" "$SCRIPT" 2>&1 >/dev/null)
  HOOK_EXIT=$?
  assert_eq "should block a commit whose subject runs past 64 characters" "2" "$HOOK_EXIT"
  case "$stderr_text" in
    *"65 characters"*) assert_eq "should name the subject's length in the denial" "named" "named" ;;
    *) assert_eq "should name the subject's length in the denial" "named" "$stderr_text" ;;
  esac
}

# The relative path resolves against the JSON cwd, not the hook
# process's directory, so this proves the cwd is passed on.
it_should_block_a_message_file_commit_whose_subject_runs_past_64_characters() {
  local dir payload stderr_text
  dir=$(make_repo main)
  printf '%s\n\n%s\n' \
    'fix(git-guard): stop a commit whose subject is longer than a cap.' \
    'Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>' > "$dir/msg.txt"
  payload=$(jq -n --arg c 'git commit --allow-empty -q -F msg.txt' --arg d "$dir" '{tool_input: {command: $c}, cwd: $d}')
  stderr_text=$(printf '%s' "$payload" | "$bash_bin" "$SCRIPT" 2>&1 >/dev/null)
  HOOK_EXIT=$?
  assert_eq "should block a message file commit whose subject runs past 64 characters" "2" "$HOOK_EXIT"
  case "$stderr_text" in
    *"65 characters"*) assert_eq "should name the message file subject's length in the denial" "named" "named" ;;
    *) assert_eq "should name the message file subject's length in the denial" "named" "$stderr_text" ;;
  esac
}

it_should_allow_a_message_file_commit_whose_subject_is_40_characters() {
  local dir
  dir=$(make_repo main)
  printf '%s\n\n%s\n' \
    'fix(git-guard): keep the subject short' \
    'Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>' > "$dir/msg.txt"
  run_hook 'git commit --allow-empty -q -F msg.txt' "$dir"
  assert_eq "should allow a message file commit whose subject is under the cap" "0" "$HOOK_EXIT"
}

it_should_allow_a_commit_whose_subject_is_exactly_64_characters() {
  local dir cmd
  dir=$(make_repo main)
  cmd=$(printf 'git commit --allow-empty -m "fix(git-guard): stop a commit whose subject is longer than a cap\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"')
  run_hook "$cmd" "$dir"
  assert_eq "should allow a commit whose subject is exactly 64 characters" "0" "$HOOK_EXIT"
}

it_should_block_an_attributed_commit_when_the_message_reader_is_missing() {
  local dir hook cmd
  dir=$(make_repo main)
  hook=$(make_hook_without_lib)
  cmd=$(printf 'git commit --allow-empty -m "fix(git-guard): stop a commit whose subject is longer than a cap.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"')
  run_hook_with_script "$hook" "$cmd" "$dir"
  assert_eq "should fail closed when the message reader cannot be run, since the attribution trailer goes unread" "2" "$HOOK_EXIT"
}

# A git global option between "git" and the subcommand must not
# hide the subcommand from the guard's checks.
it_should_block_an_unattributed_commit_behind_a_global_option() {
  local cmd
  for cmd in \
    'git -C /tmp/x commit -m msg' \
    'git -c user.name=t commit -m msg' \
    'git -C "/tmp/my dir" commit -m msg' \
    'git --no-pager commit -m msg' \
    'git --git-dir=/tmp/x/gitdir commit -m msg' \
    'git --git-dir /tmp/x/gitdir --work-tree /tmp/x commit -m msg'; do
    run_hook "$cmd"
    assert_eq "should block a commit without attribution behind a global option: $cmd" "2" "$HOOK_EXIT"
  done
}

it_should_block_a_destructive_operation_behind_a_global_option() {
  local cmd
  for cmd in \
    'git -C /tmp/x commit --amend -m "fix\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"' \
    'git -C /tmp/x reset --hard' \
    'git -C /tmp/x clean -fd' \
    'git -C /tmp/x branch -D feat' \
    'git -C /tmp/x checkout .' \
    'git -C /tmp/x restore .' \
    'git -C /tmp/x worktree remove --force /tmp/wt' \
    'git -C /tmp/x push --force origin feat'; do
    run_hook "$cmd"
    assert_eq "should block a destructive operation behind a global option: $cmd" "2" "$HOOK_EXIT"
  done
}

it_should_allow_a_safe_operation_behind_a_global_option() {
  local cmd
  for cmd in \
    'git -C /tmp/x status' \
    'git -C /tmp/x checkout feat' \
    'git -C /tmp/x branch -d feat' \
    'git -C /tmp/x push --force-with-lease origin feat' \
    'git -c core.pager=cat log'; do
    run_hook "$cmd"
    assert_eq "should allow a safe operation behind a global option: $cmd" "0" "$HOOK_EXIT"
  done
}

it_should_block_a_commit_into_another_repo_whose_staged_file_breaks_comment_format() {
  local dir elsewhere cmd
  dir=$(make_repo main)
  elsewhere=$(make_repo main)
  printf '%s\n' '# this standalone comment line runs well past the sixty-four character cap' > "$dir/f.sh"
  git -C "$dir" add f.sh
  cmd=$(printf 'git -C %s commit -m "add f.sh\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"' "$dir")
  run_hook "$cmd" "$elsewhere"
  assert_eq "should block a commit run with -C into a repo whose staged file carries a comment-format violation" "2" "$HOOK_EXIT"
}

# make_message_file <dir> <kind> - writes a commit message file
# into <dir>, with or without Co-Authored-By per <kind>
# (with-attribution | without-attribution), prints its path.
make_message_file() {
  local dir="$1" kind="$2" path="$1/commit-message.txt"
  if [ "$kind" = "with-attribution" ]; then
    printf 'fix(git-guard): read the message file\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\n' > "$path"
  else
    printf 'fix(git-guard): read the message file\n\nNo trailer in this body.\n' > "$path"
  fi
  printf '%s' "$path"
}

it_should_allow_a_commit_whose_message_file_carries_attribution() {
  local dir msg_dir msg_file cmd
  dir=$(make_repo main)
  msg_dir=$(mktemp -d)
  CLEANUP_DIRS+=("$msg_dir")
  msg_file=$(make_message_file "$msg_dir" with-attribution)
  for cmd in \
    "git commit --allow-empty -F $msg_file" \
    "git commit --allow-empty -F$msg_file" \
    "git commit --allow-empty --file $msg_file" \
    "git commit --allow-empty --file=$msg_file"; do
    run_hook "$cmd" "$dir"
    assert_eq "should allow a commit whose message file carries Co-Authored-By: $cmd" "0" "$HOOK_EXIT"
  done
}

it_should_allow_a_commit_whose_message_file_path_is_relative_to_the_working_directory() {
  local dir
  dir=$(make_repo main)
  make_message_file "$dir" with-attribution >/dev/null
  run_hook "git commit --allow-empty --file=commit-message.txt" "$dir"
  assert_eq "should allow a commit whose relative message file, read from the working directory, carries Co-Authored-By" "0" "$HOOK_EXIT"
}

it_should_block_a_commit_whose_message_file_lacks_attribution() {
  local dir msg_file
  dir=$(make_repo main)
  msg_file=$(make_message_file "$dir" without-attribution)
  run_hook "git commit --allow-empty -F $msg_file" "$dir"
  assert_eq "should block a commit whose message file has no Co-Authored-By" "2" "$HOOK_EXIT"
}

it_should_block_a_commit_whose_message_file_is_missing() {
  local dir
  dir=$(make_repo main)
  run_hook "git commit --allow-empty -F $dir/no-such-message.txt" "$dir"
  assert_eq "should block a commit whose message file does not exist" "2" "$HOOK_EXIT"
}

it_should_block_a_commit_reading_its_message_from_stdin() {
  local dir msg_file
  dir=$(make_repo main)
  msg_file=$(make_message_file "$dir" with-attribution)
  run_hook "git commit --allow-empty -F - < $msg_file" "$dir"
  assert_eq "should block a commit reading its message from stdin, since the hook cannot see it" "2" "$HOOK_EXIT"
}

it_should_block_a_message_file_commit_when_shared_lib_is_missing() {
  local dir hook msg_file
  dir=$(make_repo main)
  msg_file=$(make_message_file "$dir" with-attribution)
  hook=$(make_hook_without_lib)
  run_hook_with_script "$hook" "git commit --allow-empty -F $msg_file" "$dir"
  assert_eq "should block a commit whose attributed message file cannot be located without the shared parsing lib" "2" "$HOOK_EXIT"
}

# run_hook discards stderr, and this case must prove the deny
# came from the amend rule, not from the attribution rule.
it_should_block_an_amend_whose_message_file_carries_attribution() {
  local dir msg_file payload stderr_text
  dir=$(make_repo main)
  msg_file=$(make_message_file "$dir" with-attribution)
  payload=$(jq -n --arg c "git commit --amend -F $msg_file" --arg d "$dir" '{tool_input: {command: $c}, cwd: $d}')
  stderr_text=$(printf '%s' "$payload" | "$bash_bin" "$SCRIPT" 2>&1 >/dev/null)
  HOOK_EXIT=$?
  assert_eq "should block an amend even when its message file carries Co-Authored-By" "2" "$HOOK_EXIT"
  case "$stderr_text" in
    *"--amend"*) assert_eq "should deny the amend through the amend rule" "amend" "amend" ;;
    *) assert_eq "should deny the amend through the amend rule" "amend" "$stderr_text" ;;
  esac
}

it_should_allow_a_variable_message_file_path_whose_file_carries_attribution() {
  local dir msg_dir cmd
  dir=$(make_repo main)
  msg_dir=$(mktemp -d)
  CLEANUP_DIRS+=("$msg_dir")
  make_message_file "$msg_dir" with-attribution >/dev/null
  for cmd in \
    "S=$msg_dir && git commit --allow-empty -q -F \"\$S/commit-message.txt\"" \
    "S=$msg_dir && git commit --allow-empty -q -F \${S}/commit-message.txt"; do
    run_hook "$cmd" "$dir"
    assert_eq "should allow a message file reached through an assigned variable: $cmd" "0" "$HOOK_EXIT"
  done
}

it_should_block_a_variable_message_file_path_whose_file_lacks_attribution() {
  local dir msg_dir payload stderr_text
  dir=$(make_repo main)
  msg_dir=$(mktemp -d)
  CLEANUP_DIRS+=("$msg_dir")
  make_message_file "$msg_dir" without-attribution >/dev/null
  payload=$(jq -n --arg c "S=$msg_dir && git commit --allow-empty -q -F \"\$S/commit-message.txt\"" --arg d "$dir" '{tool_input: {command: $c}, cwd: $d}')
  stderr_text=$(printf '%s' "$payload" | "$bash_bin" "$SCRIPT" 2>&1 >/dev/null)
  HOOK_EXIT=$?
  assert_eq "should block a variable-path message file without Co-Authored-By" "2" "$HOOK_EXIT"
  case "$stderr_text" in
    *"Co-Authored-By: Claude attribution"*) assert_eq "should deny through the attribution rule" "ok" "ok" ;;
    *) assert_eq "should deny through the attribution rule" "ok" "$stderr_text" ;;
  esac
}

# The attributed file sits in the hook cwd, so a resolver that
# ignored the cd would find it and wrongly allow.
it_should_block_a_relative_message_file_after_a_directory_change() {
  local dir other
  dir=$(make_repo main)
  other=$(mktemp -d)
  CLEANUP_DIRS+=("$other")
  make_message_file "$dir" with-attribution >/dev/null
  run_hook "cd $other && git commit --allow-empty -q -F commit-message.txt" "$dir"
  assert_eq "should block a relative message file once a cd moved the working directory" "2" "$HOOK_EXIT"
}

# Glued onto a body sentence, git keeps the attribution as body
# text, so git log's %(trailers) shows no Co-Authored-By.
it_should_block_an_attribution_glued_onto_a_body_sentence() {
  local dir payload stderr_text
  dir=$(make_repo main)
  payload=$(jq -n --arg c 'git commit --allow-empty -m "fix(git-guard): read trailers" -m "Why text. Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"' --arg d "$dir" '{tool_input: {command: $c}, cwd: $d}')
  stderr_text=$(printf '%s' "$payload" | "$bash_bin" "$SCRIPT" 2>&1 >/dev/null)
  HOOK_EXIT=$?
  assert_eq "should block an attribution glued onto a body sentence" "2" "$HOOK_EXIT"
  case "$stderr_text" in
    *"its own last -m"*) assert_eq "should tell the author to put the attribution in its own last -m" "told" "told" ;;
    *) assert_eq "should tell the author to put the attribution in its own last -m" "told" "$stderr_text" ;;
  esac
}

# Inside double quotes bash keeps \n as a backslash and an n, so
# the attribution is part of the Gate trailer's value.
it_should_block_an_attribution_after_a_literal_backslash_n() {
  local dir
  dir=$(make_repo main)
  run_hook 'git commit --allow-empty -m "fix(git-guard): read trailers" -m "Gate: metrics\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"' "$dir"
  assert_eq "should block an attribution that follows a literal backslash-n" "2" "$HOOK_EXIT"
}

it_should_allow_an_attribution_in_its_own_last_message_option() {
  local dir
  dir=$(make_repo main)
  run_hook 'git commit --allow-empty -m "fix(git-guard): read trailers" -m "Why text." -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"' "$dir"
  assert_eq "should allow an attribution passed as its own last -m" "0" "$HOOK_EXIT"
}

it_should_allow_an_attribution_passed_as_a_trailer_option() {
  local dir
  dir=$(make_repo main)
  run_hook 'git commit --allow-empty -m "fix(git-guard): read trailers" --trailer "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"' "$dir"
  assert_eq "should allow an attribution passed through --trailer" "0" "$HOOK_EXIT"
}

it_should_allow_a_heredoc_message_whose_last_paragraph_is_the_attribution() {
  local dir cmd
  dir=$(make_repo main)
  cmd=$(printf '%s\n' \
    "git commit --allow-empty -m \"\$(cat <<'EOF'" \
    'fix(git-guard): read trailers' \
    '' \
    'Why text.' \
    '' \
    'Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>' \
    'EOF' \
    ')"')
  run_hook "$cmd" "$dir"
  assert_eq "should allow a heredoc message whose last paragraph is the attribution" "0" "$HOOK_EXIT"
}

it_should_block_a_command_whose_first_commit_cannot_be_read() {
  local dir
  dir=$(make_repo main)
  run_hook 'git commit --allow-empty -m "$SUBJECT" && git commit --allow-empty -m "fix(git-guard): read trailers" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"' "$dir"
  assert_eq "should block a command when one of its commits cannot be read, even if another is attributed" "2" "$HOOK_EXIT"
}

# A commit run through an expanded or aliased command word never
# shows a literal "git commit" for the guard to spot.
it_should_block_a_commit_run_through_an_unknown_command_word() {
  local cmd
  for cmd in \
    '$GIT commit -m msg' \
    '"$G" commit -m msg' \
    '${GIT} commit -m msg' \
    '$GIT "commit" -m msg' \
    'alias g=git; g commit -m msg' \
    'g commit -m msg' \
    '$GIT commit -m msg # note'; do
    run_hook "$cmd"
    assert_eq "should block a commit run through an unknown command word: $cmd" "2" "$HOOK_EXIT"
  done
}

it_should_allow_a_command_whose_paths_only_contain_the_word_commit() {
  local cmd
  for cmd in \
    'git add configs/ai-docs/claude/hooks/lib/check-commit-subject-length.py' \
    'git diff -- configs/ai-docs/claude/hooks/lib/check-commit-subject-length.py' \
    'cat hooks/claude-git-guard.sh hooks/lib/check-commit-subject-length.py' \
    "$(printf '# note\ngit status')"; do
    run_hook "$cmd"
    assert_eq "should allow a command whose paths only contain the word commit: $cmd" "0" "$HOOK_EXIT"
  done
}

# A git alias can map any name that is not a git command to
# commit, from -c, --config-env or the repo's own config.
it_should_block_a_commit_run_through_a_git_alias() {
  local cmd
  for cmd in \
    'git ci -m msg' \
    'git -c alias.ci=commit ci -m msg' \
    "git -c alias.ci='!git commit' ci" \
    'git --config-env=alias.ci=GIT_ALIAS ci' \
    'git -c alias.status=commit status' \
    'git -C /tmp/x ci -m msg'; do
    run_hook "$cmd"
    assert_eq "should block a commit run through a git alias: $cmd" "2" "$HOOK_EXIT"
  done
}

it_should_allow_a_git_command_no_alias_can_shadow() {
  local cmd
  for cmd in \
    'git log --oneline -5' \
    'git diff --stat' \
    'git show HEAD' \
    'git add notes.md' \
    'git -C /tmp/x log'; do
    run_hook "$cmd"
    assert_eq "should allow a git command no alias can shadow: $cmd" "0" "$HOOK_EXIT"
  done
}

it_should_allow_git_hash_object_a_builtin_that_writes_no_commit() {
  run_hook "git hash-object README.md"
  assert_eq "should allow git hash-object, a builtin that writes no commit" "0" "$HOOK_EXIT"
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
it_should_block_a_cat_heredoc_naming_git_push_fed_through_a_command_substitution_since_any_substitution_fails_closed
it_should_allow_a_dangerous_phrase_inside_a_quoted_argument
it_should_allow_quoted_prose_in_a_command_substitution_that_uses_the_apostrophe_idiom
it_should_allow_multi_line_quoted_prose_that_names_git_show_and_commit
it_should_allow_a_here_string_of_multi_line_prose_that_names_commit
it_should_block_an_unattributed_commit_after_a_multi_line_quoted_argument
it_should_block_an_unattributed_commit_inside_a_double_quoted_command_substitution
it_should_block_an_unattributed_commit_in_a_function_called_from_a_command_substitution
it_should_block_an_unattributed_commit_after_a_comment_that_follows_a_closing_paren
it_should_block_an_unattributed_commit_after_a_comment_that_follows_a_redirect
it_should_block_an_unattributed_commit_after_a_hash_that_follows_an_escaped_semicolon
it_should_block_an_unattributed_commit_after_a_comment_that_follows_a_line_continuation
it_should_block_an_unattributed_commit_in_backticks_inside_double_quotes
it_should_block_an_unattributed_commit_in_a_case_branch_inside_a_double_quoted_command_substitution
it_should_block_a_guarded_git_command_that_only_the_line_by_line_reading_sees
it_should_block_an_unattributed_commit_after_a_comment_holding_an_apostrophe
it_should_block_an_unattributed_commit_after_an_escaped_apostrophe
it_should_block_an_unattributed_commit_after_an_ansi_c_string_with_an_escaped_quote
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
it_should_block_env_prefixed_push_to_main
it_should_block_bare_env_assignment_push_to_main
it_should_block_command_prefixed_push_to_main
it_should_block_git_dash_c_config_push_to_main
it_should_block_implicit_push_with_unresolvable_cwd
it_should_block_unparseable_segment_naming_git_and_push
it_should_block_an_unparseable_push_after_an_attributed_heredoc_commit
it_should_allow_a_stdin_heredoc_commit_message_with_an_apostrophe_naming_git_and_push
it_should_allow_a_stdin_heredoc_commit_message_line_that_reads_as_a_push_to_main
it_should_allow_a_stdin_heredoc_commit_message_that_names_a_force_push
it_should_block_a_push_to_master_chained_after_a_commit
it_should_block_a_force_push_after_a_commit_whose_message_is_push
it_should_block_a_push_to_main_on_the_line_after_a_heredoc_commit_message
it_should_block_a_push_to_main_in_a_bash_heredoc_opened_after_a_commit
it_should_block_a_push_to_main_after_a_quoted_heredoc_marker_in_a_commit_message
it_should_block_git_dash_c_absolute_path_push_to_main
it_should_block_a_push_to_main_in_a_heredoc_that_ansi_c_quoting_hands_to_bash
it_should_block_a_push_to_main_after_a_heredoc_marker_inside_a_comment
it_should_block_a_push_to_main_in_a_commit_message_that_an_env_set_editor_runs
it_should_block_a_push_to_main_in_a_commit_message_that_a_dash_c_editor_runs
it_should_block_a_push_to_main_on_the_lines_after_a_here_string
it_should_block_a_push_to_main_in_a_commit_message_whose_unquoted_variable_splits_into_an_editor_flag
it_should_block_a_push_to_main_in_a_commit_message_whose_unquoted_directory_variable_splits_into_git_options
it_should_block_a_push_to_main_in_a_commit_message_after_a_git_config_that_can_set_its_hooks
it_should_block_a_push_to_main_in_a_commit_message_whose_double_dash_directory_hides_an_editor_flag_variable
it_should_block_a_push_to_main_in_a_commit_message_after_an_env_run_git_config
it_should_block_a_push_to_main_in_a_commit_message_after_a_zsh_lowercase_path_assignment
it_should_block_a_push_to_main_in_a_commit_message_after_a_mixed_case_assignment
it_should_allow_a_stdin_heredoc_commit_whose_variables_sit_only_in_pathspecs_after_the_double_dash
it_should_allow_a_commit_whose_inline_message_mentions_git_push
it_should_block_a_commit_whose_message_is_a_cat_heredoc_substitution_naming_a_push_to_main_since_any_substitution_fails_closed
it_should_block_a_push_to_main_in_an_unquoted_cat_heredoc_body_command_substitution
it_should_block_a_push_to_main_in_a_bash_heredoc_after_an_earlier_cat_stage
it_should_block_a_push_to_main_in_a_dollar_paren_substitution
it_should_block_a_push_to_main_in_backticks
it_should_block_a_push_to_main_after_another_statement_inside_a_substitution
it_should_block_a_push_to_main_in_a_nested_substitution
it_should_block_even_a_push_to_a_feature_branch_in_a_substitution_since_any_substitution_fails_closed
it_should_block_a_push_to_main_after_a_closing_paren_inside_a_comment_in_a_substitution
it_should_block_a_push_to_main_after_a_case_pattern_closing_paren_in_a_substitution
it_should_block_a_push_to_main_after_an_unbalanced_closing_paren_in_a_parameter_default_in_a_substitution
it_should_block_a_push_to_main_after_an_ansi_c_quoted_escaped_quote_in_a_substitution
it_should_block_a_push_to_main_in_an_input_process_substitution
it_should_block_a_push_to_main_in_an_output_process_substitution
it_should_block_a_push_to_main_in_escaped_backticks_nested_inside_backticks
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
it_should_block_force_push_when_shared_lib_is_missing
it_should_block_push_to_main_when_shared_lib_is_missing
it_should_allow_git_status_when_shared_lib_is_missing
it_should_block_commit_whose_file_breaks_comment_format
it_should_allow_commit_whose_file_respects_comment_format
it_should_allow_commit_with_violation_when_format_gate_is_missing
it_should_block_a_commit_whose_subject_runs_past_64_characters
it_should_block_a_message_file_commit_whose_subject_runs_past_64_characters
it_should_allow_a_message_file_commit_whose_subject_is_40_characters
it_should_allow_a_commit_whose_subject_is_exactly_64_characters
it_should_block_an_attributed_commit_when_the_message_reader_is_missing
it_should_block_an_unattributed_commit_behind_a_global_option
it_should_block_a_destructive_operation_behind_a_global_option
it_should_allow_a_safe_operation_behind_a_global_option
it_should_block_a_commit_into_another_repo_whose_staged_file_breaks_comment_format
it_should_allow_a_commit_whose_message_file_carries_attribution
it_should_allow_a_commit_whose_message_file_path_is_relative_to_the_working_directory
it_should_block_a_commit_whose_message_file_lacks_attribution
it_should_block_a_commit_whose_message_file_is_missing
it_should_block_a_commit_reading_its_message_from_stdin
it_should_block_a_message_file_commit_when_shared_lib_is_missing
it_should_block_an_amend_whose_message_file_carries_attribution
it_should_allow_a_variable_message_file_path_whose_file_carries_attribution
it_should_block_a_variable_message_file_path_whose_file_lacks_attribution
it_should_block_a_relative_message_file_after_a_directory_change
it_should_block_an_attribution_glued_onto_a_body_sentence
it_should_block_an_attribution_after_a_literal_backslash_n
it_should_allow_an_attribution_in_its_own_last_message_option
it_should_allow_an_attribution_passed_as_a_trailer_option
it_should_allow_a_heredoc_message_whose_last_paragraph_is_the_attribution
it_should_block_a_command_whose_first_commit_cannot_be_read
it_should_block_a_commit_run_through_an_unknown_command_word
it_should_allow_a_command_whose_paths_only_contain_the_word_commit
it_should_block_a_commit_run_through_a_git_alias
it_should_allow_a_git_command_no_alias_can_shadow
it_should_allow_git_hash_object_a_builtin_that_writes_no_commit

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
