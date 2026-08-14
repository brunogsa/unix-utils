#!/usr/bin/env bash
# check.sh - Audit CLAUDE.md and skills against budgets.
#
# Usage:
#   check.sh [path]
#
# No arg: audits ~/.claude/CLAUDE.md and ~/.claude/skills/
# Path:   audits <path>/CLAUDE.md; skills dir tried as
#         <path>/.claude/skills/, then <path>/skills/
#
# Examples:
#   check.sh                          # user config
#   check.sh ~/work/my-project        # repo config
#
# Exit codes:
#   0 - all budgets met
#   1 - one or more overages, or a hard failure (e.g.
#       missing skills directory)

set -eo pipefail

# Budgets — keep in sync with SKILL.md.
#
# 260, not 200: the marker convention pairs a [Why] line
# under every [Instruction], so ~100 instructions cost ~200
# lines of pairs before any header/example/meta.
#
# The old 200 assumed "1 line ≈ 1 instruction" (pre-markers)
# and now binds before the real gate — the [Instruction]
# count (CLAUDE_INSTRUCTIONS_BUDGET).
#
# See references/research-claudemd-budgets.md#claudemd-length
readonly CLAUDE_LINES_BUDGET=260
readonly CLAUDE_WORDS_PER_LINE_BUDGET=32
readonly SKILLS_COUNT_BUDGET=50
readonly SKILL_LINES_BUDGET=500
readonly SKILL_WORDS_BUDGET=2048
readonly SKILL_DESC_BUDGET=250
readonly SKILL_NAME_BUDGET=64

# Bundled-resource budgets (references/ + assets/), the
# same fixed pair for every file.
#
# Half of SKILL_WORDS_BUDGET on purpose: a reference is ONE
# focused topic, not a second SKILL.md, so a file that
# outgrows this is usually two topics sharing one filename.
#
# Remedy order is trim, then split by topic; the frontmatter
# override is the user's call.
readonly BUNDLED_WORDS_BUDGET=1024
readonly BUNDLED_LINES_BUDGET=256

# Half the word budget. Past it, a flat file costs the
# reader a full scroll to find one section, so it must
# carry at least one "## " landmark.
#
# Not overridable: unlike the size budgets there is no file
# that legitimately needs to stay flat at this length.
readonly BUNDLED_HEADINGS_THRESHOLD=512

# Instruction-density budgets. See CLAUDE.md "Counting
# conventions" plus
# references/research-instruction-load-budgets.md.
#
# Two per-bucket budgets so each failure surface is
# independent and self-explanatory.
#
# Both sit well under IFScale's 500-instruction adherence
# ceiling — deliberately tight to preserve adherence
# headroom rather than burn it.
#
# 100 + 200 = 300, leaving ~200 instructions of slack
# against the 500 cliff for repo-level CLAUDE.md and
# ad-hoc rules.

# CLAUDE.md alone
readonly CLAUDE_INSTRUCTIONS_BUDGET=100

# Sum across *-standards skills
readonly STANDARDS_INSTRUCTIONS_BUDGET=200

# Percent of [Instruction] count per file
readonly CRITICAL_RATIO_BUDGET=16

# Bytes one [Why] line may cost.
#
# Every budget above counts markers or words, never bytes,
# so a file can sit exactly on its [Instruction] cap while
# rationale eats 42.7% of it — 15,488 of CLAUDE.md's 37.1 KB
# at the measurement that motivated this cap.
#
# 128 is the user's own pick against the distribution of
# that file's 100 [Why] lines: min 54, p50 159, p75 181,
# p90 198, max 227.
#
# It sits below the median on purpose, so the cap binds the
# typical rationale rather than only the tail.
readonly WHY_BYTES_BUDGET=128

