#!/usr/bin/env bash
# claude-markdown-standards-stop-hook - At review handoff, gate on doc-standards
#                            violations the AI/human just wrote in markdown, and
#                            report each offending file as a [Scout] task.
#
# Usage (Claude Code Stop hook):
#   stdin:  hook event JSON ({ session_id, stop_hook_active, ... })
#   stdout: optional JSON ({ decision: "block", reason: "..." }) to keep Claude going
#
# Three checkers, one gate — all are line-level doc-standards rules a Haiku fixes
# the same mechanical way, so they share one block instead of three competing ones:
#   - check-density.sh     line over 256 chars / 32 words → split it.
#   - check-bullet-gap.py  bullet with a sub-bullet, or over 80% of that cap,
#                          sitting flush against the next bullet → gap it.
#   - check-lazy-continuation.py  prose indented for an outer list item that the
#                          bullet above swallows → re-indent, gap, or reorder it.
#                          The other two only make a doc read worse; this one makes
#                          it render the opposite of what the source says, which is
#                          why it earns a place in the same blocking gate.
#
# Rationale:
#   The Stop event IS the review handoff — the AI finishes a turn and hands the
#   doc back to the human to read. Formatting nits fixed inline (PostToolUse) fork
#   the writing session's attention; fixed at commit they land too late (the human
#   reads before the commit). So this gate fires at Stop: if changed markdown still
#   violates, it blocks and tells the main agent to FILE ONE [Scout] TaskList entry
#   per offending file, naming what is off standard and which fixer would repair it.
#   Reporting (not dispatching, and not asking) is the point: not every edited .md
#   is the user's own doc to hold to personal doc-standards — e.g. a company/vendor
#   file the user merely touched — and a Stop hook has no interactive channel to ask
#   through, so an "ask the user" instruction just becomes the AI guessing. A [Scout]
#   defers the whole decision to the human, who triages if and when it ever runs.
#
# Scope — "everything THIS SESSION wrote/edited on .md", narrowed twice:
#   - Working-tree filter: which lines changed. Untracked .md (new spec/plan) →
#     the WHOLE file is new, every line is checked. Tracked, modified .md → only
#     lines changed vs HEAD (git diff -U0 intersection), so a PRE-EXISTING long
#     line in a file you merely touched never blocks — that would churn unrelated
#     lines into your commit.
#   - Session filter: which FILES this session's own Edit/Write/NotebookEdit
#     tool calls touched (read from transcript_path). A file dirty in the working
#     tree but never opened by this session's tools — another session's WIP, or
#     the human's own manual edit — is silently skipped.
#   Without the session filter, every concurrent session/subagent sees the same
#   shared working-tree violations and each independently files a [Scout] for
#   files it never touched — duplicate TaskList entries for one violation.
#   Scoping to this session's own tool calls is the deterministic fix: only the
#   session that actually wrote the violation is ever told to report it.
#
# Enforcement vs. loop-safety:
#   Honors stop_hook_active=true → bows out, so an always-on global hook can never
#   spin an infinite stop-block loop within one turn. Across turns the loop is
#   broken by the skip record below, NOT by the guard: the fix now happens whenever
#   the human runs the Scout, which can be days later or never, so the violation
#   itself outlives the block that reported it.
#
# Session memory:
#   Per-file reports persist in /tmp/claude-md-fixer-decisions-<session_id> — one
#   "skip:<abs path>" line per file, appended by the main session right after it
#   files that file's [Scout]. "skip" means "already reported as a Scout, do not
#   raise again this session" — NOT "the user declined to have it reformatted",
#   which is what it meant under the removed approval flow. On a later Stop in the
#   SAME session a skip-listed file is dropped from violations outright. The memory
#   is per-file, not per-session, so one reported doc never silences the gate for
#   every other file this session.
#
#   No session_id (or one with characters unsafe for a filename) means there is
#   nowhere to write that record, so this hook exits 0 instead of blocking: with no
#   way to suppress, every later Stop would re-block and the AI would file the same
#   Scout again each turn. A silent gate beats a duplicate-Scout loop.
#
# Safeguards (all silent no-ops — never break Claude on a tooling/context gap):
#   - jq / git / awk / comm missing, or BOTH checkers unavailable → exit 0.
#     One checker missing is not fatal: the other still gates on its own rule,
#     so a missing python3 degrades the gate instead of silently disabling it.
#   - Not inside a git work tree → exit 0 (no reliable "what changed" signal; the
#     documented corner — all five stack repos are git, so this is rare).
#   - No changed .md, or no violations on changed lines → exit 0.
#   - transcript_path missing/unreadable, or no Edit/Write/NotebookEdit calls in
#     it → exit 0 (fail open to "no block", NOT to the old whole-tree scope —
#     the session filter is what prevents the race, so a missing signal must
#     never fall back to scanning every uncommitted file again).
#
# NO env-var opt-out by design — a kill switch would let Claude silence its own
# doc-quality gate via a Bash call. To disable, remove this hook from settings.json.

