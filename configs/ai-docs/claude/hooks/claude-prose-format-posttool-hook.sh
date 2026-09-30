#!/bin/bash
# claude-prose-format-posttool-hook - detect-only prose/comment
# format reminder, fired right after a Write/Edit lands.
#
# Usage (Claude Code hooks):
#   PostToolUse matcher Write|Edit|Bash -> read the stdin
#   payload, check the file(s) just written, report or stay
#   silent.
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
# A file outside any git work tree has no baseline to diff
# against, so every line counts as new: it is checked whole,
# without --changed-only.
#
# A Bash payload names no file, so outside a work tree the
# files directly in cwd touched
# within the write window stand in for git's list.
#
# Fail-open is the safety property this hook lives or dies
# by: a missing file, a missing checker, a checker that
# errors (e.g. a non-UTF-8 file), or a missing python3/node
# must all read as "no signal" and exit 0, never as a block.
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

# check_file - run one file's checkers and print its report on
# stderr, returning 2 when it found anything and 0 when clean.
check_file() {
  local FILE_PATH="$1"
  [ -f "$FILE_PATH" ] || return 0

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
    return 0
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

# scope_flag is --changed-only only for a file inside a git
# work tree, resolved from the FILE's own directory - never
# the hook's cwd, which sits in a repo while the file may not.
#
# Outside a work tree get-changed-lines.sh has no baseline and
# exits 2, which every checker passes on as exit 2 and this
# hook reads as "no signal". With no baseline every line is
# this write's own, so the whole file is the honest scope.
#
# Deciding here, not by retrying on exit 2, keeps a transient
# failure inside a work tree from widening to a whole-file
# check.
scope_flag="--changed-only"
git -C "$(dirname -- "$FILE_PATH")" rev-parse --is-inside-work-tree >/dev/null 2>&1 || scope_flag=""

rows_file=$(mktemp)
hit_checkers_file=$(mktemp)

for name in "${checker_names[@]}"; do
  chk="$doc_scripts_dir/$name"
  [ -x "$chk" ] || continue

  # invocation_path guards a FILE_PATH whose first character is
  # "-": passed raw, every checker here would parse it as an
  # option instead of a path.
  #
  # check-density.sh, check-hard-wrap.py, check-bullet-gap.py
  # and check-bullet-structure.py all accept a "--"
  # end-of-options separator.
  #
  # check-comment-format.js does not, so it gets a "./"-prefixed
  # path instead.
  invocation_path="$FILE_PATH"
  case "$name" in
    check-comment-format.js)
      case "$invocation_path" in
        -*) invocation_path="./$invocation_path" ;;
      esac
      out=$("$chk" ${scope_flag:+"$scope_flag"} "$invocation_path" 2>/dev/null)
      ;;
    *)
      case "$invocation_path" in
        -*) out=$("$chk" ${scope_flag:+"$scope_flag"} -- "$invocation_path" 2>/dev/null) ;;
        *) out=$("$chk" ${scope_flag:+"$scope_flag"} "$invocation_path" 2>/dev/null) ;;
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
if [ "$total" -eq 0 ]; then
  rm -f "$rows_file" "$hit_checkers_file"
  return 0
fi

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
    # printed command's flag-or-path lines up in one column
    # regardless of which checker names ran.
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
      printf '  ~/.claude/skills/doc-standards/scripts/%-*s   %s%s%s\n' \
        "$name_width" "$name" "${scope_flag:+$scope_flag }" "$extra_flag" "$quoted_path"
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

  rm -f "$rows_file" "$hit_checkers_file"
  return 2
}

# How recently a file must have been touched to count as
# written by the Bash call that just ran.
#
# git reports every dirty file in the tree, but this hook only
# has standing over the ones its own Bash call produced.
#
# A long-dirty work tree - a concurrent session's scratch, a
# half-finished refactor - would otherwise be re-reported in
# full on every Bash call.
#
# That measured 29 files and 30 seconds per call in this repo,
# which is how a hook gets switched off.
BASH_WRITE_WINDOW_SECONDS=300

# file_mtime_seconds - epoch mtime of a file, via the BSD form
# first and the GNU form second, since this repo runs on both.
file_mtime_seconds() {
  stat -f %m "$1" 2>/dev/null || stat -c %Y "$1" 2>/dev/null
}

# collect_bash_paths - fill `paths` with every file git reports
# as changed in the work tree the Bash call ran in.
#
# A Bash payload names no file, and the write may have come
# from a redirect, a heredoc, tee, an in-place edit or a script
# the command invoked, so git's own view is the only signal
# that needs no hand-maintained list of writers.
#
# Outside a work tree git has nothing to report, so the fallback
# is the files directly in cwd touched inside the same window.
# Depth 1, never recursive: a cwd of $HOME or / must not turn
# every Bash call into a disk walk.
#
# Returns non-zero when cwd is no directory, which is the
# fail-open case: no signal.
collect_bash_paths() {
  local cwd="$1" top entry status_pair relative_path absolute_path mtime now
  now=$(date +%s)
  if ! git -C "$cwd" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    [ -d "$cwd" ] || return 1
    while IFS= read -r -d '' absolute_path; do
      mtime=$(file_mtime_seconds "$absolute_path")
      [ -n "$mtime" ] || continue
      [ "$((now - mtime))" -le "$BASH_WRITE_WINDOW_SECONDS" ] || continue
      paths+=("$absolute_path")
    done < <(find "$cwd" -maxdepth 1 -type f -print0 2>/dev/null)
    return 0
  fi
  top=$(git -C "$cwd" rev-parse --show-toplevel 2>/dev/null) || return 1
  [ -n "$top" ] || return 1

  # -z keeps every path raw, so a name carrying a space or a
  # quote needs no unquoting; -uall lists files inside a new
  # directory instead of collapsing it to the directory.
  while IFS= read -r -d '' entry; do
    status_pair="${entry:0:2}"
    relative_path="${entry:3}"

    # A rename or copy entry carries its old path as a second
    # NUL field, which names no file on disk to check.
    case "$status_pair" in
      *R*|*C*) IFS= read -r -d '' _ ;;
    esac

    absolute_path="$top/$relative_path"
    mtime=$(file_mtime_seconds "$absolute_path")
    [ -n "$mtime" ] || continue
    [ "$((now - mtime))" -le "$BASH_WRITE_WINDOW_SECONDS" ] || continue

    paths+=("$absolute_path")
  done < <(git -C "$cwd" status --porcelain -z -uall 2>/dev/null)
}

paths=()
case "$TOOL_NAME" in
  Write|Edit)
    FILE_PATH=$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
    [ -n "$FILE_PATH" ] || exit 0
    paths=("$FILE_PATH")
    ;;
  Bash)
    HOOK_CWD=$(printf '%s' "$INPUT" | jq -r '.cwd // empty' 2>/dev/null)
    [ -n "$HOOK_CWD" ] || HOOK_CWD="$PWD"
    collect_bash_paths "$HOOK_CWD" || exit 0
    ;;
  *)
    exit 0
    ;;
esac

reported=0
for candidate_path in "${paths[@]:-}"; do
  [ -n "$candidate_path" ] || continue
  check_file "$candidate_path" || reported=1
done

[ "$reported" -eq 1 ] || exit 0
exit 2
