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
#   Once a still-violating file clears the two scope filters
#   below, the hook blocks and tells the main agent to file
#   ONE [Scout] TaskList entry per offending file.
#
#   Reporting rather than dispatching matters because not
#   every edited source file is the user's own code to hold
#   to personal comment-format caps - e.g. a vendored or
#   generated file the user merely touched.
#
#   Asking at hook time is no substitute: a Stop hook has no
#   interactive channel, so "ask the user" degrades into the
#   agent guessing.
#
#   A [Scout] hands the whole call to the human, who triages
#   if and when it ever runs.
#
# Repo scope - only this repo's own sources:
#   The caps above are the user's personal standards,
#   so only sources in the repo this hook itself
#   lives in are the user's to hold to them.
#
#   A block raised anywhere else - a client repo, a
#   vendored tree - is noise the user asked to be rid
#   of.
#
#   lib/gate-repo-scope.sh derives that repo from its
#   own location, so nothing here spells out a path.
#
#   It fails closed: a copy outside any git work tree
#   gates nothing, and a missing lib exits 0.
#
#   The check runs before the transcript parse, the
#   most expensive step a session outside this repo
#   would otherwise pay for nothing.
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
#   the same shared working-tree violations and each files
#   its own [Scout] for files it never touched - duplicate
#   TaskList entries for one violation.
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
#   bring back the cross-session duplication the session
#   filter exists to stop, so the narrower reach is a
#   deliberate trade, shared with both sibling gates.
#
# Session memory:
#   Per-file reports persist in /tmp/claude-comment-fixer-
#   decisions-<session_id> as one "skip:<abs path>" line per
#   file.
#
#   Appended by the main session right after it files that
#   file's [Scout].
#
#   "skip" means "already reported as a Scout, do not raise
#   again this session" - NOT "the user declined to have it
#   reformatted", which is what it meant under the removed
#   approval flow.
#
#   On a later Stop in the SAME session a skip-listed file is
#   dropped from violations outright.
#
#   This is per-file, not per-session - one reported file must
#   not silence the gate for every other file this session.
#
# Enforcement vs. loop-safety:
#   Honors stop_hook_active=true, bowing out so an always-on
#   global hook can never spin an infinite stop-block loop
#   within one turn.
#
#   Across turns the skip record is what breaks the loop, not
#   that guard: the fix now happens whenever the human runs
#   the Scout, which can be days later or never, so the
#   violation outlives the block that reported it.
#
# Safeguards (silent no-ops - never break Claude on a
# tooling or context gap):
# - jq / git / awk / comm / node missing, or the checker
#     missing, exits 0.
#
# - No session_id, or one with characters unsafe for a
#     filename, exits 0: there is nowhere to record the skip,
#     and blocking without it would re-file the same Scout on
#     every later Stop.
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

# Per-file report memory for this session (see the Session
# memory section above).
#
# An empty session_id, or one with characters unsafe for a
# filename, leaves the hook nowhere to record that a file was
# already reported - and that record is the only thing that
# stops the next Stop from re-blocking.
#
# So it bows out entirely rather than re-file the same
# [Scout] every turn.
session_id=$(printf '%s' "$input" | jq -r '.session_id // empty' 2>/dev/null || true)
decisions_file=""
case "$session_id" in
  "" | *[!A-Za-z0-9_-]*) : ;;
  *) decisions_file="/tmp/claude-comment-fixer-decisions-${session_id}" ;;
esac
[ -n "$decisions_file" ] || exit 0

CHECKER="$HOME/.claude/skills/doc-standards/scripts/check-comment-format.js"
[ -f "$CHECKER" ] || exit 0

CHANGED_LINES="$HOME/.claude/skills/doc-standards/scripts/get-changed-lines.sh"

git rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 0

# Both git listings below emit repo-root-relative paths, so
# this anchors on the repo root rather than the session's
# cwd.
#
# Anchoring on cwd breaks whenever a session sits in a
# subdirectory: the paths resolve to files that do not exist
# and the gate silently stops firing.
repo_root=$(git rev-parse --show-toplevel 2>/dev/null || true)
[ -n "$repo_root" ] || exit 0

# Repo scope, resolved before the transcript parse (see the
# header): a session in any other repo pays none of it.
#
# It also sits before the cd below, because BASH_SOURCE
# carries whatever path the caller typed: a relative one
# resolves against the cwd the hook started in, so moving
# first would aim the gate at the wrong directory.
#
# A missing lib exits 0 like every other tooling-gap
# safeguard here.
gate_lib="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd -P)/lib/gate-repo-scope.sh"
[ -f "$gate_lib" ] || exit 0

# shellcheck source-path=SCRIPTDIR
# shellcheck source=lib/gate-repo-scope.sh
. "$gate_lib"
is_gated_repo "$repo_root" || exit 0

cd "$repo_root" 2>/dev/null || exit 0

transcript_path=$(printf '%s' "$input" | jq -r '.transcript_path // empty' 2>/dev/null || true)
[ -n "$transcript_path" ] && [ -f "$transcript_path" ] || exit 0

session_files=$(jq -r '
    select(.message.content != null) | .message.content[]?
    | select(.type == "tool_use")
    | select(.name == "Edit" or .name == "Write" or .name == "NotebookEdit")
    | .input.file_path // empty
  ' "$transcript_path" 2>/dev/null | sort -u || true)
[ -n "$session_files" ] || exit 0

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

  # Missing/failing helper narrows this file to no diff hits,
  # never drops the gate for other files (whole-mode is safe).
  local added
  added=$("$CHANGED_LINES" "$f" 2>/dev/null || true)
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

# Drop files already reported as a [Scout] this session - see
# "Session memory" above.
#
# A "delegate:" line from a session that ran the older
# approval flow parses to no verb this hook knows, so it is
# inert rather than special-cased away.
decided_skip=""
if [ -f "$decisions_file" ]; then
  decided_skip=$(awk -F: '$1 == "skip" {print $2}' "$decisions_file" 2>/dev/null | sort -u || true)
fi

if [ -n "$decided_skip" ]; then
  violations=$(printf '%s\n' "$violations" | while IFS= read -r v; do
    [ -n "$v" ] || continue
    vf_abs=$(to_abs "${v%%:*}")
    printf '%s\n' "$decided_skip" | grep -qxF "$vf_abs" || printf '%s\n' "$v"
  done || true)
fi
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

# Kept minimal on purpose: this string is injected into the
# MAIN session context on every block, and a Stop can block
# repeatedly - a verbose reason would accumulate and crowd
# out real work.
#
# The --fix command rides inside the Scout's description
# rather than running here.
#
# Same reason doc-standards puts fix-density.py before its
# markdown fixer: it repairs the mechanical subset in one
# pass, where an AI fixer burns turns re-deriving the same
# edits.
#
# Carrying it in the description is what keeps that
# deterministic first pass available to whoever runs the
# Scout, now that no branch of this hook runs it.
reason="Source comments you edited this session break doc-standards' comment-format caps — ${list}. \
File ONE [Scout] TaskList entry per file, describing the broken caps and its repair: run \
'node ~/.claude/skills/doc-standards/scripts/check-comment-format.js --fix --changed-only <file>' first, then a Haiku \
(claude-haiku-4-5) comment-format-fixer subagent for whatever it still reports. Dispatch nothing now, \
run nothing now, and ask nothing — the user alone decides if and when a Scout runs. Then append \
'skip:<abs path>' for each file to ${decisions_file}."

jq -n --arg r "$reason" '{decision: "block", reason: $r}'
