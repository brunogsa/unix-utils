#!/usr/bin/env bash

# check-machine-headroom.sh - decides whether this machine has
# CPU/RAM/disk headroom to start a heavy command (test suite,
# build, lint) without starving the human co-tenant of this
# laptop.

# Usage:
#   check-machine-headroom.sh
#
#   if check-machine-headroom.sh; then
#     ./run-heavy-command.sh
#   fi

# Exit codes:
# - 0: GO, all three gates pass.
# - 1: NO-GO, at least one gate fails.
#
# - 2: UNKNOWN, a gate could not be measured; treated as
#     NO-GO by any caller that only checks the exit code.
#

# stdout is one greppable line, verdict word first. Every
# example below is one real stdout line, wrapped here only to
# fit this comment's width cap: fields are space-separated,
# with no line breaks, in the order shown.

# GO example:
#   HEADROOM=GO cores=12 load1=2.10 ratio=0.18 max_ratio=0.70
#   mem_avail_mb=6144 min_avail_mb=1536 disk_free_mb=104200
#   min_disk_mb=5120

# NO-GO example (reason joins each failing gate with "; "):
#   HEADROOM=NO-GO cores=4 load1=5.10 ratio=1.28 max_ratio=0.70
#   mem_avail_mb=500 min_avail_mb=1536 disk_free_mb=900
#   min_disk_mb=5120 reason="load ratio 1.28 exceeds max 0.70"

# UNKNOWN example:
#   HEADROOM=UNKNOWN reason="neither /proc/loadavg nor sysctl
#   found; cannot measure machine load"

# Thresholds, all env-overridable:
# - HEADROOM_LOAD_RATIO_MAX: default 0.70 (load1 / cores).
# - HEADROOM_MIN_AVAILABLE_MB: default 1536 (available RAM,
#   MiB).
#
# - HEADROOM_MIN_FREE_DISK_MB: default 5120 (free disk, MiB).

# HEADROOM_PROC_ROOT overrides the /proc mount point, so tests
# can point the Linux code path at a fixture directory without
# touching the real /proc.

# Only the 1-minute load average is read.
#
# The 5/15-minute windows lag a command that started seconds ago
# and would report false headroom right after a spike begins -
# that lag is inherent to load averaging, not something a wider
# window fixes, so don't "improve" this into reading them.

# Platform selection is existence-based, never
# `uname`/$OSTYPE: the Linux path is taken when
# $HEADROOM_PROC_ROOT/loadavg exists, and the macOS/sysctl path
# otherwise.

# A missing MemAvailable: line in /proc/meminfo (pre-3.14
# kernel) is reported UNKNOWN rather than reconstructed from
# MemFree, which undercounts reclaimable page cache and would
# report a confident false NO-GO.

# macOS "available" memory deliberately excludes `active`
# and `wired` pages - only free + inactive + speculative +
# purgeable count.
#
# Read the page size via `sysctl -n hw.pagesize`, never a
# hardcoded 4096: Apple Silicon uses 16384, and hardcoding
# is wrong by 4x.

# This script writes nothing to disk and caches nothing -
# headroom is a live-only signal, and a stale read is worse than
# no read.

set -uo pipefail

: "${HEADROOM_LOAD_RATIO_MAX:=0.70}"
: "${HEADROOM_MIN_AVAILABLE_MB:=1536}"
: "${HEADROOM_MIN_FREE_DISK_MB:=5120}"

# proc_root_path - the /proc mount point to read, or the
# HEADROOM_PROC_ROOT override tests use to point this at a
# fixture directory.
proc_root_path() {
  printf '%s\n' "${HEADROOM_PROC_ROOT:-/proc}"
}

# is_number - true when $1 is a bare non-negative integer or
# decimal (no sign, no exponent).
#
# Guards every value this script feeds into
# `awk`/`[ -gt ]` arithmetic, so a malformed or
# missing source value is caught before it can crash the script
# or silently coerce to zero.
is_number() {
  printf '%s' "$1" | grep -Eq '^[0-9]+(\.[0-9]+)?$'
}

# ----------------------------------------------------------
# Linux readers
# ----------------------------------------------------------

