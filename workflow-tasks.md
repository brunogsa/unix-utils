# workflow-tasks.md — AI & tooling workflow backlog

**What this file is for**: tracking the things I want to improve or add to my AI and tooling workflow — Claude Code (hooks, skills, CLAUDE.md), tmux, neovim, zshrc/oh-my-zsh, ghostty, and the rest of the stack. It is the durable, committable backlog of open improvements.

**Convention — open work only**: when a task is **done, REMOVE it from this file** (do not mark it as done). This file always lists *only* what's still open; git history holds the record of what was completed.

**Each task is meant to run in its own fresh Claude Code session** for quality (no cross-task context bleed). Every section is therefore written to stand alone — a new session should be able to execute it from this file plus the repo's `CLAUDE.md` and the global `~/.claude/CLAUDE.md`, without the originating chat.

## Shared context (read once per session)

- **Repo**: `unix-utils` — system setup + config-versioning repo. Base of a five-repo stack: `unix-utils`, `oh-my-zsh`, `tmux`, `neovim`, `ghostty`.
- **Sibling repos** (this user, absolute paths):
  - tmux config → `~/tmux`
  - ghostty config → `~/ghostty`
  - neovim config → `~/neovim`
  - oh-my-zsh → `~/oh-my-zsh`
- **Global Claude config lives here**, symlinked to `~/.claude/`:
  - `configs/ai-docs/claude/CLAUDE.md`
  - `configs/ai-docs/claude/settings.json`
  - `configs/ai-docs/claude/hooks/` → `claude-tasklist-stop-hook.sh`, `claude-tmux-notification.sh`, `claude-git-guard.sh`, `claude-rm-guard.sh`
  - `configs/ai-docs/claude/skills/` → includes `spec-driven-development`, `notify-user`, `open-in-tmux`, `performance-check-principles-and-skills`, etc.
- **Editing rule**: always edit source in `configs/`, never the `~/.claude` symlink target. `settings.json` and skill files get silently replaced by temp+rename writes — edit the source file directly; re-run `install.sh` to restore a broken symlink.
- **Keep `install.sh` in sync**: any new hook, script, symlink target, package, or plugin must be mirrored there (canonical fresh-machine bootstrap).
- **Conventions**: one logical change per commit; load `skill-creator` before editing any `SKILL.md`; follow `commit-standards` / `code-standards` / `doc-standards`.

---

## 1. [Task] tmux + ghostty scrollback line-wrapping fix (tmux required)

**Goal**: Fix broken line wrapping when scrolling Claude Code output upward in tmux running under ghostty — long lines break at the wrong column in scrollback.

**Hard constraint**: dropping tmux is **NOT** an option (rules out "just run Claude in a bare ghostty window").

