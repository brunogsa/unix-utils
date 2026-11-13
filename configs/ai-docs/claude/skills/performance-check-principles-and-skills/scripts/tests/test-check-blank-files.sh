#!/usr/bin/env bash
# test-check-blank-files.sh - Tests that check.sh still prints
# its full report when a measured file holds no non-blank line.
#
# Usage:
#   bash test-check-blank-files.sh
#
# `grep -c` exits 1 on zero matches, so under check.sh's
# `set -e` a blank CLAUDE.md, SKILL.md or bundled reference
# once aborted the run with exit 1 and no output at all - a
# caller could not tell that apart from a real overage.
#
# lib-fake-home.sh builds and tears down the fake HOME these
# run under; see that file for the full reasoning. Fixtures
# live inside $FAKE_HOME so its EXIT trap cleans them too.

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

# Prints "yes" when the report holds the given literal text.
report_has() {
    local out=$1 text=$2
    if printf '%s\n' "$out" | grep -qF -- "$text"; then
        echo "yes"
    else
        echo "no"
    fi
}

# A repo fixture that meets every budget: a marker-bearing
# CLAUDE.md and one real skill. Each test then blanks the one
# file it is about. Prints the fixture dir.
new_fixture() {
    local d
    d=$(mktemp -d "$FAKE_HOME/fixture.XXXXXX")
    printf -- '# Principles\n\n- [Instruction] Be brief.\n  - [Why] Brevity saves tokens.\n' > "$d/CLAUDE.md"
    mkdir -p "$d/skills/real-skill/references"
    printf -- '---\nname: real-skill\ndescription: "Real."\n---\n\n- [Instruction] Do the thing.\n' \
        > "$d/skills/real-skill/SKILL.md"
    echo "$d"
}

readonly BLANK_CONTENT=$'\n   \n\t\n'

it_should_report_zero_claude_md_lines_and_the_unmigrated_failure_when_claude_md_is_blank() {
    echo "it_should_report_zero_claude_md_lines_and_the_unmigrated_failure_when_claude_md_is_blank"
    local d out rc
    d=$(new_fixture)
    printf '%s' "$BLANK_CONTENT" > "$d/CLAUDE.md"

    out=$(HOME="$FAKE_HOME" bash "$CHECK" "$d" 2>&1)
    rc=$?
    assert_eq "check.sh exits 1 for the visible unmigrated row" "1" "$rc"
    assert_eq "report shows 0 CLAUDE.md non-blank lines" "yes" \
        "$(report_has "$out" "| CLAUDE.md non-blank lines | 0 |")"
    assert_eq "report shows the 0-[Instruction] CLAUDE.md row" "yes" \
        "$(report_has "$out" "| CLAUDE.md [Instruction] count | 0 |")"
}

it_should_report_zero_claude_md_lines_and_the_unmigrated_failure_when_claude_md_is_blank

echo
echo "$passed passed, $failed failed"
[ "$failed" -eq 0 ]
