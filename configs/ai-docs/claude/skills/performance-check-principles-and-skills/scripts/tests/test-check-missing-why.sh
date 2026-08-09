#!/usr/bin/env bash
# test-check-missing-why.sh - Tests check.sh's
# CRITICAL-[Instruction]-with-no-[Why] gate.
#
# Usage:
#   bash test-check-missing-why.sh
#
# These assert ONLY the missing-[Why] section of the report.
#
# Every fixture below trips other budgets too, so the exit
# code is ignored: a fixture tuned to satisfy all ten
# budgets would be rewritten by every future budget change.
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
    printf '# Principles\n' > "$d/CLAUDE.md"
    echo "$d"
}

# Write a SKILL.md under the fixture, content from stdin.
write_skill() {
    local dir=$1 name=$2
    mkdir -p "$dir/skills/$name"
    cat > "$dir/skills/$name/SKILL.md"
}

# Run check.sh on the fixture and echo the missing-[Why]
# section's bullet lines, with the fixture prefix stripped
# so assertions stay readable and path-independent.
run_check() {
    local dir=$1
    bash "$CHECK" "$dir" 2>/dev/null | awk '
        /^## CRITICAL \[Instruction\] lines with no \[Why\]/ { in_section = 1; next }
        /^## / { in_section = 0 }
        in_section && /^- / { print }
    ' | sed "s|$dir/||"
}

it_should_stay_silent_when_every_critical_has_its_why() {
    echo "it_should_stay_silent_when_every_critical_has_its_why"
    local d; d=$(new_fixture)
    cat > "$d/CLAUDE.md" <<'EOF'
# Principles

- [Instruction] CRITICAL: Verify everything you build.
  - [Why] Unverified beliefs compound.
EOF
    assert_eq "no findings" "" "$(run_check "$d")"
    rm -rf "$d"
}

it_should_flag_a_critical_with_no_why_at_all() {
    echo "it_should_flag_a_critical_with_no_why_at_all"
    local d; d=$(new_fixture)
    cat > "$d/CLAUDE.md" <<'EOF'
# Principles

- [Instruction] CRITICAL: Verify everything you build.
EOF
    assert_eq "flags line 3" "- CLAUDE.md:3" "$(run_check "$d")"
    rm -rf "$d"
}

it_should_accept_a_why_on_the_third_non_blank_line() {
    echo "it_should_accept_a_why_on_the_third_non_blank_line"
    local d; d=$(new_fixture)
    cat > "$d/CLAUDE.md" <<'EOF'
# Principles

- [Instruction] CRITICAL: Verify everything you build.
  - [Example] Dry-run before you start.

  - [Example] Grep the file before claiming a count.

  - [Why] Unverified beliefs compound.
EOF
    assert_eq "no findings" "" "$(run_check "$d")"
    rm -rf "$d"
}

it_should_flag_a_why_that_arrives_on_the_fourth_non_blank_line() {
    echo "it_should_flag_a_why_that_arrives_on_the_fourth_non_blank_line"
    local d; d=$(new_fixture)
    cat > "$d/CLAUDE.md" <<'EOF'
# Principles

- [Instruction] CRITICAL: Verify everything you build.
  - [Example] Dry-run before you start.
  - [Example] Grep the file before claiming a count.
  - [Example] Re-read the code on contradiction.
  - [Why] Unverified beliefs compound.
EOF
    assert_eq "flags line 3" "- CLAUDE.md:3" "$(run_check "$d")"
    rm -rf "$d"
}

it_should_close_the_window_at_the_next_instruction() {
    echo "it_should_close_the_window_at_the_next_instruction"
    local d; d=$(new_fixture)
    cat > "$d/CLAUDE.md" <<'EOF'
# Principles

- [Instruction] CRITICAL: Verify everything you build.
- [Instruction] Highlight assumptions.
  - [Why] Unspoken assumptions drive the wrong outcome.
EOF
    assert_eq "flags only the CRITICAL" "- CLAUDE.md:3" "$(run_check "$d")"
    rm -rf "$d"
}

it_should_ignore_a_why_whose_prose_contains_the_word_critical() {
    echo "it_should_ignore_a_why_whose_prose_contains_the_word_critical"
    local d; d=$(new_fixture)
    cat > "$d/CLAUDE.md" <<'EOF'
# Principles

- [Instruction] Load the skill-standards skill before editing.
  - [Why] It holds the CRITICAL marker-authoring rules.
EOF
    assert_eq "no findings" "" "$(run_check "$d")"
    rm -rf "$d"
}

it_should_ignore_a_non_critical_instruction_with_no_why() {
    echo "it_should_ignore_a_non_critical_instruction_with_no_why"
    local d; d=$(new_fixture)
    cat > "$d/CLAUDE.md" <<'EOF'
# Principles

- [Instruction] Highlight assumptions.
EOF
    assert_eq "no findings" "" "$(run_check "$d")"
    rm -rf "$d"
}

it_should_flag_a_standards_skill() {
    echo "it_should_flag_a_standards_skill"
    local d; d=$(new_fixture)
    write_skill "$d" "demo-standards" <<'EOF'
---
name: demo-standards
description: "Demo."
---

- [Instruction] CRITICAL: Never bundle unrelated changes.
EOF
    assert_eq "flags the skill" "- skills/demo-standards/SKILL.md:6" "$(run_check "$d")"
    rm -rf "$d"
}

it_should_ignore_an_ordinary_skill() {
    echo "it_should_ignore_an_ordinary_skill"
    local d; d=$(new_fixture)
    write_skill "$d" "demo-helper" <<'EOF'
---
name: demo-helper
description: "Demo."
---

- [Instruction] CRITICAL: Never bundle unrelated changes.
EOF
    assert_eq "no findings" "" "$(run_check "$d")"
    rm -rf "$d"
}

it_should_report_every_offending_site() {
    echo "it_should_report_every_offending_site"
    local d; d=$(new_fixture)
    cat > "$d/CLAUDE.md" <<'EOF'
# Principles

- [Instruction] CRITICAL: Verify everything you build.
- [Instruction] CRITICAL: Search before creating.
EOF
    write_skill "$d" "demo-standards" <<'EOF'
---
name: demo-standards
description: "Demo."
---

- [Instruction] CRITICAL: Never bundle unrelated changes.
EOF
    local expected
    expected=$'- CLAUDE.md:3\n- CLAUDE.md:4\n- skills/demo-standards/SKILL.md:6'
    assert_eq "flags all three" "$expected" "$(run_check "$d")"
    rm -rf "$d"
}

it_should_stay_silent_when_every_critical_has_its_why
it_should_flag_a_critical_with_no_why_at_all
it_should_accept_a_why_on_the_third_non_blank_line
it_should_flag_a_why_that_arrives_on_the_fourth_non_blank_line
it_should_close_the_window_at_the_next_instruction
it_should_ignore_a_why_whose_prose_contains_the_word_critical
it_should_ignore_a_non_critical_instruction_with_no_why
it_should_flag_a_standards_skill
it_should_ignore_an_ordinary_skill
it_should_report_every_offending_site

echo
echo "$passed passed, $failed failed"
[ "$failed" -eq 0 ]
