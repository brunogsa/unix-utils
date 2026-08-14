#!/bin/bash
# claude-git-guard - Block non-reversible git operations and unattributed commits
#
# Usage (Claude Code PreToolUse hook):
#   Reads JSON from stdin, exits 2 to block, 0 to allow
#
# Blocks:
#   git push --force/-f, git push -f (non-reversible)
#   git reset --hard (non-reversible)
#   git clean -f/-fd/-fx (non-reversible)
#   git worktree remove --force (discards a dirty worktree's uncommitted changes)
#   git branch -D (non-reversible)
#   git checkout . / git restore . (bulk discard)
#   git commit --amend (must create new commits)
#   aigitcommit (human-only tool)
#   git commit without Co-Authored-By: Claude attribution
#
# Every "is this a dangerous invocation" check below matches against
# CMD_STRUCT, not the raw command: heredoc bodies fed to a non-executing
# sink (cat, python3) are dropped, and quoted-string contents are blanked
# to a placeholder. Otherwise text that only ever appears as *data* — a
# scratchpad doc line mentioning "git commit", a test string containing
# "aigitcommit" — reads as a real invocation. Heredocs fed to a shell
# (bash, sh, ssh) are left unstripped, since those genuinely execute an
# embedded git command. The one exception is the Co-Authored-By search
# a few lines down, which must look at the RAW command: that's the
# actual commit message text, which always lives inside quotes.
#
# Examples:
#   echo '{"tool_input":{"command":"git push --force"}}' | bash claude-git-guard.sh  # blocked
#   echo '{"tool_input":{"command":"git status"}}' | bash claude-git-guard.sh        # allowed

CMD=$(jq -r '.tool_input.command // empty')

if [ -z "$CMD" ]; then
  exit 0
fi

CMD_STRUCT=$(printf '%s\n' "$CMD" | python3 -c '
import re, sys

def blank_quotes(line):
    out, state, j, n = [], None, 0, len(line)
    while j < n:
        c = line[j]
        if state is None:
            out.append(c)
            if c in ("\x27", "\""):
                state = c
        elif state == "\x27":
            out.append("x" if c != "\x27" else c)
            if c == "\x27":
                state = None
        else:
            if c == "\\" and j + 1 < n:
                out.append("xx")
                j += 2
                continue
            out.append("x" if c != "\"" else c)
            if c == "\"":
                state = None
        j += 1
    return "".join(out)

lines = sys.stdin.read().split("\n")
heredoc_open = re.compile(r"<<-?\s*([\"\x27]?)(\w+)\1")
safe_sink = re.compile(r"(^|[;&|(`]|\s)(cat|python3?)\b")
out = []
i = 0
while i < len(lines):
    line = lines[i]
    m = heredoc_open.search(line)
    out.append(blank_quotes(line))
    i += 1
    if not m or not safe_sink.search(line[:m.start()]):
        continue
    strip_tabs = line[m.start():m.start() + 3] == "<<-"
    delim = m.group(2)
    while i < len(lines):
        body = lines[i].lstrip("\t") if strip_tabs else lines[i]
        i += 1
        if body == delim:
            break
print("\n".join(out))
' 2>/dev/null) || CMD_STRUCT="$CMD"

# Block aigitcommit — human-only commit tool
if echo "$CMD_STRUCT" | grep -qE '\baigitcommit\b'; then
  echo 'aigitcommit is a human-only tool. Use git commit with Co-Authored-By: Claude attribution instead.' >&2
  exit 2
fi

# Block git push --force/-f, but allow --force-with-lease (lease-protected, safe against
# clobbering someone else's push). --force\b alone would also match inside
# "--force-with-lease" (word boundary sits right after "force", before the hyphen), so
# strip --force-with-lease occurrences first and only then check for a bare --force/-f.
PUSH_FORCE_CHECK=$(echo "$CMD_STRUCT" | sed -E 's/--force-with-lease(=[^ ]*)?//g')
if echo "$PUSH_FORCE_CHECK" | grep -qE 'git\s+push\s+.*(-f\b|--force\b)'; then
  echo 'git push --force is non-reversible. Use git push --force-with-lease, git push (without --force), or ask the user for approval.' >&2
  exit 2
fi

# Block git reset --hard
if echo "$CMD_STRUCT" | grep -qE 'git\s+reset\s+--hard'; then
  echo 'git reset --hard is non-reversible. Use git stash or git reset --soft instead, or ask the user.' >&2
  exit 2
fi

# Block git clean -f (and variants like -fd, -fx, -fxd)
if echo "$CMD_STRUCT" | grep -qE 'git\s+clean\s+.*-[a-z]*f'; then
  echo 'git clean -f is non-reversible. List untracked files with git clean -n first, or ask the user.' >&2
  exit 2
fi

# Block git worktree remove --force (bypasses ExitWorktree's dirty-tree refusal)
# Plain "git worktree remove" already refuses a dirty tree; only --force/-f discards
# uncommitted changes. "git worktree add --force" stays allowed (legitimate).
if echo "$CMD_STRUCT" | grep -qE 'git\s+worktree\s+remove\s+.*(-f\b|--force\b)'; then
  echo 'git worktree remove --force discards a dirty worktree'\''s uncommitted changes. Run git worktree remove (no --force), or ask the user.' >&2
  exit 2
fi

# Block git branch -D (force delete)
if echo "$CMD_STRUCT" | grep -qE 'git\s+branch\s+.*-D\b'; then
  echo 'git branch -D is non-reversible. Use git branch -d (lowercase) for safe delete, or ask the user.' >&2
  exit 2
fi

# Block git checkout . (bulk discard all changes)
if echo "$CMD_STRUCT" | grep -qE 'git\s+checkout\s+(\.|--\s+\.)'; then
  echo 'git checkout . discards all uncommitted changes. Use git stash instead, or ask the user.' >&2
  exit 2
fi

# Block git restore . (bulk discard all changes)
if echo "$CMD_STRUCT" | grep -qE 'git\s+restore\s+(\.|--\s+\.)'; then
  echo 'git restore . discards all uncommitted changes. Use git stash instead, or ask the user.' >&2
  exit 2
fi

# Block git commit --amend (must create new commits per CLAUDE.md)
if echo "$CMD_STRUCT" | grep -qE 'git\s+commit\s+.*--amend'; then
  echo 'git commit --amend modifies the previous commit. Create a new commit instead, or ask the user.' >&2
  exit 2
fi

# Block git commit without Co-Authored-By: Claude attribution. The trigger
# checks CMD_STRUCT (a real invocation), but the attribution search checks
# the RAW command, since the message text lives inside quotes that
# CMD_STRUCT has blanked out.
if echo "$CMD_STRUCT" | grep -qE 'git\s+commit\b'; then
  if ! echo "$CMD" | grep -qi 'Co-Authored-By:.*Claude'; then
    echo 'git commit must include Co-Authored-By: Claude attribution. Add it to the commit message.' >&2
    exit 2
  fi
fi

exit 0
