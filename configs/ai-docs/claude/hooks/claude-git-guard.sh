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
#   git branch -D (non-reversible)
#   git checkout . / git restore . (bulk discard)
#   git commit --amend (must create new commits)
#   aigitcommit (human-only tool)
#   git commit without Co-Authored-By: Claude attribution
#
# Examples:
#   echo '{"tool_input":{"command":"git push --force"}}' | bash claude-git-guard.sh  # blocked
#   echo '{"tool_input":{"command":"git status"}}' | bash claude-git-guard.sh        # allowed

CMD=$(jq -r '.tool_input.command // empty')

if [ -z "$CMD" ]; then
  exit 0
fi

# Block aigitcommit — human-only commit tool
if echo "$CMD" | grep -qE '\baigitcommit\b'; then
  echo 'aigitcommit is a human-only tool. Use git commit with Co-Authored-By: Claude attribution instead.' >&2
  exit 2
fi

# Block git push --force (includes --force-with-lease as acceptable, only block --force and -f)
if echo "$CMD" | grep -qE 'git\s+push\s+.*(-f\b|--force\b)'; then
  echo 'git push --force is non-reversible. Use git push (without --force) or ask the user for approval.' >&2
  exit 2
fi

# Block git reset --hard
if echo "$CMD" | grep -qE 'git\s+reset\s+--hard'; then
  echo 'git reset --hard is non-reversible. Use git stash or git reset --soft instead, or ask the user.' >&2
  exit 2
fi

# Block git clean -f (and variants like -fd, -fx, -fxd)
if echo "$CMD" | grep -qE 'git\s+clean\s+.*-[a-z]*f'; then
  echo 'git clean -f is non-reversible. List untracked files with git clean -n first, or ask the user.' >&2
  exit 2
fi

# Block git branch -D (force delete)
if echo "$CMD" | grep -qE 'git\s+branch\s+.*-D\b'; then
  echo 'git branch -D is non-reversible. Use git branch -d (lowercase) for safe delete, or ask the user.' >&2
  exit 2
fi

# Block git checkout . (bulk discard all changes)
if echo "$CMD" | grep -qE 'git\s+checkout\s+(\.|--\s+\.)'; then
  echo 'git checkout . discards all uncommitted changes. Use git stash instead, or ask the user.' >&2
  exit 2
fi

# Block git restore . (bulk discard all changes)
if echo "$CMD" | grep -qE 'git\s+restore\s+(\.|--\s+\.)'; then
  echo 'git restore . discards all uncommitted changes. Use git stash instead, or ask the user.' >&2
  exit 2
fi

# Block git commit --amend (must create new commits per CLAUDE.md)
if echo "$CMD" | grep -qE 'git\s+commit\s+.*--amend'; then
  echo 'git commit --amend modifies the previous commit. Create a new commit instead, or ask the user.' >&2
  exit 2
fi

# Block git commit without Co-Authored-By: Claude attribution
if echo "$CMD" | grep -qE 'git\s+commit\b'; then
  if ! echo "$CMD" | grep -qi 'Co-Authored-By:.*Claude'; then
    echo 'git commit must include Co-Authored-By: Claude attribution. Add it to the commit message.' >&2
    exit 2
  fi
fi

exit 0
