---
name: lateral-session
description: Hand a side, spike or scout item to a new Claude session in its own tmux window. USE only on an explicit ask - 'open a new session', 'new window', 'in tmux', 'start a session for this' - about one item. Never for unprompted delegation.
---

# lateral-session

Hand one item to a separate Claude session in a new tmux window, so the user can work it in parallel while I keep going on the main goal.

## When to use

Only when the user explicitly asks for a new session, a new window, or tmux, for one side, spike or scout item.

Without that ask, off-goal items go to a subagent as usual.

## Before launching

1. Pin down exactly one item.

   - If the ask names zero or two items, ask which one first, then stop until answered.

2. Pin down the item's repo directory.

   - Use main's own working directory unless the item belongs to another repo.

   - If the repo is unclear, ask first, then stop until answered.

3. Write the hand-off prompt to a file in my own scratchpad directory (the one named in my system prompt), never in the repo.

## What the prompt carries

- The user's own words asking for the item.

- My findings about the item so far, so the new session starts where I am.

- File paths to read instead of pasted contents.

  - The prompt reaches `claude` as a single argument, and Linux caps one argument at 128 KiB (`MAX_ARG_STRLEN`), so keep it well under that.

- A note that main compacted after the user explained the item, when that happened.

  - It tells the new session my findings may miss detail the user gave earlier.

- The git-worktree lines only when the user asked for isolation: create its own worktree, merge back when done, remove the worktree.

  - Without that ask, the lateral session works in the repo's own tree, with no worktree lines.

## Launch

```
~/.claude/skills/lateral-session/scripts/lateral-session.sh <repo-dir> <prompt-file>
```

- Pass no window name: the lateral session's own title hook names the window.

- Success prints nothing and exits 0; the call needs no permission prompt.

- Works the same from `/Users/<user>/` and `/home/<user>/`.

After each launch, tell the user one line: "if the window closed at once, the start failed; tell me and I re-open the entry."

A start that exits closes its window within ~0.3s and loses the error while `new-window` still returns 0, so only the user can see that failure.

## Reading the result

| Result | What I do |
|---|---|
| Exit 0 | Close the item's TaskList entry, if it has one. An item with no entry leaves the TaskList unchanged. |
| Exit 2, `lateral-session: refused - not inside tmux` | Refuse. Do not fall back to a subagent. Leave the entry open and tell the user. |
| Exit 2, `lateral-session: refused - no such dir: <path>` | Name the path looked for. Leave the entry open. |
| Any other non-zero exit | Name that it was tmux's `new-window` that failed, quote its stderr, leave the entry open. |
| User later reports the window closed at once | Re-open the entry. |

If the new window shows claude's trust prompt for an untrusted directory, that is the user's to answer there; it is not a launch failure in main.

## After the launch

- Follow-up questions about the item are answered in the new window, not in main.

- Main learns only the request, the prompt it wrote, and the launch result.

  - Never read the window back (`capture-pane` or similar), so main's context stays on its own goal.