# *-standards skills excluded from
# STANDARDS_INSTRUCTIONS_BUDGET (space-separated).
#
# That subtotal caps what ONE source change can pull in at
# once — touching code, its comments, and its tests fires
# code/doc/test-standards together, so they share a budget.
#
# skill-standards and agent-standards fire on a disjoint
# trigger — authoring the harness itself — and never ride
# along with that set, so charging them to the shared pool
# would cap unrelated budgets against each other.
#
# Each stays gated by its own frontmatter
# `instructions-budget:` and still appears in the
# CRITICAL-ratio table below.
readonly STANDARDS_SUBTOTAL_EXCLUDED="skill-standards agent-standards"

# Resolve targets
if [ -z "${1:-}" ]; then
    CLAUDE_MD="$HOME/.claude/CLAUDE.md"
    SKILLS_DIR="$HOME/.claude/skills"
    SKILLS_DIR_TRIED="$SKILLS_DIR"
    TARGET_LABEL="user (~/.claude)"
else
    CLAUDE_MD="$1/CLAUDE.md"

    # A path arg may name a repo laid out either way: nested
    # <path>/.claude/skills/, or a sibling <path>/skills/
    # (this repo's own layout). Try nested first, then fall
    # back to the sibling.
    skills_dir_nested="$1/.claude/skills"
    skills_dir_sibling="$1/skills"
    if [ -d "$skills_dir_nested" ]; then
        SKILLS_DIR="$skills_dir_nested"
    elif [ -d "$skills_dir_sibling" ]; then
        SKILLS_DIR="$skills_dir_sibling"
    else
        SKILLS_DIR="$skills_dir_nested"
    fi
    SKILLS_DIR_TRIED="$skills_dir_nested, $skills_dir_sibling"
    TARGET_LABEL="repo ($1)"
fi

has_claude_md=0
[ -f "$CLAUDE_MD" ] && has_claude_md=1

if [ "$has_claude_md" -eq 0 ] && [ ! -d "$SKILLS_DIR" ]; then
    echo "ERROR: neither $CLAUDE_MD nor $SKILLS_DIR found" >&2
    exit 1
fi

# A missing skills dir must hard-fail here, never fall
# through to a green report that measured zero skills.
if [ ! -d "$SKILLS_DIR" ]; then
    echo "ERROR: no skills directory found (tried $SKILLS_DIR_TRIED)" >&2
    exit 1
fi

# The agent-contract row always targets the canonical
# installed agents dir, never $1 or the no-arg default
# above — the contract is about this config repo, not
# whatever tree the caller pointed check.sh at.
#
# readlink -f (not a literal repo path) tracks wherever
# install.sh actually pointed the symlink, so a clone at a
# different location still resolves correctly.
AGENT_CONTRACT_SCRIPT="$HOME/.claude/skills/agent-standards/scripts/check-agent-contract.sh"
CANONICAL_AGENTS_DIR=$(readlink -f "$HOME/.claude/agents" 2>/dev/null || true)

# A missing/broken symlink hard-fails here, mirroring the
# missing-skills-dir check above — never a silent skip of
# the agent-contract row in the report below.
if [ -z "$CANONICAL_AGENTS_DIR" ] || [ ! -d "$CANONICAL_AGENTS_DIR" ]; then
    echo "ERROR: cannot resolve ~/.claude/agents (readlink -f)" >&2
    exit 1
fi
if [ ! -x "$AGENT_CONTRACT_SCRIPT" ]; then
    echo "ERROR: agent-contract checker missing: $AGENT_CONTRACT_SCRIPT" >&2
    exit 1
fi

# Helper functions
# ==============================================================
# All defined up-front so any measurement block below can
# call them.
#
# Bash resolves function names at call time, not at parse
# time — definitions must precede their first call site in
# source order.

# Extract single-line YAML frontmatter description.
# Handles optional surrounding quotes.
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

