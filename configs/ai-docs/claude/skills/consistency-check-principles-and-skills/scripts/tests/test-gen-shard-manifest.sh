#!/usr/bin/env bash
# test-gen-shard-manifest.sh - Tests gen-shard-manifest.sh's shard
# construction: one shard per skill dir, dispatched-agent inclusion,
# cross-reference inclusion, the dedicated claude-md shard, and the
# hard-fail/determinism guarantees.
#
# Usage:
#   bash test-gen-shard-manifest.sh

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GEN="$SCRIPT_DIR/../gen-shard-manifest.sh"

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

assert_status() {
    local label=$1 expected=$2 actual=$3
    assert_eq "$label" "$expected" "$actual"
}

# Build a fixture repo laid out like this repo: <root>/configs/ai-docs/claude
# with CLAUDE.md, skills/, and agents/ siblings — the "sibling" branch of
# check.sh's nested-then-sibling resolution.
new_fixture() {
    local d
    d=$(mktemp -d)
    mkdir -p "$d/configs/ai-docs/claude/skills"
    mkdir -p "$d/configs/ai-docs/claude/agents"
    printf '# Principles\n' > "$d/configs/ai-docs/claude/CLAUDE.md"
    echo "$d"
}

# Physical claude-root for a fixture (mktemp -d can itself sit behind a
# symlink, e.g. macOS's /tmp -> /private/tmp — resolve it the same way
# the script under test must, so path assertions compare like with like).
claude_root() {
    local d=$1
    (cd "$d/configs/ai-docs/claude" && pwd -P)
}

write_skill_file() {
    local dir=$1 skill=$2 relpath=$3
    mkdir -p "$(dirname "$dir/configs/ai-docs/claude/skills/$skill/$relpath")"
    cat > "$dir/configs/ai-docs/claude/skills/$skill/$relpath"
}

write_agent() {
    local dir=$1 name=$2
    cat > "$dir/configs/ai-docs/claude/agents/$name.md"
}

# Run gen-shard-manifest.sh against the fixture's claude-config dir
# (the sibling-branch layout) and echo raw stdout.
run_gen() {
    local d=$1
    bash "$GEN" "$d/configs/ai-docs/claude" 2>/dev/null
}

# Echo the sorted, newline-joined file list under a `[SHARD] <slug>`
# header, up to the next blank line.
shard_files() {
    local output=$1 slug=$2
    printf '%s\n' "$output" | awk -v slug="[SHARD] $slug" '
        $0 == slug { in_shard = 1; next }
        in_shard && /^\[SHARD\] / { in_shard = 0 }
        in_shard && /^$/ { in_shard = 0 }
        in_shard { print }
    '
}

it_should_emit_one_shard_per_skill_directory_including_every_file_in_it() {
    echo "it_should_emit_one_shard_per_skill_directory_including_every_file_in_it"
    local d; d=$(new_fixture)
    local root; root=$(claude_root "$d")
    write_skill_file "$d" "demo-skill" "SKILL.md" <<'EOF'
---
name: demo-skill
description: "Demo."
---
Demo skill body.
EOF
    write_skill_file "$d" "demo-skill" "references/notes.md" <<'EOF'
Notes.
EOF
    local output; output=$(run_gen "$d")
    local expected; expected=$(printf '%s\n%s\n' \
        "$root/skills/demo-skill/SKILL.md" \
        "$root/skills/demo-skill/references/notes.md" | LC_ALL=C sort)
    local actual; actual=$(shard_files "$output" "demo-skill" | grep -v CLAUDE.md | LC_ALL=C sort)
    assert_eq "demo-skill shard has both files" "$expected" "$actual"
    rm -rf "$d"
}

it_should_include_agent_files_a_skill_dispatches_by_name_in_its_shard() {
    echo "it_should_include_agent_files_a_skill_dispatches_by_name_in_its_shard"
    local d; d=$(new_fixture)
    local root; root=$(claude_root "$d")
    write_skill_file "$d" "demo-skill" "SKILL.md" <<'EOF'
---
name: demo-skill
description: "Demo."
---
Dispatch: agent(subAgent=tdd-coder, title=Do it)
EOF
    write_agent "$d" "tdd-coder"
    write_agent "$d" "unrelated-agent"
    local output; output=$(run_gen "$d")
    local actual; actual=$(shard_files "$output" "demo-skill")
    assert_eq "includes dispatched agent" "1" "$(printf '%s\n' "$actual" | grep -c "agents/tdd-coder.md")"
    assert_eq "excludes unrelated agent" "0" "$(printf '%s\n' "$actual" | grep -c "agents/unrelated-agent.md")"
    rm -rf "$d"
}

