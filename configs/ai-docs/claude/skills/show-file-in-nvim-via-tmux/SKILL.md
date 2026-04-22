---
name: show-file-in-nvim-via-tmux
description: Open a file at a specific line in the user's tmux session for visual review — vertical pane, horizontal pane, new window, or replace an existing pane by number. USE PROACTIVELY after 3 consecutive edit rejections from the user (without an accepted edit between) or when the user says any variant of "let me check", "open in nvim", "show me", "vertical/horizontal pane", "new window", or names a specific pane to inspect. After every successful invocation, MUST wait for the user's next message before any further action — the user signals whether to re-read the file (they may have edited it in the pane); when CC re-reads, it MUST diff-summarize the observed changes, since those edits are signal for later session-learnings. SKIP for multi-file diff review (use diffview/vimreview instead).
---

# show-file-in-nvim-via-tmux

Open a file at a specific line in the user's tmux session so the user can review with full context in nvim. Composable with itself to build multi-pane layouts.

## How to invoke

```
~/.claude/skills/show-file-in-nvim-via-tmux/scripts/show-file-in-nvim-via-tmux.sh <mode> <file> <line> [col]
```

`<mode>` selects the placement:

| Mode         | Behavior                                                                                                             |
| ------------ | -------------------------------------------------------------------------------------------------------------------- |
| `vertical`   | Side-by-side split of the current pane.                                                                              |
| `horizontal` | Stacked split of the current pane.                                                                                   |
| `window`     | New tmux window — leaves the current window's pane layout untouched.                                                 |
| `pane:<N>`   | Replace the file shown in tmux pane N (visible index — the number the user sees via `prefix + q`).                   |

`pane:<N>` is smart: if pane N already runs nvim, the script sends `:edit +<line> <file>` to it via `tmux send-keys` so the existing nvim's jump list (`C-o` / `C-i`) and unsaved buffers survive. Otherwise it respawns the pane with a fresh nvim.

## Picking the mode

Map the user's spoken placement to the right mode:

- "let me check ... — vertical pane" → `vertical`
- "let me check ... — horizontal pane" → `horizontal`
- "open it in a new window", "let me check the last edited file in a new window" → `window`
- "open it in pane 2", "show me on pane 1" → `pane:<N>`

For multi-file layouts in one exchange ("model in pane 1, repo in pane 2, controller in a horizontal pane"), invoke the skill once per file with the matching mode.

## After every successful invocation

**Wait for the user's next message before any further action.** The pane is now open; the user is reading. Do not edit, commit, or proceed in the conversation until they reply.

When the user replies:

- **If they signal they edited the file in the pane** ("I added a guard at line 42", "I changed the imports", "check it again now"): re-read the file from disk and diff-summarize the observed changes back to them — e.g. "I see you replaced the early return at L42 with a guard clause; want me to extend my original edit to use it?". The diff-summary confirms you understand the new state and surfaces user-made edits as signal for later session-learning audits.
- **If they signal nothing changed** ("ok proceed", "fine, continue"): proceed with the originally proposed work.

The script prints this reminder on stdout after every successful dispatch — honor it.

## Outside tmux

If `$TMUX` is unset, the script prints a fallback `nvim +<line> <file>` command on stdout and exits non-zero. Tell the user something like: "I can't open a tmux pane from here, but you can run the printed command yourself to inspect."

## What NOT to use this for

**Multi-file diff review.** The user has `vimreview` and `diffview` for batch-comparing many changes at once. This skill is for "gather more context before proceeding" or "manual edit a single file at a known line", not bulk diff-walking.
