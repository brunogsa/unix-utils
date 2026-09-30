#!/usr/bin/env bash
# test-check-density-scan.sh - Tests how check.sh's density
# section reacts to each exit code of check-density.sh:
# 0 clean, 1 violations, 2 scan could not complete.
#
# Usage:
#   bash test-check-density-scan.sh
#
# A stub check-density.sh stands in for the real one.
#
# That lets each of its exit codes be forced.
#
# Bash, not pytest, because lib-fake-home.sh is bash.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHECK="$SCRIPT_DIR/../check.sh"

source "$SCRIPT_DIR/lib-fake-home.sh"

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

assert_contains() {
    local label=$1 needle=$2 haystack=$3
    if printf '%s\n' "$haystack" | grep -q -F -e "$needle"; then
        passed=$((passed + 1))
        echo "  ✓ $label"
    else
        failed=$((failed + 1))
        echo "  ✗ $label"
        echo "      missing: [$needle]"
    fi
}

assert_not_contains() {
    local label=$1 needle=$2 haystack=$3
    if printf '%s\n' "$haystack" | grep -q -F -e "$needle"; then
        failed=$((failed + 1))
        echo "  ✗ $label"
        echo "      unexpected: [$needle]"
    else
        passed=$((passed + 1))
        echo "  ✓ $label"
    fi
}

# Replace the fake HOME's symlinked doc-standards with a real
# dir holding only a stub check-density.sh; $1 is the stub
# body, run under bash.
install_density_stub() {
    rm -rf "$FAKE_HOME/.claude/skills/doc-standards"
    mkdir -p "$FAKE_HOME/.claude/skills/doc-standards/scripts"
    printf '#!/usr/bin/env bash\n%s\n' "$1" \
        > "$FAKE_HOME/.claude/skills/doc-standards/scripts/check-density.sh"
    chmod +x "$FAKE_HOME/.claude/skills/doc-standards/scripts/check-density.sh"
}

# Fixture with a CLAUDE.md so the density section has a target.
new_fixture() {
    local d
    d=$(mktemp -d)
    mkdir -p "$d/skills"
    printf '# Principles\n' > "$d/CLAUDE.md"
    echo "$d"
}

# Run check.sh on the fixture; stdout to $OUT_FILE, stderr
# dropped, exit code echoed.
run_check() {
    local dir=$1
    HOME="$FAKE_HOME" bash "$CHECK" "$dir" > "$OUT_FILE" 2>/dev/null
    echo $?
}

OUT_FILE=$(mktemp)

it_should_fail_the_density_section_when_the_scan_cannot_complete() {
    echo "it_should_fail_the_density_section_when_the_scan_cannot_complete"
    local d; d=$(new_fixture)
    # Prints one violation before dying, like a scan that hits
    # an unreadable file partway through.
    install_density_stub 'printf "== a.md\n3:300:40\n"; echo "check-density.sh: cannot read b.md" >&2; exit 2'
    run_check "$d" > /dev/null
    local out; out=$(cat "$OUT_FILE")
    assert_contains "prints a FAIL line carrying the scan's error" \
        "FAIL density scan could not complete: check-density.sh: cannot read b.md" "$out"
    assert_not_contains "does not report all budgets met" "All budgets met" "$out"
    rm -rf "$d"
}

it_should_fail_the_density_section_even_when_the_partial_scan_found_nothing() {
    echo "it_should_fail_the_density_section_even_when_the_partial_scan_found_nothing"
    local d; d=$(new_fixture)
    install_density_stub 'echo "check-density.sh: not valid UTF-8: b.md" >&2; exit 2'
    run_check "$d" > /dev/null
    local out; out=$(cat "$OUT_FILE")
    assert_contains "prints a FAIL line carrying the scan's error" \
        "FAIL density scan could not complete: check-density.sh: not valid UTF-8: b.md" "$out"
    assert_not_contains "does not report zero violations as OK" "Total violations: 0 (OK)" "$out"
    rm -rf "$d"
}

it_should_report_the_violation_count_as_over_when_the_scan_finds_violations() {
    echo "it_should_report_the_violation_count_as_over_when_the_scan_finds_violations"
    local d; d=$(new_fixture)
    install_density_stub 'printf "== a.md\n3:300:40\n9:280:35\n"; exit 1'
    run_check "$d" > /dev/null
    local out; out=$(cat "$OUT_FILE")
    assert_contains "counts both violations as OVER" "Total violations: 2 (OVER)" "$out"
    assert_contains "lists the per-file count" "- a.md: 2" "$out"
    assert_not_contains "no scan-failure line" "density scan could not complete" "$out"
    rm -rf "$d"
}

it_should_fail_the_density_section_when_the_scan_cannot_complete
it_should_fail_the_density_section_even_when_the_partial_scan_found_nothing
it_should_report_the_violation_count_as_over_when_the_scan_finds_violations

rm -f "$OUT_FILE"

echo
echo "$passed passed, $failed failed"
[ "$failed" -eq 0 ]