# Extract an optional numeric budget override from a
# file's YAML frontmatter.
#
# Usage: extract_frontmatter_budget <key> <file>
# Keys: "words-budget", "lines-budget".
#
# Empty string = no override; every caller falls back to
# the matching global default.
#
# One generic reader rather than one function per key:
# SKILL.md, references/, and assets/ all declare overrides
# the same way, so the parse belongs in one place.
extract_frontmatter_budget() {
    awk -v key="$1" '
        /^---[[:space:]]*$/ { in_fm = !in_fm; if (!in_fm) exit; next }
        in_fm && NF == 2 && $1 == key ":" && $2 ~ /^[0-9]+$/ { print $2; exit }
    ' "$2"
}

# Count [Instruction] markers (one per line).
# Always returns an integer.
#
# Anchored to a leading tag — optional list marker
# (-, *, N.) then the bracket — so prose mentions of the
# marker name and the glossary definition in CLAUDE.md's
# Counting Conventions section are excluded, not counted.
count_instructions() {
    awk '/^[[:space:]]*([-*]|[0-9]+\.)?[[:space:]]*\[Instruction\]/ { c++ } END { print c+0 }' "$1"
}

# Count [Instruction] lines also marked CRITICAL.
# Always returns an integer.
count_critical_instructions() {
    awk '/^[[:space:]]*([-*]|[0-9]+\.)?[[:space:]]*\[Instruction\]/ && /CRITICAL/ { c++ } END { print c+0 }' "$1"
}

# Print `- <file>:<line>` for every CRITICAL [Instruction]
# with no [Why] among the next 3 non-blank lines.
# Silent when the file is clean.
#
# CLAUDE.md's Counting Conventions make CRITICAL a
# tiebreaker marker, and a tiebreaker with no stated
# rationale can't be weighed against the rule it overrides.
#
# Three lines, because an [Example] and a second [Why]-less
# sub-bullet may legitimately sit between the two.
#
# Anchored on the same leading-tag pattern as the counters
# above.
#
# That anchoring is what a hand-run of this check lacks: a
# [Why] line whose prose merely says CRITICAL reads as an
# [Instruction] to the eye, never to the regex.
#
# Any later [Instruction] closes the window early: a [Why]
# below it belongs to that instruction, never to the one
# before it.
missing_why_after_critical() {
    awk '
        function flush() {
            if (pending) { printf "- %s:%d\n", FILENAME, pending; pending = 0 }
        }
        /^[[:space:]]*([-*]|[0-9]+\.)?[[:space:]]*\[Instruction\]/ {
            flush()
            if ($0 ~ /CRITICAL/) { pending = FNR; seen = 0 }
            next
        }
        pending && /^[[:space:]]*([-*]|[0-9]+\.)?[[:space:]]*\[Why\]/ { pending = 0; next }
        pending && NF > 0 { if (++seen >= 3) flush() }
        END { flush() }
    ' "$1"
}

# Print `<file>:<line>: <n> bytes (>cap)` for every [Why]
# marker line over WHY_BYTES_BUDGET.
# Silent when the file is clean.
#
# A [Why] adds no constraint by convention, so its bytes buy
# the reader rationale and nothing else — the one marker
# whose length is worth capping on its own.
#
# An [Instruction] earns its length by adding a rule; a
# [Why] past the cap is always-on context buying no rule,
# so it is gated like every other budget here.
#
# Bytes, not characters: these files are full of em dashes,
# arrows and ×, which cost 2-3 bytes each, and context is
# spent in bytes. LC_ALL=C is what makes awk's length()
# count them.
#
# Anchored on the same leading-tag pattern as the counters
# above, fenced blocks included — a fenced [Why] costs the
# same bytes on load and still models the convention for
# the next author.
#
# Measures the same population the [Instruction] counters
# measure: CLAUDE.md plus every top-level SKILL.md.
# references/ and assets/ stay outside it by design.
over_budget_why_lines() {
    LC_ALL=C awk -v b="$WHY_BYTES_BUDGET" '
        /^[[:space:]]*([-*]|[0-9]+\.)?[[:space:]]*\[Why\]/ && length($0) > b {
            printf "%s:%d: %d bytes (>%d)\n", FILENAME, FNR, length($0), b
        }
    ' "$1"
}

