#!/usr/bin/env bash

# test-resolve-base-ref.sh - plain-bash test file for
# resolve-base-ref.sh, the shared base-branch resolver five
# skill docs now invoke instead of inlining the bare
# `git symbolic-ref refs/remotes/origin/HEAD` one-liner.

# Usage:
#   bash test-resolve-base-ref.sh

# No bats dependency by design — same precedent as these
# sibling suites under configs/ai-docs/claude/:
#
# - scripts/tests/test-statusline-tier.sh
# - scripts/tests/test-tmux-window-title.sh

# Every fixture below builds its own throwaway git repo under
# a scratch dir and runs the script with that repo as CWD. The
# real unix-utils repo and the user's real git config are
# never touched.

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT_UNDER_TEST="$script_dir/../resolve-base-ref.sh"

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

# fresh_repo - a scratch git repo for one test, torn down by
# the caller when done. Isolated identity (user.name/email)
# so the fixture never depends on the machine's real
# ~/.gitconfig.
fresh_repo() {
  local repo
  repo="$(mktemp -d "${TMPDIR:-/tmp}/resolve-base-ref-test.XXXXXX")"
  git -C "$repo" init -q
  git -C "$repo" config user.name "Test"
  git -C "$repo" config user.email "test@example.com"
  printf '%s\n' "$repo"
}

# commit_on - create (or switch to) branch $2 in repo $1 and
# add one empty commit, so `git rev-parse --verify` finds it.
commit_on() {
  local repo="$1" branch="$2"
  git -C "$repo" checkout -q -B "$branch"
  git -C "$repo" commit -q --allow-empty -m "commit on $branch"
}

# set_fake_origin_head - points $repo/.git/refs/remotes/
# origin/HEAD at $branch, mimicking what `git remote set-head
# origin -a` (or a non-single-branch clone) would leave
# behind — without needing a real second remote repo.
set_fake_origin_head() {
  local repo="$1" branch="$2"
  git -C "$repo" symbolic-ref "refs/remotes/origin/HEAD" \
    "refs/remotes/origin/$branch"
}

# resolve - runs the script under test with $1 as CWD, and
# echoes "<stdout>|<exit status>" so a single assert_eq can
# pin both halves of the contract at once.
resolve() {
  local repo="$1" out status
  out="$(cd "$repo" && "$SCRIPT_UNDER_TEST")"
  status=$?
  printf '%s|%s' "$out" "$status"
}

it_should_prefer_origin_head_when_it_is_set() {
  local repo
  repo="$(fresh_repo)"
  commit_on "$repo" "trunk"
  set_fake_origin_head "$repo" "trunk"

  # main also exists, so this proves origin/HEAD wins over it
  # rather than the two happening to agree.
  commit_on "$repo" "main"

  assert_eq \
    "ResolveBaseRef > happy > should print origin/HEAD's target when it is set" \
    "trunk|0" "$(resolve "$repo")"
  rm -rf "$repo"
}

it_should_fall_back_to_local_main_when_origin_head_is_unset() {
  local repo
  repo="$(fresh_repo)"
  commit_on "$repo" "main"

  assert_eq \
    "ResolveBaseRef > fallback > should print local main when origin/HEAD is unset" \
    "main|0" "$(resolve "$repo")"
  rm -rf "$repo"
}

it_should_fall_back_to_local_master_when_only_master_exists() {
  local repo
  repo="$(fresh_repo)"
  commit_on "$repo" "master"

  assert_eq \
    "ResolveBaseRef > fallback > should print local master when origin/HEAD and main are both absent" \
    "master|0" "$(resolve "$repo")"
  rm -rf "$repo"
}

it_should_prefer_main_over_master_when_both_exist_locally() {
  local repo
  repo="$(fresh_repo)"
  commit_on "$repo" "master"
  commit_on "$repo" "main"

  # The fallback order is load-bearing: main must win even
  # though master also resolves, proving the loop checks main
  # first rather than matching either one arbitrarily.
  assert_eq \
    "ResolveBaseRef > fallback > should prefer main over master when both exist" \
    "main|0" "$(resolve "$repo")"
  rm -rf "$repo"
}

it_should_exit_one_with_no_stdout_when_none_of_the_three_exist() {
  local repo
  repo="$(fresh_repo)"

  # A repo with no commits at all has neither origin/HEAD nor
  # a resolvable main/master — the genuine "all three miss"
  # case the contract carves out for the caller to handle.
  assert_eq \
    "ResolveBaseRef > failure > should exit 1 with empty stdout when origin/HEAD, main, and master all miss" \
    "|1" "$(resolve "$repo")"
  rm -rf "$repo"
}

it_should_prefer_origin_head_when_it_is_set
it_should_fall_back_to_local_main_when_origin_head_is_unset
it_should_fall_back_to_local_master_when_only_master_exists
it_should_prefer_main_over_master_when_both_exist_locally
it_should_exit_one_with_no_stdout_when_none_of_the_three_exist

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
