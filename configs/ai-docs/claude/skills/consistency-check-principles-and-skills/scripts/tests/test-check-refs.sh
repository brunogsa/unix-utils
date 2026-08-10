#!/usr/bin/env bash
# test-check-refs.sh - Tests check-refs.sh's ref resolution: markdown
# links and backtick paths, file-existence checking, GitHub-style
# anchor-heading matching, relative-path resolution, and the
# report-every-broken-ref guarantee.
#
# Usage:
#   bash test-check-refs.sh

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHECK="$SCRIPT_DIR/../check-refs.sh"

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

new_fixture() {
    mktemp -d
}

it_should_pass_a_markdown_link_ref_that_resolves() {
    echo "it_should_pass_a_markdown_link_ref_that_resolves"
    local d; d=$(new_fixture)
    printf '# Target\nBody.\n' > "$d/target.md"
    printf 'See [target](target.md) for details.\n' > "$d/source.md"
    local status; bash "$CHECK" "$d/source.md" >/tmp/check-refs-out.txt 2>&1; status=$?
    assert_status "exits 0" "0" "$status"
    assert_eq "no broken refs reported" "" "$(cat /tmp/check-refs-out.txt)"
    rm -rf "$d"
}

it_should_pass_a_backtick_path_ref_that_resolves() {
    echo "it_should_pass_a_backtick_path_ref_that_resolves"
    local d; d=$(new_fixture)
    mkdir -p "$d/references"
    printf '# Foo\nBody.\n' > "$d/references/foo.md"
    printf 'See `references/foo.md` for details.\n' > "$d/source.md"
    local status; bash "$CHECK" "$d/source.md" >/tmp/check-refs-out.txt 2>&1; status=$?
    assert_status "exits 0" "0" "$status"
    assert_eq "no broken refs reported" "" "$(cat /tmp/check-refs-out.txt)"
    rm -rf "$d"
}

it_should_pass_a_ref_whose_anchor_heading_exists_in_the_target() {
    echo "it_should_pass_a_ref_whose_anchor_heading_exists_in_the_target"
    local d; d=$(new_fixture)
    printf '# Target\n## Some Heading\nBody.\n' > "$d/target.md"
    printf 'See [target](target.md#some-heading) for details.\n' > "$d/source.md"
    local status; bash "$CHECK" "$d/source.md" >/tmp/check-refs-out.txt 2>&1; status=$?
    assert_status "exits 0" "0" "$status"
    assert_eq "no broken refs reported" "" "$(cat /tmp/check-refs-out.txt)"
    rm -rf "$d"
}

it_should_resolve_a_relative_parent_directory_path() {
    echo "it_should_resolve_a_relative_parent_directory_path"
    local d; d=$(new_fixture)
    mkdir -p "$d/skill-a" "$d/skill-b"
    printf '# Shared\nBody.\n' > "$d/skill-b/shared.md"
    printf 'See [shared](../skill-b/shared.md) for details.\n' > "$d/skill-a/source.md"
    local status; bash "$CHECK" "$d/skill-a/source.md" >/tmp/check-refs-out.txt 2>&1; status=$?
    assert_status "exits 0" "0" "$status"
    assert_eq "no broken refs reported" "" "$(cat /tmp/check-refs-out.txt)"
    rm -rf "$d"
}

it_should_report_every_broken_ref_in_a_file_with_more_than_one() {
    echo "it_should_report_every_broken_ref_in_a_file_with_more_than_one"
    local d; d=$(new_fixture)
    printf 'See [one](missing-one.md).\nSee [two](missing-two.md).\n' > "$d/source.md"
    local status; bash "$CHECK" "$d/source.md" >/tmp/check-refs-out.txt 2>&1; status=$?
    assert_status "exits 1" "1" "$status"
    assert_eq "both broken refs listed" "2" "$(grep -c ' -> ' /tmp/check-refs-out.txt)"
    assert_eq "first broken ref cites its line" "1" "$(grep -c '^'"$d"'/source.md:1 -> missing-one.md$' /tmp/check-refs-out.txt)"
    assert_eq "second broken ref cites its line" "1" "$(grep -c '^'"$d"'/source.md:2 -> missing-two.md$' /tmp/check-refs-out.txt)"
    rm -rf "$d"
}

