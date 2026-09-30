#!/usr/bin/env bash
# test-check-words-budget.sh - Tests check.sh's words-budget
# rules for a SKILL.md: the 2048-word default and the
# 4096-word ceiling on the frontmatter override.
#
# Usage:
#   bash test-check-words-budget.sh
#
# These assert the "Skills exceeding budgets" section of the
# report AND the exit code.
#
# The ceiling is 5,000 re-attach tokens x 0.75 words/token,
# rounded up to the next power of two. It caps only the
# escape hatch, so the default-budget test guards against the
# cap accidentally replacing the 2048 default.
#
# The exit code is only this gate's own signal while the
# fixture trips no other budget, so new_fixture() writes a
# CLAUDE.md that already satisfies every other check.
#
# write_skill_with_words() builds skills with an exact word
# count. wc -w counts the frontmatter too, so the filler is
# sized from what wc reports rather than guessed.
#
# The filler wraps at 10 words per line, because one giant
# line would trip the density budget and flip the exit code.
#
# lib-fake-home.sh builds and tears down the fake HOME these
# run under; see that file for the full reasoning.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHECK="$SCRIPT_DIR/../check.sh"

source "$SCRIPT_DIR/lib-fake-home.sh"

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

# Build a fixture tree and return its path.
#
# `skills/` must exist or check.sh hard-fails before it ever
# reaches the check under test.
new_fixture() {
    local d
    d=$(mktemp -d)
    mkdir -p "$d/skills"
    cat > "$d/CLAUDE.md" <<'EOF'
# Principles

- [Instruction] Highlight every assumption you make.
  - [Why] Unspoken assumptions silently drive the wrong outcome.
EOF
    echo "$d"
}

# Write a SKILL.md whose total word count is exactly
# <total_words>, as wc -w counts it.
#
# Usage: write_skill_with_words <dir> <name> <words> [budget]
write_skill_with_words() {
    local dir=$1 name=$2 total_words=$3 budget=${4:-}
    local file="$dir/skills/$name/SKILL.md"
    mkdir -p "$dir/skills/$name"
    {
        echo "---"
        echo "name: $name"
        echo 'description: "Demo skill."'
        [ -n "$budget" ] && echo "words-budget: $budget"
        echo "---"
    } > "$file"

    local header_words filler_words
    header_words=$(wc -w < "$file" | tr -d ' ')
    filler_words=$((total_words - header_words))
    yes filler | head -n "$filler_words" | xargs -n 10 >> "$file"
}

# Run check.sh on the fixture and echo the bullet lines of
# the "Skills exceeding budgets" section.
run_check() {
    local dir=$1
    HOME="$FAKE_HOME" bash "$CHECK" "$dir" 2>/dev/null | awk '
        /^## Skills exceeding budgets/ { in_section = 1; next }
        /^## / { in_section = 0 }
        in_section && /^- / { print }
    '
}

# Run check.sh on the fixture and echo its exit code.
run_check_status() {
    local dir=$1
    HOME="$FAKE_HOME" bash "$CHECK" "$dir" >/dev/null 2>&1
    echo $?
}

it_should_measure_a_skill_declaring_no_words_budget_against_the_2048_word_default() {
    echo "it_should_measure_a_skill_declaring_no_words_budget_against_the_2048_word_default"
    local at_default over_default
    at_default=$(new_fixture)
    write_skill_with_words "$at_default" "plain-skill" 2048
    assert_eq "2048 words: no findings" "" "$(run_check "$at_default")"
    assert_eq "2048 words: exits zero" "0" "$(run_check_status "$at_default")"

    over_default=$(new_fixture)
    write_skill_with_words "$over_default" "plain-skill" 2049
    assert_eq "2049 words: flagged against the 2048 default" \
        "- plain-skill: words=2049(>2048)" "$(run_check "$over_default")"
    assert_eq "2049 words: exits non-zero" "1" "$(run_check_status "$over_default")"
    rm -rf "$at_default" "$over_default"
}

it_should_accept_a_words_budget_override_of_exactly_4096() {
    echo "it_should_accept_a_words_budget_override_of_exactly_4096"
    local d; d=$(new_fixture)
    write_skill_with_words "$d" "big-skill" 3000 4096
    assert_eq "no findings" "" "$(run_check "$d")"
    assert_eq "exits zero" "0" "$(run_check_status "$d")"
    rm -rf "$d"
}

it_should_measure_a_skill_declaring_no_words_budget_against_the_2048_word_default
it_should_accept_a_words_budget_override_of_exactly_4096

echo
echo "$passed passed, $failed failed"
[ "$failed" -eq 0 ]
