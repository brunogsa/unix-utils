#!/usr/bin/env bash
# test-severity-vocabulary.sh - plain-bash test file
# guarding the one ordinal severity scale every review
# lens feeding /address-verdicts must label findings on.
#
# The floor in address-verdicts SKILL.md section 2
# accepts arguments like `high` and `high+`, and
# comparing those needs a HIGH/MEDIUM/LOW ordering.
#
# test-sdd and refactor already stamp one; auto-review's
# reviewer vocabulary is the five priority tags, which
# rank nothing on their own.
#
# A tag left unmapped makes the floor silently skip a
# third of its own input, and this contract has already
# drifted twice in prose.
#
# So this suite pins it: each priority tag names its
# ordinal equivalent, and each lens stamps a bracketed
# ordinal tag in its finding headings.
#
# Exits 0 when every assertion passes, non-zero otherwise.
#
# No bats dependency, matching the sibling hook/skill
# suites (e.g. test-audit-session-shard-tiers.sh).

set -uo pipefail

skills_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
REVIEW_PRINCIPLES="$skills_dir/code-review-pipeline/references/review-principles.md"
LOCAL_TEMPLATE="$skills_dir/code-review-pipeline/references/local-review-template.md"
AUTO_REVIEW_SKILL="$skills_dir/auto-review/SKILL.md"
TEST_SDD_SKILL="$skills_dir/test-sdd/SKILL.md"
REFACTOR_SKILL="$skills_dir/refactor/SKILL.md"

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

# tag_bullet <file> <tag> - the one priority-tag bullet
# for the given tag, or empty when the file or that
# bullet is absent.
tag_bullet() {
  local file="$1" tag="$2"
  [ -f "$file" ] || return 0
  grep -E "^- \*\*$tag\*\*" "$file" || true
}

# tag_ordinal <line> - the HIGH/MEDIUM/LOW rank a tag
# bullet declares, or empty when it declares none.
tag_ordinal() {
  printf '%s' "$1" | grep -oE 'ordinal severity `(HIGH|MEDIUM|LOW)`' | head -n1 |
    grep -oE 'HIGH|MEDIUM|LOW'
}

# stamps_ordinal_tag <file> - yes when the file shows a
# bracketed ordinal severity tag, the shape
# /address-verdicts parses out of a finding heading.
stamps_ordinal_tag() {
  local file="$1"
  if [ -f "$file" ] && grep -qE '\[(HIGH|MEDIUM|LOW)\]' "$file"; then
    printf 'yes'
  else
    printf 'no'
  fi
}

# check_severity_contract <file> - verifies the priority
# tags in the given review-principles file each declare
# their ordinal rank, and that QUESTION is declared
# non-ordinal instead.
#
# Prints the first mismatch reason to stdout and returns
# 1 on any failure.
check_severity_contract() {
  local file="$1"
  if [ ! -f "$file" ]; then
    printf 'missing: %s\n' "$file"
    return 1
  fi
  local tag expected line ordinal
  for entry in "MANDATORY:HIGH" "RECOMMENDED:MEDIUM" "NITPICK:LOW" "OPTIONAL:LOW"; do
    tag="${entry%%:*}"
    expected="${entry##*:}"
    line=$(tag_bullet "$file" "$tag")
    if [ -z "$line" ]; then
      printf 'no priority-tag bullet found for %s\n' "$tag"
      return 1
    fi
    ordinal=$(tag_ordinal "$line")
    if [ -z "$ordinal" ]; then
      printf '%s declares no ordinal severity\n' "$tag"
      return 1
    fi
    if [ "$ordinal" != "$expected" ]; then
      printf '%s ordinal mismatch: got %s, want %s\n' "$tag" "$ordinal" "$expected"
      return 1
    fi
  done
  line=$(tag_bullet "$file" "QUESTION")
  if ! printf '%s' "$line" | grep -q 'no ordinal severity'; then
    printf 'QUESTION does not declare itself non-ordinal\n'
    return 1
  fi
  return 0
}

it_should_assert_mandatory_maps_to_high() {
  assert_eq "should assert MANDATORY declares the ordinal severity HIGH" \
    "HIGH" "$(tag_ordinal "$(tag_bullet "$REVIEW_PRINCIPLES" MANDATORY)")"
}

it_should_assert_recommended_maps_to_medium() {
  assert_eq "should assert RECOMMENDED declares the ordinal severity MEDIUM" \
    "MEDIUM" "$(tag_ordinal "$(tag_bullet "$REVIEW_PRINCIPLES" RECOMMENDED)")"
}

it_should_assert_nitpick_maps_to_low() {
  assert_eq "should assert NITPICK declares the ordinal severity LOW" \
    "LOW" "$(tag_ordinal "$(tag_bullet "$REVIEW_PRINCIPLES" NITPICK)")"
}