# Integer percentage, rounded to nearest, not truncated.
#
# The single source used for BOTH the displayed value and
# the pass/fail comparison, so what the report shows is
# exactly what it verified. 0 when total is 0.
ratio_percent_int() {
    awk -v c="$1" -v t="$2" 'BEGIN { if (t == 0) print 0; else printf "%d", (c*100)/t + 0.5 }'
}

# Compare a measured integer against a budget.
# Echo "OK" or "OVER".
status_of() {
    local measured=$1
    local budget=$2
    if [ "$measured" -le "$budget" ]; then
        echo "OK"
    else
        echo "OVER"
    fi
}

# Measurements
# ==============================================================

# CRITICAL [Instruction] sites missing their [Why], across
# CLAUDE.md + the *-standards skills — the same population
# the CRITICAL-ratio check measures, since the marker
# convention binds only there.
missing_why_rows=""

# [Why] lines over the byte cap, across the same population
# the [Instruction] counters measure: CLAUDE.md plus every
# SKILL.md.
#
# Wider than the CRITICAL-ratio population on purpose: any
# skill that writes a [Why] pays for its bytes, whether or
# not it is a *-standards skill.
why_over_rows=""

# CLAUDE.md measurements
if [ "$has_claude_md" -eq 1 ]; then
    claude_lines=$(grep -c '\S' "$CLAUDE_MD")
    claude_max_words=$(awk '{ if (NF > max) { max = NF; ln = NR } } END { print max+0 }' "$CLAUDE_MD")
    claude_max_words_line=$(awk '{ if (NF > max) { max = NF; ln = NR } } END { print ln+0 }' "$CLAUDE_MD")
    claude_offending=$(awk -v b="$CLAUDE_WORDS_PER_LINE_BUDGET" '{ if (NF > b) print NR": "NF" words" }' "$CLAUDE_MD")

    # Instruction-density measurements.
    # Transitional: 0 markers = unmigrated, skip ratio check.
    claude_instructions=$(count_instructions "$CLAUDE_MD")
    claude_criticals=$(count_critical_instructions "$CLAUDE_MD")
    claude_ratio_int=$(ratio_percent_int "$claude_criticals" "$claude_instructions")

    claude_missing_why=$(missing_why_after_critical "$CLAUDE_MD")
    [ -n "$claude_missing_why" ] && missing_why_rows+=$'\n'"$claude_missing_why"

    claude_why_over=$(over_budget_why_lines "$CLAUDE_MD")
    [ -n "$claude_why_over" ] && why_over_rows+=$'\n'"$claude_why_over"
fi

# Skill measurements
skill_count=$(find -L "$SKILLS_DIR" -maxdepth 1 -mindepth 1 -type d | wc -l | tr -d ' ')

skill_overages=""
max_desc=0
max_desc_skill="—"
max_name=0
max_name_skill="—"

# Instruction-density accumulators.
# Only *-standards skills participate.
standards_total_instructions=0
standards_ratio_rows=""
standards_unmigrated=""
standards_ratio_over=0

# Status-table rows for the *-standards skills the subtotal
# excludes.
#
# An excluded skill answers only to its own frontmatter
# `instructions-budget:`, and that gate is silent while
# passing.
#
# Without these rows the table names the exclusion but never
# shows the number or the limit that replaced the shared
# budget.
excluded_standards_rows=""