**Root cause (verified via web)**: tmux freezes wrap points at the column width that was active when text was *printed*, and its scrollback reflow on resize is limited (tmux issues #4814, #516). ghostty reflows natively. So **tmux is the degrading layer**, not ghostty.

**Where to look**: `~/tmux` (tmux config), `~/ghostty` (ghostty config). Read-only investigation first.

**Things to check / try (cheapest first)**:
- `TERM` inside tmux is `tmux-256color` (NOT `screen-256color`) — wrong terminfo worsens redraw. Check both ghostty's configured `TERM` and tmux's `default-terminal`.
- tmux `history-limit`, `aggressive-resize`, and any `window-size`/`force-width` settings.
- Whether the breakage is triggered specifically by pane **resize** mid-session vs. appears on first print.
- ghostty's own reflow/wrap settings and whether a terminfo mismatch defeats it.

**Deliverable**: a concrete config diff (in `~/tmux` and/or `~/ghostty`), not generic advice. If the change affects bootstrap, mirror into the relevant repo's installer. Verify by reproducing the wrap break before/after.

---

## 2. [Spike] Simulate desktop-style diff view via terminal + tmux + neovim

**Goal**: Approximate the Claude Code **desktop app's visual diff review** inside the terminal stack (terminal + tmux + neovim), so a desktop switch isn't needed just for nicer diffs.

**Context**: User stays terminal-primary (heavy tmux/hooks/skills investment). Desktop app's main draws are visual diffs, file tree, and multi-cloud-agent concurrency. This task targets only the **diff** draw.

**Where to look**: `~/neovim` (check which plugin manager + whether fugitive / diffview.nvim / gitsigns already present), git config (`~/.gitconfig` / oh-my-zsh) for current pager.

**Options to evaluate**:
- (a) neovim diff: `diffview.nvim` (best side-by-side + file panel, closest to desktop) or `:Gdiffsplit` via fugitive.
- (b) syntax-aware pager: `delta` or `difftastic` as `git` pager for inline review without leaving the shell.
- (c) a Claude Code `PostToolUse` hook (Edit/Write) that opens the just-changed files in a neovim diff split in an adjacent tmux pane.

**Deliverable**: recommendation + concrete wiring (keybind / alias / hook). Favor `diffview.nvim` if neovim plugins are acceptable. Spike — may conclude "current setup is enough."

---

## 3. [Spike] Discuss disadvantages of multi-agent-in-separate-tabs orchestration

**Goal**: Produce a clear trade-off writeup (NOT code) on the real downsides of running multiple Claude Code agents in separate tmux tabs/panes, vs. the desktop app's single concurrency dashboard. Output helps the user decide whether tabs are actually a problem for them.

**Cover at minimum**:
- Cognitive cost of context-switching across tabs; no single "who needs me now?" attention surface.
- Notification fan-in (each agent nags independently).
- Coordination between agents: shared-file races, branch/merge collision risk, who owns what.
- How existing hooks could mitigate: `Notification`, `Stop` (exit 2 to force-continue), `SubagentStop`; and the existing `claude-tmux-notification.sh` hook + `notify-user` skill.

**Deliverable**: trade-off writeup with a recommendation on whether/when tabs are fine vs. when to reach for the desktop concurrency view. Pairs with task #4.

---

## 4. [Spike] Evaluate /remote phone notifications vs. cross-OS desktop notifications

**Goal**: Decide the user's notification strategy: Claude Code `/remote` (push to phone) exclusively, local desktop notifications only, or both.

**Research**:
- How `/remote` (RemoteTrigger) works: setup, which events it fires on, whether it needs cloud/Routines, latency, what the phone payload contains.
- A **cross-OS desktop** path that works on BOTH macOS and Linux: a `Notification` hook shelling to `terminal-notifier`/`osascript` on macOS and `notify-send` on Linux (or a unified wrapper).

**Existing assets to reuse, don't duplicate**: `configs/ai-docs/claude/hooks/claude-tmux-notification.sh` already exists; the `notify-user` skill exists. Check whether to wire `notify-user` to the `Notification` hook rather than build new.

**Deliverable**: recommendation — likely a split (phone for away-from-keyboard, desktop for at-desk), with the concrete hook config to implement it. Pairs with task #3.

---

## 5. [Feature] Human-only authenticated command to toggle Claude Code hook behaviors

**Goal**: A command that **ONLY the human** can run — gated by a secret Claude cannot know or retrieve — that switches certain hook behaviors on/off (e.g. relax the Stop-hook nag, loosen a future PR-size ceiling, enable a bypass/loop mode for low-stakes work).

**CRITICAL threat model**: Claude Code runs with the user's uid. Any file Claude can read, it can read; any file it can write, it can write.
- The secret must NOT live where Claude can read it: not env vars, not repo/home files, not shell history (read interactively via `/dev/tty`, never as a CLI arg), not process listings.
- The **toggle STATE must be tamper-resistant against Claude too** — otherwise Claude can flip the state file directly and skip the gate. A password that only guards the *command* is insufficient.

**Mechanisms whose boundary actually holds (evaluate, Spike first)**:
- macOS Keychain + Touch ID via `security` CLI — Claude can't satisfy the biometric/GUI prompt. (macOS-only.)
- HMAC/signature on the state, key held only in Keychain/`pass` — Claude can read state but can't forge a valid signature. (Cross-OS if key store is.)
- Root- or other-user-owned state file writable only via `sudo` — OS permission separation; Claude lacks the password. (Works on Linux; puts `sudo` in the loop.)
- REJECT: plain dotfile/env flag, or password stored in a readable file.

**Lean**: HMAC-signed state with key in Keychain/`pass` for cross-OS fit — but confirm before building.

**Deliverable**: chosen mechanism whose boundary holds at Claude's privilege level, the command (interactive secret prompt), hooks wired to honor the authenticated toggle, threat model documented in the command, mirrored into `install.sh`.

---

## 6. [Task] Separate tasks.md from plan.md in the planning workflow

**Goal**: Split planning into two artifacts instead of one blended doc:
- **plan.md** — DESIGN/approach: problem framing, chosen strategy, trade-offs, and the explicit **list of files to check/touch** (token-efficient grounding). Stable, read-mostly, written once.
- **tasks.md** — EXECUTION checklist: ordered, checkable tasks/sub-steps derived from the plan. Volatile, durable across sessions, diffable, committable. (This very file is the prototype.)

**Rationale**: plan = why/how (stable); tasks = what's-left (write-often). Separating them stops the volatile checklist from churning the stable design doc, and makes tasks.md the per-feature backlog of record alongside `spec.md`.

**Touches**: `spec-driven-development` skill, and possibly the TaskList conventions in the global `CLAUDE.md`. Load `skill-creator` before editing any `SKILL.md`.

**OPEN QUESTION to confirm before implementing**: should tasks.md **replace** the live TaskList tool, or **coexist** (durable file as source-of-record + TaskList for in-flight session execution)? Author's lean: coexist.

**Deliverable**: updated `spec-driven-development` skill establishing the plan.md / tasks.md split; CLAUDE.md TaskList convention reconciled with tasks.md; one isolated commit.
