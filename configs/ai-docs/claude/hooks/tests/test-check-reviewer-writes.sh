#!/usr/bin/env bash
# Plain-bash test file for check-reviewer-writes.sh.
#
# Usage:
#   bash test-check-reviewer-writes.sh
#
# Exits 0 when every assertion passes, non-zero otherwise.

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$script_dir/check-reviewer-writes.sh"

pass_count=0
fail_count=0

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

# run_hook - feeds a Write payload for one path and the
# session cwd; prints the exit code and whether the output
# auto-approves.
run_hook() {
  local path="$1" cwd="${2:-/work/repo}" output code
  output=$(printf '{"cwd":"%s","tool_input":{"file_path":"%s"}}' "$cwd" "$path" | bash "$SCRIPT" 2>/dev/null)
  code=$?
  if [[ "$output" == *'"permissionDecision":"allow"'* ]]; then
    printf '%s allow' "$code"
  else
    printf '%s no-allow' "$code"
  fi
}

assert_eq "allows the inferred layer map written to the working directory" \
  "0 allow" "$(run_hook "/work/repo/layers_inferred_2026-11-16_01-19.yaml")"

assert_eq "blocks the inferred layer map under a CI workflow directory" \
  "2 no-allow" "$(run_hook "/work/repo/.github/workflows/layers_inferred_x.yaml")"

assert_eq "blocks the inferred layer map reached through a parent-directory hop" \
  "2 no-allow" "$(run_hook "/work/repo/sub/../layers_inferred_x.yaml")"

assert_eq "blocks the inferred layer map in a directory other than the working one" \
  "2 no-allow" "$(run_hook "/work/other/layers_inferred_x.yaml")"

assert_eq "allows a bare relative inferred layer map name" \
  "0 allow" "$(run_hook "layers_inferred_x.yaml")"

assert_eq "blocks a relative inferred layer map name that has a slash" \
  "2 no-allow" "$(run_hook "sub/layers_inferred_x.yaml")"

assert_eq "still allows a verdict markdown file" \
  "0 allow" "$(run_hook "/work/repo/verdict_metrics_2026-11-16_01-19.md")"

assert_eq "still allows scratch under /tmp" \
  "0 allow" "$(run_hook "/tmp/auto-review.abc123/wave2.json")"

assert_eq "blocks an unrelated yaml name in the working directory" \
  "2 no-allow" "$(run_hook "/work/repo/config.yaml")"

assert_eq "blocks a layers_inferred name with a non-yaml extension" \
  "2 no-allow" "$(run_hook "/work/repo/layers_inferred_2026-11-16.sh")"

assert_eq "blocks a write whose path is missing" \
  "2 no-allow" "$(run_hook "")"

assert_eq "allows a verdict file at the working directory top level" \
  "0 allow" "$(run_hook "/work/repo/verdict_x.md")"

assert_eq "allows a bare relative verdict file name" \
  "0 allow" "$(run_hook "verdict_x.html")"

assert_eq "blocks a verdict file under a CI workflow directory" \
  "2 no-allow" "$(run_hook "/work/repo/.github/verdict_x.md")"

assert_eq "blocks a relative verdict file name that has a slash" \
  "2 no-allow" "$(run_hook "sub/verdict_x.md")"

assert_eq "blocks a verdict file in a directory other than the working one" \
  "2 no-allow" "$(run_hook "/work/other/verdict_x.md")"

assert_eq "blocks a verdict file reached through a parent-directory hop" \
  "2 no-allow" "$(run_hook "/work/repo/sub/../verdict_x.md")"

# run_bash - feeds a Bash payload with one command and the
# session cwd; prints the exit code.
run_bash() {
  local command="$1" cwd="${2:-/work/repo}" code
  jq -n --arg c "$cwd" --arg m "$command" \
    '{cwd:$c,tool_name:"Bash",tool_input:{command:$m}}' \
    | bash "$SCRIPT" >/dev/null 2>&1
  code=$?
  printf '%s' "$code"
}

assert_eq "blocks a Bash redirect into a repo source file" \
  "2" "$(run_bash 'echo x > src/a.py')"

assert_eq "blocks a Bash append redirect into a repo file" \
  "2" "$(run_bash 'git diff >> /work/repo/notes.txt')"

assert_eq "blocks tee into a repo file" \
  "2" "$(run_bash 'echo x | tee src/a.py')"

