#!/usr/bin/env bash
# test-repo-budgets.sh - Tests that this repo's own
# configs/ai-docs/claude tree meets every check.sh budget.
#
# Usage:
#   bash test-repo-budgets.sh
#
# This is a gate on the repo's content, not on check.sh's
# logic: a failure here means a CLAUDE.md, skill, bundled
# reference or agent file went over budget, and the failure
# output names which one.
#
# It exists because the only thing enforcing these budgets
# used to be one exit-code assertion inside a [Why]-byte unit
# suite. A real overage then reported itself as "a broken
# test", which cost a full misdiagnosis once.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHECK="$SCRIPT_DIR/../check.sh"

# tests -> scripts -> performance-check... -> skills -> claude
readonly TREE="$SCRIPT_DIR/../../../.."

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

it_should_meet_every_budget_in_this_repos_claude_tree() {
    echo "it_should_meet_every_budget_in_this_repos_claude_tree"
    local out rc
    out=$(bash "$CHECK" "$TREE" 2>&1)
    rc=$?
    assert_eq "check.sh exits 0 over $TREE" "0" "$rc"

    # Reprint what went over, so the failure names the file
    # instead of sending the next reader back to check.sh.
    if [ "$rc" -ne 0 ]; then
        echo "      --- offending rows and sections ---"
        printf '%s\n' "$out" | grep -E '\| OVER \||^## |^- ' | sed 's/^/      /'
    fi
}

# Falsifiability guard: without it, the assertion above would
# still pass if check.sh stopped measuring anything at all.
it_should_fail_when_a_bundled_reference_exceeds_its_word_budget() {
    echo "it_should_fail_when_a_bundled_reference_exceeds_its_word_budget"
    local d
    d=$(mktemp -d)
    printf '# Principles\n' > "$d/CLAUDE.md"
    mkdir -p "$d/skills/real-skill/references"
    printf -- '---\nname: real-skill\ndescription: "Real."\n---\n\n- [Instruction] Do the thing.\n' \
        > "$d/skills/real-skill/SKILL.md"
    { printf 'word %.0s' $(seq 1 1100); printf '\n'; } \
        > "$d/skills/real-skill/references/over-budget.md"

    local rc
    bash "$CHECK" "$d" >/dev/null 2>&1
    rc=$?
    assert_eq "check.sh exits non-zero on an over-budget reference" "1" "$rc"
    rm -rf "$d"
}

it_should_meet_every_budget_in_this_repos_claude_tree
it_should_fail_when_a_bundled_reference_exceeds_its_word_budget

echo
echo "$passed passed, $failed failed"
[ "$failed" -eq 0 ]
