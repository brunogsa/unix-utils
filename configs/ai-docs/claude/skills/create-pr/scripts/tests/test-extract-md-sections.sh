#!/usr/bin/env bash
# test-extract-md-sections.sh - plain-bash test file for
# extract-md-sections.sh.
#
# Usage:
#   bash test-extract-md-sections.sh
#
# Exits 0 when every assertion passes, non-zero otherwise.
# No bats dependency by design, matching the other scripts in
# this skill's test suite.
#
# Fixtures cover the reshaped doc layout: a human body, then a
# literal H1 "# Appendix" line, then AI-only "## " sections.
#
# A separate fixture covers a plain doc with no Appendix marker
# at all, proving the un-reshaped extract-to-EOF behavior still
# holds.

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$script_dir/extract-md-sections.sh"

work_dir=$(mktemp -d)
trap 'rm -rf "$work_dir"' EXIT

pass_count=0
fail_count=0

# assert_eq - inline assert helper: compares expected vs actual,
# prints ok/not-ok.
assert_eq() {
  local description="$1" expected="$2" actual="$3"
  if [ "$expected" = "$actual" ]; then
    pass_count=$((pass_count + 1))
    printf 'ok - %s\n' "$description"
  else
    fail_count=$((fail_count + 1))
    printf 'not ok - %s\n  expected: %s\n  actual:   %s\n' "$description" "$expected" "$actual"
  fi
}

# assert_contains - inline assert helper: fails unless haystack
# contains needle verbatim.
assert_contains() {
  local description="$1" haystack="$2" needle="$3"
  if [[ "$haystack" == *"$needle"* ]]; then
    pass_count=$((pass_count + 1))
    printf 'ok - %s\n' "$description"
  else
    fail_count=$((fail_count + 1))
    printf 'not ok - %s\n  needle not found: %s\n' "$description" "$needle"
  fi
}

# assert_not_contains - inline assert helper: fails when
# haystack contains needle.
assert_not_contains() {
  local description="$1" haystack="$2" needle="$3"
  if [[ "$haystack" != *"$needle"* ]]; then
    pass_count=$((pass_count + 1))
    printf 'ok - %s\n' "$description"
  else
    fail_count=$((fail_count + 1))
    printf 'not ok - %s\n  unwanted needle found: %s\n' "$description" "$needle"
  fi
}

reshaped_doc="$work_dir/plan_fixture.md"
cat > "$reshaped_doc" <<'EOF'
# plan_fixture

## Open Questions

- none

Here is the closing line of the last human-body section.

# Appendix

## Task Details

- appendix-only content that must never leak into Open Questions

## Technical Decisions

- another appendix-only section
EOF

out=$("$SCRIPT" "$reshaped_doc" "Open Questions")
assert_not_contains \
  "should stop the wanted section at the literal '# Appendix' line, not bleed into appendix content" \
  "$out" "appendix-only content"
assert_not_contains \
  "should never print the literal '# Appendix' boundary line itself" \
  "$out" "# Appendix"
assert_contains \
  "should still keep the wanted section's own body up to the Appendix boundary" \
  "$out" "Here is the closing line"

fenced_doc="$work_dir/plan_fenced.md"
cat > "$fenced_doc" <<'EOF'
# plan_fixture

## General Flow

```bash
# a bash comment, not a markdown heading
echo "still inside the fenced block"
```

More prose after the fence, still in General Flow.

# Appendix

## Task Details

- appendix-only content
EOF

out=$("$SCRIPT" "$fenced_doc" "General Flow")
assert_contains \
  "should not treat a '# comment' line inside a fenced code block as the Appendix boundary" \
  "$out" "# a bash comment, not a markdown heading"
assert_contains \
  "should keep fenced-block content after the bash comment line" \
  "$out" 'echo "still inside the fenced block"'
assert_contains \
  "should keep prose after the fence, still stopping before the real Appendix boundary" \
  "$out" "More prose after the fence"
assert_not_contains \
  "should still stop at the real Appendix boundary once the fence has closed" \
  "$out" "appendix-only content"
assert_not_contains \
  "should never print the literal '# Appendix' boundary line itself, even after a fenced block" \
  "$out" "# Appendix"

fenced_heading_doc="$work_dir/plan_fenced_heading.md"
cat > "$fenced_heading_doc" <<'EOF'
# plan_fixture

## Wanted Section

Body line one.

```markdown
## Not Wanted Section
```

Body line two, still inside Wanted Section.

## Not Wanted Section

Real section content that must never appear.
EOF

out=$("$SCRIPT" "$fenced_heading_doc" "Wanted Section")
assert_contains \
  "should not end the wanted section at a '## ' line that only appears inside a fenced code block" \
  "$out" "Body line two, still inside Wanted Section."
assert_not_contains \
  "should never pull in the real (non-fenced) Not Wanted Section that follows" \
  "$out" "Real section content that must never appear."

no_appendix_doc="$work_dir/plan_no_appendix.md"
cat > "$no_appendix_doc" <<'EOF'
# plan_fixture

## Task Design

- row one
- row two
EOF

out=$("$SCRIPT" "$no_appendix_doc" "Task Design")
assert_contains \
  "should keep extracting to EOF on a doc with no '# Appendix' marker at all" \
  "$out" "row two"

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
