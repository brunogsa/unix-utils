# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Repo Is

System setup and configuration versioning repo. Part of a five-repo tooling stack (`unix-utils`, `oh-my-zsh`, `tmux`, `neovim`, `ghostty`). One installer (`install.sh`) and a `configs/` directory with dotfiles symlinked to their expected locations.

## Setup

```bash
./install.sh
```

The install script:
- Detects OS via inline `detect_os` function (this is the base repo -- no external dependency)
- Configures git globals (user, editor)
- Installs core CLI tools: ripgrep, fd, jq, tree, htop, meld, tldr, etc.
- Installs copyq (clipboard manager) and symlinks config to `~/.config/copyq`
- Installs espanso (text expander) and symlinks config
- Installs Docker, AWS CLI, dev tools (shellcheck, luacheck, lua-language-server, deno, pipx)
- Installs global npm packages (Claude Code, MCP servers, ccusage, trash-cli)
- Sets up Claude Code: symlinks `configs/ai-docs/claude/*` to `~/.claude/`, installs plugins and MCP servers
- Installs peon-ping (sound notifications for Claude Code)
- Linux-only: symlinks xubuntu keyboard shortcuts

## Directory Structure

- `configs/ai-docs/claude/` -- global Claude Code config (CLAUDE.md, skills/, commands/, settings.json, hooks/). Symlinked to `~/.claude/`. **This is the global CLAUDE.md, not this file.**
- `configs/copyq/` -- copyq clipboard manager settings
- `configs/espanso/` -- espanso text expansion rules
- `configs/xubuntu/` -- xfce4 keyboard shortcuts (Linux-only)

## Conventions

- `install.sh` uses inline OS detection (unlike other repos that source `detect-os.sh` from oh-my-zsh) because this is the base repo with no external dependencies
- Idempotent: safe to re-run
- Config files live in `configs/`, symlinked to system locations by the installer
- Always edit source in `configs/`, never the symlink targets
