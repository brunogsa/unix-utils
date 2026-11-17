#!/usr/bin/env bash

# test-diffview-in-tmux.sh - plain-bash test file for the
# base-branch resolution in diffview-in-tmux.sh (the no-<ref>
# path).

# Usage:
#   bash test-diffview-in-tmux.sh

# No bats dependency by design - same precedent as
# scripts/tests/test-resolve-base-ref.sh.

# SAFETY: this suite runs inside a live tmux session and must
# never open a real pane. open-in-tmux.sh exits 2 and prints
# the command when $TMUX is empty, before it reaches any
# `tmux split-window`.
#
# Every run below goes through `env -u TMUX -u TMUX_PANE`, so
# that early exit is the only reachable path; TMUX_DRY_RUN=1
# is belt and braces.

# Every fixture builds its own throwaway git repo under a
# scratch dir; the real repo and the user's git config are
# never touched.

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT_UNDER_TEST="$script_dir/../diffview-in-tmux.sh"

pass_count=0
fail_count=0

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

# fresh_repo - a scratch git repo with an isolated identity.
fresh_repo() {
  local repo
  repo="$(mktemp -d "${TMPDIR:-/tmp}/diffview-in-tmux-test.XXXXXX")"
  git -C "$repo" init -q
  git -C "$repo" config user.name "Test"
  git -C "$repo" config user.email "test@example.com"
  printf '%s\n' "$repo"
}

# commit_on - create (or switch to) branch $2 in repo $1 and
# add one empty commit.
commit_on() {
  local repo="$1" branch="$2"
  git -C "$repo" checkout -q -B "$branch"
  git -C "$repo" commit -q --allow-empty -m "commit on $branch"
}

# set_dangling_origin_head - points origin/HEAD at a
# remote-tracking ref that does not exist, the state a pruned
# remote branch leaves behind.
set_dangling_origin_head() {
  local repo="$1" branch="$2"
  git -C "$repo" symbolic-ref "refs/remotes/origin/HEAD" \
    "refs/remotes/origin/$branch"
}

# clone_with_lagging_local_main - a real bare origin, a clone
# of it, and one more upstream commit fetched into the clone,
# so local main sits one commit behind origin/main.
# Echoes "<scratch dir>|<clone path>".
clone_with_lagging_local_main() {
  local scratch origin seed clone
  scratch="$(mktemp -d "${TMPDIR:-/tmp}/diffview-in-tmux-test.XXXXXX")"
  origin="$scratch/origin.git"
  seed="$scratch/seed"
  clone="$scratch/clone"
  git init -q --bare --initial-branch=main "$origin"
  git init -q --initial-branch=main "$seed"
  git -C "$seed" config user.name "Test"
  git -C "$seed" config user.email "test@example.com"
  git -C "$seed" commit -q --allow-empty -m "first commit on main"
  git -C "$seed" push -q "$origin" main
  git clone -q "$origin" "$clone"
  git -C "$seed" commit -q --allow-empty -m "upstream commit the clone's local main lacks"
  git -C "$seed" push -q "$origin" main
  git -C "$clone" fetch -q origin
  git -C "$clone" remote set-head origin -a >/dev/null
  printf '%s|%s' "$scratch" "$clone"
}

# diffview_ref - runs the script with no <ref> argument and
# $1 as CWD, with TMUX unset so no pane can open. Echoes
# "<ref after DiffviewOpen>|<exit status>"; open-in-tmux.sh's
# outside-tmux exit is 2.
diffview_ref() {
  local repo="$1" out status
  out="$(cd "$repo" && env -u TMUX -u TMUX_PANE TMUX_DRY_RUN=1 bash "$SCRIPT_UNDER_TEST" 2>/dev/null)"
  status=$?
  printf '%s|%s' \
    "$(printf '%s' "$out" | grep -o "DiffviewOpen [^']*" | head -n 1)" \
    "$status"
}

it_should_diff_against_origin_main_when_local_main_lags_behind_origin() {
  local fixture scratch clone
  fixture="$(clone_with_lagging_local_main)"
  scratch="${fixture%%|*}"
  clone="${fixture#*|}"

  assert_eq \
    "DiffviewInTmux > happy > should open Diffview against origin/main, not the lagging local main, when origin/HEAD points at main" \
    "DiffviewOpen origin/main|2" "$(diffview_ref "$clone")"
  rm -rf "$scratch"
}

it_should_fall_back_to_local_main_when_origin_head_points_at_a_missing_branch() {
  local repo
  repo="$(fresh_repo)"
  commit_on "$repo" "main"
  set_dangling_origin_head "$repo" "trunk"

  assert_eq \
    "DiffviewInTmux > fallback > should open Diffview against local main when origin/HEAD points at a remote branch that no longer exists" \
    "DiffviewOpen main|2" "$(diffview_ref "$repo")"
  rm -rf "$repo"
}

it_should_fall_back_to_local_main_when_origin_head_is_unset() {
  local repo
  repo="$(fresh_repo)"
  commit_on "$repo" "main"

  assert_eq \
    "DiffviewInTmux > fallback > should open Diffview against local main when origin/HEAD is unset" \
    "DiffviewOpen main|2" "$(diffview_ref "$repo")"
  rm -rf "$repo"
}

it_should_diff_against_origin_main_when_local_main_lags_behind_origin
it_should_fall_back_to_local_main_when_origin_head_points_at_a_missing_branch
it_should_fall_back_to_local_main_when_origin_head_is_unset

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