it_should_include_cross_referenced_paths_outside_the_skill_dir_in_its_shard() {
    echo "it_should_include_cross_referenced_paths_outside_the_skill_dir_in_its_shard"
    local d; d=$(new_fixture)
    local root; root=$(claude_root "$d")
    write_skill_file "$d" "other-skill" "references/shared.md" <<'EOF'
Shared reference content.
EOF
    write_skill_file "$d" "demo-skill" "SKILL.md" <<'EOF'
---
name: demo-skill
description: "Demo."
---
See `skills/other-skill/references/shared.md` for details.
EOF
    local output; output=$(run_gen "$d")
    local actual; actual=$(shard_files "$output" "demo-skill")
    assert_eq "includes cross-referenced file" "1" "$(printf '%s\n' "$actual" | grep -c "other-skill/references/shared.md")"
    rm -rf "$d"
}

# Regression: a skill's own vendored `node_modules/` (e.g. a scripts/
# dependency tree, gitignored and never skill content) must not be
# walked into the shard's own-file list. Before the fix, `find -L`
# descended into it unconditionally — harmless for a tiny fixture, but
# this repo's doc-standards/scripts/node_modules/typescript ships
# multi-megabyte minified bundles that turned this same walk into a
# multi-minute hang ending in SIGBUS (Scout #42).
it_should_exclude_files_under_a_node_modules_directory_from_a_skills_own_file_list() {
    echo "it_should_exclude_files_under_a_node_modules_directory_from_a_skills_own_file_list"
    local d; d=$(new_fixture)
    write_skill_file "$d" "demo-skill" "SKILL.md" <<'EOF'
---
name: demo-skill
description: "Demo."
---
Demo skill body.
EOF
    write_skill_file "$d" "demo-skill" "node_modules/some-dep/index.js" <<'EOF'
module.exports = function noop() {};
EOF
    local output; output=$(run_gen "$d")
    local actual; actual=$(shard_files "$output" "demo-skill" | grep -c "node_modules")
    assert_eq "node_modules file excluded from own-file list" "0" "$actual"
    rm -rf "$d"
}

# Regression: the cross-reference scan must not read files under
# node_modules either — otherwise a vendored file that happens to
# contain a backtick or markdown-link span pulls in whatever it
# resolves to, and (per the Scout #42 hang) the scan itself is the
# expensive part: it forks a subprocess per candidate span, and a
# single real-world vendored bundle can yield thousands of spans.
it_should_not_pull_in_cross_references_found_inside_a_node_modules_directory() {
    echo "it_should_not_pull_in_cross_references_found_inside_a_node_modules_directory"
    local d; d=$(new_fixture)
    write_skill_file "$d" "other-skill" "references/shared.md" <<'EOF'
Shared reference content.
EOF
    write_skill_file "$d" "demo-skill" "SKILL.md" <<'EOF'
---
name: demo-skill
description: "Demo."
---
Demo skill body.
EOF
    write_skill_file "$d" "demo-skill" "node_modules/some-dep/notes.md" <<'EOF'
See `skills/other-skill/references/shared.md` for details.
EOF
    local output; output=$(run_gen "$d")
    local actual; actual=$(shard_files "$output" "demo-skill")
    assert_eq "cross-ref found only inside node_modules is not pulled in" "0" "$(printf '%s\n' "$actual" | grep -c "other-skill/references/shared.md")"
    rm -rf "$d"
}

it_should_emit_a_dedicated_claude_md_only_shard() {
    echo "it_should_emit_a_dedicated_claude_md_only_shard"
    local d; d=$(new_fixture)
    local root; root=$(claude_root "$d")
    write_skill_file "$d" "demo-skill" "SKILL.md" <<'EOF'
---
name: demo-skill
description: "Demo."
---
Demo.
EOF
    local output; output=$(run_gen "$d")
    local actual; actual=$(shard_files "$output" "claude-md")
    assert_eq "claude-md shard has only CLAUDE.md" "$root/CLAUDE.md" "$actual"
    rm -rf "$d"
}

