#!/bin/bash

# PreToolUse guard shared by every reviewer agent that
# references it from frontmatter: code-reviewer,
# spec-reviewer, plan-reviewer, test-reviewer,
# performance-check-auditor.
#
# It screens Write/Edit paths and Bash write forms (a `>`,
# `>>`, `>|`, `&>` or `&>>` redirect, `tee`, `sed -i`).
#
# Each is a read-only judge.
#
# Its write affordances are exactly three:
#   1. persisting a verdict to a verdict file,
#
#   2. persisting an inferred layer map to a
#      layers_inferred_*.yaml file, and
#
#   3. scratch under /tmp - the review pipeline (auto-review)
#      persists wave artifacts to a mktemp dir there; /tmp is
#      never repo source.
#
#      Safe only because subagent-notes-guard.py denies
#      writes to the main session's notes.md.
#
# When code-reviewer runs auto-review's local mode (its own
# pin), Wave 2's findings JSON lands in that same mktemp dir
# under the third affordance.
#
# An opus context running the whole pipeline still cannot reach
# repo source even under a bypassPermissions parent.
#
# Both `.md` and `.html` count as a verdict
# file: the html-artifacts router picks the extension per
# artifact type, and it routes a review report to an HTML
# artifact.
#
# A guard allowing only `.md` would deny that write at
# the tool layer and lose the whole review at its last step.
#
# This guard enforces that at the tool layer: a Write/Edit to a
# verdict file or to a path under /tmp is auto-approved (so an
# unattended background subagent needs no interactive prompt);
#
# every other Write/Edit is denied (so it can never touch repo
# source, even under a bypassPermissions parent).
#
# Why `verdict_` and not `report_`/`findings_`: the Claude Code
# harness itself intercepts a subagent Write whose basename
# matches a reserved stem, before this hook ever runs.
#
# It silently substitutes "return findings as text" instead of
# performing the write. `verdict_` sidesteps that reserved set.
#
# The full trigger (all four stems, the `.md`-only
# scope, case-insensitivity, start-anchoring) is documented
# once, in agent-standards' "Subagent dispatch" section - see
# that skill rather than re-deriving it here.

INPUT=$(cat)

CWD=$(echo "$INPUT" | jq -r '.cwd // empty')
CWD=${CWD:-$PWD}
CWD=${CWD%/}

