#!/usr/bin/env bash
# test-resolve-repo-targets.sh - plain-bash test file
# for resolve-repo-targets.py.
#
# Usage:
#   bash test-resolve-repo-targets.sh
#
# Exits 0 when every assertion passes, nonzero otherwise.
# No pytest dependency, matching this skill's other test
# files (test-extract-session-feedback.sh).

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$script_dir/resolve-repo-targets.py"

work_dir=$(mktemp -d)
# Resolve once: macOS's /tmp is a symlink to /private/tmp, and both
# `git rev-parse --show-toplevel` and the OS's real getcwd() resolve
# symlinks -- so every path built under an unresolved work_dir would
# mismatch what the script under test actually reports. Resolving the
# root here means everything mkdir'd/mktemp'd underneath is already
# canonical, with no need to re-resolve each one individually.
work_dir=$(cd "$work_dir" && pwd -P)
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

# make_fake_home - creates an isolated $HOME (with an
# empty .claude/projects dir) under work_dir, echoes its
# path. Every CLI-level test uses its own fake HOME so
# real ~/.claude/CLAUDE.md and ~/.claude/skills are never
# touched.
make_fake_home() {
  local home
  home=$(mktemp -d "$work_dir/home.XXXXXX")
  mkdir -p "$home/.claude/projects"
  echo "$home"
}

# add_project_dir - creates an empty ~/.claude/projects/<slug>
# dir under the given fake home, simulating a Claude Code
# project transcript directory.
add_project_dir() {
  local home="$1" slug="$2"
  mkdir -p "$home/.claude/projects/$slug"
}

# make_git_repo - creates and git-inits a directory named
# exactly $2 under parent dir $1, echoes its full path.
make_git_repo() {
  local parent="$1" name="$2" repo="$1/$2"
  mkdir -p "$repo"
  git -C "$repo" init -q
  echo "$repo"
}

# add_unix_utils_marker - creates the
# configs/ai-docs/claude/CLAUDE.md file inside repo_dir
# that is_unix_utils_repo requires as the corollary guard.
add_unix_utils_marker() {
  local repo_dir="$1"
  mkdir -p "$repo_dir/configs/ai-docs/claude"
  : >"$repo_dir/configs/ai-docs/claude/CLAUDE.md"
}

# run_from - runs resolve-repo-targets.py --json with cwd
# set to $1 and HOME set to $2, capturing stdout/stderr/exit
# into VERDICT_OUT/VERDICT_ERR/VERDICT_EXIT.
run_from() {
  local cwd="$1" home="$2"
  local out_file="$work_dir/stdout.txt"
  local err_file="$work_dir/stderr.txt"
  (cd "$cwd" && HOME="$home" python3 "$SCRIPT" --json) >"$out_file" 2>"$err_file"
  VERDICT_EXIT=$?
  VERDICT_OUT=$(cat "$out_file")
  VERDICT_ERR=$(cat "$err_file")
}

# py_field - prints JSON field <key> from JSON text <json>
# ("null"/"true"/"false" for those literal values).
py_field() {
  python3 -c '
import json, sys
data = json.loads(sys.argv[1])
value = data[sys.argv[2]]
if value is None:
    print("null")
elif isinstance(value, bool):
    print("true" if value else "false")
else:
    print(value)
' "$1" "$2"
}

# py_list_len - prints len(data[<key>]) for JSON text <json>.
py_list_len() {
  python3 -c '
import json, sys
data = json.loads(sys.argv[1])
print(len(data[sys.argv[2]]))
' "$1" "$2"
}

# py_list_contains - prints "true"/"false" for whether
# <needle> is a member of list field <key> in JSON text <json>.
py_list_contains() {
  python3 -c '
import json, sys
data = json.loads(sys.argv[1])
print("true" if sys.argv[3] in data[sys.argv[2]] else "false")
' "$1" "$2" "$3"
}

# call_matching_project_dirs - loads resolve-repo-targets.py
# via importlib (its hyphenated filename blocks a normal
# `import`) and calls matching_project_dirs(repo_root,
# projects_root) directly, printing one path per line. Used
# by the pure-unit test only -- every other test drives the
# script through its CLI/JSON contract.
call_matching_project_dirs() {
  local repo_root="$1" projects_root="$2"
  python3 -c '
import importlib.util, sys
spec = importlib.util.spec_from_file_location("resolve_repo_targets", sys.argv[1])
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
for p in mod.matching_project_dirs(sys.argv[2], sys.argv[3]):
    print(p)
' "$SCRIPT" "$repo_root" "$projects_root"
}

# ---------------------------------------------------------------
# matching_project_dirs > pure unit test
# ---------------------------------------------------------------

