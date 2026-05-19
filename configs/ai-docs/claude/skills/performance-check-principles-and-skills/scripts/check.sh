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
readonly SKILL_DESC_BUDGET=250
readonly SKILL_NAME_BUDGET=64

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

# Extract single-line YAML frontmatter description (handles optional surrounding quotes)
extract_description() {
    awk '
        /^---[[:space:]]*$/ { in_fm = !in_fm; if (!in_fm) exit; next }
        in_fm && /^description:[[:space:]]/ {
            sub(/^description:[[:space:]]+/, "")
            sub(/^["\047]/, "")
            sub(/["\047][[:space:]]*$/, "")
            print
            exit
        }
    ' "$1"
}

# Extract optional per-skill word-budget override (frontmatter `words-budget: N`)
# Empty string = no override; caller falls back to SKILL_WORDS_BUDGET.
extract_words_budget() {
    awk '
        /^---[[:space:]]*$/ { in_fm = !in_fm; if (!in_fm) exit; next }
        in_fm && /^words-budget:[[:space:]]+[0-9]+[[:space:]]*$/ {
            sub(/^words-budget:[[:space:]]+/, "")
            sub(/[[:space:]]*$/, "")
            print
            exit
        }
    ' "$1"
}

# Skill measurements
if [ "$has_skills_dir" -eq 1 ]; then
    skill_count=$(find -L "$SKILLS_DIR" -maxdepth 1 -mindepth 1 -type d | wc -l | tr -d ' ')

    skill_overages=""
    max_desc=0
    max_desc_skill="—"
    max_name=0
    max_name_skill="—"
    for f in "$SKILLS_DIR"/*/SKILL.md; do
        [ -f "$f" ] || continue
        name=$(basename "$(dirname "$f")")
        lines=$(grep -c '\S' "$f")
        words=$(wc -w < "$f" | tr -d ' ')
        desc=$(extract_description "$f")
        desc_chars=$(printf '%s' "$desc" | LC_ALL=en_US.UTF-8 wc -m | tr -d ' ')
        name_chars=${#name}

        # Per-skill override beats default. Skills that legitimately pair
        # principles with inline examples opt in via `words-budget: N`.
        skill_words_budget_override=$(extract_words_budget "$f")
        if [ -n "$skill_words_budget_override" ]; then
            skill_words_budget=$skill_words_budget_override
            words_overage_suffix=" (override; default=$SKILL_WORDS_BUDGET)"
        else
            skill_words_budget=$SKILL_WORDS_BUDGET
            words_overage_suffix=""
        fi

        if [ "$desc_chars" -gt "$max_desc" ]; then
            max_desc=$desc_chars
            max_desc_skill=$name
        fi
        if [ "$name_chars" -gt "$max_name" ]; then
            max_name=$name_chars
            max_name_skill=$name
        fi

        issues=""
        [ "$lines" -gt "$SKILL_LINES_BUDGET" ] && issues+=" lines=$lines"
        [ "$words" -gt "$skill_words_budget" ] && issues+=" words=$words(>$skill_words_budget$words_overage_suffix)"
        [ "$desc_chars" -gt "$SKILL_DESC_BUDGET" ] && issues+=" desc=${desc_chars}c"
        [ "$name_chars" -gt "$SKILL_NAME_BUDGET" ] && issues+=" name=${name_chars}c"

        if [ -n "$issues" ]; then
            skill_overages+=$'\n'"- $name:$issues"
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
    echo "| Max skill desc chars | $max_desc ($max_desc_skill) | $SKILL_DESC_BUDGET | $(status_of "$max_desc" "$SKILL_DESC_BUDGET") |"
    echo "| Max skill name chars | $max_name ($max_name_skill) | $SKILL_NAME_BUDGET | $(status_of "$max_name" "$SKILL_NAME_BUDGET") |"
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
    echo "## Skills exceeding budgets (lines >$SKILL_LINES_BUDGET, words >$SKILL_WORDS_BUDGET, desc >${SKILL_DESC_BUDGET}c, name >${SKILL_NAME_BUDGET}c)"
    echo "$skill_overages"
    echo
fi

# Density check across CLAUDE.md + all SKILL.md + references + assets
density_script="$HOME/.claude/skills/doc-standards/scripts/check-density.sh"
if [ -x "$density_script" ]; then
    density_targets=()
    [ "$has_claude_md" -eq 1 ] && density_targets+=("$CLAUDE_MD")
    if [ "$has_skills_dir" -eq 1 ]; then
        while IFS= read -r f; do density_targets+=("$f"); done < <(
            find -L "$SKILLS_DIR" -type f \( -name "SKILL.md" -o -path "*/references/*.md" -o -path "*/assets/*.md" \) | sort
        )
    fi
    if [ "${#density_targets[@]}" -gt 0 ]; then
        density_out=$("$density_script" "${density_targets[@]}" 2>/dev/null || true)
        density_total=$(printf '%s\n' "$density_out" | awk '/^[0-9]/' | wc -l | tr -d ' ')
        density_status="OK"
        [ "$density_total" -gt 0 ] && density_status="OVER" && overages=1
        echo "## Density check (256 chars / 32 words per line)"
        echo
        echo "Total violations: $density_total ($density_status)"
        if [ "$density_total" -gt 0 ]; then
            echo
            echo "Per-file:"
            printf '%s\n' "$density_out" | awk '
                /^==/ { file=$2; next }
                /^[0-9]/ { count[file]++ }
                END { for (f in count) printf "- %s: %d\n", f, count[f] }
            ' | sort
        fi
        echo
    fi
fi

if [ "$overages" -eq 0 ]; then
    echo "All budgets met ✓"
    exit 0
else
    exit 1
fi
