# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Repo Is

System setup and configuration versioning repo. Part of a five-repo tooling stack (`unix-utils`, `oh-my-zsh`, `tmux`, `neovim`, `ghostty`). Base repo — no cross-repo dependencies.

`configs/` holds dotfiles that `install.sh` symlinks to their expected locations.

`configs/ai-docs/claude/` holds the **global** Claude Code config (CLAUDE.md, skills, settings.json, hooks), symlinked to `~/.claude/`. Changes there affect every Claude Code session.

## Setup

```bash
./install.sh
```

Idempotent; safe to re-run. Uses inline OS detection (unlike the other stack repos that source `detect-os.sh` from oh-my-zsh) because this is the base repo with no external dependencies.

## Editing

Always edit source in `configs/`, never the symlink targets.

**`settings.json` caveat**: Claude Code's `/config` command and the `update-config` skill write through temp+rename, which **replaces the symlink with a regular file** and detaches it from the repo.

Always edit `configs/ai-docs/claude/settings.json` directly. If the symlink has been broken, re-run `install.sh` to restore it.

## Conventions

- **Cross-platform is a MUST; cross-tool is a bonus** -- **Claude Code is the main tool and primary concern — it MUST work**, on both OSes (macOS + Linux). opencode and Gemini CLI should be remembered (prefer designs that also port to them) but are NOT requirements.
  - Cross-platform (MUST): path-based config needs both home-dir forms (`/Users/...` and `/home/...`); prefer OS-agnostic logic. (See the `personal-environment` skill for the symlink/permission gotchas.)
  - Cross-tool (bonus): when cheap, favor guards/worktree ergonomics that also hold for opencode/Gemini — e.g. Gemini's `BeforeTool` shares Claude Code's stdin + exit-2 hook contract, so a guard often ports for free. Never block or delay Claude Code work for cross-tool parity.
  - Why: a config that breaks on the other OS is a silent hole that surfaces only when work moves there — non-negotiable. Cross-tool parity is worth taking when free, not worth slowing the primary tool for.

- **Keep `install.sh` in sync** -- `install.sh` is the canonical bootstrap — the source of truth for a fresh-machine setup.
  - When you add/remove a plugin, MCP server, npm global, symlink target, config file, or OS package, mirror the change in `install.sh`.
  - If unsure, ask.

- **Read skills from source, not the symlink** -- when reading or auditing a skill, use `configs/ai-docs/claude/skills/<name>/SKILL.md`, not `~/.claude/skills/<name>/` (which is a symlink target that can be replaced silently — same caveat as `settings.json`).
  - **Native skills** (`simplify`, `init`, `review`, `security-review`) are built into Claude Code; no local file exists.
  - **Plugin skills** (`claude-hud:*`, `plugin:context7:*`, etc.) live in plugin marketplace dirs, not in this repo.
  - If the source path is missing, check whether the skill is native or plugin-provided before assuming the file is gone.