assert_eq "blocks an in-place sed edit" \
  "2" "$(run_bash 'sed -i s/a/b/ src/a.py')"

assert_eq "blocks a redirect that traverses out of /tmp" \
  "2" "$(run_bash 'echo x > /tmp/../work/repo/a.py')"

assert_eq "allows a Bash redirect into the /tmp run directory" \
  "0" "$(run_bash 'git diff > /tmp/auto-review.abc123/d.txt')"

assert_eq "allows tee into the /tmp run directory" \
  "0" "$(run_bash 'git diff | tee /tmp/auto-review.abc123/d.txt')"

assert_eq "allows a plain grep" \
  "0" "$(run_bash 'grep -rn foo src')"

assert_eq "allows stderr merged into stdout and discarded output" \
  "0" "$(run_bash 'git log 2>&1 >/dev/null')"

assert_eq "allows a quoted angle bracket that is not a redirect" \
  "0" "$(run_bash 'grep "a > b" src/a.py')"

assert_eq "blocks a verdict redirect in Bash even at the working directory top level" \
  "2" "$(run_bash 'echo done > /work/repo/verdict_x.md')"

assert_eq "blocks a verdict redirect that follows a cd into a source directory" \
  "2" "$(run_bash 'cd src && echo x > verdict_a.md')"

assert_eq "blocks an inferred layer map redirect in Bash" \
  "2" "$(run_bash 'echo x > layers_inferred_a.yaml')"

assert_eq "blocks a clobber redirect into repo source" \
  "2" "$(run_bash 'echo x >| src/a.py')"

assert_eq "blocks an stdout-and-stderr redirect into repo source" \
  "2" "$(run_bash 'echo x &> src/a.py')"

assert_eq "blocks an stdout-and-stderr append redirect into repo source" \
  "2" "$(run_bash 'echo x &>> src/a.py')"

assert_eq "allows a clobber redirect into /tmp" \
  "0" "$(run_bash 'echo x >| /tmp/a.txt')"

assert_eq "allows an stdout-and-stderr redirect into /tmp" \
  "0" "$(run_bash 'echo x &> /tmp/a.txt')"

assert_eq "blocks a redirect with no target" \
  "2" "$(run_bash 'echo x >')"

assert_eq "blocks a redirect whose target is missing before a pipe" \
  "2" "$(run_bash 'echo x > | cat')"

assert_eq "blocks a verdict redirect in a subdirectory" \
  "2" "$(run_bash 'echo done > .github/verdict_x.md')"

# run_bash_output - like run_bash, but prints the exit code and
# whether stdout carried any approval output.
run_bash_output() {
  local command="$1" output code
  output=$(jq -n --arg c "/work/repo" --arg m "$command" \
    '{cwd:$c,tool_name:"Bash",tool_input:{command:$m}}' \
    | bash "$SCRIPT" 2>/dev/null)
  code=$?
  if [ -z "$output" ]; then printf '%s no-output' "$code"; else printf '%s output' "$code"; fi
}

assert_eq "allows a quoted redirect target with a space under /tmp" \
  "0" "$(run_bash 'echo x > "/tmp/a b.txt"')"

assert_eq "allows tee into a quoted /tmp path with a space" \
  "0" "$(run_bash 'cat a | tee "/tmp/x y"')"

assert_eq "blocks a quoted redirect target that is repo source" \
  "2" "$(run_bash 'echo x > "src/a.py"')"

assert_eq "blocks a quoted /tmp target with a space that hops out of /tmp" \
  "2" "$(run_bash 'echo x > "/tmp/a b/../../x"')"

assert_eq "passes a quoted angle bracket in grep with no output" \
  "0 no-output" "$(run_bash_output 'grep "a > b" src/a.py')"

assert_eq "passes a quoted angle bracket in a git log format with no output" \
  "0 no-output" "$(run_bash_output 'git log --format="%h > x"')"

assert_eq "passes a quoted work_dir variable redirect target with no output" \
  "0 no-output" "$(run_bash_output 'git diff > "$work_dir/diff.txt"')"

assert_eq "passes an unquoted variable redirect target with no output" \
  "0 no-output" "$(run_bash_output 'python3 x.py > $RUN_DIR/out.md')"

assert_eq "passes a braced variable redirect target with no output" \
  "0 no-output" "$(run_bash_output 'echo x > ${RUN_DIR}/x')"

