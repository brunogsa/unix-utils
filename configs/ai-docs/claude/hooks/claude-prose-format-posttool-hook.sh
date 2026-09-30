#!/bin/bash
# claude-prose-format-posttool-hook - detect-only prose/comment
# format reminder, fired right after a Write/Edit lands.
#
# Usage (Claude Code hooks):
#   PostToolUse matcher Write|Edit -> read the stdin payload,
#   check the file just written, report or stay silent.
#
# The user's complaint is walls of text in docs and code
# comments. The rule already exists (doc-standards), but
# nothing triggers it: today's checkers are opt-in via a
# skill that may never load.
#
# This hook is the trigger. It never fixes anything - it
# only puts the checkers' own findings back in front of the
# model that just wrote the file, on stderr, on a non-zero
# exit - the one channel PostToolUse feeds back to it.
#
# Scope: only lines this session itself added
# (--changed-only on every checker), never pre-existing
# content - "I just dont wanna us fixing what is already
# there."
#
# Fail-open is the safety property this hook lives or dies
# by: a missing file, a non-repo path (every /tmp scratchpad
# write), a missing checker, or a missing python3/node must
# all read as "no signal" and exit 0, never as a block.
#
# Any checker exit code other than 0 (clean) or 1
# (violations) is treated exactly that way, one checker at a
# time, so one broken checker never silences the others.
#
# Examples:
#   jq -n '{tool_name:"Write",
#     tool_input:{file_path:"/tmp/x.md"}}' \
#     | bash claude-prose-format-posttool-hook.sh
#
#   jq -n '{tool_name:"Read",
#     tool_input:{file_path:"a.md"}}' \
#     | bash claude-prose-format-posttool-hook.sh
#     # not a write -> silent

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
doc_scripts_dir="$script_dir/../skills/doc-standards/scripts"

VIOLATION_THRESHOLD=10

INPUT=$(cat)

TOOL_NAME=$(printf '%s' "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
case "$TOOL_NAME" in
  Write|Edit) ;;
  *) exit 0 ;;
esac

FILE_PATH=$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
[ -n "$FILE_PATH" ] || exit 0
[ -f "$FILE_PATH" ] || exit 0

ext="${FILE_PATH##*.}"
base="$(basename -- "$FILE_PATH")"

# checker_names holds the checker basenames for this file's
# extension, in the fixed order they run and report in.
checker_names=()
case "$ext" in
  md)
    checker_names=(check-density.sh check-hard-wrap.py check-bullet-gap.py check-bullet-structure.py)
    ;;
  ts|tsx|js|jsx|sh|bash|py)
    checker_names=(check-comment-format.js)
    ;;
  *)
    exit 0
    ;;
esac

# label_for_tag - normalize a checker's own violation tag
# (the first token of its output line) to this hook's
# report label.
#
# check-density.sh/check-hard-wrap.py/check-bullet-gap.py
# lines start with the line number directly, so their
# caller passes the fixed label instead of a tag;
# check-bullet-structure.py's rule token is already a label.
label_for_tag() {
  case "$1" in
    WIDTH) echo "width" ;;
    PARAGRAPH) echo "paragraph" ;;
    SENTENCE-BREAK) echo "sentence-break" ;;
    BULLET-SPACING) echo "bullet-spacing" ;;
    BULLET-BLANK) echo "bullet-blank" ;;
    CODE-GAP) echo "code-gap" ;;
    *) echo "$1" ;;
  esac
}

