#!/usr/bin/env bash
# check.sh - Audit CLAUDE.md and skills against performance budgets
#
# Usage:
#   check.sh [path]
#
# No arg: audits ~/.claude/CLAUDE.md and ~/.claude/skills/
# Path:   audits <path>/CLAUDE.md and <path>/.claude/skills/
#
# Examples:
#   check.sh                          # user config
#   check.sh ~/work/my-project        # repo config
#
# Exit codes:
#   0 — all budgets met
#   1 — one or more overages

set -eo pipefail

# Budgets — keep in sync with SKILL.md
readonly CLAUDE_LINES_BUDGET=200
readonly CLAUDE_WORDS_PER_LINE_BUDGET=32
readonly SKILLS_COUNT_BUDGET=32
readonly SKILL_LINES_BUDGET=500
readonly SKILL_WORDS_BUDGET=2048

# Resolve targets
if [ -z "${1:-}" ]; then
    CLAUDE_MD="$HOME/.claude/CLAUDE.md"
    SKILLS_DIR="$HOME/.claude/skills"
    TARGET_LABEL="user (~/.claude)"
else
    CLAUDE_MD="$1/CLAUDE.md"
    SKILLS_DIR="$1/.claude/skills"
    TARGET_LABEL="repo ($1)"
fi

has_claude_md=0
has_skills_dir=0
[ -f "$CLAUDE_MD" ] && has_claude_md=1
[ -d "$SKILLS_DIR" ] && has_skills_dir=1

if [ "$has_claude_md" -eq 0 ] && [ "$has_skills_dir" -eq 0 ]; then
    echo "ERROR: neither $CLAUDE_MD nor $SKILLS_DIR found" >&2
    exit 1
fi

# CLAUDE.md measurements
if [ "$has_claude_md" -eq 1 ]; then
    claude_lines=$(grep -c '\S' "$CLAUDE_MD")
    claude_max_words=$(awk '{ if (NF > max) { max = NF; ln = NR } } END { print max+0 }' "$CLAUDE_MD")
    claude_max_words_line=$(awk '{ if (NF > max) { max = NF; ln = NR } } END { print ln+0 }' "$CLAUDE_MD")
    claude_offending=$(awk -v b="$CLAUDE_WORDS_PER_LINE_BUDGET" '{ if (NF > b) print NR": "NF" words" }' "$CLAUDE_MD")
fi

# Skill measurements
if [ "$has_skills_dir" -eq 1 ]; then
    skill_count=$(find -L "$SKILLS_DIR" -maxdepth 1 -mindepth 1 -type d | wc -l | tr -d ' ')

    skill_overages=""
    for f in "$SKILLS_DIR"/*/SKILL.md; do
        [ -f "$f" ] || continue
        lines=$(grep -c '\S' "$f")
        words=$(wc -w < "$f" | tr -d ' ')
        if [ "$lines" -gt "$SKILL_LINES_BUDGET" ] || [ "$words" -gt "$SKILL_WORDS_BUDGET" ]; then
            name=$(basename "$(dirname "$f")")
            skill_overages+=$'\n'"- $name: $lines lines, $words words"
        fi
    done
fi

status_of() {
    local measured=$1
    local budget=$2
    if [ "$measured" -le "$budget" ]; then
        echo "OK"
    else
        echo "OVER"
    fi
}

# Report
echo "# Performance Check — $TARGET_LABEL"
echo
echo "| Target | Measured | Budget | Status |"
echo "|---|---|---|---|"

overages=0
if [ "$has_claude_md" -eq 1 ]; then
    echo "| CLAUDE.md non-blank lines | $claude_lines | $CLAUDE_LINES_BUDGET | $(status_of "$claude_lines" "$CLAUDE_LINES_BUDGET") |"
    echo "| CLAUDE.md max words/line | $claude_max_words (line $claude_max_words_line) | $CLAUDE_WORDS_PER_LINE_BUDGET | $(status_of "$claude_max_words" "$CLAUDE_WORDS_PER_LINE_BUDGET") |"
    [ "$claude_lines" -gt "$CLAUDE_LINES_BUDGET" ] && overages=1
    [ "$claude_max_words" -gt "$CLAUDE_WORDS_PER_LINE_BUDGET" ] && overages=1
else
    echo "| CLAUDE.md | — | — | NOT FOUND at $CLAUDE_MD |"
fi

if [ "$has_skills_dir" -eq 1 ]; then
    echo "| Skill count | $skill_count | $SKILLS_COUNT_BUDGET | $(status_of "$skill_count" "$SKILLS_COUNT_BUDGET") |"
    [ "$skill_count" -gt "$SKILLS_COUNT_BUDGET" ] && overages=1
    [ -n "$skill_overages" ] && overages=1
else
    echo "| Skills directory | — | — | NOT FOUND at $SKILLS_DIR |"
fi
echo

if [ "$has_claude_md" -eq 1 ] && [ -n "$claude_offending" ]; then
    echo "## CLAUDE.md lines exceeding $CLAUDE_WORDS_PER_LINE_BUDGET words"
    echo
    echo "$claude_offending"
    echo
fi

if [ "$has_skills_dir" -eq 1 ] && [ -n "$skill_overages" ]; then
    echo "## Skills exceeding size budgets ($SKILL_LINES_BUDGET lines or $SKILL_WORDS_BUDGET words)"
    echo "$skill_overages"
    echo
fi

if [ "$overages" -eq 0 ]; then
    echo "All budgets met ✓"
    exit 0
else
    exit 1
fi
