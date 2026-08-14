#!/usr/bin/env bash
# test-batch-end-section-refs.sh - plain-bash test file
# guarding that every §8.<n> cross-reference names the
# batch-end stage it means.
#
# Its scope is the whole skill directory - prose, diagram
# and scripts - plus the hooks that drive the skill from
# outside it and carry §8 pointers of their own.
#
# §8 was renumbered when push + branch record + draft PR
# was hoisted ahead of both gates. SKILL.md and
# batch-end-review.md were updated; the reference files
# pointing INTO §8 were not.
#
# A reader following one of those stale pointers lands on
# a stage that does nothing it was sent there for - it
# reads the repo-green gate expecting the push step.
#
# Expected stage numbers are never hardcoded here. Each is
# derived from SKILL.md's own four stage-summary bullets,
# so the next renumbering retargets this suite for free
# and still fails on any file the renumbering missed.
#
# Two complementary checks, because §8 references bind
# their stage in two different ways.
#
# check_keyword_refs is the generic sweep: a reference
# naming its stage right after the section token
# ("§8.3 push failing") must carry that stage's number.
#
# It needs no per-line table, so it covers even the
# files nobody thought to list.
#
# check_pointer_refs is the explicit table: a reference
# whose stage lives only in the surrounding prose
# ("Read this at §8.3") binds to nothing the sweep can
# read.
#
# Each such pointer is listed with the stage key it
# means, never with a literal section number.
#
# A bare §8 with no sub-number means the whole batch-end
# section and is legitimate, so neither check matches it.
#
# Exits 0 when every assertion passes, non-zero otherwise.
#
# No bats dependency, matching the sibling hook/skill
# suites (e.g. test-batch-end-order.sh).

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKILL_FILE="$script_dir/../SKILL.md"
REFERENCES_DIR="$script_dir/../references"
ASSETS_DIR="$script_dir/../assets"

# A hook states its §8 pointer to a reader who has no skill
# file open, so a stale one there sends that reader to a
# stage doing nothing it was named for.
HOOKS_DIR="$script_dir/../../../hooks"

# The four stage keys this suite reasons in. Every
# expected number is looked up through one of these, so
# no assertion below carries a literal section number.
STAGE_KEYS="push quality green final"

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

# stage_bullet_pattern <stage-key> - regex matching the
# SKILL.md stage-summary bullet that OWNS this stage's
# number. Written as a case, not an associative array:
# macOS ships bash 3.2, which has none.
stage_bullet_pattern() {
  case "$1" in
    push)    printf '%s' '^- \*\*§8\.[0-9]+ — push' ;;
    quality) printf '%s' '^- \*\*§8\.[0-9]+ — the quality-gate tail' ;;
    green)   printf '%s' '^- \*\*§8\.[0-9]+ — repo-green gate' ;;
    final)   printf '%s' '^- \*\*§8\.[0-9]+ — re-push' ;;
  esac
}

# stage_keyword_pattern <stage-key> - alternation of the
# words a reference uses when it names this stage right
# after the section token.
#
# Deliberately narrow: a word only qualifies when it can
# belong to exactly one stage, so an ambiguous noun like
# a bare "gate" is left out rather than guessed at.
#
# "trashes" qualifies for the final stage because disposing
# of the state file is the last thing a batch does, and no
# earlier stage may do it.
stage_keyword_pattern() {
  case "$1" in
    push)    printf '%s' 'push|PR dispatch|draft PR|branch record|PR-creation' ;;
    quality) printf '%s' 'quality-gate|quality gate' ;;
    green)   printf '%s' 'repo-green' ;;
    final)   printf '%s' 're-push|refreshe?s|review package|Finalize|trashes' ;;
  esac
}

# Cross-file pointers whose stage is carried only by the
# prose around them, never by a word the sweep can read
# beside the token.
#
# Each row is <stage-key>|<file>|<anchor-regex>, so a
# renumbering updates SKILL.md and this table follows.
POINTER_ROWS="
push|stacked-by-task-batch-end.md|^Read this at §8\.[0-9]+, on a run where
push|stacked-by-task-batch-end.md|everything else about §8\.[0-9]+
push|pr-awareness.md|batch-end-pr-branch-record\.md\), read at §8\.[0-9]+
push|stacked-by-task.md|^Read it at §8\.[0-9]+, not now
"