it_should_match_a_slug_that_equals_the_repo_slug_or_starts_with_the_repo_slug_plus_a_hyphen_boundary() {
  local projects_root repo_root="/tmp/fake/unix-utils"
  local repo_slug="-tmp-fake-unix-utils"
  projects_root=$(mktemp -d "$work_dir/projects.XXXXXX")
  mkdir -p "$projects_root/$repo_slug"                    # equals repo slug
  mkdir -p "$projects_root/${repo_slug}-configs"           # hyphen-boundary match
  mkdir -p "$projects_root/-tmp-fake-unrelated"             # unrelated, must be excluded

  local matches
  matches=$(call_matching_project_dirs "$repo_root" "$projects_root")

  local exact_included="false" boundary_included="false" unrelated_excluded="true"
  [[ "$matches" == *"$projects_root/$repo_slug"$'\n'* || "$matches" == *"$projects_root/$repo_slug" ]] && exact_included="true"
  [[ "$matches" == *"$projects_root/${repo_slug}-configs"* ]] && boundary_included="true"
  [[ "$matches" == *"unrelated"* ]] && unrelated_excluded="false"

  assert_eq \
    "matching_project_dirs > should match a slug that equals the repo slug or starts with the repo slug plus a hyphen boundary" \
    "true true true" "$exact_included $boundary_included $unrelated_excluded"
}

# ---------------------------------------------------------------
# ResolveRepoTargets > happy
# ---------------------------------------------------------------

it_should_resolve_read_scope_to_every_claude_projects_slug_when_run_from_the_unix_utils_repo_root() {
  local home repos_parent repo
  home=$(make_fake_home)
  add_project_dir "$home" "-Users-a-alpha"
  add_project_dir "$home" "-Users-a-beta"
  add_project_dir "$home" "-Users-a-gamma"
  repos_parent=$(mktemp -d "$work_dir/repos.XXXXXX")
  repo=$(make_git_repo "$repos_parent" "unix-utils")
  add_unix_utils_marker "$repo"

  run_from "$repo" "$home"

  local len contains_alpha
  len=$(py_list_len "$VERDICT_OUT" "read_scope_dirs")
  contains_alpha=$(py_list_contains "$VERDICT_OUT" "read_scope_dirs" "$home/.claude/projects/-Users-a-alpha")
  assert_eq \
    "ResolveRepoTargets > happy > should resolve read-scope to every ~/.claude/projects slug when run from the unix-utils repo root" \
    "3 true" "$len $contains_alpha"
}

it_should_resolve_is_unix_utils_to_true_only_when_the_git_roots_directory_basename_is_exactly_the_literal_string_unix_utils() {
  local home repos_parent repo_true repo_false
  home=$(make_fake_home)
  repos_parent=$(mktemp -d "$work_dir/repos.XXXXXX")
  repo_true=$(make_git_repo "$repos_parent" "unix-utils")
  add_unix_utils_marker "$repo_true"
  repo_false=$(make_git_repo "$repos_parent" "unix-utils-fork")

  run_from "$repo_true" "$home"
  local is_true="$VERDICT_OUT"
  run_from "$repo_false" "$home"
  local is_false="$VERDICT_OUT"

  assert_eq \
    "ResolveRepoTargets > happy > should resolve is_unix_utils to true only when the git root's directory basename is exactly the literal string 'unix-utils'" \
    "true false" "$(py_field "$is_true" is_unix_utils) $(py_field "$is_false" is_unix_utils)"
}

it_should_resolve_read_scope_to_only_the_current_repos_prefix_and_boundary_matched_slugs_when_run_from_another_repo() {
  local home repos_parent repo repo_slug
  home=$(make_fake_home)
  repos_parent=$(mktemp -d "$work_dir/repos.XXXXXX")
  repo=$(make_git_repo "$repos_parent" "client-repo")
  repo_slug=$(python3 -c "import re,sys; print(re.sub(r'[/.]', '-', sys.argv[1]))" "$repo")
  add_project_dir "$home" "$repo_slug"
  add_project_dir "$home" "${repo_slug}-worktree"
  add_project_dir "$home" "-Users-someone-else-unrelated-project"

  run_from "$repo" "$home"

  local len contains_exact contains_worktree
  len=$(py_list_len "$VERDICT_OUT" "read_scope_dirs")
  contains_exact=$(py_list_contains "$VERDICT_OUT" "read_scope_dirs" "$home/.claude/projects/$repo_slug")
  contains_worktree=$(py_list_contains "$VERDICT_OUT" "read_scope_dirs" "$home/.claude/projects/${repo_slug}-worktree")
  assert_eq \
    "ResolveRepoTargets > happy > should resolve read-scope to only the current repo's prefix-and-boundary-matched slugs when run from another repo" \
    "2 true true" "$len $contains_exact $contains_worktree"
}