# Per-skill instructions-budget override accumulators.
# Any skill, not just *-standards.
skill_instr_overages=""
skill_instr_over=0
for f in "$SKILLS_DIR"/*/SKILL.md; do
    [ -f "$f" ] || continue
    name=$(basename "$(dirname "$f")")
    lines=$(grep -c '\S' "$f")
    words=$(wc -w < "$f" | tr -d ' ')
    desc=$(extract_description "$f")
    desc_chars=$(printf '%s' "$desc" | LC_ALL=en_US.UTF-8 wc -m | tr -d ' ')
    name_chars=${#name}

    # Per-skill override beats default.
    #
    # Skills that legitimately pair principles with
    # inline examples opt in via `words-budget: N`.
    skill_words_budget_override=$(extract_frontmatter_budget "words-budget" "$f")
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

    # `instructions-budget` is opt-in for ANY skill, not
    # just *-standards: a skill that caps its own
    # instruction count gets the gate without joining the
    # *-standards subtotal or CRITICAL-ratio report below.
    #
    # No key declared means no cap — the check is silent,
    # never a default.
    skill_instructions=$(count_instructions "$f")

    skill_why_over=$(over_budget_why_lines "$f")
    [ -n "$skill_why_over" ] && why_over_rows+=$'\n'"$skill_why_over"

    instr_budget_override=$(extract_frontmatter_budget "instructions-budget" "$f")
    if [ -n "$instr_budget_override" ] && [ "$skill_instructions" -gt "$instr_budget_override" ]; then
        skill_instr_overages+=$'\n'"- $name: $skill_instructions [Instruction] (>$instr_budget_override budget)"
        skill_instr_over=1
    fi

    # Instruction density — only *-standards skills participate
    case "$name" in
        *-standards)
            skill_criticals=$(count_critical_instructions "$f")

            skill_missing_why=$(missing_why_after_critical "$f")
            [ -n "$skill_missing_why" ] && missing_why_rows+=$'\n'"$skill_missing_why"

            # Excluded skills still get a ratio row and
            # status-table rows of their own; only the
            # shared subtotal skips them.
            is_subtotal_excluded=0
            case " $STANDARDS_SUBTOTAL_EXCLUDED " in
                *" $name "*) is_subtotal_excluded=1 ;;
            esac

            # An excluded skill's cap is whatever its
            # frontmatter declares.
            #
            # No key means no cap at all, which the row has
            # to say out loud — a blank budget cell would
            # read as "measured against something" and hide
            # that the count is ungated.
            if [ -n "$instr_budget_override" ]; then
                excluded_instr_budget=$instr_budget_override
                excluded_instr_status=$(status_of "$skill_instructions" "$instr_budget_override")
            else
                excluded_instr_budget="none declared"
                excluded_instr_status="—"
            fi

            if [ "$skill_instructions" -eq 0 ]; then
                standards_unmigrated+=$'\n'"- $name (0 [Instruction] markers)"
                if [ "$is_subtotal_excluded" -eq 1 ]; then
                    excluded_standards_rows+=$'\n'"| $name [Instruction] count | 0 | $excluded_instr_budget | UNMIGRATED |"
                    excluded_standards_rows+=$'\n'"| $name CRITICAL ratio | N/A | ${CRITICAL_RATIO_BUDGET}% | UNMIGRATED |"
                fi
            else
                [ "$is_subtotal_excluded" -eq 0 ] && standards_total_instructions=$((standards_total_instructions + skill_instructions))
                skill_ratio_int=$(ratio_percent_int "$skill_criticals" "$skill_instructions")
                ratio_status=$(status_of "$skill_ratio_int" "$CRITICAL_RATIO_BUDGET")
                standards_ratio_rows+=$'\n'"| $name | $skill_instructions | $skill_criticals | ${skill_ratio_int}% | $ratio_status |"
                [ "$skill_ratio_int" -gt "$CRITICAL_RATIO_BUDGET" ] && standards_ratio_over=1
                if [ "$is_subtotal_excluded" -eq 1 ]; then
                    excluded_standards_rows+=$'\n'"| $name [Instruction] count | $skill_instructions | $excluded_instr_budget | $excluded_instr_status |"
                    excluded_standards_rows+=$'\n'"| $name CRITICAL ratio | ${skill_ratio_int}% ($skill_criticals/$skill_instructions) | ${CRITICAL_RATIO_BUDGET}% | $ratio_status |"
                fi
            fi
            ;;
    esac
done

# Bundled resources (references/ + assets/) — same fixed
# pair of budgets per file.
#
# Without this, the trim hierarchy's "extract to
# references/" step could clear a SKILL.md overage by
# relocating words into a file nothing measured — budget
# cosmetics rather than a real lazy load.
bundled_overages=""
bundled_over=0
bundled_count=0
while IFS= read -r bf; do
    [ -f "$bf" ] || continue
    bundled_count=$((bundled_count + 1))
    rel=${bf#"$SKILLS_DIR"/}
    b_lines=$(grep -c '\S' "$bf")
    b_words=$(wc -w < "$bf" | tr -d ' ')

    b_words_override=$(extract_frontmatter_budget "words-budget" "$bf")
    if [ -n "$b_words_override" ]; then
        b_words_budget=$b_words_override
        b_words_suffix=" (override; default=$BUNDLED_WORDS_BUDGET)"
    else
        b_words_budget=$BUNDLED_WORDS_BUDGET
        b_words_suffix=""
    fi

    b_lines_override=$(extract_frontmatter_budget "lines-budget" "$bf")
    if [ -n "$b_lines_override" ]; then
        b_lines_budget=$b_lines_override
        b_lines_suffix=" (override; default=$BUNDLED_LINES_BUDGET)"
    else
        b_lines_budget=$BUNDLED_LINES_BUDGET
        b_lines_suffix=""
    fi

    b_issues=""
    [ "$b_words" -gt "$b_words_budget" ] && b_issues+=" words=$b_words(>$b_words_budget$b_words_suffix)"
    [ "$b_lines" -gt "$b_lines_budget" ] && b_issues+=" lines=$b_lines(>$b_lines_budget$b_lines_suffix)"

    # Past the threshold, a file with no "## " landmark
    # forces a full read to find one section.
    #
    # assets/flowchart.md is exempt: it is a single mermaid
    # diagram by construction, so an inner heading would
    # name nothing.
    if [ "$b_words" -gt "$BUNDLED_HEADINGS_THRESHOLD" ] && [ "$(basename "$bf")" != "flowchart.md" ]; then
        b_h2=$(grep -c '^## ' "$bf" || true)
        [ "$b_h2" -eq 0 ] && b_issues+=" no-'## '-headings(words=$b_words>$BUNDLED_HEADINGS_THRESHOLD)"
    fi

    if [ -n "$b_issues" ]; then
        bundled_overages+=$'\n'"- $rel:$b_issues"
        bundled_over=$((bundled_over + 1))
    fi
done < <(find -L "$SKILLS_DIR" -type f \( -path "*/references/*.md" -o -path "*/assets/*.md" \) | sort)

# Agent-contract measurement — always the canonical dir
# resolved above, never $SKILLS_DIR or $1.
agent_contract_out=$("$AGENT_CONTRACT_SCRIPT" "$CANONICAL_AGENTS_DIR" 2>&1 || true)
agent_contract_offending=$(printf '%s\n' "$agent_contract_out" | grep -c '^== ' || true)
agent_contract_total=$(find "$CANONICAL_AGENTS_DIR" -maxdepth 1 -name '*.md' | wc -l | tr -d ' ')

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

    # Instruction-density rows (CLAUDE.md).
    # A file with 0 [Instruction] markers fails.
    if [ "$claude_instructions" -eq 0 ]; then
        echo "| CLAUDE.md [Instruction] count | 0 | $CLAUDE_INSTRUCTIONS_BUDGET | UNMIGRATED |"
        echo "| CLAUDE.md CRITICAL ratio | N/A | ${CRITICAL_RATIO_BUDGET}% | UNMIGRATED |"
        overages=1
    else
        echo "| CLAUDE.md [Instruction] count | $claude_instructions | $CLAUDE_INSTRUCTIONS_BUDGET | $(status_of "$claude_instructions" "$CLAUDE_INSTRUCTIONS_BUDGET") |"
        [ "$claude_instructions" -gt "$CLAUDE_INSTRUCTIONS_BUDGET" ] && overages=1
        claude_ratio_status=$(status_of "$claude_ratio_int" "$CRITICAL_RATIO_BUDGET")
        echo "| CLAUDE.md CRITICAL ratio | ${claude_ratio_int}% ($claude_criticals/$claude_instructions) | ${CRITICAL_RATIO_BUDGET}% | $claude_ratio_status |"
        [ "$claude_ratio_int" -gt "$CRITICAL_RATIO_BUDGET" ] && overages=1
    fi
else
    echo "| CLAUDE.md | — | — | NOT FOUND at $CLAUDE_MD |"
fi

echo "| Skill count | $skill_count | $SKILLS_COUNT_BUDGET | $(status_of "$skill_count" "$SKILLS_COUNT_BUDGET") |"
echo "| Max skill desc chars | $max_desc ($max_desc_skill) | $SKILL_DESC_BUDGET | $(status_of "$max_desc" "$SKILL_DESC_BUDGET") |"
echo "| Max skill name chars | $max_name ($max_name_skill) | $SKILL_NAME_BUDGET | $(status_of "$max_name" "$SKILL_NAME_BUDGET") |"
[ "$skill_count" -gt "$SKILLS_COUNT_BUDGET" ] && overages=1
[ -n "$skill_overages" ] && overages=1

# Bundled resources — one row for the whole
# references/ + assets/ population.
echo "| Bundled files failing size or heading checks (references/ + assets/) | $bundled_over of $bundled_count | 0 | $(status_of "$bundled_over" 0) |"
[ "$bundled_over" -gt 0 ] && overages=1

# Agent-authoring contract — always $CANONICAL_AGENTS_DIR,
# so this row is identical in user mode and repo mode.
echo "| Agent-authoring contract failures ($CANONICAL_AGENTS_DIR) | $agent_contract_offending of $agent_contract_total | 0 | $(status_of "$agent_contract_offending" 0) |"
[ "$agent_contract_offending" -gt 0 ] && overages=1

# Instruction-density row: *-standards subtotal against
# its dedicated budget.
echo "| *-standards [Instruction] total (excl. $STANDARDS_SUBTOTAL_EXCLUDED) | $standards_total_instructions | $STANDARDS_INSTRUCTIONS_BUDGET | $(status_of "$standards_total_instructions" "$STANDARDS_INSTRUCTIONS_BUDGET") |"
[ "$standards_total_instructions" -gt "$STANDARDS_INSTRUCTIONS_BUDGET" ] && overages=1

# Budget is 0: every CRITICAL tiebreaker states its
# rationale, or it is not a tiebreaker.
missing_why_count=$(printf '%s' "$missing_why_rows" | grep -c '^- ' || true)
echo "| CRITICAL [Instruction] missing [Why] | $missing_why_count | 0 | $(status_of "$missing_why_count" 0) |"
[ "$missing_why_count" -gt 0 ] && overages=1

# Budget is 0: a [Why] line past the byte cap is over,
# same as any other budget in this table.
why_over_count=$(printf '%s' "$why_over_rows" | grep -c ' bytes (>' || true)
echo "| [Why] lines over $WHY_BYTES_BUDGET bytes | $why_over_count | 0 | $(status_of "$why_over_count" 0) |"
[ "$why_over_count" -gt 0 ] && overages=1

# Rows for the skills that subtotal excludes, placed right
# below it so the exclusion and the budget replacing it
# read as one unit.
#
# Their overages are already gated by `skill_instr_over`
# and `standards_ratio_over` below.
[ -n "$excluded_standards_rows" ] && printf '%s\n' "$excluded_standards_rows" | sed '/^$/d'
[ "$standards_ratio_over" -eq 1 ] && overages=1
[ "$skill_instr_over" -eq 1 ] && overages=1
[ -n "$standards_unmigrated" ] && overages=1
echo

if [ "$has_claude_md" -eq 1 ] && [ -n "$claude_offending" ]; then
    echo "## CLAUDE.md lines exceeding $CLAUDE_WORDS_PER_LINE_BUDGET words"
    echo
    echo "$claude_offending"
    echo
fi

if [ -n "$skill_overages" ]; then
    echo "## Skills exceeding budgets (lines >$SKILL_LINES_BUDGET, words >$SKILL_WORDS_BUDGET, desc >${SKILL_DESC_BUDGET}c, name >${SKILL_NAME_BUDGET}c)"
    echo "$skill_overages"
    echo
fi

if [ "$agent_contract_offending" -gt 0 ]; then
    echo "## Agent-authoring contract failures"
    echo
    echo "$agent_contract_out"
    echo
fi

if [ -n "$bundled_overages" ]; then
    echo "## Bundled resources failing size or heading checks"
    echo
    echo "Size: words >$BUNDLED_WORDS_BUDGET, lines >$BUNDLED_LINES_BUDGET. Headings: at least one \`## \` past $BUNDLED_HEADINGS_THRESHOLD words."
    echo
    echo "Remedy in order: drop redundancy, tighten wording, then split the file by topic."
    echo "A missing-headings flag is fixed by adding \`## \` landmarks, never by trimming under the threshold."
    echo "A \`words-budget:\`/\`lines-budget:\` YAML frontmatter override on the file is the user's call only — never AI's."
    echo "$bundled_overages"
    echo
fi

# *-standards CRITICAL ratio breakdown (only migrated skills)
if [ -n "$standards_ratio_rows" ]; then
    echo "## *-standards CRITICAL ratio per skill"
    echo
    echo "| Skill | [Instruction] | CRITICAL | Ratio | Status |"
    echo "|---|---|---|---|---|"
    printf '%s\n' "$standards_ratio_rows" | sed '/^$/d'
    echo
fi

# Sites the ratio table cannot show: a CRITICAL that never
# says why it outranks the rule it beats.
if [ -n "$missing_why_rows" ]; then
    echo "## CRITICAL [Instruction] lines with no [Why] in the next 3 non-blank lines"
    echo
    echo "Fix each by adding the missing \`[Why]\`, or by dropping the \`CRITICAL\` prefix — an unexplained tiebreaker cannot be weighed against the rule it overrides."
    printf '%s\n' "$missing_why_rows" | sed '/^$/d'
    echo
fi

# Over-cap [Why] sites, one per line, so a fix pass can work
# straight from the report.
if [ -n "$why_over_rows" ]; then
    echo "## [Why] lines over $WHY_BYTES_BUDGET bytes"
    echo
    echo "A \`[Why]\` adds no constraint, so every byte past the cap is always-on context buying no rule — trim each to one decision-shaping sentence."
    echo "An over-cap \`[Why]\` fails this check."
    echo
    printf '%s\n' "$why_over_rows" | sed '/^$/d'
    echo
fi

# Per-skill instructions-budget overages, listed when the
# frontmatter override is set and exceeded.
if [ -n "$skill_instr_overages" ]; then
    echo "## Skills over their \`instructions-budget\` frontmatter override"
    echo
    echo "$skill_instr_overages"
    echo
fi

# Unmigrated *-standards skills — error condition
if [ -n "$standards_unmigrated" ]; then
    echo "## Unmigrated *-standards skills (FAIL)"
    echo
    echo "These skills have 0 [Instruction] markers. Either migrate them to the marker convention (see CLAUDE.md → \"Counting conventions\") or rename the directory so it no longer matches the \`*-standards\` glob."
    echo "$standards_unmigrated"
    echo
fi

# Density check across CLAUDE.md + all SKILL.md
# + references + assets
density_script="$HOME/.claude/skills/doc-standards/scripts/check-density.sh"
if [ -x "$density_script" ]; then
    density_targets=()
    [ "$has_claude_md" -eq 1 ] && density_targets+=("$CLAUDE_MD")
    while IFS= read -r f; do density_targets+=("$f"); done < <(
        find -L "$SKILLS_DIR" -type f \( -name "SKILL.md" -o -path "*/references/*.md" -o -path "*/assets/*.md" \) | sort
    )
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
