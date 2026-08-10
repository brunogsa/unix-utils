#!/usr/bin/env bash
# claude-comment-format-stop-hook - At review handoff, gate
#                    on doc-standards comment-format caps
#                    THIS session just broke in source files.
#
# Usage (Claude Code Stop hook):
#   stdin:  hook event JSON (session_id, stop_hook_active,
#           transcript_path)
#   stdout: optional {decision, reason} JSON, to keep going
#
# One checker, one gate:
# - check-comment-format.js  the six comment-format caps
#     WIDTH, PARAGRAPH, SENTENCE-BREAK, BULLET-SPACING,
#     BULLET-BLANK, CODE-GAP.
#
# Rationale:
#   doc-standards tells the model to verify these caps with
#   that script, and nothing enforced it.
#
#   A sweep over this repo's 125 source files found 2681
#   violations across 105 of them, written by sessions that
#   had doc-standards loaded at the time.
#
#   The script scores zero against itself, so the caps are
#   followable; they were simply never checked. That is the
#   [Harness] case CLAUDE.md says to wire into the harness
#   rather than leave to the model remembering it.
#
#   Stop is the review handoff: a formatting nit fixed at
#   PostToolUse forks the writing session's attention, and
#   one fixed at commit lands after the human already read
#   the file.
#
# Scope - "source comments THIS SESSION wrote", narrowed
# twice, the same two filters the markdown gate uses:
#
# - Working-tree filter: untracked source file (all of it
#     is new) checks every line; tracked file intersects
#     violating lines with `git diff -U0 HEAD` added lines.
#
# - Session filter: only files this session's own Edit/
#     Write/NotebookEdit calls touched, read from
#     transcript_path.
#
#   Without the session filter every concurrent session sees
#   the same shared working-tree violations and each spawns
#   its own fixer for files it never touched - a race
#   between two fixers editing one file.
#
# Which rules gate on a changed line:
#   A tracked file admits only the rules whose fix stays on
#   the flagged line: WIDTH, BULLET-SPACING, BULLET-BLANK,
#   CODE-GAP.
#
#   PARAGRAPH carries a line RANGE and SENTENCE-BREAK needs
#   rewording that `--fix` refuses, so both would demand
#   rewriting lines this session never wrote - the churn the
#   diff filter exists to prevent.
#
#   An untracked file is new in full, so all six gate there:
#   no line in it predates this session.
#
# Known limitation - subagent writes are invisible:
#   transcript_path names the MAIN session's tool calls, and
#   a subagent's Edit lands in its own transcript instead.
#
#   So a file written entirely by a dispatched agent never
#   reaches this gate.
#
#   Widening the discovery source to the working tree would
#   bring back the cross-session race the session filter
#   exists to stop, so the narrower reach is a deliberate
#   trade, shared with both sibling gates.
#
# Enforcement vs. loop-safety:
#   Honors stop_hook_active=true, bowing out so an always-on
#   global hook can never spin an infinite stop-block loop.
#
#   The guard bails on the post-fix stop, so this hook can
#   never re-verify its own fix - the fixer subagent re-runs
#   the checker and confirms clean before returning.
#
# Safeguards (silent no-ops - never break Claude on a
# tooling or context gap):
# - jq / git / awk / comm / node missing, or the checker
#     missing, exits 0.
#
# - Not inside a git work tree exits 0: no reliable
#     "what changed" signal.
#
# - transcript_path missing or naming no write calls exits
#     0, failing open to "no block" rather than to the whole
#     working tree.
#
# - The checker exits 2 on an unreadable language or a
#     missing TypeScript scanner, printing no violation rows,
#     so that file drops out instead of failing the run.
#
# NO env-var opt-out by design - a kill switch would let
# Claude silence its own comment-quality gate through a Bash
# call. To disable, remove this leg from the orchestrator.

set -eo pipefail

input=$(cat)

command -v jq   >/dev/null 2>&1 || exit 0
command -v git  >/dev/null 2>&1 || exit 0
command -v awk  >/dev/null 2>&1 || exit 0
command -v comm >/dev/null 2>&1 || exit 0
command -v node >/dev/null 2>&1 || exit 0

stop_hook_active=$(printf '%s' "$input" | jq -r '.stop_hook_active // false' 2>/dev/null || true)
[ "$stop_hook_active" = "true" ] && exit 0

CHECKER="$HOME/.claude/skills/doc-standards/scripts/check-comment-format.js"
[ -f "$CHECKER" ] || exit 0

git rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 0

transcript_path=$(printf '%s' "$input" | jq -r '.transcript_path // empty' 2>/dev/null || true)
[ -n "$transcript_path" ] && [ -f "$transcript_path" ] || exit 0

