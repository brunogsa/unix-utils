#!/usr/bin/env bash
# test-check-standards-instructions-budget.sh - Tests
# check.sh's "every *-standards skill must declare
# instructions-budget" gate.
#
# Usage:
#   bash test-check-standards-instructions-budget.sh
#
# These assert the missing-instructions-budget section of
# the report AND the exit code.
#
# The exit code is only this gate's own signal while the
# fixture trips no other budget, so new_fixture() writes a
# CLAUDE.md that already satisfies every other check.
#
# A future budget change that dirties it fails the two
# exits-zero assertions loudly, rather than quietly turning
# the exits-non-zero one into a tautology.
#
# check.sh resolves $HOME/.claude/agents unconditionally, so
# these run against an installed config, not a bare checkout.

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

# Write a SKILL.md under the fixture, content from stdin.
write_skill() {
    local dir=$1 name=$2
    mkdir -p "$dir/skills/$name"
    cat > "$dir/skills/$name/SKILL.md"
}

# Run check.sh on the fixture and echo the
# missing-instructions-budget section's bullet lines.
run_check() {
    local dir=$1
    bash "$CHECK" "$dir" 2>/dev/null | awk '
        /^## \*-standards skills with no `instructions-budget`/ { in_section = 1; next }
        /^## / { in_section = 0 }
        in_section && /^- / { print }
    '
}

# Run check.sh on the fixture and echo its exit code.
run_check_status() {
    local dir=$1
    bash "$CHECK" "$dir" >/dev/null 2>&1
    echo $?
}

it_should_flag_a_standards_skill_that_declares_no_instructions_budget() {
    echo "it_should_flag_a_standards_skill_that_declares_no_instructions_budget"
    local d; d=$(new_fixture)
    write_skill "$d" "foo-standards" <<'EOF'
---
name: foo-standards
description: "Demo standards skill."
---

- [Instruction] Never bundle unrelated changes into one commit.
  - [Why] A mixed commit cannot be reverted without losing the unrelated half.
EOF
    assert_eq "flags the skill" "- foo-standards" "$(run_check "$d")"
    assert_eq "exits non-zero" "1" "$(run_check_status "$d")"
    rm -rf "$d"
}

it_should_stay_silent_when_a_standards_skill_declares_its_instructions_budget() {
    echo "it_should_stay_silent_when_a_standards_skill_declares_its_instructions_budget"
    local d; d=$(new_fixture)
    write_skill "$d" "foo-standards" <<'EOF'
---
name: foo-standards
description: "Demo standards skill."
instructions-budget: 5
---

- [Instruction] Never bundle unrelated changes into one commit.
  - [Why] A mixed commit cannot be reverted without losing the unrelated half.
EOF
    assert_eq "no findings" "" "$(run_check "$d")"
    assert_eq "exits zero" "0" "$(run_check_status "$d")"
    rm -rf "$d"
}

it_should_ignore_an_ordinary_skill_that_declares_no_instructions_budget() {
    echo "it_should_ignore_an_ordinary_skill_that_declares_no_instructions_budget"
    local d; d=$(new_fixture)
    write_skill "$d" "plain-skill" <<'EOF'
---
name: plain-skill
description: "Demo ordinary skill."
---

- [Instruction] Never bundle unrelated changes into one commit.
  - [Why] A mixed commit cannot be reverted without losing the unrelated half.
EOF
    assert_eq "no findings" "" "$(run_check "$d")"
    assert_eq "exits zero" "0" "$(run_check_status "$d")"
    rm -rf "$d"
}

it_should_flag_a_standards_skill_that_declares_no_instructions_budget
it_should_stay_silent_when_a_standards_skill_declares_its_instructions_budget
it_should_ignore_an_ordinary_skill_that_declares_no_instructions_budget

echo
echo "$passed passed, $failed failed"
[ "$failed" -eq 0 ]
