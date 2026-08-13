#!/usr/bin/env bash
# test-subagent-prompt-script-refs.sh - plain-bash test
# guarding that every backtick-quoted script name in
# assets/subagent-prompt.md resolves to a real file.
#
# Nothing else in this repo checks that a script name
# written inside a skill doc resolves to a real file.
#
# Before commit ebab9041 reflowed this doc, a stale
# `session-timeline.py` reference (real script:
# `extract-session-timeline.py`) straddled a hard-wrap
# line break, which hid it from every human and checker.
#
# This suite is the guard that would have caught it. It
# extracts every backtick-quoted *.py/*.sh/*.js token and
# resolves each by basename search under
# configs/ai-docs/claude/.
#
# These scripts do not all live in one directory -- some
# sit beside the skill, some in the shared scripts/ tree,
# some under hooks/.
#
# Exits 0 when every assertion passes, non-zero otherwise.
#
# No bats dependency, matching the sibling audit-session
# suite (test-audit-session-shard-tiers.sh).

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROMPT_FILE="$script_dir/../assets/subagent-prompt.md"
CLAUDE_DOCS_ROOT="$(cd "$script_dir/../../.." && pwd)"

pass_count=0
fail_count=0

# assert_eq - inline assert helper: compares expected vs
# actual, prints ok/not-ok.
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

# extract_script_tokens <file> - every backtick-quoted
# word (one per output line) that ends in .py, .sh, or .js,
# with any path prefix stripped to a bare basename and any
# trailing argument or punctuation dropped.
#
# Fenced code blocks are skipped: the one fence in this
# file holds a JSON schema example, not a script to run,
# so a *.py-looking string inside it is not a reference
# to resolve.
#
# The extension check matches each word's own ending,
# never a substring match anywhere in the backtick span.
#
# `cost.json` must never match `\.js`; a span like
# `render-session-audit.py /tmp/.../cost.json` must
# yield only the .py word, not the .json one.
extract_script_tokens() {
  local file="$1"
  [ -f "$file" ] || return 0

  # Literal backtick delimiters below, not expansions to
  # interpolate.
  # shellcheck disable=SC2016
  awk '
    /^```/ { infence = !infence; next }
    infence { next }
    { print }
  ' "$file" \
    | grep -oE '`[^`]*`' \
    | sed -E 's/^`//; s/`$//' \
    | tr ' ' '\n' \
    | sed -E 's/[^A-Za-z0-9._-]+$//' \
    | grep -E '\.(py|sh|js)$' \
    | xargs -n1 basename
}

# resolve_by_basename <name> <root> - the first file
# under root whose basename is exactly name, or empty
# when none exists.
#
# Basename search, not a fixed directory, because these
# scripts spread across the skill's own scripts/, the
# shared configs/ai-docs/claude/scripts/, and hooks/.
resolve_by_basename() {
  local name="$1" root="$2"
  find "$root" -type f -name "$name" 2>/dev/null | head -n1
}

# check_script_refs <file> <root> - prints "" and
# returns 0 when every backtick-quoted script token in
# file resolves under root.
#
# Otherwise prints the unresolved tokens, so a failing
# assertion names the offending reference, and returns 1.
check_script_refs() {
  local file="$1" root="$2"
  if [ ! -f "$file" ]; then
    printf 'missing file: %s\n' "$file"
    return 1
  fi
  local token resolved missing=""
  while IFS= read -r token; do
    [ -n "$token" ] || continue
    resolved=$(resolve_by_basename "$token" "$root")
    if [ -z "$resolved" ]; then
      missing="$missing $token"
    fi
  done < <(extract_script_tokens "$file")
  if [ -n "$missing" ]; then
    printf 'unresolved script references:%s\n' "$missing"
    return 1
  fi
  return 0
}

it_should_strip_trailing_arguments_before_resolving_a_backticked_script_token() {
  local tmp_file tokens
  tmp_file="$(mktemp)"

  # literal backtick fixture, no expansion intended
  # shellcheck disable=SC2016
  printf 'Run `extract-session-timeline.py <sid>` then `claude-usage-report.py --session` next.\n' > "$tmp_file"
  tokens=$(extract_script_tokens "$tmp_file" | tr '\n' ',')
  rm -f "$tmp_file"
  assert_eq "should strip a trailing argument (e.g. <sid> or --session) from a backticked script token before resolving its basename" \
    "extract-session-timeline.py,claude-usage-report.py," "$tokens"
}

it_should_not_mistake_a_json_output_path_sharing_a_backtick_span_with_a_script_name_for_a_second_script_reference() {
  local tmp_file tokens
  tmp_file="$(mktemp)"

  # literal backtick fixture, no expansion intended
  # shellcheck disable=SC2016
  printf 'Run `render-session-audit.py /tmp/audit-session-<sid>/cost.json /tmp/audit-session-<sid>/timeline.json -o <dir>`.\n' > "$tmp_file"
  tokens=$(extract_script_tokens "$tmp_file" | tr '\n' ',')
  rm -f "$tmp_file"
  assert_eq "should extract only the .py script name from a backtick span that also carries .json output paths, since .json is not .js" \
    "render-session-audit.py," "$tokens"
}

it_should_ignore_a_script_looking_token_inside_a_fenced_code_block() {
  local tmp_file tokens
  tmp_file="$(mktemp)"
  {
    # literal backtick fixture, no expansion intended
    # shellcheck disable=SC2016
    printf 'Run `extract-session-timeline.py <sid>` first.\n\n'
    printf '```\n'

    # literal backtick fixture, no expansion intended
    # shellcheck disable=SC2016
    printf 'example reference inside the schema fence: `fake-fenced-script.py` (not a real dispatch)\n'
    printf '```\n'
  } > "$tmp_file"
  tokens=$(extract_script_tokens "$tmp_file" | tr '\n' ',')
  rm -f "$tmp_file"
  assert_eq "should ignore a backtick-quoted script-extension-looking token that sits inside a fenced code block" \
    "extract-session-timeline.py," "$tokens"
}

it_should_resolve_extract_session_timeline_py_by_basename_search_under_the_shared_claude_docs_tree() {
  local resolved
  resolved=$(resolve_by_basename "extract-session-timeline.py" "$CLAUDE_DOCS_ROOT")
  case "$resolved" in
    */skills/audit-session/scripts/extract-session-timeline.py) resolved="resolved-in-expected-dir" ;;
  esac
  assert_eq "should resolve extract-session-timeline.py by basename search to its file under skills/audit-session/scripts/" \
    "resolved-in-expected-dir" "$resolved"
}