# description_for_label - the over-threshold table's fixed
# right-hand description for each known label.
description_for_label() {
  case "$1" in
    density) echo "line over its cap (prose 512c/64w, bullet 256c/32w)" ;;
    hard-wrap) echo "paragraph split across physical lines" ;;
    bullet-gap) echo "bullet missing its blank line" ;;
    dangling-colon) echo "bullet ends in a colon but introduces no deeper item" ;;
    dangling-dash) echo "bullet ends in a dash and the next bullet continues its sentence" ;;
    staircase) echo "3+ single-child bullets, each a level deeper" ;;
    width) echo "comment line over its width cap" ;;
    paragraph) echo "comment paragraph over its line cap with no blank break" ;;
    sentence-break) echo "comment run ends without a blank line" ;;
    bullet-spacing) echo "bullet marker missing its required spacing" ;;
    bullet-blank) echo "code-adjacent bullet missing its blank line" ;;
    code-gap) echo "comment separated from its code by a blank line" ;;
    *) echo "" ;;
  esac
}

rows_file=$(mktemp)
hit_checkers_file=$(mktemp)
trap 'rm -f "$rows_file" "$hit_checkers_file"' EXIT

for name in "${checker_names[@]}"; do
  chk="$doc_scripts_dir/$name"
  [ -x "$chk" ] || continue

  # invocation_path guards a FILE_PATH whose first character is
  # "-": passed raw, every checker here would parse it as an
  # option instead of a path.
  #
  # check-density.sh, check-hard-wrap.py, check-bullet-gap.py
  # and check-bullet-structure.py all accept a "--"
  # end-of-options separator;
  # check-comment-format.js does not, so it gets a "./"-prefixed
  # path instead.
  invocation_path="$FILE_PATH"
  case "$name" in
    check-comment-format.js)
      case "$invocation_path" in
        -*) invocation_path="./$invocation_path" ;;
      esac
      out=$("$chk" --changed-only "$invocation_path" 2>/dev/null)
      ;;
    *)
      case "$invocation_path" in
        -*) out=$("$chk" --changed-only -- "$invocation_path" 2>/dev/null) ;;
        *) out=$("$chk" --changed-only "$invocation_path" 2>/dev/null) ;;
      esac
      ;;
  esac
  rc=$?

  # 0 = clean, anything but 0/1 = no signal from this checker -
  # never treated as a violation and never as a block.
  [ "$rc" -eq 1 ] || continue

  case "$name" in
    check-density.sh)
      printf '%s\n' "$out" | awk -F: '/^== / {next} NF>=3 {print "density\t" $1 "\t" $2 "c/" $3 "w"}' >> "$rows_file"
      ;;
    check-hard-wrap.py)
      printf '%s\n' "$out" | awk -F: '/^== / {next} NF>=1 {print "hard-wrap\t" $1 "\t"}' >> "$rows_file"
      ;;
    check-bullet-gap.py)
      printf '%s\n' "$out" | awk -F: '/^== / {next} NF>=2 {print "bullet-gap\t" $1 "\t" (NF>=3 ? $3 : "")}' >> "$rows_file"
      ;;
    check-bullet-structure.py)
      printf '%s\n' "$out" | awk -F: '/^== / {next} NF>=2 {print $2 "\t" $1 "\t"}' >> "$rows_file"
      ;;
    check-comment-format.js)
      printf '%s\n' "$out" | awk '
        /^== / {next}
        {
          tag = $1
          rest = $0
          sub(/^[A-Z-]+ /, "", rest)
          line = rest
          sub(/[:-].*/, "", line)
          print tag "\t" line "\t"
        }' >> "$rows_file"
      ;;
  esac

  echo "$name" >> "$hit_checkers_file"
done

total=$(wc -l < "$rows_file" | tr -d ' ')
[ "$total" -gt 0 ] || exit 0

RULE_BLOCK='Prose: small paragraphs of 1-4 sentences, blank line between each.
Bullets + sub-bullets: 1-2 sentences each.
One paragraph = one physical line — never hard-wrap. Never drop information.
Colon-ended bullet: nest the items it introduces under it, or end it with a period. Single-child chain 3+ levels deep: flatten it into siblings under the shared parent.
Dash-ended bullet whose next bullet continues its sentence: rewrite the pair as two full sentences, or rejoin them into one bullet. Before flattening a chain, rewrite as a full sentence any line that continues the sentence above it.'

