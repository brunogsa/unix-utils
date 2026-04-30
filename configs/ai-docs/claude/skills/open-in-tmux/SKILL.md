---
name: open-in-tmux
description: Run any command in a new tmux pane, split, or window. USE PROACTIVELY for: (1) file review — when user says 'open in tmux', 'open in nvim', 'new window/pane', 'show me', 'let me check', after 3 edit rejections; (2) streaming long output — when a slow command saves to /tmp/ and the output is large or still running, or user says 'stream it', 'show me live', 'tail the log', 'follow the output'.
---

# open-in-tmux

Open any command in the user's tmux session — file review in nvim, live output streaming with `tail -f`, or any other shell command. Composable for multi-pane layouts.

## How to invoke

```
~/.claude/skills/open-in-tmux/scripts/open-in-tmux.sh <mode> <command>
```

`<command>` is the full shell command to run in the pane. Common patterns:

| Use case | Command |
|---|---|
| Review file at line | `"nvim +42 src/auth.ts"` |
| Review file at line + col | `"nvim '+call cursor(42,8)' src/auth.ts"` |
| Stream live output | `"tail -f /tmp/build.log"` |
| Watch a process | `"watch -n2 kubectl get pods"` |

`<mode>` selects the placement:

| Mode | Behavior |
|---|---|
| `vertical` | Side-by-side split of the current pane. |
| `horizontal` | Stacked split of the current pane. |
| `window` | New tmux window — leaves the current layout untouched. |
| `pane:<N>` | Send the command to pane N (types it into the existing shell via send-keys; preserves pane history and state). |

## Picking the mode

Map the user's spoken placement:

- "vertical pane", "side by side" → `vertical`
- "horizontal pane", "below" → `horizontal`
- "new window" → `window`
- "pane 2", "send to pane 1" → `pane:<N>`

For multi-pane layouts in one exchange, invoke once per command with the matching mode.

## After every successful invocation

**Wait for the user's next message before any further action.** The pane is open; the user is reading or watching. Do not edit, commit, or proceed until they reply.

When the user replies:

- **File review — they edited in the pane** ("I added a guard", "I changed the import"): re-read the file from disk and diff-summarize the changes — e.g. "I see you replaced the early return at L42 with a guard clause; want me to extend my edit to match?" This confirms you understand the new state.
- **Streaming output — they signal done** ("ok stop", "looks good", "continue"): proceed with the originally proposed work.
- **Nothing changed** ("ok proceed", "fine"): proceed.

The script prints this reminder on stdout after every dispatch — honor it.

## Outside tmux

If `$TMUX` is unset, the script exits non-zero and prints the command to stdout. Tell the user: "I can't open a tmux pane from here, but you can run the printed command yourself."

## What NOT to use this for

**Multi-file diff review.** The user has `vimreview` and `diffview` for batch-comparing many changes. This skill is for "gather more context" or "watch a running command", not bulk diff-walking.
