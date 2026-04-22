#!/usr/bin/env bash
# test-extract-commentable-lines - regression test for scripts/extract-commentable-lines.sh
#
# Usage:
#   bash ~/.claude/skills/reviewer-agent/tests/test-extract-commentable-lines.sh
#
# Covers:
#   - simple hunk with + lines -> new-file line numbers
#   - multi-hunk file -> line counter respects hunk headers
#   - "\ No newline at end of file" marker ignored
#   - binary diffs skipped (no +++ b/ line seen)
#   - deleted files (+++ /dev/null) skipped
#   - multiple files in one diff attributed correctly
#   - renames with new path
#
# Exit 0 on pass, 1 on failure.

set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
script="$here/../scripts/extract-commentable-lines.sh"
fixture="$here/fixtures/sample.diff"

expected=$(cat <<'EOF'
src/simple.ts:12
src/simple.ts:13
src/multi-hunk.ts:2
src/multi-hunk.ts:23
README.md:8
src/renamed-new.ts:7
EOF
)

fail() {
  echo "FAIL: $1" >&2
  echo "--- expected ---" >&2
  echo "$expected" >&2
  echo "--- actual ---" >&2
  echo "$actual" >&2
  exit 1
}

# 1) positional arg
actual=$(bash "$script" "$fixture")
[[ "$actual" == "$expected" ]] || fail "positional-arg invocation produced wrong output"

# 2) stdin pipe
actual=$(bash "$script" - < "$fixture")
[[ "$actual" == "$expected" ]] || fail "stdin-pipe invocation produced wrong output"

# 3) --help exits 0 and writes usage to stdout
help_out=$(bash "$script" --help)
[[ "$help_out" == *"extract-commentable-lines"* ]] || fail "--help did not print usage"

echo "PASS: extract-commentable-lines (3 invocations, 7 behaviors covered)"
