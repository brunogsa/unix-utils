#!/usr/bin/env bash
# run-tests.sh - Run every bash test suite in this repo.
#
# Usage:
#   ./run-tests.sh
#
# Exit codes:
#   0 - every suite passed
#   1 - at least one suite failed
#
# The repo-root pytest.ini's suites run here too, as one
# more entry alongside the bash suites below.
#
# A prior version left pytest out and pointed at running
# it separately — but nothing enforced that second
# command, so this script's own exit code silently lied
# about whether the repo was actually green.
#
# Why this exists:
#   Four separate bash test trees had nothing
#   enumerating them, so a suite ran only when someone
#   remembered it by name.
#
#   The hooks tree was the sharpest case: ten gate
#   suites, zero callers, so a regression in any Stop
#   hook would have shipped silently.
#
# Discovery is by glob, never by an enumerated list:
#   a runner that needs each new suite registered
#   reproduces the exact failure it exists to fix.
#
# Every suite runs even after one fails, because a
# runner that stops at the first failure hides the
# other 36.

set -uo pipefail

# Anchored on this script's own directory, not the
# caller's, so the globs below resolve the same from
# any subdirectory.
repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
cd "$repo_root" || exit 1

# Only one full-suite run at a time.
#
# Five sessions sharing this checkout launched five
# concurrent runs, the oldest 7m54s in. They starved
# each other for CPU until three callers gave up on a
# suite that never came back.
#
# Nothing stopped them, so the serialization belongs
# here and not in every caller's memory.
#
# mkdir, not flock(1): flock ships with util-linux and
# is absent from stock macOS, while this repo's
# CLAUDE.md makes macOS + Linux support non-negotiable.
#
# mkdir is atomic on every POSIX filesystem, so exactly
# one racer creates the directory and the rest fail.
#
# The lock lives under TMPDIR, never in the working
# tree: a lock inside the repo would surface in
# `git status` for every session and risks being
# committed.
#
# It is keyed by this script's own directory, so a copy
# running from a test sandbox takes a lock of its own.
#
# Without that key, a suite exercising a sandboxed copy
# would deadlock against the outer run already holding
# the one shared lock.
#
# cksum is POSIX and spelled the same on macOS and
# Linux, unlike md5sum/md5. A checksum collision
# between two checkouts would only over-serialize them,
# never corrupt a run.
lock_root="${TMPDIR:-/tmp}"
lock_key=$(printf '%s' "$repo_root" | cksum)
lock_key=${lock_key%% *}
lock_dir="$lock_root/run-tests-$lock_key.lock"
lock_pid_file="$lock_dir/pid"
lock_break_dir="$lock_dir.breaking"
lock_held=0
lock_poll_seconds=2
empty_pid_polls=0

# release_lock - drops the lock only when this run owns
# it, so a run that broke someone else's stale lock, or
# one that bailed before taking any, can never delete
# the live lock a third run is holding.
release_lock() {
  [ "$lock_held" -eq 1 ] || return 0
  lock_held=0
  rm -rf "$lock_dir"
}

# break_pidless_lock - clears a lock whose pid file
# never appeared, which is what an owner killed between
# taking the lock and recording itself leaves behind.
#
# It waits for a second sighting one poll later, so the
# microseconds a healthy owner spends between those two
# steps are never mistaken for that orphan.
break_pidless_lock() {
  if [ "$empty_pid_polls" -lt 1 ]; then
    empty_pid_polls=$((empty_pid_polls + 1))
    return 1
  fi

  printf '%s\n' "run-tests.sh: clearing a stale lock with no owner recorded" >&2
  rm -rf "$lock_dir"
}

# break_stale_lock - clears a lock whose owner is gone,
# reporting non-zero when there was nothing to clear.
#
# Breaking is itself serialized behind a second mkdir,
# so two waiters cannot both decide to clear the same
# directory and have the loser delete the fresh lock
# the winner took in between.
#
# Residual risk, stated rather than pretended away: the
# OS recycles pids, so a dead owner's pid since handed
# to an unrelated live process still reads as alive.
#
# This run then waits until that unrelated process
# exits. Closing that hole needs an OS-level lock
# (flock/fcntl), which is what stock macOS lacks.
break_stale_lock() {
  mkdir "$lock_break_dir" 2>/dev/null || return 1

  local owner_pid broke=1
  owner_pid=$(cat "$lock_pid_file" 2>/dev/null)

  if [ ! -d "$lock_dir" ]; then
    broke=0
  elif [ -z "$owner_pid" ]; then
    break_pidless_lock && broke=0
  elif ! kill -0 "$owner_pid" 2>/dev/null; then
    printf '%s\n' "run-tests.sh: clearing a stale lock left by dead pid $owner_pid" >&2
    rm -rf "$lock_dir"
    broke=0
  fi

  [ -z "$owner_pid" ] || empty_pid_polls=0
  rmdir "$lock_break_dir" 2>/dev/null
  return "$broke"
}