# section_number_of <text> - the digits of the first
# §8.<n> in the text, or empty when it carries none.
section_number_of() {
  printf '%s' "$1" | sed -E 's/^.*§8\.([0-9]+).*$/\1/'
}

# derive_stage_section <skill-file> <stage-key> - the
# number SKILL.md currently assigns that stage, or empty
# when the bullet is gone.
derive_stage_section() {
  local file="$1" stage="$2" bullet
  [ -f "$file" ] || return 0
  bullet=$(grep -o -m1 -E "$(stage_bullet_pattern "$stage")" "$file")
  [ -n "$bullet" ] || return 0
  section_number_of "$bullet"
}

# check_stage_numbers_derivable <skill-file> - returns 0
# only when all four stage bullets are still present.
#
# Every other check reads its expected numbers from them,
# so a lost bullet would silently turn this whole suite
# into a pass by vacuous truth.
check_stage_numbers_derivable() {
  local file="$1" stage number
  if [ ! -f "$file" ]; then
    printf 'missing: %s\n' "$file"
    return 1
  fi
  for stage in $STAGE_KEYS; do
    number=$(derive_stage_section "$file" "$stage")
    if [ -z "$number" ]; then
      printf 'no batch-end stage bullet for %s in %s\n' "$stage" "$file"
      return 1
    fi
  done
  return 0
}

# check_keyword_refs <file> - returns 0 only when every
# §8.<n> that names its stage beside the token carries
# that stage's derived number.
#
# Prints one line per mismatch so a failing run names the
# reference to fix, not just the file holding it.
check_keyword_refs() {
  local file="$1"
  if [ ! -f "$file" ]; then
    printf 'missing: %s\n' "$file"
    return 1
  fi
  local status=0 stage expected match found matches
  for stage in $STAGE_KEYS; do
    expected=$(derive_stage_section "$SKILL_FILE" "$stage")
    if [ -z "$expected" ]; then
      printf 'cannot derive the %s stage number from %s\n' "$stage" "$SKILL_FILE"
      return 1
    fi
    matches=$(grep -oE "§8\.[0-9]+('s)?( —)?[[:space:]]+($(stage_keyword_pattern "$stage"))" "$file")
    while IFS= read -r match; do
      [ -n "$match" ] || continue
      found=$(section_number_of "$match")
      if [ "$found" != "$expected" ]; then
        printf '%s: "%s" points at §8.%s, but the %s stage is §8.%s\n' \
          "$file" "$match" "$found" "$stage" "$expected"
        status=1
      fi
    done <<< "$matches"
  done
  return $status
}