set -eo pipefail

input=$(cat)

command -v jq   >/dev/null 2>&1 || exit 0
command -v git  >/dev/null 2>&1 || exit 0
command -v awk  >/dev/null 2>&1 || exit 0
command -v comm >/dev/null 2>&1 || exit 0

stop_hook_active=$(printf '%s' "$input" | jq -r '.stop_hook_active // false' 2>/dev/null || true)
[ "$stop_hook_active" = "true" ] && exit 0

# Per-file report memory for this session (see "Session memory" above).
#
# An empty session_id, or one with characters unsafe for a filename, leaves the
# hook nowhere to record that a file was already reported — and that record is the
# only thing that stops the next Stop from re-blocking. So it bows out entirely
# rather than re-file the same [Scout] every turn.
session_id=$(printf '%s' "$input" | jq -r '.session_id // empty' 2>/dev/null || true)
decisions_file=""
case "$session_id" in
  "" | *[!A-Za-z0-9_-]*) : ;;
  *) decisions_file="/tmp/claude-md-fixer-decisions-${session_id}" ;;
esac
[ -n "$decisions_file" ] || exit 0

git rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 0

# Session filter setup: which files did THIS session's own Edit/Write/
# NotebookEdit tool calls touch? Computed up front — no signal, no point
# scanning the working tree at all.
transcript_path=$(printf '%s' "$input" | jq -r '.transcript_path // empty' 2>/dev/null || true)
[ -n "$transcript_path" ] && [ -f "$transcript_path" ] || exit 0