it_should_fail_a_ref_to_a_nonexistent_file() {
    echo "it_should_fail_a_ref_to_a_nonexistent_file"
    local d; d=$(new_fixture)
    printf 'See [ghost](does-not-exist.md) for details.\n' > "$d/source.md"
    local status; bash "$CHECK" "$d/source.md" >/tmp/check-refs-out.txt 2>&1; status=$?
    assert_status "exits 1" "1" "$status"
    assert_eq "broken ref listed" "1" "$(grep -c 'does-not-exist.md' /tmp/check-refs-out.txt)"
    rm -rf "$d"
}

it_should_not_flag_a_trailing_slash_directory_mention_as_a_broken_ref() {
    echo "it_should_not_flag_a_trailing_slash_directory_mention_as_a_broken_ref"
    local d; d=$(new_fixture)
    mkdir -p "$d/scripts"
    printf 'See the shared `scripts/` entry for details.\n' > "$d/source.md"
    local status; bash "$CHECK" "$d/source.md" >/tmp/check-refs-out.txt 2>&1; status=$?
    assert_status "exits 0" "0" "$status"
    assert_eq "no broken refs reported" "" "$(cat /tmp/check-refs-out.txt)"
    rm -rf "$d"
}

it_should_fail_a_ref_whose_anchor_heading_does_not_exist_in_an_existing_target() {
    echo "it_should_fail_a_ref_whose_anchor_heading_does_not_exist_in_an_existing_target"
    local d; d=$(new_fixture)
    printf '# Target\n## Some Heading\nBody.\n' > "$d/target.md"
    printf 'See [target](target.md#missing-heading) for details.\n' > "$d/source.md"
    local status; bash "$CHECK" "$d/source.md" >/tmp/check-refs-out.txt 2>&1; status=$?
    assert_status "exits 1" "1" "$status"
    assert_eq "broken ref listed" "1" "$(grep -c 'target.md#missing-heading' /tmp/check-refs-out.txt)"
    rm -rf "$d"
}

it_should_pass_a_ref_whose_anchor_matches_an_em_dash_heading_github_style() {
    echo "it_should_pass_a_ref_whose_anchor_matches_an_em_dash_heading_github_style"
    local d; d=$(new_fixture)
    printf '# Target\n## Counting conventions — markers for deterministic measurement\nBody.\n' > "$d/target.md"
    printf 'See [target](target.md#counting-conventions--markers-for-deterministic-measurement) for details.\n' > "$d/source.md"
    local status; bash "$CHECK" "$d/source.md" >/tmp/check-refs-out.txt 2>&1; status=$?
    assert_status "exits 0" "0" "$status"
    assert_eq "no broken refs reported" "" "$(cat /tmp/check-refs-out.txt)"
    rm -rf "$d"
}

it_should_pass_a_ref_whose_anchor_matches_the_second_occurrence_of_a_duplicate_heading() {
    echo "it_should_pass_a_ref_whose_anchor_matches_the_second_occurrence_of_a_duplicate_heading"
    local d; d=$(new_fixture)
    printf '# Target\n## Dupe\nBody one.\n## Dupe\nBody two.\n' > "$d/target.md"
    printf 'See [target](target.md#dupe-1) for details.\n' > "$d/source.md"
    local status; bash "$CHECK" "$d/source.md" >/tmp/check-refs-out.txt 2>&1; status=$?
    assert_status "exits 0" "0" "$status"
    assert_eq "no broken refs reported" "" "$(cat /tmp/check-refs-out.txt)"
    rm -rf "$d"
}