{
  printf 'prose-format: %s — %s violation%s\n\n' "$base" "$total" "$([ "$total" -eq 1 ] && echo "" || echo "s")"

  # labels_seen preserves first-appearance order across
  # checkers, matching the fixed run order above.
  labels_seen=()
  while IFS=$'\t' read -r raw_label line detail; do
    label=$(label_for_tag "$raw_label")
    seen=0
    for l in "${labels_seen[@]:-}"; do
      [ "$l" = "$label" ] && seen=1 && break
    done
    [ "$seen" -eq 1 ] || labels_seen+=("$label")
  done < "$rows_file"

  # label_width is the widest label among this report's rows, so
  # every row's value column lines up under it.
  label_width=0
  for label in "${labels_seen[@]}"; do
    [ "${#label}" -gt "$label_width" ] && label_width="${#label}"
  done

  if [ "$total" -gt "$VIOLATION_THRESHOLD" ]; then
    for label in "${labels_seen[@]}"; do
      count=$(awk -F'\t' -v l="$label" 'BEGIN{c=0} {rl=$1; if (rl=="WIDTH") rl="width"; else if (rl=="PARAGRAPH") rl="paragraph"; else if (rl=="SENTENCE-BREAK") rl="sentence-break"; else if (rl=="BULLET-SPACING") rl="bullet-spacing"; else if (rl=="BULLET-BLANK") rl="bullet-blank"; else if (rl=="CODE-GAP") rl="code-gap"; if (rl==l) c++} END{print c}' "$rows_file")
      desc=$(description_for_label "$label")
      printf '  %-*s %3d  %s\n' "$((label_width + 2))" "$label" "$count" "$desc"
    done
    printf '\n%s\n\n' "$RULE_BLOCK"

    # name_width is the longest hit checker's basename, so every
    # printed command's --changed-only flag lines up in one
    # column regardless of which checker names ran.
    name_width=0
    while IFS= read -r name; do
      [ "${#name}" -gt "$name_width" ] && name_width="${#name}"
    done < "$hit_checkers_file"

    while IFS= read -r name; do
      # print_path/extra_flag mirror the invocation guard above,
      # so the printed command is the exact one that was
      # actually run - never a bare unquoted path a shell
      # metacharacter or a space could split or execute out of.
      print_path="$FILE_PATH"
      extra_flag=""
      case "$name" in
        check-comment-format.js)
          case "$print_path" in
            -*) print_path="./$print_path" ;;
          esac
          ;;
        *)
          case "$print_path" in
            -*) extra_flag="-- " ;;
          esac
          ;;
      esac
      quoted_path=$(printf '%q' "$print_path")
      printf '  ~/.claude/skills/doc-standards/scripts/%-*s   --changed-only %s%s\n' \
        "$name_width" "$name" "$extra_flag" "$quoted_path"
    done < "$hit_checkers_file"
  else
    for label in "${labels_seen[@]}"; do
      # Only density rows carry a per-line c/w detail - it tells
      # the model how far over the cap a line is, which decides
      # one split vs four.
      #
      # hard-wrap/bullet-gap rows stay bare line numbers; a
      # flood of detail on every label defeats the
      # under-threshold regime's whole point.
      lines_for_label=()
      while IFS=$'\t' read -r raw_label line detail; do
        rl=$(label_for_tag "$raw_label")
        [ "$rl" = "$label" ] || continue
        if [ "$label" = "density" ] && [ -n "$detail" ]; then
          lines_for_label+=("L$line $detail")
        else
          lines_for_label+=("L$line")
        fi
      done < "$rows_file"
      joined=""
      for l in "${lines_for_label[@]}"; do
        if [ -z "$joined" ]; then
          joined="$l"
        else
          joined="$joined, $l"
        fi
      done
      printf '  %-*s %s\n' "$((label_width + 2))" "$label" "$joined"
    done
    printf '\n%s\n' "$RULE_BLOCK"
  fi
} >&2

exit 2
