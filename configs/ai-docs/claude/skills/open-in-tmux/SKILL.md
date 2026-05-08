---
name: open-in-tmux
description: Run a command in a new tmux pane. USE for file review ('open in tmux'/'nvim'/'new pane', after 3 edit rejections) or streaming output ('tail log'/'show live'). User observes; I keep going.
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

Two modes — behavior differs:

**File review** (nvim, diffview): wait for the user's next message.

- They may edit the file in the pane.
- When they reply, re-read the file from disk and diff-summarize any changes.
- E.g. "I see you replaced the early return at L42 with a guard clause; want me to extend my edit to match?"

**Streaming output** (`tail -f`, long-running command): the pane is for the user to observe IN PARALLEL.

- Do NOT pause or wait.
- Continue executing the next steps immediately — check the output file yourself.
- Never ask the user to signal when the command finishes.

The script prints a reminder on stdout after every dispatch. For streaming invocations, override it: keep working.

## Outside tmux

If `$TMUX` is unset, the script exits non-zero and prints the command to stdout.

Tell the user: "I can't open a tmux pane from here, but you can run the printed command yourself."

## What NOT to use this for

**Unsolicited streaming.** The pane is a viewer for the user — open it only when they ask.

- For streaming, always `tail -f /tmp/file.txt` in the pane.
- Never re-run the original command (it exits when done, closing the pane immediately).

**Multi-file diff review.** The user has `vimreview` and `diffview` for batch-comparing many changes. This skill is for "gather more context" or "watch a running command", not bulk diff-walking.