assert_eq "blocks a bare variable that is not a known mktemp scratch dir" \
  "2" "$(run_bash 'echo x > "$f"')"

assert_eq "blocks a literal repo source redirect target" \
  "2" "$(run_bash 'echo x > src/a.py')"

assert_eq "blocks a literal append redirect into README.md" \
  "2" "$(run_bash 'echo x >> README.md')"

# A variable the hook cannot prove is a /tmp scratch dir may
# point anywhere, so only the pipelines' mktemp dirs pass.
assert_eq "blocks a redirect into the home directory variable" \
  "2" "$(run_bash 'echo x > $HOME/x')"

assert_eq "blocks a braced working-directory variable redirect into source" \
  "2" "$(run_bash 'echo x > ${PWD}/src/a.py')"

assert_eq "blocks a quoted previous-directory variable redirect" \
  "2" "$(run_bash 'echo x > "$OLDPWD/README.md"')"

assert_eq "blocks tee into an unknown variable directory" \
  "2" "$(run_bash 'echo x | tee $X/a')"

assert_eq "blocks an ANSI-C quoted redirect target" \
  "2" "$(run_bash "echo x > \$'foo'")"

assert_eq "blocks a locale-quoted redirect target" \
  "2" "$(run_bash 'echo x > $"foo"')"

assert_eq "blocks a command substitution inside a scratch dir target" \
  "2" "$(run_bash 'echo x > "$work_dir/`id`"')"

assert_eq "blocks a redirect into a home-relative tilde path" \
  "2" "$(run_bash 'echo x > ~/x')"

assert_eq "allows tee into the quoted auto-review scratch dir" \
  "0" "$(run_bash 'git diff | tee "$work_dir/d.txt"')"

assert_eq "allows an append redirect into the braced quality-gate run dir" \
  "0" "$(run_bash 'echo x >> "${RUN_DIR}/x.md"')"

assert_eq "blocks a scratch dir target that hops out with a parent-directory step" \
  "2" "$(run_bash 'echo x > $work_dir/../src/a.py')"

assert_eq "blocks a variable whose name only starts with a scratch dir name" \
  "2" "$(run_bash 'echo x > $work_dir2/x')"

assert_eq "blocks a braced scratch dir name glued to more text" \
  "2" "$(run_bash 'echo x > ${work_dir}x')"

assert_eq "allows stderr discarded to /dev/null" \
  "0" "$(run_bash 'echo x 2>/dev/null')"

assert_eq "blocks a quoted /tmp target that hops out to /etc" \
  "2" "$(run_bash 'echo x > "/tmp/a/../../etc/x"')"

# Every redirect or tee line in the review pipeline's own
# references must pass the hook, or the pipeline breaks on its
# first scratch write. Lines are derived by grep at test time:
# fenced code lines plus inline code spans.
pipeline_dir="$script_dir/../skills/code-review-pipeline"
pipeline_files=(
  "$pipeline_dir/SKILL.md"
  "$pipeline_dir/references/wave1-context-prep.md"
  "$pipeline_dir/references/wave2-fan-out.md"
  "$pipeline_dir/references/wave5-emit-github.md"
  "$pipeline_dir/references/wave1-repo-wide-checks.md"
)
redirect_line_regex='(^|[[:space:]0-9])>>?[[:space:]]*["$]|(^|[|;&[:space:]])tee[[:space:]]'
pipeline_lines=$(for f in "${pipeline_files[@]}"; do
  awk '/^[[:space:]]*```/{inside=!inside; next} inside' "$f"
  grep -o '`[^`]*`' "$f" | tr -d '`'
done | grep -E "$redirect_line_regex" | sed -E 's/<[a-z_ -]+>//g')

line_count=0
denied_lines=""
while IFS= read -r line; do
  [ -z "$line" ] && continue
  line_count=$((line_count + 1))
  [ "$(run_bash "$line")" = "0" ] || denied_lines="$denied_lines
$line"
done <<< "$pipeline_lines"

assert_eq "denies none of the review pipeline's own redirect and tee lines" \
  "" "$denied_lines"

assert_eq "finds at least 10 redirect or tee lines in the pipeline references" \
  "yes" "$([ "$line_count" -ge 10 ] && echo yes || echo "no ($line_count)")"

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
