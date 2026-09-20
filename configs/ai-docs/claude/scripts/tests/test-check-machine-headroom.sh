#!/usr/bin/env bash

# test-check-machine-headroom.sh - plain-bash test file for
# check-machine-headroom.sh, the CPU/RAM/disk headroom gate an
# AI agent calls before launching a heavy command.

# Usage:
#   bash test-check-machine-headroom.sh

# No bats dependency by design - same precedent as:
#   scripts/tests/test-resolve-base-ref.sh
#   scripts/tests/test-statusline-tier.sh

# Every fixture builds its own throwaway scratch dir (a fake
# /proc tree and/or a fake bin/ dir) and points the script at it
# via HEADROOM_PROC_ROOT and a curated PATH.
#
# The real /proc, the real sysctl/vm_stat/df, and the real
# filesystem outside each fixture's own scratch dir are never
# touched.
#
# PATH is always fully curated (env -i, never merely
# prepended-to), so a tool a test means to keep absent (nproc,
# sysctl, vm_stat) stays genuinely unreachable regardless of
# what the host machine has installed.

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT_UNDER_TEST="$script_dir/../check-machine-headroom.sh"
real_bash="$(command -v bash)"

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

# assert_contains - like assert_eq, but for output whose exact
# text isn't pinned (never used for a dynamic path - every
# reason string in this script is a fixed literal - only for
# assertions phrased as "the fixture directory now differs").
assert_contains() {
  local description="$1" needle="$2" haystack="$3"
  case "$haystack" in
    *"$needle"*)
      pass_count=$((pass_count + 1))
      printf 'ok - %s\n' "$description"
      ;;
    *)
      fail_count=$((fail_count + 1))
      printf 'not ok - %s\n  expected to contain: %s\n  actual:   %s\n' "$description" "$needle" "$haystack"
      ;;
  esac
}

# scratch_dir - a fresh throwaway directory for one test.
scratch_dir() {
  mktemp -d "${TMPDIR:-/tmp}/check-machine-headroom-test.XXXXXX"
}

# empty_proc_root - a scratch dir with no loadavg file, so the
# script's existence check falls through to the macOS/sysctl
# branch (or to "neither" when sysctl is also curated out).
empty_proc_root() {
  scratch_dir
}

# add_real_tool - symlinks the host's real $tool into $bindir,
# for the handful of generic utilities (awk, grep) every
# fixture needs regardless of which platform branch it drives.
add_real_tool() {
  local bindir="$1" tool="$2" real
  mkdir -p "$bindir"
  real="$(command -v "$tool" 2>/dev/null)" || return 1
  ln -sf "$real" "$bindir/$tool"
}

# build_linux_proc_root - writes loadavg/cpuinfo/meminfo under
# $dir. $mem_avail_kb of "" omits the MemAvailable: line
# entirely (case 6). $cores of 0 writes an empty cpuinfo (case
# 7, combined with a curated PATH that excludes nproc).
build_linux_proc_root() {
  local dir="$1" cores="$2" load1="$3" mem_avail_kb="$4"
  mkdir -p "$dir"
  printf '%s 0.00 0.00 1/200 12345\n' "$load1" >"$dir/loadavg"

  : >"$dir/cpuinfo"
  local i=0
  while [ "$i" -lt "$cores" ]; do
    printf 'processor\t: %d\n' "$i" >>"$dir/cpuinfo"
    i=$((i + 1))
  done

  {
    printf 'MemTotal:       16384000 kB\n'
    if [ -n "$mem_avail_kb" ]; then
      printf 'MemAvailable:   %s kB\n' "$mem_avail_kb"
    fi
    printf 'MemFree:        1000000 kB\n'
  } >"$dir/meminfo"
}

# write_malformed_loadavg - overwrites loadavg with a
# non-numeric first field (case 19a).
write_malformed_loadavg() {
  local dir="$1"
  mkdir -p "$dir"
  printf 'abc 0.00 0.00 1/200 12345\n' >"$dir/loadavg"
}

