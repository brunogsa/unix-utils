---
name: show-file-in-nvim-via-tmux
description: Open a file at a specific line in the user's tmux session for visual review — vertical pane, horizontal pane, new window, or replace an existing pane by number. USE PROACTIVELY after 3 consecutive edit rejections from the user (without an accepted edit between) or when the user says any variant of "let me check", "open in nvim", "show me", "vertical/horizontal pane", "new window", or names a specific pane to inspect. After every successful invocation, MUST wait for the user's next message before any further action — the user signals whether to re-read the file (they may have edited it in the pane); when CC re-reads, it MUST diff-summarize the observed changes, since those edits are signal for later session-learnings. SKIP for multi-file diff review (use diffview/vimreview instead).
---

# show-file-in-nvim-via-tmux

Body to be filled in by plan task 5 (discovery rule and post-run language for CC).
