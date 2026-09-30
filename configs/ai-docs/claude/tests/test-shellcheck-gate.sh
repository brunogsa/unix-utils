#!/usr/bin/env bash
# test-shellcheck-gate.sh - runs shellcheck over every
# tracked *.sh in this repo, and over fixtures proving the
# gate still detects a violation.
#
# Usage:
#   bash test-shellcheck-gate.sh

# Exits 0 when every assertion passes, non-zero otherwise.
#
# A gate asserting only "the repo is clean" stays green once
# it has stopped looking at all. The fixture cases below are
# what tell those two states apart.
#
# No bats dependency by design, matching
# test-global-config-invariants.sh in this directory.

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/../../../.." && pwd)"

# A missing binary must fail loudly rather than read as a
# pass, which is the same gap run-tests.sh closed for
# pytest.
if ! command -v shellcheck > /dev/null 2>&1; then
  echo "shellcheck: command not found (install.sh installs it)" >&2
  exit 1
fi

# Codes excluded repo-wide; each owes its reason here.
#
# SC2016 - a single-quoted literal $VAR is this repo's
# deliberate idiom in test fixtures and awk programs, and
# install.sh already marks it inline as
# "# shellcheck disable=SC2016 # single quotes intentional".
SHELLCHECK_EXCLUDES="SC2016"

# run_shellcheck - every finding over the given paths, one
# gcc-format line each, empty when there are none.
#
# -x -P SCRIPTDIR follows sourced files, so SC1091 is
# resolved rather than muted and stays live for scripts
# added later.
#
# No --severity floor: SC2094, reading and writing one file
# in a single pipeline, is a real bug class shipping as a
# note, so a warning floor would drop it silently.
run_shellcheck() {
  (cd "$repo_root" && shellcheck -x -P SCRIPTDIR -f gcc \
    -e "$SHELLCHECK_EXCLUDES" "$@" 2>&1)
}

# keep_existing_paths - of the NUL-separated repo-relative
# paths on stdin, the ones still on disk, one per line.
#
# A concurrent session can have a deletion staged while
# git ls-files still reports the path, and shellcheck exits
# non-zero on a missing file.
keep_existing_paths() {
  local path
  while IFS= read -r -d '' path; do
    if [ -f "$repo_root/$path" ]; then
      printf '%s\n' "$path"
    fi
  done
}

tracked_shell_files() {
  (cd "$repo_root" && git ls-files -z -- '*.sh') | keep_existing_paths
}

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
    printf 'not ok - %s\n' "$description"
    printf '    expected: %s\n' "$expected"
    printf '    actual:   %s\n' "$actual"
  fi
}

# assert_contains - inline assert helper: checks haystack
# holds needle, prints ok/not-ok.
assert_contains() {
  local description="$1" haystack="$2" needle="$3"
  case "$haystack" in
    *"$needle"*)
      pass_count=$((pass_count + 1))
      printf 'ok - %s\n' "$description" ;;
    *)
      fail_count=$((fail_count + 1))
      printf 'not ok - %s\n' "$description"
      printf '    wanted substring: %s\n' "$needle"
      printf '    in:               %s\n' "$haystack" ;;
  esac
}

work_dir=$(mktemp -d)
trap 'rm -rf "$work_dir"' EXIT

# write_fixture - writes $2 as a shell script named $1 under
# the fixture dir, echoes its path.
write_fixture() {
  local path="$work_dir/$1"
  printf '%s' "$2" > "$path"
  printf '%s\n' "$path"
}

# describe(ViolationDetection)

it_should_report_an_unquoted_variable_which_shellcheck_ranks_below_warning() {
  local fixture actual
  fixture=$(write_fixture unquoted.sh '#!/usr/bin/env bash
greet() {
  echo $1
}
')
  actual=$(run_shellcheck "$fixture")
  assert_contains \
    "ViolationDetection > happy > should report an unquoted variable, which shellcheck ranks below warning" \
    "$actual" "SC2086"
}

it_should_report_reading_and_writing_one_file_in_a_single_pipeline() {
  local fixture actual
  fixture=$(write_fixture same-file.sh '#!/usr/bin/env bash
dedupe() {
  sort "$1" > "$1"
}
')
  actual=$(run_shellcheck "$fixture")
  assert_contains \
    "ViolationDetection > happy > should report reading and writing one file in a single pipeline (dropped by a warning severity floor)" \
    "$actual" "SC2094"
}

it_should_exit_non_zero_when_a_file_has_a_violation() {
  local fixture
  fixture=$(write_fixture exit-code.sh '#!/usr/bin/env bash
echo $1
')
  run_shellcheck "$fixture" > /dev/null 2>&1
  assert_eq \
    "ViolationDetection > happy > should exit non-zero when a file has a violation" \
    "1" "$?"
}

# describe(ExcludedCodes)

it_should_report_nothing_for_the_repos_intentional_single_quoted_variable_idiom() {
  local fixture actual
  fixture=$(write_fixture single-quoted.sh '#!/usr/bin/env bash
print_template() {
  printf "%s\n" '"'"'literal $HOME stays unexpanded'"'"'
}
')
  actual=$(run_shellcheck "$fixture")
  assert_eq \
    "ExcludedCodes > happy > should report nothing for the repo's intentional single-quoted \$VAR idiom" \
    "" "$actual"
}

# describe(MissingPathHandling)

it_should_skip_a_listed_path_that_is_no_longer_on_disk() {
  local actual
  actual=$(printf 'run-tests.sh\0deleted-by-another-session.sh\0' \
    | keep_existing_paths | tr '\n' ' ' | sed 's/ *$//')
  assert_eq \
    "MissingPathHandling > corner > should skip a listed path that is no longer on disk" \
    "run-tests.sh" "$actual"
}

# describe(RepoWideGate)

it_should_report_no_violation_across_every_tracked_shell_file() {
  local actual
  local files=()
  while IFS= read -r path; do
    files+=("$path")
  done < <(tracked_shell_files)
  actual=$(run_shellcheck "${files[@]}")
  assert_eq \
    "RepoWideGate > happy > should report no shellcheck violation across every tracked shell file" \
    "" "$actual"
}

it_should_report_an_unquoted_variable_which_shellcheck_ranks_below_warning
it_should_report_reading_and_writing_one_file_in_a_single_pipeline
it_should_exit_non_zero_when_a_file_has_a_violation
it_should_report_nothing_for_the_repos_intentional_single_quoted_variable_idiom
it_should_skip_a_listed_path_that_is_no_longer_on_disk
it_should_report_no_violation_across_every_tracked_shell_file

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