# write_fake_df - a fake `df` printing a fixed Available (KB)
# column, so every test's disk_free_mb is deterministic and no
# fixture ever reads the real filesystem's free space.
write_fake_df() {
  local bindir="$1" avail_kb="$2" f
  f="$bindir/df"
  mkdir -p "$bindir"
  {
    printf '#!%s\n' "$real_bash"
    printf 'printf "%%s\\n" "Filesystem 1024-blocks Used Available Capacity Mounted-on"\n'
    printf 'printf "%%s\\n" "/dev/disk1 1000000 500000 %s 50 /"\n' "$avail_kb"
  } >"$f"
  chmod +x "$f"
}

# write_fake_sysctl - a fake `sysctl` answering
# `-n hw.ncpu`, `-n vm.loadavg`, and `-n hw.pagesize`.
#
# $loadavg_raw is exactly what `sysctl -n vm.loadavg` prints, so
# a caller can pass a genuinely malformed shape (case 19b), not
# just a high/low number.
write_fake_sysctl() {
  local bindir="$1" ncpu="$2" loadavg_raw="$3" pagesize="$4" f
  f="$bindir/sysctl"
  mkdir -p "$bindir"
  {
    printf '#!%s\n' "$real_bash"

    # literal $2 for the generated script, not a shell expansion
    # shellcheck disable=SC2016
    printf 'case "$2" in\n'
    printf '  hw.ncpu) printf "%%s\\n" "%s" ;;\n' "$ncpu"
    printf '  vm.loadavg) printf "%%s\\n" "%s" ;;\n' "$loadavg_raw"
    printf '  hw.pagesize) printf "%%s\\n" "%s" ;;\n' "$pagesize"
    printf 'esac\n'
  } >"$f"
  chmod +x "$f"
}

# write_fake_vm_stat - a fake `vm_stat` reporting the four
# page counts the script sums, each with the real tool's
# trailing period so the fixture also proves that period gets
# stripped correctly.
write_fake_vm_stat() {
  local bindir="$1" free="$2" inactive="$3" spec="$4" purg="$5" f
  f="$bindir/vm_stat"
  mkdir -p "$bindir"
  {
    printf '#!%s\n' "$real_bash"
    printf 'echo "Mach Virtual Memory Statistics: (page size of 16384 bytes)"\n'
    printf 'echo "Pages free:                                   %s."\n' "$free"
    printf 'echo "Pages active:                                 1000."\n'
    printf 'echo "Pages inactive:                               %s."\n' "$inactive"
    printf 'echo "Pages speculative:                            %s."\n' "$spec"
    printf 'echo "Pages purgeable:                               %s."\n' "$purg"
    printf 'echo "Pages wired down:                             500."\n'
  } >"$f"
  chmod +x "$f"
}

# run_headroom - runs the script under test with a fully curated
# environment (env -i, so no host env var or PATH entry leaks
# in), $2 as PATH, and $1 as HEADROOM_PROC_ROOT.
# Trailing args are extra `VAR=value` env assignments (e.g.
#
# threshold overrides).
# Echoes "<stdout>|<exit status>".
run_headroom() {
  local proc_root="$1" bindir="$2"
  shift 2
  local out status
  out="$(env -i PATH="$bindir" HEADROOM_PROC_ROOT="$proc_root" "$@" "$real_bash" "$SCRIPT_UNDER_TEST" 2>&1)"
  status=$?
  printf '%s|%s' "$out" "$status"
}

# run_headroom_stdout_only - like run_headroom, but keeps
# stderr out of the captured value, for the one test (case 16)
# that must prove stdout alone is a single line.
run_headroom_stdout_only() {
  local proc_root="$1" bindir="$2"
  shift 2
  local out status
  out="$(env -i PATH="$bindir" HEADROOM_PROC_ROOT="$proc_root" "$@" "$real_bash" "$SCRIPT_UNDER_TEST" 2>/dev/null)"
  status=$?
  printf '%s|%s' "$out" "$status"
}

