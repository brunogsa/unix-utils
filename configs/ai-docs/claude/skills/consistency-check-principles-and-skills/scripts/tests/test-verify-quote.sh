#!/usr/bin/env bash
# test-verify-quote.sh - Tests verify-quote.sh's literal, contiguous,
# trailing-whitespace-normalized quote matching (D5, A4), and its
# hard-fail behavior on a missing target file.
#
# Usage:
#   bash test-verify-quote.sh

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERIFY="$SCRIPT_DIR/../verify-quote.sh"
STDERR_FILE="/tmp/verify-quote-test-stderr.txt"

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

write_file() {
    local path=$1
    cat > "$path"
}

it_should_pass_a_single_line_quote_present_verbatim() {
    echo "verify-quote.sh > happy > should pass a single line quote present verbatim"
    local d; d=$(mktemp -d)
    local f="$d/notes.md"
    write_file "$f" <<'EOF'
First line of the file.
The exact line we will quote back.
Last line of the file.
EOF
    printf '%s' "The exact line we will quote back." | bash "$VERIFY" "$f" >/dev/null 2>"$STDERR_FILE"
    local status=$?
    assert_status "exits 0" "0" "$status"
    rm -rf "$d"
}

it_should_pass_a_quote_that_is_a_fragment_of_a_longer_line() {
    echo "verify-quote.sh > happy > should pass a quote that is a fragment of a longer line"
    local d; d=$(mktemp -d)
    local f="$d/notes.md"
    # doc-standards mandates one prose paragraph per physical line, so
    # real files are made of long single-line bullets — an auditor
    # quoting "the exact text" will usually hand back a fragment of
    # such a line, not the whole line. grep -F semantics (the AC's own
    # words) match a fixed string anywhere inside a line, not only a
    # full-line match, so this must pass.
    write_file "$f" <<'EOF'
Intro line.
- [Instruction] Prefer CLI scripts + skills over MCP servers — use MCP only for capabilities CLI + skills can't provide.
Outro line.
EOF
    printf '%s' "Prefer CLI scripts + skills over MCP servers" | bash "$VERIFY" "$f" >/dev/null 2>"$STDERR_FILE"
    local status=$?
    assert_status "exits 0 for a substring fragment of a longer line" "0" "$status"
    rm -rf "$d"
}

it_should_pass_a_multi_line_quote_present_as_a_contiguous_block() {
    echo "verify-quote.sh > happy > should pass a multi line quote present as a contiguous block"
    local d; d=$(mktemp -d)
    local f="$d/notes.md"
    write_file "$f" <<'EOF'
Intro line.
Block line one.
Block line two.
Block line three.
Outro line.
EOF
    printf '%s\n%s\n%s' "Block line one." "Block line two." "Block line three." \
        | bash "$VERIFY" "$f" >/dev/null 2>"$STDERR_FILE"
    local status=$?
    assert_status "exits 0" "0" "$status"
    rm -rf "$d"
}

it_should_normalize_trailing_whitespace_before_comparing() {
    echo "verify-quote.sh > corner > should normalize trailing whitespace before comparing"
    local d; d=$(mktemp -d)
    local f="$d/notes.md"
    printf 'Intro line.\nLine with trailing spaces.   \nOutro line.\n' > "$f"
    printf 'Line with trailing spaces.' | bash "$VERIFY" "$f" >/dev/null 2>"$STDERR_FILE"
    local status=$?
    assert_status "exits 0 despite differing trailing whitespace" "0" "$status"
    rm -rf "$d"
}

it_should_treat_the_quote_as_a_literal_substring_not_a_regex() {
    echo "verify-quote.sh > corner > should treat the quote as a literal substring not a regex"
    local d; d=$(mktemp -d)
    local f="$d/notes.md"
    # a.c[x]* as an ERE means "a, any char, c, zero-or-more x" and
    # would wrongly match the decoy "aYc" below if the matcher ran it
    # as a pattern instead of a literal string.
    write_file "$f" <<'EOF'
Intro line.
This looks like it could match a regex: aYc
Outro line.
EOF
    printf 'a.c[x]*' | bash "$VERIFY" "$f" >/dev/null 2>"$STDERR_FILE"
    local status=$?
    assert_status "fails since a.c[x]* is absent literally (a regex would wrongly match aYc)" "1" "$status"
    rm -rf "$d"
}

it_should_fail_a_quote_absent_from_the_file() {
    echo "verify-quote.sh > failure > should fail a quote absent from the file"
    local d; d=$(mktemp -d)
    local f="$d/notes.md"
    write_file "$f" <<'EOF'
First line of the file.
Second line of the file.
EOF
    printf 'This text does not exist anywhere in the file.' | bash "$VERIFY" "$f" >/dev/null 2>"$STDERR_FILE"
    local status=$?
    assert_status "exits 1" "1" "$status"
    assert_eq "prints a diagnostic to stderr" "1" "$([ -s "$STDERR_FILE" ] && echo 1 || echo 0)"
    rm -rf "$d"
}

it_should_fail_a_quote_whose_lines_appear_but_not_contiguously() {
    echo "verify-quote.sh > failure > should fail a quote whose lines appear but not contiguously"
    local d; d=$(mktemp -d)
    local f="$d/notes.md"
    write_file "$f" <<'EOF'
Block line one.
Unrelated line in between.
Block line two.
EOF
    printf '%s\n%s' "Block line one." "Block line two." | bash "$VERIFY" "$f" >/dev/null 2>"$STDERR_FILE"
    local status=$?
    assert_status "exits 1 for lines separated by an unrelated line" "1" "$status"

    # AC #6's other named sub-case: the same two lines present but
    # reordered (no interleaving line at all) must fail too.
    printf '%s\n%s' "Block line two." "Block line one." | bash "$VERIFY" "$f" >/dev/null 2>"$STDERR_FILE"
    status=$?
    assert_status "exits 1 for lines present but reordered" "1" "$status"
    rm -rf "$d"
}

it_should_fail_loud_when_the_target_file_does_not_exist() {
    echo "verify-quote.sh > failure > should fail loud when the target file does not exist"
    local d; d=$(mktemp -d)
    local f="$d/does-not-exist.md"
    printf 'anything' | bash "$VERIFY" "$f" >/dev/null 2>"$STDERR_FILE"
    local status=$?
    assert_status "exits nonzero" "1" "$status"
    assert_eq "prints a clear diagnostic to stderr" "1" "$([ -s "$STDERR_FILE" ] && echo 1 || echo 0)"
    rm -rf "$d"
}

it_should_pass_a_single_line_quote_present_verbatim
it_should_pass_a_quote_that_is_a_fragment_of_a_longer_line
it_should_pass_a_multi_line_quote_present_as_a_contiguous_block
it_should_normalize_trailing_whitespace_before_comparing
it_should_treat_the_quote_as_a_literal_substring_not_a_regex
it_should_fail_a_quote_absent_from_the_file
it_should_fail_a_quote_whose_lines_appear_but_not_contiguously
it_should_fail_loud_when_the_target_file_does_not_exist

echo
echo "$passed passed, $failed failed"
[ "$failed" -eq 0 ]
