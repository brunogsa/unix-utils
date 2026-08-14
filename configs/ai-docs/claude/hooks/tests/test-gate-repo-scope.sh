#!/usr/bin/env bash
# Plain-bash test file for lib/gate-repo-scope.sh.
#
# Usage:
#   bash test-gate-repo-scope.sh
#
# Exits 0 when every assertion passes, non-zero
# otherwise.
#
# Same no-bats rationale as the sibling test files.
#
# How the lib is exercised: it derives its gate repo
# from its OWN location, so each case plants a copy
# somewhere and asks the copy what it gates.
#
# Planting the copy is what tells a derived answer
# apart from a hardcoded one - a hardcoded path would
# keep naming unix-utils from anywhere on disk.
#
# Every case sources the lib in a subshell under the
# same `set -eo pipefail` both hooks run with, so a
# non-zero command at file scope would surface here
# as an aborted source rather than in production.

set -uo pipefail

hooks_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LIB="$hooks_dir/lib/gate-repo-scope.sh"

# The repo the installed lib is expected to gate,
# asked of git rather than written down: a literal
# path here would pass on this machine and fail on
# the other home-directory form.
own_repo=$(git -C "$hooks_dir" rev-parse --show-toplevel)

# pwd -P resolves /var -> /private/var on macOS.
#
# The lib compares against `git rev-parse
# --show-toplevel`, always physical, so an unresolved
# work_dir would make every match case a false miss.
work_dir=$(cd "$(mktemp -d)" && pwd -P)
cleanup() {
  rm -rf "$work_dir"
}
trap cleanup EXIT

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

# new_repo - creates an empty git repo under work_dir
# and prints its path. Identity is set locally so
# nothing here depends on the machine's global git
# config.
new_repo() {
  local dir="$work_dir/$1"
  mkdir -p "$dir"
  git -C "$dir" init -q .
  git -C "$dir" config user.email test@example.com
  git -C "$dir" config user.name test
  printf '%s' "$dir"
}

# plant_lib - copies the lib into <dir>/lib and
# prints the copy's path, so the copy derives its
# gate repo from where it was planted.
plant_lib() {
  local dir="$1"
  mkdir -p "$dir/lib"
  cp "$LIB" "$dir/lib/"
  printf '%s' "$dir/lib/gate-repo-scope.sh"
}

# ask_gate - sources the given lib copy and prints
# yes/no for is_gated_repo against the given root.
#
# The subshell carries `set -eo pipefail` because
# that is what both hooks set before sourcing it, and
# an unguarded non-zero at file scope would abort the
# hook instead of failing closed.
ask_gate() {
  local lib="$1" candidate="$2"
  bash -c '
    set -eo pipefail
    . "$1"
    if is_gated_repo "$2"; then printf yes; else printf no; fi
  ' _ "$lib" "$candidate" 2>/dev/null
}

# The installed lib lives inside unix-utils, so that
# is the one repo whose sessions the gates may fire
# in.
it_should_gate_the_repo_the_installed_lib_lives_in() {
  assert_eq "should gate the repo the installed lib lives in" \
    "yes" "$(ask_gate "$LIB" "$own_repo")"
}

# The whole point of the change: a session sitting in
# someone else's repo is not the user's to hold to
# personal standards.
it_should_not_gate_a_repo_the_installed_lib_does_not_live_in() {
  local foreign; foreign=$(new_repo foreign)

  assert_eq "should not gate a repo the installed lib does not live in" \
    "no" "$(ask_gate "$LIB" "$foreign")"
}

# Derived, not hardcoded: a copy planted in another
# repo gates THAT repo. This is also what lets the
# hook suites seat a copy in each throwaway fixture.
it_should_gate_whichever_repo_the_lib_copy_was_planted_in() {
  local planted; planted=$(new_repo planted)
  local lib_copy; lib_copy=$(plant_lib "$planted")

  assert_eq "should gate whichever repo the lib copy was planted in" \
    "yes" "$(ask_gate "$lib_copy" "$planted")"
}

# The other half of the same rule: the planted copy
# stops gating unix-utils, which a hardcoded path
# would keep naming from anywhere on disk.
it_should_stop_gating_unix_utils_once_the_copy_lives_elsewhere() {
  local planted; planted=$(new_repo planted-elsewhere)
  local lib_copy; lib_copy=$(plant_lib "$planted")

  assert_eq "should stop gating unix-utils once the copy lives elsewhere" \
    "no" "$(ask_gate "$lib_copy" "$own_repo")"
}

# Fail closed: with no repo to derive, the gate must
# match nothing rather than everything.
#
# Quiet is the direction this change wants, so an
# unresolvable gate repo silences the hooks instead of
# firing them everywhere.
it_should_gate_nothing_when_the_lib_sits_outside_any_git_work_tree() {
  local loose="$work_dir/loose"
  local lib_copy; lib_copy=$(plant_lib "$loose")
  local session; session=$(new_repo loose-session)

  assert_eq "should gate nothing when the lib sits outside any git work tree (fixture really is outside one)" \
    "outside" "$(git -C "$loose" rev-parse --show-toplevel >/dev/null 2>&1 && printf inside || printf outside)"
  assert_eq "should gate nothing when the lib sits outside any git work tree (a session repo)" \
    "no" "$(ask_gate "$lib_copy" "$session")"
  assert_eq "should gate nothing when the lib sits outside any git work tree (its own directory)" \
    "no" "$(ask_gate "$lib_copy" "$loose")"
}

# Sourcing it must never abort the hook that sourced
# it, and the outside-a-work-tree case is where an
# unguarded git call would.
it_should_source_cleanly_under_set_e_pipefail_outside_a_work_tree() {
  local loose="$work_dir/loose-source"
  local lib_copy; lib_copy=$(plant_lib "$loose")

  assert_eq "should source cleanly under set -e pipefail outside a work tree" \
    "sourced" "$(bash -c 'set -eo pipefail; . "$1"; printf sourced' _ "$lib_copy" 2>/dev/null)"
}

it_should_gate_the_repo_the_installed_lib_lives_in
it_should_not_gate_a_repo_the_installed_lib_does_not_live_in
it_should_gate_whichever_repo_the_lib_copy_was_planted_in
it_should_stop_gating_unix_utils_once_the_copy_lives_elsewhere
it_should_gate_nothing_when_the_lib_sits_outside_any_git_work_tree
it_should_source_cleanly_under_set_e_pipefail_outside_a_work_tree

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