# stat_mtime - GNU stat first, falling back to BSD stat -
# same two-flavour fallback as statusline-tier.sh's
# stat_mtime_epoch.
stat_mtime() {
  stat -c '%Y' "$1" 2>/dev/null || stat -f '%m' "$1" 2>/dev/null
}

# snapshot_tree - "<path> <mtime>" per file under $1, sorted,
# so two snapshots can be diffed to prove a directory tree was
# not written to.
snapshot_tree() {
  local dir="$1" f
  find "$dir" -type f 2>/dev/null | sort | while IFS= read -r f; do
    printf '%s %s\n' "$f" "$(stat_mtime "$f")"
  done
}

it_should_go_when_linux_load_memory_and_disk_are_all_ample() {
  local proc bin
  proc="$(scratch_dir)"
  bin="$(scratch_dir)"
  build_linux_proc_root "$proc" 8 "1.60" "4194304"
  add_real_tool "$bin" awk
  add_real_tool "$bin" grep
  write_fake_df "$bin" "20971520"

  assert_eq \
    "CheckMachineHeadroom > linux > should GO when load, memory and disk are all ample" \
    "HEADROOM=GO cores=8 load1=1.60 ratio=0.20 max_ratio=0.70 mem_avail_mb=4096 min_avail_mb=1536 disk_free_mb=20480 min_disk_mb=5120|0" \
    "$(run_headroom "$proc" "$bin")"
  rm -rf "$proc" "$bin"
}

it_should_no_go_when_linux_load_ratio_alone_exceeds_max() {
  local proc bin
  proc="$(scratch_dir)"
  bin="$(scratch_dir)"
  build_linux_proc_root "$proc" 8 "7.20" "4194304"
  add_real_tool "$bin" awk
  add_real_tool "$bin" grep
  write_fake_df "$bin" "20971520"

  assert_eq \
    "CheckMachineHeadroom > linux > should NO-GO citing load when only the load ratio exceeds max" \
    'HEADROOM=NO-GO cores=8 load1=7.20 ratio=0.90 max_ratio=0.70 mem_avail_mb=4096 min_avail_mb=1536 disk_free_mb=20480 min_disk_mb=5120 reason="load ratio 0.90 exceeds max 0.70"|1' \
    "$(run_headroom "$proc" "$bin")"
  rm -rf "$proc" "$bin"
}

it_should_no_go_when_linux_available_memory_alone_is_below_floor() {
  local proc bin
  proc="$(scratch_dir)"
  bin="$(scratch_dir)"
  build_linux_proc_root "$proc" 8 "1.60" "524288"
  add_real_tool "$bin" awk
  add_real_tool "$bin" grep
  write_fake_df "$bin" "20971520"

  assert_eq \
    "CheckMachineHeadroom > linux > should NO-GO citing memory when only available memory is below floor" \
    'HEADROOM=NO-GO cores=8 load1=1.60 ratio=0.20 max_ratio=0.70 mem_avail_mb=512 min_avail_mb=1536 disk_free_mb=20480 min_disk_mb=5120 reason="available memory 512MB below min 1536MB"|1' \
    "$(run_headroom "$proc" "$bin")"
  rm -rf "$proc" "$bin"
}

it_should_no_go_when_linux_free_disk_alone_is_below_floor() {
  local proc bin
  proc="$(scratch_dir)"
  bin="$(scratch_dir)"
  build_linux_proc_root "$proc" 8 "1.60" "4194304"
  add_real_tool "$bin" awk
  add_real_tool "$bin" grep
  write_fake_df "$bin" "1048576"

  assert_eq \
    "CheckMachineHeadroom > linux > should NO-GO citing disk when only free disk is below floor" \
    'HEADROOM=NO-GO cores=8 load1=1.60 ratio=0.20 max_ratio=0.70 mem_avail_mb=4096 min_avail_mb=1536 disk_free_mb=1024 min_disk_mb=5120 reason="free disk 1024MB below min 5120MB"|1' \
    "$(run_headroom "$proc" "$bin")"
  rm -rf "$proc" "$bin"
}

