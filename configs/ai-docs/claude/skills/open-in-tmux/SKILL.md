---
name: open-in-tmux
description: Run a command in a new tmux pane, or open a git diff in neovim's Diffview. USE for file/diff review ('open in tmux'/'new pane'/'review this'/'let me review'/'show me the diff', after 3 edit rejections) or streaming output ('tail log'/'show live').
---

# open-in-tmux

Open any command in the user's tmux session — file review in nvim, live output streaming with `tail -f`, or any other shell command.
Composable for multi-pane layouts.
The user observes the pane; I keep going.

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
| `vertical` | Side-by-side split of the caller's own pane (this session's pane, not the pane the user is currently viewing). |
| `horizontal` | Stacked split of the caller's own pane (same targeting as `vertical`). |
| `window` | New tmux window — leaves the current layout untouched. |
| `pane:<N>` | Send the command to pane N (types it into the existing shell via send-keys; preserves pane history and state). |

## Picking the mode

Map the user's spoken placement:

- "vertical pane", "side by side" → `vertical`
- "horizontal pane", "below" → `horizontal`
- "new window" → `window`
- "pane 2", "send to pane 1" → `pane:<N>`

For multi-pane layouts in one exchange, invoke once per command with the matching mode.

## Reviewing a git diff (branch, or since a commit)

For the common "let me review what you did" case — the whole-branch diff, or the diff since some commit — use the sibling helper instead of hand-writing the nvim command:

```
~/.claude/skills/open-in-tmux/scripts/diffview-in-tmux.sh [<ref>]
```

- No `<ref>` → diffs the working tree vs the repo's base branch (origin/HEAD → main → master), i.e. the whole-branch diff. Matches neovim's `<leader>tD`.
- With `<ref>` → diffs the working tree vs that commit-ish (a SHA, a `git merge-base` output, a branch, a tag).
  - When the user says "since X", YOU resolve X to that ref and pass it.
  - "Review this session" / "let me review" with no explicit ref: resolve `<ref>` yourself, don't ask which ref.
  - Resolve it to the parent of the first commit *you* made this session, not the branch-base default.
  - The branch-base default is wrong here: in a direct-to-default-branch repo it shows unrelated history too.

It opens a `vertical` pane running `nvim -c 'DiffviewOpen <ref>'` in the repo root, then follows the **File review** post-invocation behavior below (wait for the user; re-read on reply).

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

**Interactive bulk diff-walking.** `vimreview` and the neovim diffview keymaps (`<leader>td/tD/th`) are the user's own interactive TTY tools for stepping through many changes — Claude can't drive them (they need a hands-on terminal).

For a git branch/commit diff Claude CAN open on request, use the `diffview-in-tmux.sh` helper above — that leaves `vimreview` for the human's own review, no overlap.
