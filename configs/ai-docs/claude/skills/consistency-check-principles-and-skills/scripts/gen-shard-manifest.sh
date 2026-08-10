#!/usr/bin/env bash
# gen-shard-manifest.sh - Emit the file-shard manifest consistency-check
# hands to its per-shard ensemble dispatch (D12).
#
# For each skills/*/ directory, emits a shard listing every file in
# it, plus any agents/*.md file it dispatches by name, plus any other
# in-repo file its own files reference outside its own directory.
# Emits one further dedicated shard containing only CLAUDE.md, and
# adds CLAUDE.md to every other shard's file list (D13) so every shard
# carries the principles that govern it.
#
# Usage:
#   gen-shard-manifest.sh [path]
#
# No arg: shards ~/.claude/CLAUDE.md and ~/.claude/skills/
# Path:   shards <path>/CLAUDE.md; skills dir tried as
#         <path>/.claude/skills/, then <path>/skills/
#
# Examples:
#   gen-shard-manifest.sh                    # user config
#   gen-shard-manifest.sh ~/work/my-project  # repo config
#
# Output format (stdout):
#   [SHARD] <slug>
#   <absolute file path>
#   <absolute file path>
#   ...
#   <blank line>
#   ... one block per skill, sorted by slug, then a final
#   [SHARD] claude-md block containing only CLAUDE.md.
#
# Exit codes:
#   0 - manifest emitted
#   1 - hard failure (missing skills directory, missing CLAUDE.md,
#       or a skills directory with zero skill subdirectories) —
#       never an empty manifest.

set -eo pipefail

usage() {
    sed -n '2,25p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
}

if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
    usage
    exit 0
fi

# Resolve targets — mirrors check.sh's nested-then-sibling resolution
# exactly, so a path arg behaves identically for both scripts.
if [ -z "${1:-}" ]; then
    CLAUDE_MD="$HOME/.claude/CLAUDE.md"
    SKILLS_DIR="$HOME/.claude/skills"
    SKILLS_DIR_TRIED="$SKILLS_DIR"
    AGENTS_DIR_CANDIDATE="$HOME/.claude/agents"
else
    CLAUDE_MD="$1/CLAUDE.md"
    skills_dir_nested="$1/.claude/skills"
    skills_dir_sibling="$1/skills"
    if [ -d "$skills_dir_nested" ]; then
        SKILLS_DIR="$skills_dir_nested"
        AGENTS_DIR_CANDIDATE="$1/.claude/agents"
    elif [ -d "$skills_dir_sibling" ]; then
        SKILLS_DIR="$skills_dir_sibling"
        AGENTS_DIR_CANDIDATE="$1/agents"
    else
        SKILLS_DIR="$skills_dir_nested"
        AGENTS_DIR_CANDIDATE="$1/.claude/agents"
    fi
    SKILLS_DIR_TRIED="$skills_dir_nested, $skills_dir_sibling"
fi

# A missing skills dir must hard-fail here, never fall through to an
# empty manifest.
if [ ! -d "$SKILLS_DIR" ]; then
    echo "ERROR: no skills directory found (tried $SKILLS_DIR_TRIED)" >&2
    exit 1
fi

# Unlike check.sh (where CLAUDE.md is optional), D13 requires CLAUDE.md
# in every shard — a run with no CLAUDE.md can never honor that, so it
# hard-fails here too rather than silently omitting it everywhere.
if [ ! -f "$CLAUDE_MD" ]; then
    echo "ERROR: no CLAUDE.md found ($CLAUDE_MD)" >&2
    exit 1
fi

# A skills dir that exists but has zero skill subdirectories must also
# hard-fail — otherwise it would silently produce a manifest holding
# only the dedicated claude-md shard, which is an empty manifest for
# every purpose that matters (no skill ever gets audited).
skill_dir_count=$(find -L "$SKILLS_DIR" -maxdepth 1 -mindepth 1 -type d | wc -l | tr -d ' ')
if [ "$skill_dir_count" -eq 0 ]; then
    echo "ERROR: no skill directories found under $SKILLS_DIR" >&2
    exit 1
fi