it_should_resolve_the_write_target_to_configs_ai_docs_claude_claude_md_when_run_from_the_unix_utils_repo() {
  local home repos_parent repo
  home=$(make_fake_home)
  repos_parent=$(mktemp -d "$work_dir/repos.XXXXXX")
  repo=$(make_git_repo "$repos_parent" "unix-utils")
  add_unix_utils_marker "$repo"

  run_from "$repo" "$home"

  assert_eq \
    "ResolveRepoTargets > happy > should resolve the write target to configs/ai-docs/claude/CLAUDE.md when run from the unix-utils repo" \
    "$repo/configs/ai-docs/claude/CLAUDE.md" "$(py_field "$VERDICT_OUT" claude_md_target)"
}

it_should_resolve_the_write_target_to_the_current_repos_own_claude_md_when_run_from_another_repo() {
  local home repos_parent repo
  home=$(make_fake_home)
  repos_parent=$(mktemp -d "$work_dir/repos.XXXXXX")
  repo=$(make_git_repo "$repos_parent" "client-repo")

  run_from "$repo" "$home"

  assert_eq \
    "ResolveRepoTargets > happy > should resolve the write target to the current repo's own CLAUDE.md when run from another repo" \
    "$repo/CLAUDE.md" "$(py_field "$VERDICT_OUT" claude_md_target)"
}

# ---------------------------------------------------------------
# ResolveRepoTargets > corner
# ---------------------------------------------------------------

it_should_match_a_worktree_slug_to_its_parent_repo_with_no_worktree_specific_logic() {
  local home repos_parent repo repo_slug worktree_slug
  home=$(make_fake_home)
  repos_parent=$(mktemp -d "$work_dir/repos.XXXXXX")
  repo=$(make_git_repo "$repos_parent" "arco2-integrator")
  repo_slug=$(python3 -c "import re,sys; print(re.sub(r'[/.]', '-', sys.argv[1]))" "$repo")
  # Shaped exactly like a real observed worktree project-dir slug:
  # <repo-slug>--claude-worktrees-<branch>. No worktree was actually
  # created -- this proves plain prefix+boundary matching alone
  # (no git-worktree detection) is what includes it.
  worktree_slug="${repo_slug}--claude-worktrees-someone-cdpi-1-fix"
  add_project_dir "$home" "$worktree_slug"

  run_from "$repo" "$home"

  assert_eq \
    "ResolveRepoTargets > corner > should match a worktree slug to its parent repo with no worktree-specific logic" \
    "true" "$(py_list_contains "$VERDICT_OUT" "read_scope_dirs" "$home/.claude/projects/$worktree_slug")"
}

it_should_not_match_a_sibling_repo_whose_slug_shares_the_same_prefix_without_a_boundary() {
  local home repos_parent repo repo_slug
  home=$(make_fake_home)
  repos_parent=$(mktemp -d "$work_dir/repos.XXXXXX")
  # A non-unix-utils repo, deliberately: the unix-utils branch lists
  # every ~/.claude/projects dir unconditionally (per the "list every
  # slug" happy-path test above) and never calls matching_project_dirs
  # at all, so it can't exercise this exclusion rule.
  repo=$(make_git_repo "$repos_parent" "client-repo")
  repo_slug=$(python3 -c "import re,sys; print(re.sub(r'[/.]', '-', sys.argv[1]))" "$repo")
  # No hyphen between the repo slug and "fork" -- a genuinely
  # boundary-less shared prefix (unlike "<slug>-fork", which the
  # rule legitimately treats as an in-scope worktree-shaped slug).
  add_project_dir "$home" "${repo_slug}fork"

  run_from "$repo" "$home"

  assert_eq \
    "ResolveRepoTargets > corner > should not match a sibling repo whose slug shares the same prefix without a boundary" \
    "false" "$(py_list_contains "$VERDICT_OUT" "read_scope_dirs" "$home/.claude/projects/${repo_slug}fork")"
}

it_should_detect_the_unix_utils_repo_from_a_deeply_nested_subdirectory_of_the_repo_root() {
  local home repos_parent repo nested
  home=$(make_fake_home)
  repos_parent=$(mktemp -d "$work_dir/repos.XXXXXX")
  repo=$(make_git_repo "$repos_parent" "unix-utils")
  add_unix_utils_marker "$repo"
  nested="$repo/configs/ai-docs/claude/skills"
  mkdir -p "$nested"

  run_from "$nested" "$home"

  assert_eq \
    "ResolveRepoTargets > corner > should detect the unix-utils repo from a deeply nested subdirectory of the repo root" \
    "$repo true" "$(py_field "$VERDICT_OUT" repo_root) $(py_field "$VERDICT_OUT" is_unix_utils)"
}