# A verdict or layer-map file counts only in the working
# directory itself: a basename match alone would let a reviewer
# write a CI workflow such as
# .github/workflows/layers_inferred_x.yaml, which would run.
#
# The same holds for a verdict_x.md in a source directory.
#
# A relative path counts as the working directory only when
# it has no slash.
is_in_cwd_top_level() {
  local path="$1"
  [[ "$path" != *..* && ( "$path" != */* || "${path%/*}" == "$CWD" ) ]]
}

# Prints the allow reason for a write target, or nothing when
# the target is not one this reviewer may write.
#
# Scratch under /tmp (the pipeline's wave-artifact dir, e.g.
# /tmp/auto-review.XXXXXX) is allowed, but a path containing
# `..` is rejected first, so /tmp/../<repo>/file can't escape
# /tmp back into repo source.
allowed_write_reason() {
  local path="$1" base="${1##*/}"
  if [[ "$base" == verdict_*.md || "$base" == verdict_*.html ]] \
    && is_in_cwd_top_level "$path"; then
    echo "this reviewer may persist its verdict to its verdict file ($base)"
  elif [[ "$base" == layers_inferred_*.yaml ]] \
    && is_in_cwd_top_level "$path"; then
    echo "this reviewer may persist its inferred layer map ($base)"
  elif [[ "$path" != *..* && ( "$path" == /tmp/* || "$path" == /private/tmp/* ) ]]; then
    echo "this reviewer may write scratch under /tmp ($path)"
  fi
}

# A Bash command is checked for the write forms it can use to
# reach repo source: a `>`/`>>` redirect, `tee`, and `sed -i`.
#
# The allowed targets are /dev/null and scratch under /tmp.
# A command with none of those forms (git diff, grep, a
# metrics script) passes with no approval output, so the
# normal permission flow still decides it.
#
# Known gap: a write hidden inside `bash -c`, a script, an
# interpreter (`python3 -c`) or `cp`/`mv` is not parsed - the
# guard is best-effort, not a sandbox.
#
# A target that starts with a shell variable cannot be
# resolved statically. It passes only when the variable is one
# of the review pipelines' mktemp scratch dirs; any other
# variable may hold $HOME or the repo, so it is denied.
#
# Known gap: the allowlist trusts the name, so a command that
# reassigns `work_dir=$PWD` first still passes.
CMD=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

# Variables the reviewer pipelines mint with mktemp under /tmp:
#   work_dir - code-review-pipeline/references/
#     wave1-context-prep.md and refactor/SKILL.md
#   RUN_DIR - quality-gate/SKILL.md
SCRATCH_DIR_VARS='work_dir|RUN_DIR'

# `$NAME/` or `${NAME}/`, then a rest with no further
# expansion, so `$work_dir2/x` and `${work_dir}x` fail.
SCRATCH_VAR_TARGET_REGEX='^\$(\{('"$SCRATCH_DIR_VARS"')\}|('"$SCRATCH_DIR_VARS"'))/[^$`]*$'

# Bash writes are narrower than Write/Edit: a verdict file is
# written with the Write tool, and a Bash redirect into one
# lands wherever a prior `cd` left the shell.
#
# A backslash is denied rather than modelled, since an escape
# such as `.\.` can still spell a `..` step.
bash_target_allowed() {
  local path="$1" rest
  [[ "$path" == /dev/null ]] && return 0
  [[ "$path" == *\\* ]] && return 1
  if [[ "$path" =~ $SCRATCH_VAR_TARGET_REGEX ]]; then
    rest=${path#*/}
  elif [[ "$path" == /tmp/* || "$path" == /private/tmp/* ]]; then
    rest=${path#/*tmp/}
  else
    return 1
  fi
  is_literal_path_below "$rest"
}

# Succeeds when a path below the scratch dir is plain literal
# text with no `..` segment, so it cannot hop out.
#
# A variable, substitution, glob, brace, tilde or extended
# glob is denied rather than modelled, since the shell may
# expand any of them into a `..` step or another directory.
#
# A `..` inside a name, as in `a..b.txt`, still passes.
is_literal_path_below() {
  local rest="$1"
  case "$rest" in
    *'$'* | *'`'* | *'*'* | *'?'* | *'['* | *'{'* | *'~'* | *'('*)
      return 1 ;;
  esac
  [[ "/$rest/" != */../* ]]
}

# Stand-ins for quoted text, so a quoted space or shell
# operator neither splits a word nor reads as a redirect.
SPACE_PLACEHOLDER=$'\001'
INERT_PLACEHOLDER=$'\002'

# Marks a spot where the hook's quote pairing may differ from
# the shell's, so a command that writes is denied there.
UNREADABLE_MARKER=$'\003'

# Prints the command with every quote removed in place. One
# pass pairs each quote with its real closing quote.
#
# - Quoted whitespace becomes SPACE_PLACEHOLDER.
# - A quoted shell operator becomes INERT_PLACEHOLDER.
# - A single-quoted dollar sign or backtick does too.
# - The dollar sign of an ANSI-C or locale quote is dropped.
#
# A backslash is kept with the character it escapes.
#
# A backslash-newline outside single quotes is dropped, since
# bash joins the two lines before it splits words, so
# `te\<newline>e` runs tee.
#
# A comment is kept as raw text up to its line break, since
# bash ends it there and reads no quote or backslash inside,
# so `#x\<newline>tee f` runs tee.
#
# UNREADABLE_MARKER is added for a substitution inside double
# quotes, a quote open at a line break, a quote never closed,
# and a quote or line-ending backslash inside a comment, in
# case the hook and the shell disagree on where a word starts.
remove_quotes() {
  printf '%s' "$1" | awk -v space="$SPACE_PLACEHOLDER" -v inert="$INERT_PLACEHOLDER" \
    -v unreadable="$UNREADABLE_MARKER" '
    function quoted(c, is_single) {
      if (index(" \t\n", c)) return space
      if (c ~ /[<>|;&()]/) return inert
      if (is_single && (c == "$" || c == "`")) return inert
      return c
    }

    # A quote inside a variable name ends that name for the
    # shell, so `"$"work_dir` and `$work_"dir"` must not fuse
    # into the `$work_dir` the scratch dir check trusts.
    function name_break(i) {
      if (out ~ /[$][{]?[A-Za-z0-9_]*$/ && substr(text, i + 1, 1) ~ /[A-Za-z0-9_{]/)
        return inert
      return ""
    }
    { text = text (NR > 1 ? "\n" : "") $0 }
    END {
      n = length(text)
      for (i = 1; i <= n; i++) {
        c = substr(text, i, 1)
        if (comment) {
          if (c == "\n") comment = 0
          else if (c == "\047" || c == "\"" || (c == "\\" && substr(text, i + 1, 1) == "\n"))
            out = out unreadable
          out = out c
          continue
        }
        if (state != "" && c == "\n") out = out unreadable
        if (state == "double" && (c == "`" || (c == "$" && substr(text, i + 1, 1) == "(")))
          out = out unreadable
        if (state == "single") {
          if (c == "\047") { state = ""; out = out name_break(i) }
          else out = out quoted(c, 1)
        } else if (c == "\\" && substr(text, i + 1, 1) == "\n") {
          i++
        } else if (c == "\\" && i < n) {
          i++
          out = out c quoted(substr(text, i, 1), 0)
        } else if (state == "double") {
          if (c == "\"") { state = ""; out = out name_break(i) }
          else out = out quoted(c, 0)
        } else if (c == "\047" || c == "\"") {
          state = (c == "\"") ? "double" : "single"
          if (substr(out, length(out)) == "$") out = substr(out, 1, length(out) - 1)
          out = out name_break(i)
        } else {
          if (c == "#" && (out == "" || substr(out, length(out)) ~ /[ \t\n;&|()<>`]/))
            comment = 1
          out = out c
        }
      }
      if (state != "") out = out unreadable
      printf "%s", out
    }'
}

# Drops a descriptor duplication such as `2>&1` or `>&-`.
#
# `>&word` duplicates only when the word is digits or `-`
# ending at a blank, the line end or a shell operator; any
# other word, as in `>&2src`, is a file the shell writes.
#
# The blanks are listed by hand, since [[:space:]] also holds
# characters bash keeps inside a word.
FD_DUP_SED='s/[0-9]*>&([0-9]+-?|-)([ '$'\t'';|&()<>]|$)/\2/g'

if [ -n "$CMD" ]; then
  # Quotes are removed first, so a target whose quote sits
  # anywhere in the word is judged as the path the shell uses.
  STRIPPED=$(remove_quotes "$CMD" | sed -E "$FD_DUP_SED")
  # The write form is read from the raw command, so a quote
  # paired wrongly cannot hide it.
  #
  # An ANSI-C quote, an UNREADABLE_MARKER spot or a heredoc
  # in a command that writes is denied rather than modelled.
  #
  # So is a blank other than space, tab or newline, such as a
  # carriage return: the target split below may end a word at
  # it, while bash keeps it inside the word.
  ODD_BLANK_LINES=$(printf '%s' "$CMD" | tr -d ' \t\n' | grep -c '[[:space:]]')
  if printf '%s' "$CMD" | sed -E "$FD_DUP_SED" \
      | grep -qE '>|(^|[^A-Za-z0-9_-])(tee|g?sed)([[:space:]]|$)' \
    && [[ "$CMD" == *"\$'"* || "$STRIPPED" == *"$UNREADABLE_MARKER"* \
      || "$STRIPPED" == *'<<'* || "$ODD_BLANK_LINES" != 0 ]]; then
    echo "Blocked: this reviewer's Bash command writes and holds quoting the hook cannot read safely (an ANSI-C quote, a substitution inside double quotes, a quote left open at a line break or the end, a heredoc, or a blank other than space, tab or newline); write with a plain one-line command instead" >&2
    exit 2
  fi

  # Bash drops a backslash inside an unquoted word, so `t\ee`
  # runs tee and `se\d` runs sed.
  #
  # The tee and sed -i checks below read the escaped text, so a
  # tee whose name holds an inner backslash is denied here, and
  # sed -i is matched on a copy with every backslash removed.
  UNESCAPED=${STRIPPED//\\/}
  ESCAPED_TEE_WORDS=$(printf '%s\n' "$STRIPPED" \
    | grep -oE '[A-Za-z0-9_\\-]*[A-Za-z0-9_-]\\[A-Za-z0-9_\\-]*' \
    | tr -d '\\' | grep -cx 'tee')
  if [ "$ESCAPED_TEE_WORDS" != 0 ]; then
    echo "Blocked: this reviewer's Bash names tee with a backslash inside the name; spell tee plainly" >&2
    exit 2
  fi
  TARGETS=$(printf '%s\n' "$STRIPPED" \
    | grep -oE '(&>>?|>>?\|?)[[:space:]]*[^[:space:]<>|;&)]*' \
    | sed -E 's/^(&>>?|>>?\|?)[[:space:]]*/T:/')
  TEE_ARGS=$(printf '%s\n' "$STRIPPED" \
    | grep -oE '(^|[^A-Za-z0-9_-])tee[[:space:]]+[^|;&]*' \
    | sed -E 's/^[^A-Za-z0-9_-]?tee[[:space:]]+//' | tr ' \t' '\n\n' | grep -v '^-')
  # Each redirect target carries a `T:` prefix, so a redirect
  # with no target is denied, not skipped as a blank line.
  while IFS= read -r target; do
    [ -z "$target" ] && continue
    target=${target#T:}
    target=${target//$SPACE_PLACEHOLDER/ }
    bash_target_allowed "$target" && continue
    echo "Blocked: this reviewer's Bash may write only to /dev/null or scratch under /tmp (attempted: ${target:-<empty target>})" >&2
    exit 2
  done <<< "$TARGETS"
  while IFS= read -r target; do
    [ -z "$target" ] && continue
    target=${target//$SPACE_PLACEHOLDER/ }
    bash_target_allowed "$target" && continue
    echo "Blocked: this reviewer's Bash may write only to /dev/null or scratch under /tmp (attempted: $target)" >&2
    exit 2
  done <<< "$TEE_ARGS"

  # GNU sed takes any unambiguous prefix of a long option, so
  # `--i` and `--in-pl` mean --in-place, per getopt_long:
  # https://www.gnu.org/software/sed/manual/sed.html#Command_002dLine-Options
  #
  # --in-place is its only long option starting with --i, so
  # `--i` needs no right edge, and a shell operator right
  # after it, as in `--i;`, cannot hide it.
  if printf '%s' "$UNESCAPED" | grep -qE '(^|[^A-Za-z0-9_-])g?sed[[:space:]]([^|;&]*[[:space:]])?(-[A-Za-z]*i|--i)'; then
    echo "Blocked: this reviewer may not edit files in place with sed -i" >&2
    exit 2
  fi
  exit 0
fi

FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
REASON=$(allowed_write_reason "$FILE_PATH")
if [ -n "$REASON" ]; then
  # Auto-approve: bypasses the permission prompt the background
  # subagent can't answer.
  jq -nc --arg reason "$REASON" \
    '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"allow",permissionDecisionReason:$reason}}'
  exit 0
fi

# Any other write target is a repo-source/artifact mutation -
# deny it outright.
echo "Blocked: this reviewer may write only verdict_*.md, verdict_*.html, layers_inferred_*.yaml in the working directory, or scratch under /tmp (attempted: ${FILE_PATH:-<no path>})" >&2
exit 2