it_should_not_flag_a_slash_command_mention_as_a_broken_ref() {
    echo "it_should_not_flag_a_slash_command_mention_as_a_broken_ref"
    local d; d=$(new_fixture)
    printf 'Run `/implement` to start the batch.\n' > "$d/source.md"
    local status; bash "$CHECK" "$d/source.md" >/tmp/check-refs-out.txt 2>&1; status=$?
    assert_status "exits 0" "0" "$status"
    assert_eq "no broken refs reported" "" "$(cat /tmp/check-refs-out.txt)"
    rm -rf "$d"
}

it_should_pass_a_ref_to_an_existing_directory_without_a_trailing_slash() {
    echo "it_should_pass_a_ref_to_an_existing_directory_without_a_trailing_slash"
    local d; d=$(new_fixture)
    mkdir -p "$d/references"
    printf 'See [references](references) for details.\n' > "$d/source.md"
    local status; bash "$CHECK" "$d/source.md" >/tmp/check-refs-out.txt 2>&1; status=$?
    assert_status "exits 0" "0" "$status"
    assert_eq "no broken refs reported" "" "$(cat /tmp/check-refs-out.txt)"
    rm -rf "$d"
}

it_should_not_flag_a_broken_looking_link_shown_as_an_example_inside_a_fenced_code_block() {
    echo "it_should_not_flag_a_broken_looking_link_shown_as_an_example_inside_a_fenced_code_block"
    local d; d=$(new_fixture)
    printf '%s\n' \
        'Example usage:' \
        '```markdown' \
        'See [target](does-not-exist.md) for details.' \
        '```' \
        'End of example.' \
        > "$d/source.md"
    local status; bash "$CHECK" "$d/source.md" >/tmp/check-refs-out.txt 2>&1; status=$?
    assert_status "exits 0" "0" "$status"
    assert_eq "no broken refs reported" "" "$(cat /tmp/check-refs-out.txt)"
    rm -rf "$d"
}

it_should_fail_a_ref_whose_anchor_matches_only_a_heading_line_inside_a_fenced_code_block() {
    echo "it_should_fail_a_ref_whose_anchor_matches_only_a_heading_line_inside_a_fenced_code_block"
    local d; d=$(new_fixture)
    printf '%s\n' \
        '# Target' \
        'Real content.' \
        '```bash' \
        '# Usage: some comment' \
        '```' \
        'More body.' \
        > "$d/target.md"
    printf 'See [target](target.md#usage-some-comment) for details.\n' > "$d/source.md"
    local status; bash "$CHECK" "$d/source.md" >/tmp/check-refs-out.txt 2>&1; status=$?
    assert_status "exits 1" "1" "$status"
    assert_eq "broken ref listed" "1" "$(grep -c 'target.md#usage-some-comment' /tmp/check-refs-out.txt)"
    rm -rf "$d"
}

it_should_pass_a_markdown_link_ref_that_resolves
it_should_pass_a_backtick_path_ref_that_resolves
it_should_pass_a_ref_whose_anchor_heading_exists_in_the_target
it_should_resolve_a_relative_parent_directory_path
it_should_report_every_broken_ref_in_a_file_with_more_than_one
it_should_not_flag_a_trailing_slash_directory_mention_as_a_broken_ref
it_should_fail_a_ref_to_a_nonexistent_file
it_should_fail_a_ref_whose_anchor_heading_does_not_exist_in_an_existing_target
it_should_pass_a_ref_whose_anchor_matches_an_em_dash_heading_github_style
it_should_pass_a_ref_whose_anchor_matches_the_second_occurrence_of_a_duplicate_heading
it_should_not_flag_a_slash_command_mention_as_a_broken_ref
it_should_pass_a_ref_to_an_existing_directory_without_a_trailing_slash
it_should_not_flag_a_broken_looking_link_shown_as_an_example_inside_a_fenced_code_block
it_should_fail_a_ref_whose_anchor_matches_only_a_heading_line_inside_a_fenced_code_block

echo
echo "$passed passed, $failed failed"
[ "$failed" -eq 0 ]
