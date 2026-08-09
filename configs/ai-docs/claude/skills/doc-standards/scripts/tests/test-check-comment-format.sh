#!/usr/bin/env bash
# test-check-comment-format.sh - plain-bash test file for
# check-comment-format.js, covering its --fix repair passes.
#
# Usage:
#   bash test-check-comment-format.sh
#
# Exits 0 when every assertion passes, non-zero otherwise.
# No bats dependency by design, matching this skill area's other
# suites (test-fix-density.sh, test-check-bullet-gap-fix.sh).

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$script_dir/check-comment-format.js"

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
    printf 'not ok - %s\n  expected: %s\n  actual:   %s\n' \
      "$description" "$expected" "$actual"
  fi
}

# assert_contains - passes when the haystack carries the literal
# row.
assert_contains() {
  local description="$1" haystack="$2" needle="$3"
  if printf '%s\n' "$haystack" | grep -qF -- "$needle"; then
    pass_count=$((pass_count + 1))
    printf 'ok - %s\n' "$description"
  else
    fail_count=$((fail_count + 1))
    printf 'not ok - %s\n  missing: %s\n  actual:\n%s\n' \
      "$description" "$needle" "$haystack"
  fi
}

# assert_absent - passes when the haystack carries no such row.
assert_absent() {
  local description="$1" haystack="$2" needle="$3"
  if printf '%s\n' "$haystack" | grep -qF -- "$needle"; then
    fail_count=$((fail_count + 1))
    printf 'not ok - %s\n  unexpected: %s\n' "$description" "$needle"
  else
    pass_count=$((pass_count + 1))
    printf 'ok - %s\n' "$description"
  fi
}

# new_fixture - points FIXTURE at a fresh path under work_dir.
#
# Write the fixture with a heredoc straight into the file,
# never through a `"$(cat <<EOF ...)"` command substitution.
# Bash mis-tracks quote state across a heredoc nested in a
# command substitution once the body holds an apostrophe.
new_fixture() {
  FIXTURE="$work_dir/$1"
}

# comment_words - the word stream of every standalone comment
# line, one token per line.
#
# --fix only ever re-packs comment prose, so this stream must
# survive a repair byte-identical.
# A dropped or duplicated word is invisible to a syntax check
# but not to this.
comment_words() {
  python3 - "$1" <<'PY'
import re
import sys

PREFIX = re.compile(r'^(\*/|/\*\*|/\*|\*|//|#)\s?')
for line in open(sys.argv[1], encoding='utf-8'):
    stripped = line.strip()
    if not PREFIX.match(stripped):
        continue
    for word in PREFIX.sub('', stripped).split():
        print(word)
PY
}

# snapshot_fixture - keeps a pristine copy of FIXTURE at
# BASELINE, so a repair can be diffed against the file it was
# measured on.
snapshot_fixture() {
  BASELINE="$FIXTURE.baseline"
  cp "$FIXTURE" "$BASELINE"
}

# run_fix - invokes --fix on FIXTURE, capturing the exit code
# into FIX_EXIT and stdout+stderr into FIX_OUT.
run_fix() {
  node "$SCRIPT" --fix "$FIXTURE" >"$work_dir/fix-stdout.txt" 2>&1
  FIX_EXIT=$?
  FIX_OUT=$(cat "$work_dir/fix-stdout.txt")
}

# run_check - re-verifies FIXTURE in report-only mode, so a
# passing repair is confirmed by the same invocation a caller
# would run, not by --fix's own opinion of itself.
run_check() {
  node "$SCRIPT" "$FIXTURE" >"$work_dir/check-stdout.txt" 2>&1
  CHECK_EXIT=$?
  CHECK_OUT=$(cat "$work_dir/check-stdout.txt")
}

# ==============================================================
# Python: the re-flow, word preservation, syntax, idempotence
# ==============================================================

new_fixture reflow.py
cat >"$FIXTURE" <<'EOF'
#!/usr/bin/env python3
# The aggregator collapses the many records one response emits into a single billed unit.
# The message id alone is not enough, because a synthetic record reuses it and the request id is absent on replayed records.
VALUE = 1
EOF
snapshot_fixture
run_fix
assert_eq "should exit 0 once every python violation is repaired" "0" "$FIX_EXIT"
assert_eq "should preserve every comment word through a python re-flow" \
  "$(comment_words "$BASELINE")" "$(comment_words "$FIXTURE")"
python3 -c "import ast,sys; ast.parse(open(sys.argv[1]).read())" "$FIXTURE" 2>/dev/null
assert_eq "should leave the repaired python file parseable" "0" "$?"
assert_eq "should hold every repaired python line inside the width cap" "" \
  "$(awk 'length > 64' "$FIXTURE")"

cp "$FIXTURE" "$work_dir/reflow-once.py"
run_fix
assert_eq "should make a second python --fix a byte-level no-op" "" \
  "$(diff "$work_dir/reflow-once.py" "$FIXTURE")"

# ==============================================================
# Shell and TypeScript: the same invariants per language
# ==============================================================

new_fixture reflow.sh
cat >"$FIXTURE" <<'EOF'
#!/usr/bin/env bash
# Run the Stop hooks in series so the notification fires exactly once, on the real stop.
# Claude Code runs every hook on one event in parallel with no short-circuit, so a blocked gate still lets a sibling fire.
value=1
EOF
snapshot_fixture
run_fix
assert_eq "should exit 0 once every shell violation is repaired" "0" "$FIX_EXIT"
assert_eq "should preserve every comment word through a shell re-flow" \
  "$(comment_words "$BASELINE")" "$(comment_words "$FIXTURE")"