it_should_name_both_gates_when_load_and_disk_fail_together() {
  local proc bin
  proc="$(scratch_dir)"
  bin="$(scratch_dir)"
  build_linux_proc_root "$proc" 8 "7.20" "4194304"
  add_real_tool "$bin" awk
  add_real_tool "$bin" grep
  write_fake_df "$bin" "1048576"

  assert_eq \
    "CheckMachineHeadroom > linux > should name both load and disk in reason when they fail together" \
    'HEADROOM=NO-GO cores=8 load1=7.20 ratio=0.90 max_ratio=0.70 mem_avail_mb=4096 min_avail_mb=1536 disk_free_mb=1024 min_disk_mb=5120 reason="load ratio 0.90 exceeds max 0.70; free disk 1024MB below min 5120MB"|1' \
    "$(run_headroom "$proc" "$bin")"
  rm -rf "$proc" "$bin"
}

it_should_be_unknown_when_linux_meminfo_has_no_mem_available_line() {
  local proc bin
  proc="$(scratch_dir)"
  bin="$(scratch_dir)"
  build_linux_proc_root "$proc" 8 "1.60" ""
  add_real_tool "$bin" awk
  add_real_tool "$bin" grep
  write_fake_df "$bin" "20971520"

  assert_eq \
    "CheckMachineHeadroom > linux > should be UNKNOWN when meminfo has no MemAvailable line" \
    'HEADROOM=UNKNOWN reason="MemAvailable not found in /proc/meminfo"|2' \
    "$(run_headroom "$proc" "$bin")"
  rm -rf "$proc" "$bin"
}

it_should_be_unknown_when_nproc_is_absent_and_cpuinfo_has_no_processor_lines() {
  local proc bin
  proc="$(scratch_dir)"
  bin="$(scratch_dir)"
  build_linux_proc_root "$proc" 0 "1.60" "4194304"
  add_real_tool "$bin" awk
  add_real_tool "$bin" grep
  write_fake_df "$bin" "20971520"

  assert_eq \
    "CheckMachineHeadroom > linux > should be UNKNOWN when nproc is absent and cpuinfo has zero processor lines" \
    'HEADROOM=UNKNOWN reason="cannot determine cpu core count from nproc or /proc/cpuinfo"|2' \
    "$(run_headroom "$proc" "$bin")"
  rm -rf "$proc" "$bin"
}

it_should_go_when_macos_load_memory_and_disk_are_all_ample() {
  local proc bin
  proc="$(empty_proc_root)"
  bin="$(scratch_dir)"
  add_real_tool "$bin" awk
  add_real_tool "$bin" grep
  write_fake_sysctl "$bin" "8" "{ 1.60 1.40 1.20 }" "16384"
  write_fake_vm_stat "$bin" "300000" "50000" "20000" "14000"
  write_fake_df "$bin" "104857600"

  assert_eq \
    "CheckMachineHeadroom > macos > should GO when load, memory and disk are all ample" \
    "HEADROOM=GO cores=8 load1=1.60 ratio=0.20 max_ratio=0.70 mem_avail_mb=6000 min_avail_mb=1536 disk_free_mb=102400 min_disk_mb=5120|0" \
    "$(run_headroom "$proc" "$bin")"
  rm -rf "$proc" "$bin"
}

it_should_no_go_when_macos_load_average_exceeds_max() {
  local proc bin
  proc="$(empty_proc_root)"
  bin="$(scratch_dir)"
  add_real_tool "$bin" awk
  add_real_tool "$bin" grep
  write_fake_sysctl "$bin" "8" "{ 7.20 3.96 3.42 }" "16384"
  write_fake_vm_stat "$bin" "300000" "50000" "20000" "14000"
  write_fake_df "$bin" "104857600"

  assert_eq \
    "CheckMachineHeadroom > macos > should NO-GO when vm.loadavg's first number exceeds max ratio" \
    'HEADROOM=NO-GO cores=8 load1=7.20 ratio=0.90 max_ratio=0.70 mem_avail_mb=6000 min_avail_mb=1536 disk_free_mb=102400 min_disk_mb=5120 reason="load ratio 0.90 exceeds max 0.70"|1' \
    "$(run_headroom "$proc" "$bin")"
  rm -rf "$proc" "$bin"
}

