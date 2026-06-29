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

**Permission-glob caveat**: in `settings.json` `permissions.allow`, an `Edit`/`Write` path glob with a SINGLE leading slash (`Edit(/tmp/**)`) is read as project-root-relative and silently matches nothing. A filesystem-absolute path needs a DOUBLE slash: `Edit(//tmp/**)`.

For a symlinked dir (macOS `/tmp` → `/private/tmp`), add both the symlink path and its resolved target — `//tmp/**` and `//private/tmp/**`. The failure reads as a missing permission, not a typo, so it recurs on every rediscovery.

**`~/.gitconfig` caveat**: `git config --global ...` writes through lock+rename, which **replaces the symlink with a regular file** and detaches it from the repo — same hazard as `settings.json`, but easier to trip since `git config --global` (and a re-run of `gh auth setup-git`) is reflexive.

Always edit `configs/git/.gitconfig` directly. If the symlink has been broken, re-run `install.sh` to restore it.

## Conventions

- **Cross-platform is a MUST; cross-tool is a should-have** -- **Claude Code is the primary tool and MUST work** on both OSes (macOS + Linux). opencode and Gemini CLI ports are DESIRABLE (should-have) — genuinely wanted, but never required and never ahead of Claude Code.
  - Cross-platform (MUST): path-based config needs both home-dir forms (`/Users/...` and `/home/...`); prefer OS-agnostic logic. (See the `personal-environment` skill for the symlink/permission gotchas.)
  - Cross-tool (should-have): opencode/Gemini parity is desirable, not required — pursue it when it's cheap or when actually working in those tools, but never block, delay, or complicate Claude Code work for it. The worktree-guard port exploring this was cancelled as not-now, not never.
  - Why: a config that breaks on the other OS is a silent hole that surfaces only when work moves there — non-negotiable. Cross-tool parity is wanted but stays subordinate: it earns effort, just never at Claude Code's expense.

- **Keep `install.sh` in sync** -- `install.sh` is the canonical bootstrap — the source of truth for a fresh-machine setup.
  - When you add/remove an MCP server, npm global, symlink target, config file, or OS package, mirror the change in `install.sh`.
  - Plugins are the exception — they live in `settings.json`, not `install.sh` (see below).
  - If unsure, ask.

- **Plugins live in `settings.json`, not `install.sh`** -- Claude Code plugins and their non-official marketplaces are version-controlled in `configs/ai-docs/claude/settings.json` under `enabledPlugins` (which plugins are on) and `extraKnownMarketplaces` (their GitHub sources). A fresh install symlinks settings.json, and Claude Code installs the enabled plugins on first launch — so `install.sh` needs no plugin logic.
  - `claude plugin install <name>@<marketplace>` writes *through* the symlink (it does NOT detach it the way `/config` and `update-config` do), so the new `enabledPlugins` entry lands in the repo file directly — just commit it.
  - The official `claude-plugins-official` marketplace is built-in; only non-official marketplaces need an `extraKnownMarketplaces` entry.

- **Read skills from source, not the symlink** -- when reading or auditing a skill, use `configs/ai-docs/claude/skills/<name>/SKILL.md`, not `~/.claude/skills/<name>/` (which is a symlink target that can be replaced silently — same caveat as `settings.json`).
  - **Native skills** (`simplify`, `init`, `review`, `security-review`) are built into Claude Code; no local file exists.
  - **Plugin skills** (`claude-hud:*`, `plugin:context7:*`, etc.) live in plugin marketplace dirs, not in this repo.
  - If the source path is missing, check whether the skill is native or plugin-provided before assuming the file is gone.