it_should_assert_optional_maps_to_low() {
  assert_eq "should assert OPTIONAL declares the ordinal severity LOW" \
    "LOW" "$(tag_ordinal "$(tag_bullet "$REVIEW_PRINCIPLES" OPTIONAL)")"
}

it_should_assert_question_declares_itself_non_ordinal() {
  local line result
  line=$(tag_bullet "$REVIEW_PRINCIPLES" QUESTION)
  if printf '%s' "$line" | grep -q 'no ordinal severity'; then
    result="yes"
  else
    result="no"
  fi
  assert_eq "should assert QUESTION declares it carries no ordinal severity" "yes" "$result"
}

it_should_assert_question_is_stated_to_survive_every_floor() {
  local line result
  line=$(tag_bullet "$REVIEW_PRINCIPLES" QUESTION)
  if printf '%s' "$line" | grep -q 'passes every severity floor'; then
    result="yes"
  else
    result="no"
  fi
  assert_eq "should assert QUESTION is stated to pass every severity floor rather than rank under it" \
    "yes" "$result"
}

it_should_assert_the_auto_review_lens_stamps_an_ordinal_severity_tag() {
  assert_eq "should assert the auto-review lens stamps a bracketed ordinal severity tag" \
    "yes" "$(stamps_ordinal_tag "$AUTO_REVIEW_SKILL")"
}

it_should_assert_the_test_sdd_lens_stamps_an_ordinal_severity_tag() {
  assert_eq "should assert the test-sdd lens stamps a bracketed ordinal severity tag" \
    "yes" "$(stamps_ordinal_tag "$TEST_SDD_SKILL")"
}

it_should_assert_the_refactor_lens_stamps_an_ordinal_severity_tag() {
  assert_eq "should assert the refactor lens stamps a bracketed ordinal severity tag" \
    "yes" "$(stamps_ordinal_tag "$REFACTOR_SKILL")"
}

it_should_assert_the_local_verdict_template_names_the_ordinal_vocabulary() {
  local result="no"
  if [ -f "$LOCAL_TEMPLATE" ] && grep -q 'HIGH` / `MEDIUM` / `LOW' "$LOCAL_TEMPLATE"; then
    result="yes"
  fi
  assert_eq "should assert the local verdict template names the ordinal vocabulary its SEVERITY placeholder takes" \
    "yes" "$result"
}

it_should_fail_when_review_principles_is_missing() {
  local result
  if check_severity_contract "$skills_dir/code-review-pipeline/references/does-not-exist.md" >/dev/null 2>&1; then
    result="passed"
  else
    result="failed"
  fi
  assert_eq "should fail when the review-principles file is missing" "failed" "$result"
}

it_should_fail_when_a_tag_ordinal_is_altered() {
  local tmp_file result
  tmp_file="$(mktemp)"

  # MANDATORY is the tag a `high` floor exists to
  # select. Downgrade it to LOW to simulate a later
  # edit silently dropping it below every floor.
  sed 's/^\(- \*\*MANDATORY\*\*.*\)ordinal severity `HIGH`/\1ordinal severity `LOW`/' \
    "$REVIEW_PRINCIPLES" > "$tmp_file"
  if check_severity_contract "$tmp_file" >/dev/null 2>&1; then
    result="passed"
  else
    result="failed"
  fi
  rm -f "$tmp_file"
  assert_eq "should fail when any one priority tag's ordinal severity has been altered" \
    "failed" "$result"
}

it_should_fail_when_a_tag_declares_no_ordinal() {
  local tmp_file result
  tmp_file="$(mktemp)"

  # RECOMMENDED loses its ordinal clause entirely --
  # simulates a new tag added to the vocabulary with no
  # rank, which is exactly how this contract drifted.
  sed 's/^\(- \*\*RECOMMENDED\*\*.*\)ordinal severity `MEDIUM`/\1unranked/' \
    "$REVIEW_PRINCIPLES" > "$tmp_file"
  if check_severity_contract "$tmp_file" >/dev/null 2>&1; then
    result="passed"
  else
    result="failed"
  fi
  rm -f "$tmp_file"
  assert_eq "should fail when any one priority tag declares no ordinal severity at all" \
    "failed" "$result"
}

it_should_assert_mandatory_maps_to_high
it_should_assert_recommended_maps_to_medium
it_should_assert_nitpick_maps_to_low
it_should_assert_optional_maps_to_low
it_should_assert_question_declares_itself_non_ordinal
it_should_assert_question_is_stated_to_survive_every_floor
it_should_assert_the_auto_review_lens_stamps_an_ordinal_severity_tag
it_should_assert_the_test_sdd_lens_stamps_an_ordinal_severity_tag
it_should_assert_the_refactor_lens_stamps_an_ordinal_severity_tag
it_should_assert_the_local_verdict_template_names_the_ordinal_vocabulary
it_should_fail_when_review_principles_is_missing
it_should_fail_when_a_tag_ordinal_is_altered
it_should_fail_when_a_tag_declares_no_ordinal

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