it_should_no_go_when_macos_vm_stat_reports_few_reclaimable_pages() {
  local proc bin
  proc="$(empty_proc_root)"
  bin="$(scratch_dir)"
  add_real_tool "$bin" awk
  add_real_tool "$bin" grep
  write_fake_sysctl "$bin" "8" "{ 1.60 1.40 1.20 }" "16384"
  write_fake_vm_stat "$bin" "1000" "200" "50" "30"
  write_fake_df "$bin" "104857600"

  assert_eq \
    "CheckMachineHeadroom > macos > should NO-GO when vm_stat reports few free/inactive/speculative/purgeable pages" \
    'HEADROOM=NO-GO cores=8 load1=1.60 ratio=0.20 max_ratio=0.70 mem_avail_mb=20 min_avail_mb=1536 disk_free_mb=102400 min_disk_mb=5120 reason="available memory 20MB below min 1536MB"|1' \
    "$(run_headroom "$proc" "$bin")"
  rm -rf "$proc" "$bin"
}

it_should_be_unknown_when_macos_sysctl_is_present_but_vm_stat_is_absent() {
  local proc bin
  proc="$(empty_proc_root)"
  bin="$(scratch_dir)"
  add_real_tool "$bin" awk
  add_real_tool "$bin" grep
  write_fake_sysctl "$bin" "8" "{ 1.60 1.40 1.20 }" "16384"
  write_fake_df "$bin" "104857600"

  assert_eq \
    "CheckMachineHeadroom > macos > should be UNKNOWN when sysctl is present but vm_stat is absent from PATH" \
    'HEADROOM=UNKNOWN reason="vm_stat unavailable or unparseable; cannot determine available memory"|2' \
    "$(run_headroom "$proc" "$bin")"
  rm -rf "$proc" "$bin"
}

it_should_be_unknown_when_neither_proc_loadavg_nor_sysctl_is_available() {
  local proc bin
  proc="$(empty_proc_root)"
  bin="$(scratch_dir)"
  add_real_tool "$bin" awk
  add_real_tool "$bin" grep
  write_fake_df "$bin" "104857600"

  assert_eq \
    "CheckMachineHeadroom > unrecognized platform > should be UNKNOWN naming the platform when neither /proc/loadavg nor sysctl is available" \
    'HEADROOM=UNKNOWN reason="neither /proc/loadavg nor sysctl found; cannot measure machine load"|2' \
    "$(run_headroom "$proc" "$bin")"
  rm -rf "$proc" "$bin"
}

it_should_flip_to_go_when_load_ratio_max_is_overridden_above_the_fixtures_ratio() {
  local proc bin
  proc="$(scratch_dir)"
  bin="$(scratch_dir)"
  build_linux_proc_root "$proc" 8 "7.20" "4194304"
  add_real_tool "$bin" awk
  add_real_tool "$bin" grep
  write_fake_df "$bin" "20971520"

  assert_eq \
    "CheckMachineHeadroom > overrides > should flip a default-failing load ratio to GO when HEADROOM_LOAD_RATIO_MAX is raised above it" \
    "HEADROOM=GO cores=8 load1=7.20 ratio=0.90 max_ratio=0.95 mem_avail_mb=4096 min_avail_mb=1536 disk_free_mb=20480 min_disk_mb=5120|0" \
    "$(run_headroom "$proc" "$bin" HEADROOM_LOAD_RATIO_MAX=0.95)"
  rm -rf "$proc" "$bin"
}