session_files=$(jq -r '
    select(.message.content != null) | .message.content[]?
    | select(.type == "tool_use")
    | select(.name == "Edit" or .name == "Write" or .name == "NotebookEdit")
    | .input.file_path // empty
  ' "$transcript_path" 2>/dev/null | sort -u || true)
[ -n "$session_files" ] || exit 0

# Both git listings below are forced to repo-root-relative paths (`--full-name`
# for ls-files; the default for diff --name-only), so this anchors on the repo
# root rather than the session's cwd. Anchoring on cwd breaks whenever a session
# sits in a subdirectory: the paths resolve to files that don't exist, the
# session filter matches nothing, and the gate silently stops firing.
repo_root=$(git rev-parse --show-toplevel 2>/dev/null || true)
[ -n "$repo_root" ] || exit 0
# Run from the root too, so the relative paths git hands back also resolve for
# the checkers and for `git diff -U0`.
cd "$repo_root" 2>/dev/null || exit 0

to_abs() {
  case "$1" in
    /*) printf '%s\n' "$1" ;;
    *)  printf '%s/%s\n' "$repo_root" "$1" ;;
  esac
}

SCRIPTS="$HOME/.claude/skills/doc-standards/scripts"
DENSITY="$SCRIPTS/check-density.sh"
BULLET_GAP="$SCRIPTS/check-bullet-gap.py"
LAZY_CONT="$SCRIPTS/check-lazy-continuation.py"
CHANGED_LINES="$SCRIPTS/get-changed-lines.sh"

# Each checker is gated on its own availability, so one missing interpreter
# narrows the gate rather than dropping it.
[ -x "$DENSITY" ] || DENSITY=""
{ [ -x "$BULLET_GAP" ] && command -v python3 >/dev/null 2>&1; } || BULLET_GAP=""
{ [ -x "$LAZY_CONT" ] && command -v python3 >/dev/null 2>&1; } || LAZY_CONT=""
[ -n "$DENSITY$BULLET_GAP$LAZY_CONT" ] || exit 0

# Emit "path:line" for each violation that counts as "written/edited":
#   mode=whole → every violating line (untracked file; all lines are new)
#   mode=diff  → only violating lines that git shows as added/changed vs HEAD
#
# Every checker shares one output contract — "<line>:<detail>" rows under a
# "== <file>" header — so their reports concatenate and parse as one stream.
collect_file() {
  local f="$1" mode="$2"
  [ -f "$f" ] || return 0

  local vlines
  vlines=$(
    {
      [ -n "$DENSITY" ]    && { "$DENSITY"    "$f" 2>/dev/null || true; }
      [ -n "$BULLET_GAP" ] && { "$BULLET_GAP" "$f" 2>/dev/null || true; }
      [ -n "$LAZY_CONT" ]  && { "$LAZY_CONT"  "$f" 2>/dev/null || true; }
      # An unset checker leaves the group's status at 1, which pipefail would
      # turn into a set -e exit — so close on an unconditional success.
      true
    } | awk -F: '/^[0-9]+:/ {print $1}' | sort -un
  )
  [ -n "$vlines" ] || return 0

  if [ "$mode" = "whole" ]; then
    printf '%s\n' "$vlines" | awk -v f="$f" 'NF {print f ":" $0}'
    return 0
  fi

  # Missing/failing helper narrows this file to no diff hits, same
  # "narrow, don't drop" gate as the checkers above (whole-mode is safe).
  local added
  added=$("$CHANGED_LINES" "$f" 2>/dev/null || true)
  [ -n "$added" ] || return 0

  comm -12 \
    <(printf '%s\n' "$vlines" | sort -u) \
    <(printf '%s\n' "$added"  | sort -u) \
    | awk -v f="$f" 'NF {print f ":" $0}'
}

violations=""

# Untracked .md — whole file is "written".
while IFS= read -r -d '' f; do
  [ -n "$f" ] || continue
  res=$(collect_file "$f" whole || true)
  [ -n "$res" ] && violations+="$res"$'\n'
done < <(git ls-files --full-name --others --exclude-standard -z -- '*.md' 2>/dev/null || true)

# Tracked, changed vs HEAD — only changed lines.
while IFS= read -r -d '' f; do
  [ -n "$f" ] || continue
  res=$(collect_file "$f" diff || true)
  [ -n "$res" ] && violations+="$res"$'\n'
done < <(git diff --name-only -z HEAD -- '*.md' 2>/dev/null || true)

violations=$(printf '%s' "$violations" | sed '/^$/d' | sort -u)
[ -z "$violations" ] && exit 0

# Keep only violations in files this session's own tool calls wrote — a file
# dirty in the working tree that this session never opened (another session's
# WIP, or a manual edit) is not this session's problem to fix.
violations=$(printf '%s\n' "$violations" | while IFS= read -r v; do
  [ -n "$v" ] || continue
  vf_abs=$(to_abs "${v%%:*}")
  printf '%s\n' "$session_files" | grep -qxF "$vf_abs" && printf '%s\n' "$v"
# A final non-match leaves grep's 1 as the loop's status, which set -e would
# turn into a non-zero hook exit — an "error" reading of the ordinary
# nothing-to-block case.
done || true)
[ -z "$violations" ] && exit 0

# Drop files already reported as a [Scout] this session — see "Session memory"
# above. A "delegate:" line from a session that ran the older approval flow parses
# to no verb this hook knows, so it is inert rather than special-cased away.
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

# Single-char delimiter: `paste -d` cycles through a multi-char list, so ', '
# would alternate comma and space instead of joining with both.
list=$(printf '%s\n' "$violations" | paste -sd ',' -)

# Kept minimal on purpose: this string is injected into the MAIN session context on
# every block, and a Stop can block repeatedly — a verbose reason would accumulate and
# crowd out real work. WHICH rule each line broke is deliberately omitted: whoever runs
# the Scout re-runs both checkers anyway, so naming them here would only pad every block.
reason="Markdown you edited this session is off doc-standards — ${list}. \
File ONE [Scout] TaskList entry per file, describing what is off standard and that a Haiku \
(claude-haiku-4-5) markdown-standards-fixer subagent is what repairs it. Dispatch nothing now \
and ask nothing — the user alone decides if and when a Scout runs. Then append \
'skip:<abs path>' for each file to ${decisions_file}."

jq -n --arg r "$reason" '{decision: "block", reason: $r}'