it_should_add_claude_md_to_every_other_shards_file_list() {
    echo "it_should_add_claude_md_to_every_other_shards_file_list"
    local d; d=$(new_fixture)
    local root; root=$(claude_root "$d")
    write_skill_file "$d" "demo-skill" "SKILL.md" <<'EOF'
---
name: demo-skill
description: "Demo."
---
Demo.
EOF
    local output; output=$(run_gen "$d")
    local actual; actual=$(shard_files "$output" "demo-skill" | grep -c "^$root/CLAUDE.md\$")
    assert_eq "demo-skill shard contains CLAUDE.md" "1" "$actual"
    rm -rf "$d"
}

it_should_emit_no_empty_shard() {
    echo "it_should_emit_no_empty_shard"
    local d; d=$(new_fixture)
    write_skill_file "$d" "demo-skill" "SKILL.md" <<'EOF'
---
name: demo-skill
description: "Demo."
---
Demo.
EOF
    local output; output=$(run_gen "$d")
    # No `[SHARD] <slug>` header immediately followed by a blank line
    # (or EOF) with zero file lines between.
    local empty_count
    empty_count=$(printf '%s\n' "$output" | awk '
        /^\[SHARD\] / { if (in_shard && count == 0) bad++; in_shard = 1; count = 0; next }
        in_shard && /^$/ { if (count == 0) bad++; in_shard = 0; next }
        in_shard { count++ }
        END { if (in_shard && count == 0) bad++; print bad + 0 }
    ')
    assert_eq "no shard has zero files" "0" "$empty_count"
    rm -rf "$d"
}

it_should_produce_deterministic_output_on_repeated_runs() {
    echo "it_should_produce_deterministic_output_on_repeated_runs"
    local d; d=$(new_fixture)
    write_skill_file "$d" "demo-skill" "SKILL.md" <<'EOF'
---
name: demo-skill
description: "Demo."
---
Demo.
EOF
    write_skill_file "$d" "another-skill" "SKILL.md" <<'EOF'
---
name: another-skill
description: "Demo."
---
Demo.
EOF
    local run1; run1=$(run_gen "$d")
    local run2; run2=$(run_gen "$d")
    assert_eq "byte-identical across runs" "$run1" "$run2"
    rm -rf "$d"
}

it_should_resolve_a_repo_path_argument_the_same_way_check_sh_does() {
    echo "it_should_resolve_a_repo_path_argument_the_same_way_check_sh_does"
    local d; d=$(mktemp -d)
    # Nested layout: <path>/.claude/skills, with CLAUDE.md at <path>
    # itself — check.sh's CLAUDE_MD is always "$1/CLAUDE.md"
    # regardless of which skills-dir branch resolves, so a real repo
    # keeps project CLAUDE.md at its root while skills live nested
    # under .claude/. Nested skills wins over sibling when both exist.
    mkdir -p "$d/.claude/skills/demo-skill"
    printf '# Principles\n' > "$d/CLAUDE.md"
    cat > "$d/.claude/skills/demo-skill/SKILL.md" <<'EOF'
---
name: demo-skill
description: "Demo."
---
Demo.
EOF
    # Also create a sibling skills/ dir that must be IGNORED, since
    # nested wins when both exist.
    mkdir -p "$d/skills/decoy-skill"
    cat > "$d/skills/decoy-skill/SKILL.md" <<'EOF'
---
name: decoy-skill
description: "Decoy."
---
Demo.
EOF
    local output; output=$(bash "$GEN" "$d" 2>/dev/null)
    assert_eq "uses nested skills dir" "1" "$(printf '%s\n' "$output" | grep -c '\[SHARD\] demo-skill')"
    assert_eq "ignores sibling skills dir" "0" "$(printf '%s\n' "$output" | grep -c '\[SHARD\] decoy-skill')"
    rm -rf "$d"
}

# Regression: a symlinked CLAUDE.md (this repo's own ~/.claude/CLAUDE.md
# layout) must resolve to one physical path everywhere it appears —
# as the shard root AND via a cross-reference — never two spellings
# of the same file in one shard's list.
it_should_collapse_a_symlinked_claude_md_to_one_physical_path() {
    echo "it_should_collapse_a_symlinked_claude_md_to_one_physical_path"
    local d; d=$(mktemp -d)
    mkdir -p "$d/real/configs/claude"
    printf '# Principles\n' > "$d/real/configs/claude/CLAUDE.md"
    mkdir -p "$d/link"
    ln -s "$d/real/configs/claude/CLAUDE.md" "$d/link/CLAUDE.md"
    mkdir -p "$d/link/skills/demo-skill"
    cat > "$d/link/skills/demo-skill/SKILL.md" <<'EOF'
---
name: demo-skill
description: "Demo."
---
See `CLAUDE.md` for the governing principles.
EOF
    local output; output=$(bash "$GEN" "$d/link" 2>/dev/null)
    local physical="$d/real/configs/claude/CLAUDE.md"
    local occurrences
    occurrences=$(shard_files "$output" "demo-skill" | grep -c -F "$physical")
    assert_eq "physical CLAUDE.md appears exactly once in demo-skill shard" "1" "$occurrences"
    local symlink_spelling
    symlink_spelling=$(printf '%s\n' "$output" | grep -c -F "$d/link/CLAUDE.md")
    assert_eq "symlink spelling never appears" "0" "$symlink_spelling"
    rm -rf "$d"
}

it_should_exclude_a_tilde_prefixed_reference_to_a_file_outside_the_repo_root() {
    echo "it_should_exclude_a_tilde_prefixed_reference_to_a_file_outside_the_repo_root"
    local d; d=$(new_fixture)
    local outside; outside=$(mktemp -d)
    printf 'Personal notes.\n' > "$outside/notes.md"
    write_skill_file "$d" "demo-skill" "SKILL.md" <<'EOF'
---
name: demo-skill
description: "Demo."
---
See `~/notes.md` for details.
EOF
    local output; output=$(HOME="$outside" bash "$GEN" "$d/configs/ai-docs/claude" 2>/dev/null)
    local actual; actual=$(shard_files "$output" "demo-skill" | grep -c "notes.md")
    assert_eq "tilde reference outside repo root is excluded" "0" "$actual"
    rm -rf "$d" "$outside"
}

it_should_exclude_an_absolute_path_reference_to_a_file_outside_the_repo_root() {
    echo "it_should_exclude_an_absolute_path_reference_to_a_file_outside_the_repo_root"
    local d; d=$(new_fixture)
    local outside; outside=$(mktemp -d)
    printf 'Personal notes.\n' > "$outside/notes.md"
    write_skill_file "$d" "demo-skill" "SKILL.md" <<EOF
---
name: demo-skill
description: "Demo."
---
See \`$outside/notes.md\` for details.
EOF
    local output; output=$(run_gen "$d")
    local actual; actual=$(shard_files "$output" "demo-skill" | grep -c "notes.md")
    assert_eq "absolute-path reference outside repo root is excluded" "0" "$actual"
    rm -rf "$d" "$outside"
}

it_should_hard_fail_when_the_skills_directory_is_missing() {
    echo "it_should_hard_fail_when_the_skills_directory_is_missing"
    local d; d=$(mktemp -d)
    printf '# Principles\n' > "$d/CLAUDE.md"
    bash "$GEN" "$d" >/dev/null 2>/tmp/gen-shard-manifest-stderr.txt
    local status=$?
    assert_status "exits non-zero" "1" "$status"
    assert_eq "prints an error to stderr" "1" "$([ -s /tmp/gen-shard-manifest-stderr.txt ] && echo 1 || echo 0)"
    rm -rf "$d"
}

it_should_emit_one_shard_per_skill_directory_including_every_file_in_it
it_should_include_agent_files_a_skill_dispatches_by_name_in_its_shard
it_should_include_cross_referenced_paths_outside_the_skill_dir_in_its_shard
it_should_exclude_files_under_a_node_modules_directory_from_a_skills_own_file_list
it_should_not_pull_in_cross_references_found_inside_a_node_modules_directory
it_should_emit_a_dedicated_claude_md_only_shard
it_should_add_claude_md_to_every_other_shards_file_list
it_should_emit_no_empty_shard
it_should_produce_deterministic_output_on_repeated_runs
it_should_resolve_a_repo_path_argument_the_same_way_check_sh_does
it_should_collapse_a_symlinked_claude_md_to_one_physical_path
it_should_exclude_a_tilde_prefixed_reference_to_a_file_outside_the_repo_root
it_should_exclude_an_absolute_path_reference_to_a_file_outside_the_repo_root
it_should_hard_fail_when_the_skills_directory_is_missing

echo
echo "$passed passed, $failed failed"
[ "$failed" -eq 0 ]