it_should_flip_to_go_when_min_available_mb_is_overridden_below_the_fixtures_memory() {
  local proc bin
  proc="$(scratch_dir)"
  bin="$(scratch_dir)"
  build_linux_proc_root "$proc" 8 "1.60" "524288"
  add_real_tool "$bin" awk
  add_real_tool "$bin" grep
  write_fake_df "$bin" "20971520"

  assert_eq \
    "CheckMachineHeadroom > overrides > should flip a default-failing available-memory floor to GO when HEADROOM_MIN_AVAILABLE_MB is lowered below it" \
    "HEADROOM=GO cores=8 load1=1.60 ratio=0.20 max_ratio=0.70 mem_avail_mb=512 min_avail_mb=256 disk_free_mb=20480 min_disk_mb=5120|0" \
    "$(run_headroom "$proc" "$bin" HEADROOM_MIN_AVAILABLE_MB=256)"
  rm -rf "$proc" "$bin"
}

it_should_flip_to_go_when_min_free_disk_mb_is_overridden_below_the_fixtures_disk() {
  local proc bin
  proc="$(scratch_dir)"
  bin="$(scratch_dir)"
  build_linux_proc_root "$proc" 8 "1.60" "4194304"
  add_real_tool "$bin" awk
  add_real_tool "$bin" grep
  write_fake_df "$bin" "1048576"

  assert_eq \
    "CheckMachineHeadroom > overrides > should flip a default-failing free-disk floor to GO when HEADROOM_MIN_FREE_DISK_MB is lowered below it" \
    "HEADROOM=GO cores=8 load1=1.60 ratio=0.20 max_ratio=0.70 mem_avail_mb=4096 min_avail_mb=1536 disk_free_mb=1024 min_disk_mb=512|0" \
    "$(run_headroom "$proc" "$bin" HEADROOM_MIN_FREE_DISK_MB=512)"
  rm -rf "$proc" "$bin"
}

it_should_print_exactly_one_stdout_line_for_a_go_verdict() {
  local proc bin out status line_count
  proc="$(scratch_dir)"
  bin="$(scratch_dir)"
  build_linux_proc_root "$proc" 8 "1.60" "4194304"
  add_real_tool "$bin" awk
  add_real_tool "$bin" grep
  write_fake_df "$bin" "20971520"

  out="$(run_headroom_stdout_only "$proc" "$bin")"
  status="${out##*|}"
  out="${out%|*}"
  line_count="$(printf '%s\n' "$out" | wc -l | tr -d ' ')"

  assert_eq \
    "CheckMachineHeadroom > output shape > should print exactly one stdout line on a GO verdict" \
    "1|0" \
    "$line_count|$status"
  case "$out" in
    'HEADROOM=GO '*)
      pass_count=$((pass_count + 1))
      printf 'ok - %s\n' "CheckMachineHeadroom > output shape > GO stdout line should start with 'HEADROOM=GO '"
      ;;
    *)
      fail_count=$((fail_count + 1))
      printf 'not ok - %s\n  actual: %s\n' "CheckMachineHeadroom > output shape > GO stdout line should start with 'HEADROOM=GO '" "$out"
      ;;
  esac
  rm -rf "$proc" "$bin"
}

it_should_mutate_nothing_when_run_twice_against_the_same_fixtures() {
  local proc bin before after
  proc="$(scratch_dir)"
  bin="$(scratch_dir)"
  build_linux_proc_root "$proc" 8 "1.60" "4194304"
  add_real_tool "$bin" awk
  add_real_tool "$bin" grep
  write_fake_df "$bin" "20971520"

  run_headroom "$proc" "$bin" >/dev/null
  before="$(snapshot_tree "$proc"; snapshot_tree "$bin")"
  run_headroom "$proc" "$bin" >/dev/null
  run_headroom "$proc" "$bin" >/dev/null
  after="$(snapshot_tree "$proc"; snapshot_tree "$bin")"

  assert_eq \
    "CheckMachineHeadroom > no caching > should leave the fixture directories' contents and mtimes unchanged after repeated runs" \
    "$before" "$after"
  rm -rf "$proc" "$bin"
}