session_files=$(jq -r '
    select(.message.content != null) | .message.content[]?
    | select(.type == "tool_use")
    | select(.name == "Edit" or .name == "Write" or .name == "NotebookEdit")
    | .input.file_path // empty
  ' "$transcript_path" 2>/dev/null | sort -u || true)
[ -n "$session_files" ] || exit 0

# Both git listings below emit repo-root-relative paths, so
# this anchors on the repo root rather than the session's
# cwd.
#
# Anchoring on cwd breaks whenever a session sits in a
# subdirectory: the paths resolve to files that do not exist
# and the gate silently stops firing.
repo_root=$(git rev-parse --show-toplevel 2>/dev/null || true)
[ -n "$repo_root" ] || exit 0
cd "$repo_root" 2>/dev/null || exit 0

to_abs() {
  case "$1" in
    /*) printf '%s\n' "$1" ;;
    *)  printf '%s/%s\n' "$repo_root" "$1" ;;
  esac
}

# The checker resolves language by extension first, so the
# listing is restricted to the extensions it knows.
#
# An extensionless script it would resolve by shebang is out
# of reach here, since git has no shebang to glob on.
SOURCE_GLOBS=(
  '*.ts' '*.tsx' '*.mts' '*.cts'
  '*.js' '*.jsx' '*.mjs' '*.cjs'
  '*.sh' '*.py'
)

# Emit "path:line" per violation that counts as written:
#   mode=whole - every violating line, all six rules
#   mode=diff  - line-local rules only, intersected with the
#                lines git shows as added vs HEAD
#
# One checker run per file, never a batch: a file the
# checker cannot resolve exits 2 and would take every other
# file in the same invocation down with it.
collect_file() {
  local f=$1 mode=$2 whole=0
  [ -f "$f" ] || return 0
  [ "$mode" = "whole" ] && whole=1

  # Rows are "<RULE> <line>", with WIDTH and PARAGRAPH
  # carrying a ":<detail>" suffix and PARAGRAPH a "<start>-
  # <end>" range. Stripping both leaves the anchor line.
  local vlines
  vlines=$(node "$CHECKER" "$f" 2>/dev/null | awk -v whole="$whole" '
      /^== / { next }
      {
        line = $2;
        sub(/:.*$/, "", line);
        sub(/-.*$/, "", line);
        if (line !~ /^[0-9]+$/) next;
        if (whole == 0 && ($1 == "PARAGRAPH" || $1 == "SENTENCE-BREAK")) next;
        print line;
      }' | sort -un || true)
  [ -n "$vlines" ] || return 0

  if [ "$whole" = "1" ]; then
    printf '%s\n' "$vlines" | awk -v f="$f" 'NF {print f ":" $0}'
    return 0
  fi

  local added
  added=$(git diff -U0 HEAD -- "$f" 2>/dev/null | awk '
    /^@@ / {
      plus = $3; sub(/^\+/, "", plus);
      n = split(plus, a, ",");
      start = a[1] + 0; cnt = (n > 1 ? a[2] + 0 : 1);
      for (i = 0; i < cnt; i++) print start + i;
    }' || true)
  [ -n "$added" ] || return 0

  comm -12 \
    <(printf '%s\n' "$vlines" | sort -u) \
    <(printf '%s\n' "$added"  | sort -u) \
    | awk -v f="$f" 'NF {print f ":" $0}'
}

violations=""

while IFS= read -r -d '' f; do
  [ -n "$f" ] || continue
  res=$(collect_file "$f" whole || true)
  [ -n "$res" ] && violations+="$res"$'\n'
done < <(git ls-files --full-name --others --exclude-standard -z -- "${SOURCE_GLOBS[@]}" 2>/dev/null || true)

while IFS= read -r -d '' f; do
  [ -n "$f" ] || continue
  res=$(collect_file "$f" diff || true)
  [ -n "$res" ] && violations+="$res"$'\n'
done < <(git diff --name-only -z HEAD -- "${SOURCE_GLOBS[@]}" 2>/dev/null || true)

violations=$(printf '%s' "$violations" | sed '/^$/d' | sort -u)
[ -z "$violations" ] && exit 0

# Keep only files this session's own tool calls wrote. A
# file dirty in the working tree that this session never
# opened is another session's WIP, not this one's to fix.
violations=$(printf '%s\n' "$violations" | while IFS= read -r v; do
  [ -n "$v" ] || continue
  vf_abs=$(to_abs "${v%%:*}")
  printf '%s\n' "$session_files" | grep -qxF "$vf_abs" && printf '%s\n' "$v"

# A final non-match leaves grep's 1 as the loop's status,
# which set -e would read as an error rather than as the
# ordinary nothing-to-block case.
done || true)
[ -z "$violations" ] && exit 0

# Named by file plus a count, never line by line: this
# string is injected into the MAIN session context on every
# block, and a new file can carry dozens of WIDTH hits.
#
# The fixer re-runs the checker anyway, so the lines and the
# rule names would only pad every block.
list=$(printf '%s\n' "$violations" | awk -F: '
  {
    if (!($1 in count)) order[++n] = $1;
    count[$1]++;
  }
  END {
    for (k = 1; k <= n; k++)
      printf "%s%s (%d)", (k > 1 ? ", " : ""), order[k], count[order[k]];
  }
')

files=$(printf '%s\n' "$violations" | awk -F: '{print $1}' | sort -u | paste -sd ' ' -)

# --fix runs before the subagent for the same reason
# doc-standards puts fix-density.py before its markdown
# fixer: it repairs the mechanical subset in one pass, where
# an AI fixer burns turns re-deriving the same edits.
reason="Source comments you edited this session break doc-standards' comment-format caps — ${list}. \
Run: node ~/.claude/skills/doc-standards/scripts/check-comment-format.js --fix ${files} \
Then dispatch a Haiku (claude-haiku-4-5) comment-format-fixer subagent for whatever it still \
reports. Do not re-read the files in this session — trust the subagent."

jq -n --arg r "$reason" '{decision: "block", reason: $r}'