# check_keyword_refs_in_tree <dir> - the same sweep over
# every markdown file in a directory, so a newly added
# reference is covered with no registration step.
check_keyword_refs_in_tree() {
  local dir="$1" file status=0
  if [ ! -d "$dir" ]; then
    printf 'missing directory: %s\n' "$dir"
    return 1
  fi
  for file in "$dir"/*.md; do
    [ -f "$file" ] || continue
    check_keyword_refs "$file" || status=1
  done
  return $status
}

# check_keyword_refs_in_hook_tree <dir> - the same sweep
# over the hook scripts and their own suites.
#
# Source extensions are globbed by name so __pycache__
# bytecode - a stale copy of a .py the sweep already read -
# can never be scanned as a live reference.
check_keyword_refs_in_hook_tree() {
  local dir="$1" file status=0
  if [ ! -d "$dir" ]; then
    printf 'missing directory: %s\n' "$dir"
    return 1
  fi
  for file in "$dir"/*.sh "$dir"/*.py "$dir"/tests/*.sh "$dir"/tests/*.py; do
    [ -f "$file" ] || continue
    check_keyword_refs "$file" || status=1
  done
  return $status
}

# check_pointer_refs <references-dir> - returns 0 only
# when every tabled prose pointer names its stage's
# derived number.
#
# A vanished anchor fails too: the pointer it guarded may
# have been reworded into a new stale reference, and a
# silently skipped row would report that as a pass.
check_pointer_refs() {
  local dir="$1" row stage rest file anchor path expected line found status=0
  if [ ! -d "$dir" ]; then
    printf 'missing directory: %s\n' "$dir"
    return 1
  fi
  while IFS= read -r row; do
    [ -n "$row" ] || continue
    stage=${row%%|*}
    rest=${row#*|}
    file=${rest%%|*}
    anchor=${rest#*|}
    path="$dir/$file"
    expected=$(derive_stage_section "$SKILL_FILE" "$stage")
    if [ -z "$expected" ]; then
      printf 'cannot derive the %s stage number from %s\n' "$stage" "$SKILL_FILE"
      return 1
    fi
    if [ ! -f "$path" ]; then
      printf 'missing: %s\n' "$path"
      status=1
      continue
    fi
    line=$(grep -o -m1 -E "$anchor" "$path")
    if [ -z "$line" ]; then
      printf 'no line matching %s in %s\n' "$anchor" "$path"
      status=1
      continue
    fi
    found=$(section_number_of "$line")
    if [ "$found" != "$expected" ]; then
      printf '%s: "%s" points at §8.%s, but the %s stage is §8.%s\n' \
        "$path" "$line" "$found" "$stage" "$expected"
      status=1
    fi
  done <<< "$POINTER_ROWS"
  return $status
}

# run_check <check-fn> <args...> - "passed" or "failed",
# so a negative control asserts on the verdict rather
# than on the reason text.
run_check() {
  if "$@" >/dev/null 2>&1; then
    printf 'passed'
  else
    printf 'failed'
  fi
}

it_should_assert_skill_md_still_declares_all_four_batch_end_stages() {
  assert_eq "should assert SKILL.md declares a numbered bullet for each of the four batch-end stages" \
    "passed" "$(run_check check_stage_numbers_derivable "$SKILL_FILE")"
}

it_should_assert_skill_md_names_the_right_stage_for_every_reference() {
  assert_eq "should assert every SKILL.md section reference names the stage it describes" \
    "passed" "$(run_check check_keyword_refs "$SKILL_FILE")"
}

it_should_assert_every_reference_file_names_the_right_stage() {
  assert_eq "should assert every reference file's section references name the stage they describe" \
    "passed" "$(run_check check_keyword_refs_in_tree "$REFERENCES_DIR")"
}

it_should_assert_every_diagram_reference_names_the_right_stage() {
  assert_eq "should assert every flow diagram section reference names the stage it describes" \
    "passed" "$(run_check check_keyword_refs_in_tree "$ASSETS_DIR")"
}

it_should_assert_every_hook_reference_names_the_right_stage() {
  assert_eq "should assert every hook's section references name the stage they describe" \
    "passed" "$(run_check check_keyword_refs_in_hook_tree "$HOOKS_DIR")"
}

it_should_assert_every_prose_pointer_names_the_right_stage() {
  assert_eq "should assert every cross-file prose pointer names the stage it sends the reader to" \
    "passed" "$(run_check check_pointer_refs "$REFERENCES_DIR")"
}

it_should_not_flag_a_bare_section_eight_reference() {
  local tmp_file
  tmp_file="$(mktemp)"

  # A bare §8 means the whole batch-end section and is
  # legitimate, so flagging it would push authors into
  # inventing a sub-number the prose never meant.
  printf 'The §8 batch-end push runs on every batch, per §8.\n' > "$tmp_file"
  assert_eq "should not flag a bare section-8 reference that carries no sub-number" \
    "passed" "$(run_check check_keyword_refs "$tmp_file")"
  rm -f "$tmp_file"
}

it_should_fail_when_a_scanned_file_is_missing() {
  assert_eq "should fail when the file it scans is missing" \
    "failed" "$(run_check check_keyword_refs "$REFERENCES_DIR/does-not-exist.md")"
}

it_should_fail_when_a_reference_names_the_wrong_stage_beside_the_token() {
  local tmp_file
  tmp_file="$(mktemp)"

  # The renumbering's exact residue: a stage word sitting
  # beside a section number that belongs to another stage.
  printf 'A halt entry: batch-end-review.md s §8.9 push failing.\n' > "$tmp_file"
  assert_eq "should fail when a reference names the push stage beside another stage's number" \
    "failed" "$(run_check check_keyword_refs "$tmp_file")"
  rm -f "$tmp_file"
}

it_should_fail_when_a_hook_names_the_wrong_stage_for_the_state_file_disposal() {
  local tmp_dir
  tmp_dir="$(mktemp -d)"

  # Disposal moved to the final stage with the reorder, and
  # a hook left pointing at the old one sends its reader to
  # the repo-green gate to look for it.
  printf '%s\n' '# §8.9 trashes the state file at batch end.' \
    > "$tmp_dir/stale-hook.sh"
  assert_eq "should fail when a hook points the state-file disposal at another stage" \
    "failed" "$(run_check check_keyword_refs_in_hook_tree "$tmp_dir")"
  rm -rf "$tmp_dir"
}

it_should_not_read_stale_bytecode_as_a_hook_reference() {
  local tmp_dir
  tmp_dir="$(mktemp -d)"

  # Bytecode is a compiled copy of a source file the sweep
  # already reads, so flagging it would demand fixing a
  # reference that has no editable line to fix.
  mkdir -p "$tmp_dir/tests/__pycache__"
  printf '%s\n' 'msg="§8.9 trashes the state file"' \
    > "$tmp_dir/tests/__pycache__/stale-hook.test.cpython-314.pyc"
  assert_eq "should not flag a stale section reference left in compiled bytecode" \
    "passed" "$(run_check check_keyword_refs_in_hook_tree "$tmp_dir")"
  rm -rf "$tmp_dir"
}

it_should_fail_when_a_prose_pointer_names_the_wrong_stage() {
  local tmp_dir
  tmp_dir="$(mktemp -d)"

  # Mangle exactly one tabled pointer, leaving the rest of
  # the tree intact, so the verdict can only come from the
  # row under test.
  cp -R "$REFERENCES_DIR/." "$tmp_dir"
  sed -E 's/^Read it at §8\.[0-9]+, not now/Read it at §8.9, not now/' \
    "$REFERENCES_DIR/stacked-by-task.md" > "$tmp_dir/stacked-by-task.md"
  assert_eq "should fail when a prose pointer sends the reader to a stage that is not its own" \
    "failed" "$(run_check check_pointer_refs "$tmp_dir")"
  rm -rf "$tmp_dir"
}

it_should_fail_when_a_tabled_prose_pointer_disappears() {
  local tmp_dir
  tmp_dir="$(mktemp -d)"

  # A reworded pointer is how a stale reference re-enters
  # unseen, so a vanished anchor is a failure rather than
  # a row this suite quietly stops checking.
  cp -R "$REFERENCES_DIR/." "$tmp_dir"
  grep -v -E '^Read it at §8\.[0-9]+, not now' \
    "$REFERENCES_DIR/stacked-by-task.md" > "$tmp_dir/stacked-by-task.md"
  assert_eq "should fail when a tabled prose pointer no longer exists in its file" \
    "failed" "$(run_check check_pointer_refs "$tmp_dir")"
  rm -rf "$tmp_dir"
}

it_should_fail_when_a_stage_number_cannot_be_derived() {
  local tmp_file
  tmp_file="$(mktemp)"

  # Losing a stage bullet strands every expected number,
  # which would otherwise read as a clean pass instead of
  # the broken derivation it is.
  grep -v -E '^- \*\*§8\.[0-9]+ — repo-green gate' "$SKILL_FILE" > "$tmp_file"
  assert_eq "should fail when SKILL.md no longer declares one of the four stage bullets" \
    "failed" "$(run_check check_stage_numbers_derivable "$tmp_file")"
  rm -f "$tmp_file"
}

it_should_assert_skill_md_still_declares_all_four_batch_end_stages
it_should_assert_skill_md_names_the_right_stage_for_every_reference
it_should_assert_every_reference_file_names_the_right_stage
it_should_assert_every_diagram_reference_names_the_right_stage
it_should_assert_every_hook_reference_names_the_right_stage
it_should_assert_every_prose_pointer_names_the_right_stage
it_should_not_flag_a_bare_section_eight_reference
it_should_not_read_stale_bytecode_as_a_hook_reference
it_should_fail_when_a_scanned_file_is_missing
it_should_fail_when_a_reference_names_the_wrong_stage_beside_the_token
it_should_fail_when_a_hook_names_the_wrong_stage_for_the_state_file_disposal
it_should_fail_when_a_prose_pointer_names_the_wrong_stage
it_should_fail_when_a_tabled_prose_pointer_disappears
it_should_fail_when_a_stage_number_cannot_be_derived

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