it_should_fall_back_to_the_cwd_derived_slug_alone_read_only_when_cwd_is_outside_any_git_repo() {
  local home outside_dir expected_slug
  home=$(make_fake_home)
  outside_dir=$(mktemp -d "$work_dir/outside.XXXXXX")
  expected_slug=$(python3 -c "import re,sys; print(re.sub(r'[/.]', '-', sys.argv[1]))" "$outside_dir")

  run_from "$outside_dir" "$home"

  local len contains_slug claude_target skills_target
  len=$(py_list_len "$VERDICT_OUT" "read_scope_dirs")
  contains_slug=$(py_list_contains "$VERDICT_OUT" "read_scope_dirs" "$home/.claude/projects/$expected_slug")
  claude_target=$(py_field "$VERDICT_OUT" claude_md_target)
  skills_target=$(py_field "$VERDICT_OUT" skills_dir_target)
  assert_eq \
    "ResolveRepoTargets > corner > should fall back to the cwd-derived slug alone, read-only, when cwd is outside any git repo" \
    "1 true null null" "$len $contains_slug $claude_target $skills_target"
}

# ---------------------------------------------------------------
# ResolveRepoTargets > failure
# ---------------------------------------------------------------

it_should_die_loudly_when_claude_claude_md_is_a_detached_regular_file_instead_of_a_symlink_into_the_repo() {
  local home repos_parent repo
  home=$(make_fake_home)
  echo "detached, not a symlink" >"$home/.claude/CLAUDE.md"
  repos_parent=$(mktemp -d "$work_dir/repos.XXXXXX")
  repo=$(make_git_repo "$repos_parent" "unix-utils")
  add_unix_utils_marker "$repo"

  run_from "$repo" "$home"

  local died_naming_detachment="false"
  if [ "$VERDICT_EXIT" -ne 0 ] && [[ "$VERDICT_ERR" == *"detached"* ]]; then
    died_naming_detachment="true"
  fi
  assert_eq \
    "ResolveRepoTargets > failure > should die loudly when ~/.claude/CLAUDE.md is a detached regular file instead of a symlink into the repo" \
    "true" "$died_naming_detachment"
}

it_should_die_loudly_when_the_repo_basename_is_unix_utils_but_configs_ai_docs_claude_claude_md_does_not_exist() {
  local home repos_parent repo
  home=$(make_fake_home)
  repos_parent=$(mktemp -d "$work_dir/repos.XXXXXX")
  repo=$(make_git_repo "$repos_parent" "unix-utils")
  # Deliberately no add_unix_utils_marker call -- the marker file
  # this test asserts is missing.

  run_from "$repo" "$home"

  local died_naming_mismatch="false"
  if [ "$VERDICT_EXIT" -ne 0 ] && [[ "$VERDICT_ERR" == *"does not exist"* ]]; then
    died_naming_mismatch="true"
  fi
  assert_eq \
    "ResolveRepoTargets > failure > should die loudly when the repo basename is unix-utils but configs/ai-docs/claude/CLAUDE.md does not exist" \
    "true" "$died_naming_mismatch"
}

# ---------------------------------------------------------------

it_should_match_a_slug_that_equals_the_repo_slug_or_starts_with_the_repo_slug_plus_a_hyphen_boundary
it_should_resolve_read_scope_to_every_claude_projects_slug_when_run_from_the_unix_utils_repo_root
it_should_resolve_is_unix_utils_to_true_only_when_the_git_roots_directory_basename_is_exactly_the_literal_string_unix_utils
it_should_resolve_read_scope_to_only_the_current_repos_prefix_and_boundary_matched_slugs_when_run_from_another_repo
it_should_resolve_the_write_target_to_configs_ai_docs_claude_claude_md_when_run_from_the_unix_utils_repo
it_should_resolve_the_write_target_to_the_current_repos_own_claude_md_when_run_from_another_repo
it_should_match_a_worktree_slug_to_its_parent_repo_with_no_worktree_specific_logic
it_should_not_match_a_sibling_repo_whose_slug_shares_the_same_prefix_without_a_boundary
it_should_detect_the_unix_utils_repo_from_a_deeply_nested_subdirectory_of_the_repo_root
it_should_fall_back_to_the_cwd_derived_slug_alone_read_only_when_cwd_is_outside_any_git_repo
it_should_die_loudly_when_claude_claude_md_is_a_detached_regular_file_instead_of_a_symlink_into_the_repo
it_should_die_loudly_when_the_repo_basename_is_unix_utils_but_configs_ai_docs_claude_claude_md_does_not_exist

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
