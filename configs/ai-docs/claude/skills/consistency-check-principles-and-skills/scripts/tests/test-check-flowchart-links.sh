#!/usr/bin/env bash
# test-check-flowchart-links.sh - Tests
# check-flowchart-links.sh over this repo's live skills tree
# and over violating fixtures.
#
# Usage:
#   bash test-check-flowchart-links.sh
#
# The live-tree case gates the repo's content: a failure
# means a skill's flowchart lost its pointer, or gained a
# pointer to a file that is not there.
#
# The two fixture cases are the falsifiability guard: the
# live tree is clean, so the gate case passes trivially
# against a checker measuring nothing at all.
#
# Each direction gets its own fixture, because one combined
# fixture goes red as soon as either direction fires.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHECK="$SCRIPT_DIR/../check-flowchart-links.sh"

# tests -> scripts -> consistency-check... -> skills
readonly SKILLS_TREE="$SCRIPT_DIR/../../.."

# The substring the checker matches, which is all any
# spelling of the convention's link form has in common.
readonly POINTER='](assets/flowchart.md)'

passed=0
failed=0

assert_eq() {
    local label=$1 expected=$2 actual=$3
    if [ "$expected" = "$actual" ]; then
        passed=$((passed + 1))
        echo "  ✓ $label"
    else
        failed=$((failed + 1))
        echo "  ✗ $label"
        echo "      expected: [$expected]"
        echo "      actual:   [$actual]"
    fi
}

assert_mentions() {
    local label=$1 expected=$2 needle=$3 haystack=$4
    local actual=absent
    if printf '%s\n' "$haystack" | grep -qF -- "$needle"; then
        actual=present
    fi
    assert_eq "$label" "$expected" "$actual"
}

# A compliant skill, so each fixture proves the checker fires
# on the violator and not on everything.
write_compliant_skill() {
    local dir=$1/well-linked-skill
    mkdir -p "$dir/assets"
    printf -- '---\nname: well-linked-skill\n---\n\nSee [flowchart]%s.\n' \
        "$POINTER" > "$dir/SKILL.md"
    printf 'flowchart TD\n  start --> finish\n' > "$dir/assets/flowchart.md"
}

it_should_find_every_flowchart_bidirectionally_linked_in_this_repos_skills_tree() {
    echo "it_should_find_every_flowchart_bidirectionally_linked_in_this_repos_skills_tree"
    local out rc
    out=$(bash "$CHECK" "$SKILLS_TREE" 2>&1)
    rc=$?
    assert_eq "exits 0 over the live skills tree" "0" "$rc"

    # Reprint what broke, so the failure names the skill.
    if [ "$rc" -ne 0 ]; then
        printf '%s\n' "$out" | sed 's/^/      /'
    fi
}

it_should_fail_when_a_flowchart_file_has_no_pointer_in_its_skill_md() {
    echo "it_should_fail_when_a_flowchart_file_has_no_pointer_in_its_skill_md"
    local d out rc
    d=$(mktemp -d)
    write_compliant_skill "$d"

    mkdir -p "$d/orphan-flowchart-skill/assets"
    printf -- '---\nname: orphan-flowchart-skill\n---\n\nDo the thing.\n' \
        > "$d/orphan-flowchart-skill/SKILL.md"
    printf 'flowchart TD\n  start --> finish\n' \
        > "$d/orphan-flowchart-skill/assets/flowchart.md"

    out=$(bash "$CHECK" "$d" 2>&1)
    rc=$?
    assert_eq "exits 1 on a flowchart no SKILL.md points at" "1" "$rc"
    assert_mentions "names the skill owning the unreferenced flowchart" \
        "present" "orphan-flowchart-skill" "$out"
    assert_mentions "leaves the bidirectionally linked sibling unreported" \
        "absent" "well-linked-skill" "$out"
    rm -rf "$d"
}

it_should_fail_when_a_skill_md_points_at_a_missing_flowchart_file() {
    echo "it_should_fail_when_a_skill_md_points_at_a_missing_flowchart_file"
    local d out rc
    d=$(mktemp -d)
    write_compliant_skill "$d"

    mkdir -p "$d/dangling-pointer-skill"
    printf -- '---\nname: dangling-pointer-skill\n---\n\nSee [flowchart]%s.\n' \
        "$POINTER" > "$d/dangling-pointer-skill/SKILL.md"

    out=$(bash "$CHECK" "$d" 2>&1)
    rc=$?
    assert_eq "exits 1 on a pointer whose flowchart file is absent" "1" "$rc"
    assert_mentions "names the skill owning the dangling pointer" \
        "present" "dangling-pointer-skill" "$out"
    assert_mentions "leaves the bidirectionally linked sibling unreported" \
        "absent" "well-linked-skill" "$out"
    rm -rf "$d"
}

it_should_find_every_flowchart_bidirectionally_linked_in_this_repos_skills_tree
it_should_fail_when_a_flowchart_file_has_no_pointer_in_its_skill_md
it_should_fail_when_a_skill_md_points_at_a_missing_flowchart_file

echo
echo "$passed passed, $failed failed"
[ "$failed" -eq 0 ]
