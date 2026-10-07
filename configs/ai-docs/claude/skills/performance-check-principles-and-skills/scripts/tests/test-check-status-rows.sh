#!/usr/bin/env bash
# test-check-status-rows.sh - Tests the check.sh status-table
# rows for per-skill line/word overages and the CLAUDE.md
# character budget.
#
# Usage:
#   bash test-check-status-rows.sh
#
# These assert the exact table row text AND the exit code.
#
# new_fixture() writes a CLAUDE.md that already satisfies every
# other budget, so the exit code is only this row's signal.
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

new_fixture() {
    local d
    d=$(mktemp -d)
    mkdir -p "$d/skills"
    cat > "$d/CLAUDE.md" <<'MD'
# Principles

- [Instruction] Highlight every assumption you make.
  - [Why] Unspoken assumptions silently drive the wrong outcome.
MD
    echo "$d"
}

# Write a SKILL.md of exactly <total_words> words (wc -w),
# wrapped at 10 words per line to stay under the density budget.
write_skill_with_words() {
    local dir=$1 name=$2 total_words=$3
    local file="$dir/skills/$name/SKILL.md"
    mkdir -p "$dir/skills/$name"
    {
        echo "---"
        echo "name: $name"
        echo 'description: "Demo skill."'
        echo "---"
    } > "$file"
    local header_words
    header_words=$(wc -w < "$file" | tr -d ' ')
    yes filler | head -n "$((total_words - header_words))" | xargs -n 10 >> "$file"
}

# Echo the status-table row whose label starts with <prefix>.
table_row() {
    local dir=$1 prefix=$2
    HOME="$FAKE_HOME" bash "$CHECK" "$dir" 2>/dev/null | grep -F "| $prefix" | head -n 1
}

exit_code() {
    HOME="$FAKE_HOME" bash "$CHECK" "$1" >/dev/null 2>&1
    echo $?
}

SKILL_ROW="Skills failing line/word checks (excl. synced/)"

it_should_count_a_skill_over_the_word_budget_in_the_status_table() {
    echo "it_should_count_a_skill_over_the_word_budget_in_the_status_table"
    local d; d=$(new_fixture)
    write_skill_with_words "$d" "big-skill" 2100
    write_skill_with_words "$d" "small-skill" 100
    assert_eq "row reads 1 of 2 OVER" \
        "| $SKILL_ROW | 1 of 2 | 0 | OVER |" "$(table_row "$d" "$SKILL_ROW")"
    rm -rf "$d"
}

it_should_report_zero_failing_skills_when_every_skill_is_within_budget() {
    echo "it_should_report_zero_failing_skills_when_every_skill_is_within_budget"
    local d; d=$(new_fixture)
    write_skill_with_words "$d" "small-skill" 100
    assert_eq "row reads 0 of 1 OK" \
        "| $SKILL_ROW | 0 of 1 | 0 | OK |" "$(table_row "$d" "$SKILL_ROW")"
    rm -rf "$d"
}

it_should_count_a_skill_with_a_line_and_a_word_overage_once() {
    echo "it_should_count_a_skill_with_a_line_and_a_word_overage_once"
    local d; d=$(new_fixture)
    write_skill_with_words "$d" "long-skill" 2100

    # 600 short lines: over the 500-line budget as well
    yes x | head -n 600 >> "$d/skills/long-skill/SKILL.md"
    assert_eq "row reads 1 of 1 OVER" \
        "| $SKILL_ROW | 1 of 1 | 0 | OVER |" "$(table_row "$d" "$SKILL_ROW")"
    rm -rf "$d"
}