# linux_load1 - the 1-minute load average, field 1 of
# $proc_root/loadavg.
linux_load1() {
  local proc_root="$1" load1
  load1="$(awk '{print $1}' "$proc_root/loadavg" 2>/dev/null)"
  is_number "$load1" || return 1
  printf '%s\n' "$load1"
}

# linux_cores - `nproc` when it's on PATH and sane, else the
# count of `^processor[[:space:]]*:` lines in
# $proc_root/cpuinfo.
linux_cores() {
  local proc_root="$1" n
  n="$(nproc 2>/dev/null)"
  if is_number "$n" && [ "$n" -gt 0 ] 2>/dev/null; then
    printf '%s\n' "$n"
    return 0
  fi
  n="$(grep -c '^processor[[:space:]]*:' "$proc_root/cpuinfo" 2>/dev/null)"
  if is_number "$n" && [ "$n" -gt 0 ] 2>/dev/null; then
    printf '%s\n' "$n"
    return 0
  fi
  return 1
}

# linux_mem_avail_mb - MemAvailable: from $proc_root/meminfo,
# converted from kB to MiB.
# Fails (never falls back to MemFree) when that line is absent.
linux_mem_avail_mb() {
  local proc_root="$1" kb
  kb="$(awk '/^MemAvailable:/ {print $2}' "$proc_root/meminfo" 2>/dev/null)"
  is_number "$kb" || return 1
  awk -v kb="$kb" 'BEGIN { printf "%d\n", kb / 1024 }'
}

# ----------------------------------------------------------
# macOS readers
# ----------------------------------------------------------

# macos_cores - `sysctl -n hw.ncpu`.
macos_cores() {
  local n
  n="$(sysctl -n hw.ncpu 2>/dev/null)"
  is_number "$n" && [ "$n" -gt 0 ] 2>/dev/null || return 1
  printf '%s\n' "$n"
}

# macos_load1 - the first of the three numbers inside
# `sysctl -n vm.loadavg`'s "{ 4.23 3.96 3.42 }" braces.
macos_load1() {
  local raw load1
  raw="$(sysctl -n vm.loadavg 2>/dev/null)"
  load1="$(printf '%s' "$raw" | grep -oE '\{ *[0-9]+\.[0-9]+' | awk '{print $2}')"
  is_number "$load1" || return 1
  printf '%s\n' "$load1"
}

# macos_mem_avail_mb - (free + inactive + speculative +
# purgeable) pages from `vm_stat`, times the real page size
# from `sysctl -n hw.pagesize` (never hardcoded), in MiB.
#
# `active` and `wired` pages are deliberately
# excluded - they are not memory a new process can claim without
# contention.
macos_mem_avail_mb() {
  local pagesize vmstat_out free inactive spec purg v
  command -v vm_stat >/dev/null 2>&1 || return 1
  pagesize="$(sysctl -n hw.pagesize 2>/dev/null)"
  is_number "$pagesize" || return 1
  vmstat_out="$(vm_stat 2>/dev/null)" || return 1

  free="$(printf '%s\n' "$vmstat_out" | grep 'Pages free:' | grep -oE '[0-9]+')"
  inactive="$(printf '%s\n' "$vmstat_out" | grep 'Pages inactive:' | grep -oE '[0-9]+')"
  spec="$(printf '%s\n' "$vmstat_out" | grep 'Pages speculative:' | grep -oE '[0-9]+')"
  purg="$(printf '%s\n' "$vmstat_out" | grep 'Pages purgeable:' | grep -oE '[0-9]+')"

  for v in "$free" "$inactive" "$spec" "$purg"; do
    is_number "$v" || return 1
  done

  awk -v f="$free" -v i="$inactive" -v s="$spec" -v p="$purg" -v ps="$pagesize" \
    'BEGIN { printf "%d\n", (f + i + s + p) * ps / 1048576 }'
}

# ----------------------------------------------------------
# Shared: disk (identical logic on both platforms)
# ----------------------------------------------------------

# read_disk_free_mb - free space on the current working
# directory's filesystem, in MiB, from `df -Pk .`.
read_disk_free_mb() {
  df -Pk . 2>/dev/null | awk 'NR==2 { printf "%d\n", $4 / 1024 }'
}

# ----------------------------------------------------------
# Gate evaluation
# ----------------------------------------------------------

