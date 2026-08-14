#!/usr/bin/env bash
# test-check-why-bytes.sh - Tests check.sh's per-[Why]
# byte-cap gate.
#
# Usage:
#   bash test-check-why-bytes.sh
#
# These assert ONLY the over-budget-[Why] section and its
# status-table row.
#
# Every fixture below trips other budgets too, so the exit
# code is ignored: a fixture tuned to satisfy all eleven
# budgets would be rewritten by every future budget change.
#
# check.sh resolves $HOME/.claude/agents unconditionally, so
# these run against an installed config, not a bare checkout.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHECK="$SCRIPT_DIR/../check.sh"

# Mirrors WHY_BYTES_BUDGET in check.sh. Hard-coded here on
# purpose: a test that read the budget from the script would
# still pass if the constant were silently changed, which is
# the one regression this suite exists to catch.
CAP=128

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
    printf '# Principles\n' > "$d/CLAUDE.md"
    echo "$d"
}

# Write a SKILL.md under the fixture, content from stdin.
write_skill() {
    local dir=$1 name=$2
    mkdir -p "$dir/skills/$name"
    cat > "$dir/skills/$name/SKILL.md"
}

# Emit one marker bullet of EXACTLY <bytes> bytes, padded
# with ASCII filler.
#
# Usage: marker_line_of_bytes <bytes> <marker>.
#
# Boundary assertions are only meaningful against a line
# whose length is exact, and eyeballing a 129-byte literal in
# a heredoc is exactly the arithmetic a reader cannot check.
marker_line_of_bytes() {
    local bytes=$1 marker=$2
    local prefix="  - [$marker] "
    local pad=$((bytes - ${#prefix}))
    printf '%s' "$prefix"
    printf 'x%.0s' $(seq "$pad")
    printf '\n'
}

# Emit a [Why] bullet of <chars> characters built from em
# dashes, which cost 3 bytes each in UTF-8.
#
# The em dash is the real payload here: these files are full
# of them, so a check measuring characters would read this
# line as well under the cap while it actually costs triple.
why_line_of_em_dashes() {
    local chars=$1
    local prefix="  - [Why] "
    local pad=$((chars - ${#prefix}))
    printf '%s' "$prefix"
    printf '—%.0s' $(seq "$pad")
    printf '\n'
}

# Run check.sh on the fixture and echo the over-budget-[Why]
# section's citation lines, with the fixture prefix stripped
# so assertions stay readable and path-independent.
#
# Citations are matched by their measurement text rather
# than a `- ` bullet: the section prints none, which is what
# keeps the regression gate from keying on them.
run_check() {
    local dir=$1
    bash "$CHECK" "$dir" 2>/dev/null | awk '
        /^## \[Why\] lines over / { in_section = 1; next }
        /^## / { in_section = 0 }
        in_section && / bytes \(>/ { print }
    ' | sed "s|$dir/||"
}

# Echo the status-table row for the byte cap.
run_row() {
    local dir=$1
    bash "$CHECK" "$dir" 2>/dev/null | grep '^| \[Why\] lines over '
}

# Echo check.sh's exit code against the fixture.
#
# Fixtures here are the minimal two-line CLAUDE.md the byte
# cap needs, so this is the one gate the cap itself controls.
#
# The citation-only fixtures above pad other markers to
# arbitrary widths, leaving the exit code unasserted —
# nothing else in a minimal fixture can trip.
check_exit_code() {
    local dir=$1
    bash "$CHECK" "$dir" >/dev/null 2>&1
    echo $?
}

it_should_pass_a_why_line_of_exactly_the_byte_cap() {
    echo "it_should_pass_a_why_line_of_exactly_the_byte_cap"
    local d; d=$(new_fixture)
    {
        printf '# Principles\n\n'
        printf -- '- [Instruction] Verify everything you build.\n'
        marker_line_of_bytes "$CAP" Why
    } > "$d/CLAUDE.md"
    assert_eq "no findings at $CAP bytes" "" "$(run_check "$d")"
    rm -rf "$d"
}

it_should_flag_a_why_line_one_byte_over_the_cap() {
    echo "it_should_flag_a_why_line_one_byte_over_the_cap"
    local d; d=$(new_fixture)
    {
        printf '# Principles\n\n'
        printf -- '- [Instruction] Verify everything you build.\n'
        marker_line_of_bytes $((CAP + 1)) Why
    } > "$d/CLAUDE.md"
    assert_eq "flags line 4" "CLAUDE.md:4: 129 bytes (>$CAP)" "$(run_check "$d")"
    rm -rf "$d"
}

it_should_measure_bytes_not_characters_on_em_dashes() {
    echo "it_should_measure_bytes_not_characters_on_em_dashes"
    local d; d=$(new_fixture)
    {
        printf '# Principles\n\n'
        printf -- '- [Instruction] Verify everything you build.\n'
        why_line_of_em_dashes "$CAP"
    } > "$d/CLAUDE.md"

    # 10 ASCII prefix bytes + 118 em dashes at 3 bytes each.
    assert_eq "128 chars of em dashes cost 364 bytes" \
        "CLAUDE.md:4: 364 bytes (>$CAP)" "$(run_check "$d")"
    rm -rf "$d"
}

it_should_ignore_a_long_instruction_line() {
    echo "it_should_ignore_a_long_instruction_line"
    local d; d=$(new_fixture)
    {
        printf '# Principles\n\n'
        marker_line_of_bytes 300 Instruction
        printf -- '  - [Why] The cap binds rationale only.\n'
    } > "$d/CLAUDE.md"
    assert_eq "no findings" "" "$(run_check "$d")"
    rm -rf "$d"
}

it_should_ignore_a_long_example_line() {
    echo "it_should_ignore_a_long_example_line"
    local d; d=$(new_fixture)
    {
        printf '# Principles\n\n'
        printf -- '- [Instruction] Verify everything you build.\n'
        printf -- '  - [Why] The cap binds rationale only.\n'
        marker_line_of_bytes 300 Example
    } > "$d/CLAUDE.md"
    assert_eq "no findings" "" "$(run_check "$d")"
    rm -rf "$d"
}

it_should_flag_an_over_cap_why_inside_a_fenced_block_like_every_other_marker_check() {
    echo "it_should_flag_an_over_cap_why_inside_a_fenced_block_like_every_other_marker_check"
    local d; d=$(new_fixture)
    {
        printf '# Principles\n\n'
        printf -- '- [Instruction] Verify everything you build.\n'
        printf -- '  - [Why] The cap binds rationale only.\n\n'
        printf '```\n'
        marker_line_of_bytes $((CAP + 1)) Why
        printf '```\n'
    } > "$d/CLAUDE.md"

    # check.sh's other marker checks count fenced markers as
    # real, and a fenced [Why] costs the same bytes on load
    # and models the convention for the next author.
    assert_eq "flags the fenced line 7" "CLAUDE.md:7: 129 bytes (>$CAP)" "$(run_check "$d")"
    rm -rf "$d"
}

it_should_flag_an_over_cap_why_in_a_skill_that_is_not_a_standards_skill() {
    echo "it_should_flag_an_over_cap_why_in_a_skill_that_is_not_a_standards_skill"
    local d; d=$(new_fixture)
    {
        printf -- '---\nname: demo-helper\ndescription: "Demo."\n---\n\n'
        printf -- '- [Instruction] Verify everything you build.\n'
        marker_line_of_bytes $((CAP + 1)) Why
    } | write_skill "$d" "demo-helper"
    assert_eq "flags the ordinary skill" \
        "skills/demo-helper/SKILL.md:7: 129 bytes (>$CAP)" "$(run_check "$d")"
    rm -rf "$d"
}

it_should_report_a_clean_file_as_zero_in_the_status_table() {
    echo "it_should_report_a_clean_file_as_zero_in_the_status_table"
    local d; d=$(new_fixture)
    {
        printf '# Principles\n\n'
        printf -- '- [Instruction] Verify everything you build.\n'
        printf -- '  - [Why] Unverified beliefs compound.\n'
    } > "$d/CLAUDE.md"
    assert_eq "row counts 0" "| [Why] lines over $CAP bytes | 0 | 0 | OK |" "$(run_row "$d")"
    rm -rf "$d"
}

it_should_count_every_over_cap_why_in_the_status_table_and_read_over() {
    echo "it_should_count_every_over_cap_why_in_the_status_table_and_read_over"
    local d; d=$(new_fixture)
    {
        printf '# Principles\n\n'
        printf -- '- [Instruction] Verify everything you build.\n'
        marker_line_of_bytes $((CAP + 1)) Why
        printf -- '- [Instruction] Search before creating.\n'
        marker_line_of_bytes 200 Why
    } > "$d/CLAUDE.md"

    # An OVER status cell is the shape the regression gate
    # keys on, and the count rising is exactly what flips it.
    assert_eq "row counts both, reads over" \
        "| [Why] lines over $CAP bytes | 2 | 0 | OVER |" "$(run_row "$d")"
    rm -rf "$d"
}

it_should_exit_nonzero_when_a_why_line_is_over_the_cap() {
    echo "it_should_exit_nonzero_when_a_why_line_is_over_the_cap"
    local d; d=$(new_fixture)
    {
        printf '# Principles\n\n'
        printf -- '- [Instruction] Verify everything you build.\n'
        marker_line_of_bytes $((CAP + 1)) Why
    } > "$d/CLAUDE.md"
    assert_eq "exits non-zero" "1" "$(check_exit_code "$d")"
    rm -rf "$d"
}

it_should_report_over_in_the_row_when_a_why_line_is_over_the_cap() {
    echo "it_should_report_over_in_the_row_when_a_why_line_is_over_the_cap"
    local d; d=$(new_fixture)
    {
        printf '# Principles\n\n'
        printf -- '- [Instruction] Verify everything you build.\n'
        marker_line_of_bytes $((CAP + 1)) Why
    } > "$d/CLAUDE.md"
    assert_eq "row reads over" "| [Why] lines over $CAP bytes | 1 | 0 | OVER |" "$(run_row "$d")"
    rm -rf "$d"
}

it_should_exit_zero_and_report_ok_when_every_why_line_is_at_or_under_the_cap() {
    echo "it_should_exit_zero_and_report_ok_when_every_why_line_is_at_or_under_the_cap"
    local d; d=$(new_fixture)
    {
        printf '# Principles\n\n'
        printf -- '- [Instruction] Verify everything you build.\n'
        marker_line_of_bytes "$CAP" Why
    } > "$d/CLAUDE.md"
    assert_eq "exits zero" "0" "$(check_exit_code "$d")"
    assert_eq "row reads ok" "| [Why] lines over $CAP bytes | 0 | 0 | OK |" "$(run_row "$d")"
    rm -rf "$d"
}

it_should_pass_a_why_line_of_exactly_the_byte_cap
it_should_flag_a_why_line_one_byte_over_the_cap
it_should_measure_bytes_not_characters_on_em_dashes
it_should_ignore_a_long_instruction_line
it_should_ignore_a_long_example_line
it_should_flag_an_over_cap_why_inside_a_fenced_block_like_every_other_marker_check
it_should_flag_an_over_cap_why_in_a_skill_that_is_not_a_standards_skill
it_should_report_a_clean_file_as_zero_in_the_status_table
it_should_count_every_over_cap_why_in_the_status_table_and_read_over
it_should_exit_nonzero_when_a_why_line_is_over_the_cap
it_should_report_over_in_the_row_when_a_why_line_is_over_the_cap
it_should_exit_zero_and_report_ok_when_every_why_line_is_at_or_under_the_cap

echo
echo "$passed passed, $failed failed"
[ "$failed" -eq 0 ]