bash -n "$FIXTURE" 2>/dev/null
assert_eq "should leave the repaired shell file syntactically valid" "0" "$?"

new_fixture reflow.ts
cat >"$FIXTURE" <<'EOF'
/**
 * Resolves the billing identity of a response so the aggregator can collapse the many records it emits into one billed unit.
 */
export const KEY = 'requestId';

// Prefer the request id, because it is the field the billing side keys on and it stays stable across iterations.
export const FALLBACK = 'id';
EOF
snapshot_fixture
run_fix
assert_eq "should exit 0 once every typescript violation is repaired" "0" "$FIX_EXIT"
assert_eq "should preserve every comment word through a jsdoc re-flow" \
  "$(comment_words "$BASELINE")" "$(comment_words "$FIXTURE")"
assert_contains "should leave the jsdoc opening delimiter intact" \
  "$(cat "$FIXTURE")" "/**"
assert_contains "should leave the jsdoc closing delimiter intact" \
  "$(cat "$FIXTURE")" " */"

# ==============================================================
# What --fix must refuse: set-off literals and unsplittable
# tokens
# ==============================================================

new_fixture literals.py
cat >"$FIXTURE" <<'EOF'
#!/usr/bin/env python3
# Usage:
#   probe.py --since <DAY> --until <DAY> --format json|table|csv --verbose
#
# See https://docs.langchain.com/oss/python/deepagents/context-engineering-patterns
VALUE = 1
EOF
snapshot_fixture
run_fix
assert_contains "should leave an aligned usage line byte-identical" \
  "$(cat "$FIXTURE")" \
  "#   probe.py --since <DAY> --until <DAY> --format json|table|csv --verbose"
assert_contains "should leave an over-cap single token unwrapped" \
  "$(cat "$FIXTURE")" \
  "https://docs.langchain.com/oss/python/deepagents/context-engineering-patterns"
assert_eq "should exit 1 when --fix leaves residue behind" "1" "$FIX_EXIT"
assert_contains "should name WIDTH on each residue row --fix refused" \
  "$FIX_OUT" "WIDTH"
run_check
assert_eq "should still report the literals it refused to re-wrap" "1" "$CHECK_EXIT"

# ==============================================================
# Break placement, code gaps, and the untouched-file guarantees
# ==============================================================

new_fixture breaks.py
cat >"$FIXTURE" <<'EOF'
#!/usr/bin/env python3
# A day is only immutable once it has ended, so a mid-day sample counts only the sessions that already ran.
# It therefore reads low and poisons every comparison against a closed day, which is why the script refuses to snapshot today.
VALUE = 1
EOF
run_fix
run_check
assert_absent "should never place a paragraph break mid-sentence" \
  "$CHECK_OUT" "SENTENCE-BREAK"
assert_absent "should leave no paragraph over the four-line cap" \
  "$CHECK_OUT" "PARAGRAPH"

new_fixture ellipsis.py
cat >"$FIXTURE" <<'EOF'
#!/usr/bin/env python3
# Points FIXTURE at a fresh path under the work dir, so
# each case gets its own file to write into.
# The caller writes it via `"$(cat <<EOF ...)"`
# rather than a plain heredoc, because bash mis-tracks
# quote state once the heredoc body holds an apostrophe.
VALUE = 1
EOF
run_fix
run_check
assert_eq "should break a paragraph after a sentence end, never after an ellipsis" \
  "# The caller writes it via \`\"\$(cat <<EOF ...)\"\`" \
  "$(grep -A1 '^#$' "$FIXTURE" | tail -1)"
assert_absent "should leave no ellipsis-split paragraph over the cap" \
  "$CHECK_OUT" "PARAGRAPH"

new_fixture gap.py
cat >"$FIXTURE" <<'EOF'
#!/usr/bin/env python3
VALUE = 1
# Naming the day explicitly is what makes the delta reproducible.
OTHER = 2
EOF
run_fix
run_check
assert_eq "should insert the blank line a code-gap comment needs" "0" "$CHECK_EXIT"

new_fixture clean.py
cat >"$FIXTURE" <<'EOF'
#!/usr/bin/env python3

# Naming both days is what makes a delta reproducible.
VALUE = 1
EOF
snapshot_fixture
run_fix
assert_eq "should exit 0 on an already-clean file" "0" "$FIX_EXIT"
assert_eq "should leave an already-clean file byte-identical" "" \
  "$(diff "$BASELINE" "$FIXTURE")"

new_fixture readonly.py
cat >"$FIXTURE" <<'EOF'
#!/usr/bin/env python3
# The aggregator collapses the many records one response emits into a single billed unit.
VALUE = 1
EOF
snapshot_fixture
run_check
assert_eq "should report violations without --fix" "1" "$CHECK_EXIT"
assert_eq "should never mutate the file when --fix is absent" "" \
  "$(diff "$BASELINE" "$FIXTURE")"

# ==============================================================
# Usage errors
# ==============================================================

node "$SCRIPT" --nonsense "$FIXTURE" >/dev/null 2>&1
assert_eq "should exit 2 when given an unknown flag" "2" "$?"

node "$SCRIPT" >/dev/null 2>&1
assert_eq "should exit 2 when given no files" "2" "$?"

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