# gate_passes - true when $1 <= $2 (mode "le") or $1 >= $2 (mode
# "ge"), compared as floats via awk so this works for both
# integer and decimal inputs.
gate_passes() {
  local value="$1" threshold="$2" mode="$3"
  awk -v v="$value" -v t="$threshold" -v mode="$mode" \
    'BEGIN { exit !(mode == "le" ? v <= t : v >= t) }'
}

main() {
  local proc_root max_ratio min_avail min_disk
  proc_root="$(proc_root_path)"
  max_ratio="$HEADROOM_LOAD_RATIO_MAX"
  min_avail="$HEADROOM_MIN_AVAILABLE_MB"
  min_disk="$HEADROOM_MIN_FREE_DISK_MB"

  local cores="" load1="" mem_avail_mb="" unknown_reason=""

  if [ -f "$proc_root/loadavg" ]; then
    load1="$(linux_load1 "$proc_root")" || unknown_reason="malformed /proc/loadavg: cannot parse the load average"
    if [ -z "$unknown_reason" ]; then
      cores="$(linux_cores "$proc_root")" || unknown_reason="cannot determine cpu core count from nproc or /proc/cpuinfo"
    fi
    if [ -z "$unknown_reason" ]; then
      mem_avail_mb="$(linux_mem_avail_mb "$proc_root")" || unknown_reason="MemAvailable not found in /proc/meminfo"
    fi
  elif command -v sysctl >/dev/null 2>&1; then
    load1="$(macos_load1)" || unknown_reason="malformed sysctl vm.loadavg output: cannot parse the load average"
    if [ -z "$unknown_reason" ]; then
      cores="$(macos_cores)" || unknown_reason="cannot determine cpu core count from sysctl hw.ncpu"
    fi
    if [ -z "$unknown_reason" ]; then
      mem_avail_mb="$(macos_mem_avail_mb)" || unknown_reason="vm_stat unavailable or unparseable; cannot determine available memory"
    fi
  else
    unknown_reason="neither /proc/loadavg nor sysctl found; cannot measure machine load"
  fi

  if [ -z "$unknown_reason" ]; then
    local disk_free_mb
    disk_free_mb="$(read_disk_free_mb)"
    if ! is_number "$disk_free_mb"; then
      unknown_reason="cannot determine free disk space from df"
    fi
  fi

  if [ -n "$unknown_reason" ]; then
    printf 'HEADROOM=UNKNOWN reason="%s"\n' "$unknown_reason"
    exit 2
  fi

  local ratio load1_fmt
  ratio="$(awk -v l="$load1" -v c="$cores" 'BEGIN { printf "%.2f", l / c }')"
  load1_fmt="$(awk -v l="$load1" 'BEGIN { printf "%.2f", l }')"

  local reasons="" go=1

  if ! gate_passes "$ratio" "$max_ratio" le; then
    reasons="load ratio $ratio exceeds max $max_ratio"
    go=0
  fi

  if ! gate_passes "$mem_avail_mb" "$min_avail" ge; then
    [ -n "$reasons" ] && reasons="$reasons; "
    reasons="${reasons}available memory ${mem_avail_mb}MB below min ${min_avail}MB"
    go=0
  fi

  if ! gate_passes "$disk_free_mb" "$min_disk" ge; then
    [ -n "$reasons" ] && reasons="$reasons; "
    reasons="${reasons}free disk ${disk_free_mb}MB below min ${min_disk}MB"
    go=0
  fi

  if [ "$go" -eq 1 ]; then
    printf 'HEADROOM=GO cores=%s load1=%s ratio=%s max_ratio=%s mem_avail_mb=%s min_avail_mb=%s disk_free_mb=%s min_disk_mb=%s\n' \
      "$cores" "$load1_fmt" "$ratio" "$max_ratio" "$mem_avail_mb" "$min_avail" "$disk_free_mb" "$min_disk"
    exit 0
  fi

  printf 'HEADROOM=NO-GO cores=%s load1=%s ratio=%s max_ratio=%s mem_avail_mb=%s min_avail_mb=%s disk_free_mb=%s min_disk_mb=%s reason="%s"\n' \
    "$cores" "$load1_fmt" "$ratio" "$max_ratio" "$mem_avail_mb" "$min_avail" "$disk_free_mb" "$min_disk" "$reasons"
  exit 1
}

if ! (return 0 2>/dev/null); then
  main "$@"
fi
