#!/usr/bin/env bash
# claude-markdown-standards-stop-hook - At review handoff, gate on doc-standards
#                            violations the AI/human just wrote in markdown, and
#                            delegate the fix to Haiku.
#
# Usage (Claude Code Stop hook):
#   stdin:  hook event JSON ({ session_id, stop_hook_active, ... })
#   stdout: optional JSON ({ decision: "block", reason: "..." }) to keep Claude going
#
# Two checkers, one gate — both are line-level doc-standards rules a Haiku fixes
# the same mechanical way, so they share one block instead of two competing ones:
#   - check-density.sh     line over 256 chars / 32 words → split it.
#   - check-bullet-gap.py  bullet with a sub-bullet, or over 80% of that cap,
#                          sitting flush against the next bullet → gap it.
#
# Rationale:
#   The Stop event IS the review handoff — the AI finishes a turn and hands the
#   doc back to the human to read. Formatting nits fixed inline (PostToolUse) fork
#   the writing session's attention; fixed at commit they land too late (the human
#   reads before the commit). So this gate fires at Stop: if changed markdown still
#   violates, it blocks and tells the main agent to ASK the user before spawning a
#   cheap Haiku subagent to fix the offending lines — off the main thread — so the
#   human reads a clean doc with zero main-session churn.
#   Asking first (not auto-dispatching) matters because not every edited .md is the
#   user's own doc to hold to personal doc-standards — e.g. a company/vendor file
#   the user merely touched. If the main agent can't ask (no interactive channel),
#   it skips the fixer rather than guessing.
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
#   shared working-tree violations and each independently spawns a Haiku fixer
#   for files it never touched — redundant work at best, a race between two
#   fixers editing the same file at worst. Scoping to this session's own tool
#   calls is the deterministic fix: only the session that actually wrote the
#   violation is ever told to clean it up.
#
# Enforcement vs. loop-safety:
#   Honors stop_hook_active=true → bows out, so an always-on global hook can never
#   spin an infinite stop-block loop. Because the guard bails on the post-fix stop,
#   the hook itself can't re-verify the fix — so the Haiku subagent re-runs both
#   checkers and confirms clean BEFORE returning. Verification lives in the
#   subagent — NOT the main session, which must trust the subagent and never re-read
#   the files or re-run the gate: doing so would pull the density detail back into the
#   main context, defeating the whole point of offloading it to a subagent.
#
# Session memory:
#   Per-file answers persist in /tmp/claude-md-fixer-decisions-<session_id> —
#   one "delegate:<abs path>" or "skip:<abs path>" line per file, appended by
#   the main session right after the user answers for that file. On a later
#   Stop in the SAME session: a "skip" file is dropped from violations outright
#   (never re-blocked), and a "delegate" file's block wording says to delegate
#   directly instead of asking again. A file with no recorded answer is asked
#   about exactly as before. This is why the memory is per-file, not per-session
#   — one company doc being declined must not silence the gate for every other
#   file this session.
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

# Per-file answer memory for this session (see "Session memory" below). Empty
# session_id (or one with characters unsafe for a filename) just disables the
# memory — the hook still gates, it only re-asks every time instead of once.
session_id=$(printf '%s' "$input" | jq -r '.session_id // empty' 2>/dev/null || true)
decisions_file=""
case "$session_id" in
  "" | *[!A-Za-z0-9_-]*) : ;;
  *) decisions_file="/tmp/claude-md-fixer-decisions-${session_id}" ;;
esac

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
CHANGED_LINES="$SCRIPTS/get-changed-lines.sh"

# Each checker is gated on its own availability, so one missing interpreter
# narrows the gate rather than dropping it.
[ -x "$DENSITY" ] || DENSITY=""
{ [ -x "$BULLET_GAP" ] && command -v python3 >/dev/null 2>&1; } || BULLET_GAP=""
[ -n "$DENSITY$BULLET_GAP" ] || exit 0

# Emit "path:line" for each violation that counts as "written/edited":
#   mode=whole → every violating line (untracked file; all lines are new)
#   mode=diff  → only violating lines that git shows as added/changed vs HEAD
#
# Both checkers share one output contract — "<line>:<detail>" rows under a
# "== <file>" header — so their reports concatenate and parse as one stream.
collect_file() {
  local f="$1" mode="$2"
  [ -f "$f" ] || return 0

  local vlines
  vlines=$(
    {
      [ -n "$DENSITY" ]    && { "$DENSITY"    "$f" 2>/dev/null || true; }
      [ -n "$BULLET_GAP" ] && { "$BULLET_GAP" "$f" 2>/dev/null || true; }
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

# Drop files the user already declined this session — see "Session memory" above.
decided_skip=""
decided_delegate=""
if [ -n "$decisions_file" ] && [ -f "$decisions_file" ]; then
  decided_skip=$(awk -F: '$1 == "skip" {print $2}' "$decisions_file" 2>/dev/null | sort -u || true)
  decided_delegate=$(awk -F: '$1 == "delegate" {print $2}' "$decisions_file" 2>/dev/null | sort -u || true)
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

# Split the still-violating files into "already told us to delegate this
# session" (ask nothing, just delegate) vs "no recorded answer yet" (ask once).
new_files=""
approved_files=""
while IFS= read -r f; do
  [ -n "$f" ] || continue
  f_abs=$(to_abs "$f")
  if [ -n "$decided_delegate" ] && printf '%s\n' "$decided_delegate" | grep -qxF "$f_abs"; then
    approved_files="${approved_files}${f}, "
  else
    new_files="${new_files}${f}, "
  fi
done <<< "$(printf '%s\n' "$violations" | awk -F: '{print $1}' | sort -u)"
approved_files="${approved_files%, }"
new_files="${new_files%, }"

# Kept minimal on purpose: this string is injected into the MAIN session context on
# every block, and a Stop can block repeatedly — a verbose reason would accumulate and
# crowd out real work. WHICH rule each line broke is deliberately omitted: the fixer
# re-runs both checkers anyway, so naming them here would only pad every block.
reason="Markdown you edited this session is off doc-standards — ${list}."

if [ -n "$approved_files" ]; then
  reason="${reason} Already approved this session — delegate directly, no need to ask again: ${approved_files}."
fi

if [ -n "$new_files" ]; then
  reason="${reason} Ask the user whether to delegate ${new_files} to a Haiku (claude-haiku-4-5) \
markdown-standards-fixer subagent — some edited .md isn't yours to reformat (e.g. a company doc). \
If you can't ask here, skip the fixer for it."
  if [ -n "$decisions_file" ]; then
    reason="${reason} Record the answer so it isn't asked again this session: append \
'delegate:<abs path>' or 'skip:<abs path>' to ${decisions_file}."
  fi
fi

reason="${reason} Delegated files self-verify with check-density and check-bullet-gap. Do not \
re-read in this session — trust the subagent."

jq -n --arg r "$reason" '{decision: "block", reason: $r}'
