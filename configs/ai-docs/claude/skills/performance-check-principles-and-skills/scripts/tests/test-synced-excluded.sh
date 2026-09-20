#!/usr/bin/env bash
# test-synced-excluded.sh - Tests that check.sh excludes
# Anthropic's synced-skills bucket from every measurement.
#
# Usage:
#   bash test-synced-excluded.sh
#
# These assert ONLY the three rows/sections a synced skill
# can pollute: skill count, bundled-file denominator, density
# total.
#
# Every fixture below trips other budgets too, so the exit
# code is ignored: a fixture tuned to satisfy all eleven
# budgets would be rewritten by every future budget change.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHECK="$SCRIPT_DIR/../check.sh"

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

# Build a fixture tree with an ordinary authored skill AND a
# synced bucket, and return its path.
#
# `real-skill` proves the prune targets `synced/` only, not
# every skill; `synced/<bucket-id>/fake-upstream` mirrors the
# one-level-deeper nesting Anthropic's sync actually writes.
new_fixture() {
    local d
    d=$(mktemp -d)
    printf '# Principles\n' > "$d/CLAUDE.md"

    mkdir -p "$d/skills/real-skill/references"
    printf -- '---\nname: real-skill\ndescription: "Real."\n---\n\n- [Instruction] Do the thing.\n' \
        > "$d/skills/real-skill/SKILL.md"
    printf 'ok reference content\n' > "$d/skills/real-skill/references/ok.md"

    local bucket="bucket-abc123"
    mkdir -p "$d/skills/synced/$bucket/fake-upstream/references"

    # The synced SKILL.md must itself carry a line over the
    # 256-char density cap, or "Total violations: 0" would
    # pass vacuously even without the prune.
    {
        printf -- '---\nname: fake-upstream\ndescription: "Fake."\n---\n\n'
        printf -- '- [Instruction] '
        printf 'x%.0s' $(seq 1 260)
        printf '\n'
    } > "$d/skills/synced/$bucket/fake-upstream/SKILL.md"

    # 1024-word / 256-line bundled budget: this file must
    # exceed both, so pre-change it is counted AND failing.
    { printf 'word %.0s' $(seq 1 1100); printf '\n'; } \
        > "$d/skills/synced/$bucket/fake-upstream/references/huge.md"

    echo "$d"
}

# Echo the skill-count status-table row.
run_skill_count_row() {
    local dir=$1
    bash "$CHECK" "$dir" 2>/dev/null | grep '^| Skill count'
}

# Echo the bundled-files status-table row.
run_bundled_row() {
    local dir=$1
    bash "$CHECK" "$dir" 2>/dev/null | grep '^| Bundled files failing'
}

# Echo the density check's total-violations line.
run_density_total() {
    local dir=$1
    bash "$CHECK" "$dir" 2>/dev/null | grep '^Total violations:'
}

it_should_count_only_the_authored_skill_not_the_synced_bucket() {
    echo "it_should_count_only_the_authored_skill_not_the_synced_bucket"
    local d; d=$(new_fixture)
    local row; row=$(run_skill_count_row "$d")
    assert_eq "skill count is 1 (real-skill only)" "1" "$(echo "$row" | awk -F'|' '{gsub(/ /,"",$3); print $3}')"
    rm -rf "$d"
}

it_should_drop_the_synced_file_from_the_bundled_denominator() {
    echo "it_should_drop_the_synced_file_from_the_bundled_denominator"
    local d; d=$(new_fixture)
    local row; row=$(run_bundled_row "$d")
    local measured; measured=$(echo "$row" | awk -F'|' '{gsub(/^ +| +$/,"",$3); print $3}')
    # The denominator (the "of M" half) is the only thing a
    # dropped synced file can change here — asserting "0
    # failing" would pass even if the synced file were
    # counted and clean, so the exact "N of M" is required.
    assert_eq "denominator excludes the synced bundled file" "0 of 1" "$measured"
    rm -rf "$d"
}

it_should_exclude_the_synced_skill_md_from_the_density_total() {
    echo "it_should_exclude_the_synced_skill_md_from_the_density_total"
    local d; d=$(new_fixture)
    local line; line=$(run_density_total "$d")
    assert_eq "density total is 0 once synced/ is pruned" "Total violations: 0 (OK)" "$line"
    rm -rf "$d"
}

it_should_count_only_the_authored_skill_not_the_synced_bucket
it_should_drop_the_synced_file_from_the_bundled_denominator
it_should_exclude_the_synced_skill_md_from_the_density_total

echo
echo "$passed passed, $failed failed"
[ "$failed" -eq 0 ]
