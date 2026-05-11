---
name: personal-environment
description: "ALWAYS load when CRUDing or looking up Bruno's principles/skills (~/.claude/), oh-my-zsh (zshrc/aliases/shell utilities), neovim/tmux/ghostty, or unix-utils repo. Covers symlink rules, permission canonical paths, platform path differences."
user-invocable: false
---

# Personal Environment

Reference for Bruno's dev stack and the gotchas that come with it.

## Dev stack

Ghostty (terminal) → tmux → oh-my-zsh → neovim + Claude Code.

Five cross-platform repos (macOS/Linux), each with its own `CLAUDE.md`:

- `~/ghostty/` — Ghostty terminal config.
- `~/tmux/` — tmux config with neovim/Claude integrations.
- `~/oh-my-zsh/` — zsh config, aliases, and CLI commands Bruno runs from the terminal. AI may also call these.
- `~/neovim/` — neovim config: LSP, Treesitter, hotkeys, plugins, etc.
- `~/unix-utils/` — system setup, CLI helpers and their configs versioning, Claude Code global config (CLAUDE.md, skills, hooks, settings).
  - Scripts only used by AI belong as self-contained skills in `~/unix-utils/` instead of `~/oh-my-zsh/`.

## Configs are symlinked from repos to system locations — always edit the source repo

Examples:
- `~/.claude/CLAUDE.md` ← `~/unix-utils/configs/ai-docs/claude/`
- `~/.zshrc` ← `~/oh-my-zsh/.zshrc`

Why: edits at the system location bypass version control. They survive locally but get overwritten the next time the source repo deploys. The repo is the source of truth.

## Symlink + permission-rule gotcha

`settings.json` `permissions.allow` matches the **canonical path** (use `realpath`), not the symlink.

Why: Claude Code's permission engine resolves symlinks before matching. Adding a rule with the symlink path silently fails to match.

- One entry per platform (home dirs differ); drop symlink-path entries.
- macOS: `"Bash(/Users/brunoagostini/unix-utils/configs/ai-docs/claude/skills/.../script.sh *)"`
- Linux: `"Bash(/home/brunogsa/unix-utils/configs/ai-docs/claude/skills/.../script.sh *)"`

## Platform differences (macOS vs Linux)

Home directory paths differ — `/Users/brunoagostini` on macOS, `/home/brunogsa` on Linux. Any path-based config (permissions, hooks, scripts) needs both entries.

Why: rules baked for one platform break silently on the other. Cross-platform setup requires explicit parallel entries.
