# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Repo Is

System setup and configuration versioning repo. Part of a five-repo tooling stack (`unix-utils`, `oh-my-zsh`, `tmux`, `neovim`, `ghostty`). Base repo — no cross-repo dependencies. `configs/` holds dotfiles that `install.sh` symlinks to their expected locations.

`configs/ai-docs/claude/` holds the **global** Claude Code config (CLAUDE.md, skills, settings.json, hooks), symlinked to `~/.claude/`. Changes there affect every Claude Code session.

## Setup

```bash
./install.sh
```

Idempotent; safe to re-run. Uses inline OS detection (unlike the other stack repos that source `detect-os.sh` from oh-my-zsh) because this is the base repo with no external dependencies.

## Editing

Always edit source in `configs/`, never the symlink targets.

**`settings.json` caveat**: Claude Code's `/config` command and the `update-config` skill write through temp+rename, which **replaces the symlink with a regular file** and detaches it from the repo. Always edit `configs/ai-docs/claude/settings.json` directly. If the symlink has been broken, re-run `install.sh` to restore it.

## Conventions

- **Keep `install.sh` in sync** -- `install.sh` is the canonical bootstrap, the source of truth for what a fresh machine should end up with. When you add/remove a plugin, MCP server, npm global, symlink target, config file, or OS package, mirror the change in `install.sh` so a re-run reproduces the same state. If unsure, ask.
