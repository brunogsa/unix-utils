#!/usr/bin/env bash
# claude-density-stop-hook - At review handoff, gate on markdown density violations
#                            the AI/human just wrote, and delegate the fix to Haiku.
#
# Usage (Claude Code Stop hook):
#   stdin:  hook event JSON ({ session_id, stop_hook_active, ... })
#   stdout: optional JSON ({ decision: "block", reason: "..." }) to keep Claude going
#
# Rationale:
#   The Stop event IS the review handoff — the AI finishes a turn and hands the
#   doc back to the human to read. Density nits fixed inline (PostToolUse) fork the
#   writing session's attention; fixed at commit they land too late (the human reads
#   before the commit). So this gate fires at Stop: if changed markdown still has
#   density violations, it blocks and tells the main agent to spawn a cheap Haiku
#   subagent to split the offending lines — off the main thread — so the human reads
#   a clean doc with zero main-session churn.
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
#   the hook itself can't re-verify the fix — so the Haiku subagent re-runs
#   check-density and confirms clean BEFORE returning. Verification lives in the
#   subagent — NOT the main session, which must trust the subagent and never re-read
#   the files or re-run the gate: doing so would pull the density detail back into the
#   main context, defeating the whole point of offloading it to a subagent.
#
# Safeguards (all silent no-ops — never break Claude on a tooling/context gap):
#   - jq / git / awk / comm missing, or check-density.sh absent → exit 0.
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

hook_cwd=$(printf '%s' "$input" | jq -r '.cwd // empty' 2>/dev/null || true)
[ -n "$hook_cwd" ] || hook_cwd=$(pwd)

to_abs() {
  case "$1" in
    /*) printf '%s\n' "$1" ;;
    *)  printf '%s/%s\n' "$hook_cwd" "$1" ;;
  esac
}

DENSITY="$HOME/.claude/skills/doc-standards/scripts/check-density.sh"
[ -x "$DENSITY" ] || exit 0

# Emit "path:line" for each density violation that counts as "written/edited":
#   mode=whole → every violating line (untracked file; all lines are new)
#   mode=diff  → only violating lines that git shows as added/changed vs HEAD
collect_file() {
  local f="$1" mode="$2"
  [ -f "$f" ] || return 0

  local dens vlines
  dens=$("$DENSITY" "$f" 2>/dev/null || true)
  vlines=$(printf '%s\n' "$dens" | awk -F: '/^[0-9]+:/ {print $1}')
  [ -n "$vlines" ] || return 0

  if [ "$mode" = "whole" ]; then
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

# Untracked .md — whole file is "written".
while IFS= read -r -d '' f; do
  [ -n "$f" ] || continue
  res=$(collect_file "$f" whole || true)
  [ -n "$res" ] && violations+="$res"$'\n'
done < <(git ls-files --others --exclude-standard -z -- '*.md' 2>/dev/null || true)

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
done)
[ -z "$violations" ] && exit 0

list=$(printf '%s\n' "$violations" | paste -sd ', ' -)

# Kept minimal on purpose: this string is injected into the MAIN session context on
# every block, and a Stop can block repeatedly — a verbose reason would accumulate and
# crowd out real work. Detail (how to split, don't-loop) is left to the Haiku subagent.
reason="Density: .md you edited this session is over the 256/32 cap — ${list}. \
Delegate the split to a Haiku (claude-haiku-4-5) subagent; it self-verifies with check-density. \
Do not re-read in this session — trust the subagent."

jq -n --arg r "$reason" '{decision: "block", reason: $r}'