it_should_resolve_render_session_audit_py_by_basename_search_under_the_shared_claude_docs_tree() {
  local resolved
  resolved=$(resolve_by_basename "render-session-audit.py" "$CLAUDE_DOCS_ROOT")
  case "$resolved" in
    */skills/audit-session/scripts/render-session-audit.py) resolved="resolved-in-expected-dir" ;;
  esac
  assert_eq "should resolve render-session-audit.py by basename search to its file under skills/audit-session/scripts/" \
    "resolved-in-expected-dir" "$resolved"
}

it_should_resolve_claude_usage_report_py_by_basename_search_even_though_it_lives_outside_the_skills_own_scripts_directory() {
  local resolved
  resolved=$(resolve_by_basename "claude-usage-report.py" "$CLAUDE_DOCS_ROOT")
  case "$resolved" in
    */skills/usage-audit/scripts/claude-usage-report.py) resolved="resolved-in-expected-dir" ;;
  esac
  assert_eq "should resolve claude-usage-report.py by basename search to its file under skills/usage-audit/scripts/, a different skill's directory" \
    "resolved-in-expected-dir" "$resolved"
}

it_should_resolve_subagent_model_guard_py_by_basename_search_even_though_it_lives_under_the_hooks_tree() {
  local resolved
  resolved=$(resolve_by_basename "subagent-model-guard.py" "$CLAUDE_DOCS_ROOT")
  case "$resolved" in
    */hooks/subagent-model-guard.py) resolved="resolved-in-expected-dir" ;;
  esac
  assert_eq "should resolve subagent-model-guard.py by basename search to its file under hooks/, outside every skill directory" \
    "resolved-in-expected-dir" "$resolved"
}

it_should_fail_and_name_the_offending_token_when_a_referenced_script_does_not_exist_anywhere_in_the_tree() {
  local tmp_file output result
  tmp_file="$(mktemp)"

  # literal backtick fixture, no expansion intended
  # shellcheck disable=SC2016
  printf 'Run `totally-bogus-script.py <sid>` to do the thing.\n' > "$tmp_file"
  if output=$(check_script_refs "$tmp_file" "$CLAUDE_DOCS_ROOT" 2>&1); then
    result="passed"
  else
    case "$output" in
      *totally-bogus-script.py*) result="named the offending token" ;;
      *) result="failed without naming the token: $output" ;;
    esac
  fi
  rm -f "$tmp_file"
  assert_eq "should fail and name the offending token when a referenced script does not exist anywhere under configs/ai-docs/claude/" \
    "named the offending token" "$result"
}

it_should_assert_every_backtick_quoted_script_reference_in_the_subagent_prompt_resolves_to_a_real_file() {
  local output result
  if output=$(check_script_refs "$PROMPT_FILE" "$CLAUDE_DOCS_ROOT" 2>&1); then
    result="all resolved"
  else
    result="$output"
  fi
  assert_eq "should assert every backtick-quoted script reference in assets/subagent-prompt.md resolves to a real file under configs/ai-docs/claude/" \
    "all resolved" "$result"
}

it_should_strip_trailing_arguments_before_resolving_a_backticked_script_token
it_should_not_mistake_a_json_output_path_sharing_a_backtick_span_with_a_script_name_for_a_second_script_reference
it_should_ignore_a_script_looking_token_inside_a_fenced_code_block
it_should_resolve_extract_session_timeline_py_by_basename_search_under_the_shared_claude_docs_tree
it_should_resolve_render_session_audit_py_by_basename_search_under_the_shared_claude_docs_tree
it_should_resolve_claude_usage_report_py_by_basename_search_even_though_it_lives_outside_the_skills_own_scripts_directory
it_should_resolve_subagent_model_guard_py_by_basename_search_even_though_it_lives_under_the_hooks_tree
it_should_fail_and_name_the_offending_token_when_a_referenced_script_does_not_exist_anywhere_in_the_tree
it_should_assert_every_backtick_quoted_script_reference_in_the_subagent_prompt_resolves_to_a_real_file

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