# Fully physicalize a file path, including a symlinked leaf — `cd
# dirname && pwd -P` alone only resolves symlinked *directories* along
# the way, so a real directory holding a symlinked *file* (this repo's
# own ~/.claude/CLAUDE.md: ~/.claude is real, CLAUDE.md inside it is
# the symlink) passes through untouched and yields two spellings of
# one file. No `readlink -f` (GNU-only, absent on BSD/macOS readlink)
# — walk plain `readlink` instead, which both ship.
#
# scripts/check-refs.sh has no counterpart: it only ever
# tests `[ -e "$resolved" ]`, which already follows symlinks
# on its own, so it never needs one canonical spelling of a
# path the way this script's dedup and containment checks do.
physical_file() {
    local target=$1 link
    while [ -L "$target" ]; do
        link="$(readlink "$target")"
        case "$link" in
            /*) target="$link" ;;
            *) target="$(dirname "$target")/$link" ;;
        esac
    done
    printf '%s/%s\n' "$(cd "$(dirname "$target")" && pwd -P)" "$(basename "$target")"
}

# Physicalize every root path up front. SKILLS_DIR may be a symlink
# (e.g. no-arg mode's ~/.claude/skills), and `find -L` reports paths
# under the root as given, not canonicalized — resolving once here
# means every path this script ever prints or compares is spelled the
# same way, so string-equality dedup and containment checks
# (own-dir vs. cross-shard) just work.
SKILLS_DIR="$(cd "$SKILLS_DIR" && pwd -P)"
CLAUDE_MD="$(physical_file "$CLAUDE_MD")"
CLAUDE_ROOT="$(dirname "$SKILLS_DIR")"
if [ -d "$AGENTS_DIR_CANDIDATE" ]; then
    AGENTS_DIR="$(cd "$AGENTS_DIR_CANDIDATE" && pwd -P)"
else
    AGENTS_DIR=""
fi

# Resolve a cross-reference candidate string (already stripped of any
# markdown-link/backtick delimiters) found inside $referencing_file to
# an absolute, physical file path. Prints the resolved path and
# returns 0 on success; returns 1 for anything that isn't a real file
# (prose captured by an over-eager backtick/link match included) —
# that failure is the filter, not an error condition.
#
# scripts/check-refs.sh's check_candidate() takes the
# opposite contract on purpose: it REPORTS an unresolved
# candidate rather than dropping it, so it needs the escape
# hatches this function doesn't.
#
# Those hatches are the absolute-path check, the git-
# revision-shape check, and anchor/heading validation.
#
# This function instead carries extra resolution logic
# those hatches make unnecessary elsewhere: the skills/*
# and CLAUDE.md special-case bases, symlink-walking via
# physical_file(), and the containment check below.
#
# Its resolved path becomes an actual shard read-
# authorization entry, not just a yes/no for reporting, so
# it must land on one canonical, provably in-repo spelling.
resolve_candidate() {
    local referencing_file=$1 candidate=$2 base resolved_dir resolved
    candidate="${candidate%%#*}"
    case "$candidate" in
        *[!A-Za-z0-9_./~-]*|'')
            return 1 ;;
    esac
    case "$candidate" in
        /*)
            base="$candidate" ;;
        '~/'*)
            base="$HOME/${candidate#\~/}" ;;
        skills/*)
            base="$CLAUDE_ROOT/$candidate" ;;
        CLAUDE.md)
            base="$CLAUDE_MD" ;;
        *)
            base="$(dirname "$referencing_file")/$candidate" ;;
    esac
    resolved_dir="$(dirname "$base")"
    [ -d "$resolved_dir" ] || return 1
    resolved_dir="$(cd "$resolved_dir" && pwd -P)"
    base="$resolved_dir/$(basename "$base")"
    [ -f "$base" ] || return 1
    resolved="$(physical_file "$base")"
    # The header's contract is "in-repo" only — a `~/` or
    # `/`-absolute candidate resolves against the real
    # filesystem, not the root argument, so without this
    # check an out-of-repo personal file would land in a
    # shard's authorized read set.
    case "$resolved" in
        "$CLAUDE_ROOT"/*) ;;
        *) return 1 ;;
    esac
    printf '%s\n' "$resolved"
}

# Every file under a skill dir, skipping any node_modules or
# __pycache__ directory — both are gitignored build artifacts, never
# skill content, and walking into node_modules risks exactly the
# multi-minute hang this script's cross-ref scan once hit on a real
# vendored bundle: each file scanned spawns a subprocess per
# candidate span, and a single multi-megabyte minified file yields
# thousands of them.
list_skill_files() {
    find -L "$1" \( \( -name node_modules -o -name __pycache__ \) -type d -prune \) -o -type f -print | LC_ALL=C sort
}

# Every file a skill dispatches by `agent(subAgent=<name>...` or bare
# `subAgent=<name>` text, matched against agents/*.md basenames. A
# trailing non-name character (or end of match) is required so
# `subAgent=refactor` doesn't also match a hypothetical
# `subAgent=refactor-helper`.
list_dispatched_agents() {
    local skill_dir=$1 agent_file name
    [ -n "$AGENTS_DIR" ] || return 0
    while IFS= read -r agent_file; do
        name="$(basename "$agent_file" .md)"
        if grep -RlE --exclude-dir=node_modules --exclude-dir=__pycache__ "subAgent=${name}([^A-Za-z0-9_.:-]|\$)" "$skill_dir" >/dev/null 2>&1; then
            printf '%s\n' "$agent_file"
        fi
    done < <(find -L "$AGENTS_DIR" -maxdepth 1 -type f -name '*.md' | LC_ALL=C sort)
}

# Emit every raw ref-candidate span found in $target_file,
# delimiters stripped: both `](path)` markdown-link targets
# and backtick-quoted spans. Resolving each candidate to a
# real file is the caller's job.
list_file_ref_candidates() {
    local target_file=$1 match candidate
    while IFS= read -r match; do
        [ -n "$match" ] || continue
        candidate="${match#\]\(}"
        candidate="${candidate%)}"
        printf '%s\n' "$candidate"
    done < <(grep -oE '\]\([^)]+\)' "$target_file" 2>/dev/null || true)

    while IFS= read -r match; do
        [ -n "$match" ] || continue
        candidate="${match#\`}"
        candidate="${candidate%\`}"
        printf '%s\n' "$candidate"
    done < <(grep -oE '`[^`]+`' "$target_file" 2>/dev/null || true)
}

# Every in-repo path a skill's own files reference outside their own
# directory — markdown links `](path)` and backtick spans `` `path` ``
# that resolve to a real file. Existence-checked resolution is the
# filter: prose like `` `git status` `` or `subAgent=<name>` never
# resolves to a real file relative to the referencing file, so it's
# dropped without needing a separate extension allowlist.
#
# The skill dir is both what gets scanned and what gets excluded
# from the result: a reference to a sibling inside the same shard
# is not a CROSS-shard reference.
list_cross_refs() {
    local skill_dir=$1 own_dir_physical=$1 f candidate resolved
    while IFS= read -r f; do
        while IFS= read -r candidate; do
            resolved="$(resolve_candidate "$f" "$candidate")" || continue
            case "$resolved" in
                "$own_dir_physical"/*) continue ;;
            esac
            printf '%s\n' "$resolved"
        done < <(list_file_ref_candidates "$f")
    done < <(list_skill_files "$skill_dir")
}

emit_shard() {
    local slug=$1
    shift
    printf '[SHARD] %s\n' "$slug"
    printf '%s\n' "$@" | LC_ALL=C sort -u
    printf '\n'
}

while IFS= read -r skill_dir; do
    slug="$(basename "$skill_dir")"
    own_files_str="$(list_skill_files "$skill_dir")"
    [ -n "$own_files_str" ] || continue

    dispatched_str="$(list_dispatched_agents "$skill_dir")"
    cross_ref_str="$(list_cross_refs "$skill_dir")"

    all_files=()
    while IFS= read -r line; do [ -n "$line" ] && all_files+=("$line"); done <<EOF
$own_files_str
$dispatched_str
$cross_ref_str
EOF
    all_files+=("$CLAUDE_MD")

    emit_shard "$slug" "${all_files[@]}"
done < <(find -L "$SKILLS_DIR" -maxdepth 1 -mindepth 1 -type d | LC_ALL=C sort)

emit_shard "claude-md" "$CLAUDE_MD"