# acquire_lock - blocks until this run owns the lock.
#
# It never returns without one: skipping the suites and
# exiting 0 would report a green that nobody ran, which
# is the one outcome worse than waiting.
acquire_lock() {
  local announced=0 owner_pid

  # An unwritable lock root can never yield a lock, so
  # waiting on it would hang until someone noticed.
  # Bail out loudly instead - non-zero, and explicit
  # that no suite ran.
  if ! mkdir -p "$lock_root" 2>/dev/null || [ ! -w "$lock_root" ]; then
    printf '%s\n' "run-tests.sh: cannot create a lock under $lock_root - the suites did NOT run" >&2
    exit 2
  fi

  while ! mkdir "$lock_dir" 2>/dev/null; do
    break_stale_lock && continue

    # Announced once, not per poll: a caller needs to
    # know why the run is idle, not a running tally.
    if [ "$announced" -eq 0 ]; then
      owner_pid=$(cat "$lock_pid_file" 2>/dev/null)
      printf '%s\n' "run-tests.sh: another run is in progress (pid ${owner_pid:-unknown}), waiting..." >&2
      announced=1
    fi

    sleep "$lock_poll_seconds"
  done

  lock_held=1
  printf '%s\n' "$$" > "$lock_pid_file"
}

log_dir=$(mktemp -d)

# One cleanup path for every exit: the INT and TERM
# handlers only re-exit, which fires the EXIT trap.
#
# Releasing there is what keeps an interrupted run from
# wedging every later run behind a lock its owner is
# never coming back to drop.
trap 'rm -rf "$log_dir"; release_lock' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

acquire_lock

pass_count=0
fail_count=0
failed_suites=()
failed_logs=()
suite_index=0

# record_pass/record_fail - shared by the bash-suite loop below
# and the pytest step after it, so both report through the same
# counters, PASS/FAIL line, and failure-replay list rather than
# two near-identical bookkeeping blocks drifting apart.
record_pass() {
  pass_count=$((pass_count + 1))
  printf 'PASS  %s\n' "$1"
}

record_fail() {
  fail_count=$((fail_count + 1))
  failed_suites+=("$1")
  failed_logs+=("$2")
  printf 'FAIL  %s\n' "$1"
}

for suite in \
  configs/ai-docs/claude/tests/test-*.sh \
  configs/ai-docs/claude/scripts/tests/test-*.sh \
  configs/ai-docs/claude/hooks/tests/test-*.sh \
  configs/ai-docs/claude/skills/*/scripts/tests/test-*.sh
do
  [ -f "$suite" ] || continue

  # Named by index, not by the suite path: two trees
  # can hold a suite of the same name, and flattening
  # the path would collide their logs.
  suite_index=$((suite_index + 1))
  log_file="$log_dir/$suite_index.log"

  if bash "$suite" > "$log_file" 2>&1; then
    record_pass "$suite"
  else
    record_fail "$suite" "$log_file"
  fi
done

# pytest.ini at the repo root collects every python suite
# from one bare `pytest` invocation, so it runs here as one
# more suite through the same record_pass/record_fail path.
#
# The python failures replay below exactly like a bash
# suite's would.
#
# A missing pytest binary fails loudly instead of silently
# reading as green: skipping it here would recreate the same gap
# this fold-in exists to close, just moved from "forgot to run
# pytest" to "pytest wasn't on PATH".
suite_index=$((suite_index + 1))
log_file="$log_dir/$suite_index.log"

if ! command -v pytest > /dev/null 2>&1; then
  printf 'pytest: command not found\n' > "$log_file"
  record_fail "pytest" "$log_file"
elif pytest > "$log_file" 2>&1; then
  record_pass "pytest"
else
  record_fail "pytest" "$log_file"
fi

# A bare FAIL line names the suite but not the
# assertion, forcing a second run by hand to learn
# what broke. Replaying each failing log closes that.
#
# The count guards the loop because macOS ships bash
# 3.2, where expanding an empty array under `set -u`
# aborts the script.
if [ "$fail_count" -gt 0 ]; then
  for i in "${!failed_suites[@]}"; do
    printf '\n===== %s =====\n' "${failed_suites[$i]}"
    cat "${failed_logs[$i]}"
  done
fi

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