it_should_not_count_a_skill_failing_only_the_description_budget() {
    echo "it_should_not_count_a_skill_failing_only_the_description_budget"
    local d; d=$(new_fixture)
    write_skill_with_words "$d" "wordy-desc" 100
    local long_desc; long_desc=$(yes word | head -n 80 | tr '\n' ' ')
    sed -i.bak "s/^description: .*/description: \"$long_desc\"/" "$d/skills/wordy-desc/SKILL.md"
    assert_eq "row reads 0 of 1 OK" \
        "| $SKILL_ROW | 0 of 1 | 0 | OK |" "$(table_row "$d" "$SKILL_ROW")"
    rm -rf "$d"
}

it_should_count_a_skill_over_the_word_ceiling_override() {
    echo "it_should_count_a_skill_over_the_word_ceiling_override"
    local d; d=$(new_fixture)
    write_skill_with_words "$d" "big-skill" 100
    sed -i.bak 's/^description:/words-budget: 4097\ndescription:/' "$d/skills/big-skill/SKILL.md"
    assert_eq "row reads 1 of 1 OVER" \
        "| $SKILL_ROW | 1 of 1 | 0 | OVER |" "$(table_row "$d" "$SKILL_ROW")"
    rm -rf "$d"
}

CLAUDE_ROW="CLAUDE.md chars"

# Pad the fixture CLAUDE.md with 200-char lines until it holds
# exactly <total_chars> characters (ASCII, so bytes = chars).
pad_claude_md_to_chars() {
    local dir=$1 total_chars=$2
    local have
    have=$(wc -c < "$dir/CLAUDE.md" | tr -d ' ')
    yes "$(printf 'a%.0s' $(seq 1 199))" | head -c "$((total_chars - have))" >> "$dir/CLAUDE.md"
}

it_should_flag_a_claude_md_of_40001_characters_as_over() {
    echo "it_should_flag_a_claude_md_of_40001_characters_as_over"
    local d; d=$(new_fixture)
    pad_claude_md_to_chars "$d" 40001
    assert_eq "row reads 40001 OVER" \
        "| $CLAUDE_ROW | 40001 | 40000 | OVER |" "$(table_row "$d" "$CLAUDE_ROW")"
    assert_eq "exits non-zero" "1" "$(exit_code "$d")"
    rm -rf "$d"
}

it_should_accept_a_claude_md_of_exactly_40000_characters() {
    echo "it_should_accept_a_claude_md_of_exactly_40000_characters"
    local d; d=$(new_fixture)
    pad_claude_md_to_chars "$d" 40000
    assert_eq "row reads 40000 OK" \
        "| $CLAUDE_ROW | 40000 | 40000 | OK |" "$(table_row "$d" "$CLAUDE_ROW")"
    assert_eq "exits zero" "0" "$(exit_code "$d")"
    rm -rf "$d"
}

it_should_count_claude_md_multibyte_text_in_characters_not_bytes() {
    echo "it_should_count_claude_md_multibyte_text_in_characters_not_bytes"
    local d; d=$(new_fixture)
    local base; base=$(wc -c < "$d/CLAUDE.md" | tr -d ' ')

    # Each line is "ção→x" + newline: 6 chars but 10 bytes.
    for _ in 1 2 3 4 5 6 7 8 9 10; do echo "ção→x" >> "$d/CLAUDE.md"; done
    assert_eq "10 lines of 6 chars each added" \
        "| $CLAUDE_ROW | $((base + 60)) | 40000 | OK |" "$(table_row "$d" "$CLAUDE_ROW")"
    rm -rf "$d"
}

it_should_count_a_skill_over_the_word_budget_in_the_status_table
it_should_report_zero_failing_skills_when_every_skill_is_within_budget
it_should_count_a_skill_with_a_line_and_a_word_overage_once
it_should_not_count_a_skill_failing_only_the_description_budget
it_should_count_a_skill_over_the_word_ceiling_override
it_should_flag_a_claude_md_of_40001_characters_as_over
it_should_accept_a_claude_md_of_exactly_40000_characters
it_should_count_claude_md_multibyte_text_in_characters_not_bytes

echo
echo "$passed passed, $failed failed"
[ "$failed" -eq 0 ]