it_should_go_at_the_exact_boundary_of_every_threshold() {
  local proc bin
  proc="$(scratch_dir)"
  bin="$(scratch_dir)"
  build_linux_proc_root "$proc" 10 "7.00" "1572864"
  add_real_tool "$bin" awk
  add_real_tool "$bin" grep
  write_fake_df "$bin" "5242880"

  assert_eq \
    "CheckMachineHeadroom > boundary > should GO when ratio, available memory and free disk sit exactly at their thresholds" \
    "HEADROOM=GO cores=10 load1=7.00 ratio=0.70 max_ratio=0.70 mem_avail_mb=1536 min_avail_mb=1536 disk_free_mb=5120 min_disk_mb=5120|0" \
    "$(run_headroom "$proc" "$bin")"
  rm -rf "$proc" "$bin"
}

it_should_be_unknown_not_crash_when_linux_loadavg_first_field_is_non_numeric() {
  local proc bin
  proc="$(scratch_dir)"
  bin="$(scratch_dir)"
  build_linux_proc_root "$proc" 8 "1.60" "4194304"
  write_malformed_loadavg "$proc"
  add_real_tool "$bin" awk
  add_real_tool "$bin" grep
  write_fake_df "$bin" "20971520"

  assert_eq \
    "CheckMachineHeadroom > malformed input > should be UNKNOWN, not crash, when /proc/loadavg's first field is non-numeric" \
    'HEADROOM=UNKNOWN reason="malformed /proc/loadavg: cannot parse the load average"|2' \
    "$(run_headroom "$proc" "$bin")"
  rm -rf "$proc" "$bin"
}

it_should_be_unknown_not_crash_when_macos_vm_loadavg_does_not_match_the_expected_shape() {
  local proc bin
  proc="$(empty_proc_root)"
  bin="$(scratch_dir)"
  add_real_tool "$bin" awk
  add_real_tool "$bin" grep
  write_fake_sysctl "$bin" "8" "load average currently unavailable" "16384"
  write_fake_vm_stat "$bin" "300000" "50000" "20000" "14000"
  write_fake_df "$bin" "104857600"

  assert_eq \
    "CheckMachineHeadroom > malformed input > should be UNKNOWN, not crash, when sysctl vm.loadavg does not match the '{ a b c }' shape" \
    'HEADROOM=UNKNOWN reason="malformed sysctl vm.loadavg output: cannot parse the load average"|2' \
    "$(run_headroom "$proc" "$bin")"
  rm -rf "$proc" "$bin"
}

it_should_go_when_linux_load_memory_and_disk_are_all_ample
it_should_no_go_when_linux_load_ratio_alone_exceeds_max
it_should_no_go_when_linux_available_memory_alone_is_below_floor
it_should_no_go_when_linux_free_disk_alone_is_below_floor
it_should_name_both_gates_when_load_and_disk_fail_together
it_should_be_unknown_when_linux_meminfo_has_no_mem_available_line
it_should_be_unknown_when_nproc_is_absent_and_cpuinfo_has_no_processor_lines
it_should_go_when_macos_load_memory_and_disk_are_all_ample
it_should_no_go_when_macos_load_average_exceeds_max
it_should_no_go_when_macos_vm_stat_reports_few_reclaimable_pages
it_should_be_unknown_when_macos_sysctl_is_present_but_vm_stat_is_absent
it_should_be_unknown_when_neither_proc_loadavg_nor_sysctl_is_available
it_should_flip_to_go_when_load_ratio_max_is_overridden_above_the_fixtures_ratio
it_should_flip_to_go_when_min_available_mb_is_overridden_below_the_fixtures_memory
it_should_flip_to_go_when_min_free_disk_mb_is_overridden_below_the_fixtures_disk
it_should_print_exactly_one_stdout_line_for_a_go_verdict
it_should_mutate_nothing_when_run_twice_against_the_same_fixtures
it_should_go_at_the_exact_boundary_of_every_threshold
it_should_be_unknown_not_crash_when_linux_loadavg_first_field_is_non_numeric
it_should_be_unknown_not_crash_when_macos_vm_loadavg_does_not_match_the_expected_shape

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
