# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Repo Is

System setup and configuration versioning repo. Part of a five-repo tooling stack (`unix-utils`, `oh-my-zsh`, `tmux`, `neovim`, `ghostty`). Base repo — no cross-repo dependencies.

`configs/` holds dotfiles that `install.sh` symlinks to their expected locations.

`configs/ai-docs/claude/` holds the **global** Claude Code config (CLAUDE.md, skills, settings.json, hooks), symlinked to `~/.claude/`. Changes there affect every Claude Code session.

## Git workflow

- Sole maintainer: commit directly to the default branch (`master`/`main`) — no feature branch or PR needed.
- This overrides the global "branch first" default, which exists for shared repos where others review changes.

## Setup

```bash
./install.sh
```

Idempotent; safe to re-run. Uses inline OS detection (unlike the other stack repos that source `detect-os.sh` from oh-my-zsh) because this is the base repo with no external dependencies.

## Testing

Two commands cover the whole repo — run both:

```bash
./run-tests.sh   # every bash suite, across all four test trees
pytest           # every python suite, collected by the repo-root pytest.ini
```

`run-tests.sh` discovers suites by glob, so a new `test-*.sh` under any of the four trees is picked up with no registration step.

It runs every suite even after one fails, prints the failing suites' output, and exits non-zero if any failed.

Never compose an ad-hoc `for t in .../test-*.sh` loop instead — that is exactly how ten hook suites ended up with nothing enumerating them.

## Editing

Always edit source in `configs/`, never the symlink targets.

**`settings.json` caveat**: Claude Code's `/config` command and the `update-config` skill write through temp+rename, which **replaces the symlink with a regular file** and detaches it from the repo.

Always edit `configs/ai-docs/claude/settings.json` directly. If the symlink has been broken, re-run `install.sh` to restore it.

**`/model`, `/effort`, and `/advisor` write to `settings.json` — never commit that**: these three keys get changed session by session on purpose, so their diff is expected noise, not drift.

Leave it dirty: don't flag it, don't ask whether to commit it, don't commit it. Every other `settings.json` key change still earns its own commit.

The committed values are the declared defaults: `model` `sonnet`, `effortLevel` `high`. Restore them any time with `git checkout -- configs/ai-docs/claude/settings.json`.

The writes are documented at code.claude.com/docs/en/model-config.md and .../advisor.md.

For a session-only model that never touches the file, use the `s` key inside the `/model` picker, or launch with `claude --model <m>` / `claude --advisor <m>`.

**Permission-glob caveat**: in `settings.json` `permissions.allow`, an `Edit`/`Write` path glob with a SINGLE leading slash (`Edit(/tmp/**)`) is read as project-root-relative and silently matches nothing.
A filesystem-absolute path needs a DOUBLE slash: `Edit(//tmp/**)`.

For a symlinked dir (macOS `/tmp` → `/private/tmp`), add both the symlink path and its resolved target — `//tmp/**` and `//private/tmp/**`.
The failure reads as a missing permission, not a typo, so it recurs on every rediscovery.

**`~/.gitconfig` caveat**: `git config --global ...` writes through lock+rename, which **replaces the symlink with a regular file** and detaches it from the repo.
This is the same hazard as `settings.json`, but easier to trip since `git config --global` (and a re-run of `gh auth setup-git`) is reflexive.

Always edit `configs/git/.gitconfig` directly. If the symlink has been broken, re-run `install.sh` to restore it.

## Conventions

- **Cross-platform is a MUST; cross-tool is a should-have** -- **Claude Code is the primary tool and MUST work** on both OSes (macOS + Linux).
  - opencode and Gemini CLI ports are DESIRABLE (should-have) — genuinely wanted, but never required and never ahead of Claude Code.
  - Cross-platform (MUST): path-based config needs both home-dir forms (`/Users/...` and `/home/...`); prefer OS-agnostic logic. (See the `personal-environment` skill for the symlink/permission gotchas.)
  - Cross-tool (should-have): opencode/Gemini parity is desirable, not required — pursue it when it's cheap or when actually working in those tools.
    - Never block, delay, or complicate Claude Code work for it.
    - The worktree-guard port exploring this was cancelled as not-now, not never.
  - Why: a config that breaks on the other OS is a silent hole that surfaces only when work moves there — non-negotiable.
    - Cross-tool parity is wanted but stays subordinate: it earns effort, just never at Claude Code's expense.

- **Keep `install.sh` in sync** -- `install.sh` is the canonical bootstrap — the source of truth for a fresh-machine setup.
  - When you add/remove an MCP server, npm global, symlink target, config file, OS package, or plugin, mirror the change in `install.sh`.
  - If unsure, ask.

- **`install.sh` installs plugins; `settings.json` tracks which are enabled** -- `enabledPlugins: true` only activates an *already-installed* plugin, it does not fetch it.
  - `install.sh` still needs an explicit `claude plugin install <name>@<marketplace>` line for every plugin, mirroring `enabledPlugins`.
  - Non-official marketplaces are version-controlled the same way, under `extraKnownMarketplaces` in `configs/ai-docs/claude/settings.json`.
  - `claude plugin install <name>@<marketplace>` writes *through* the symlink (it does NOT detach it the way `/config` and `update-config` do).
    - The new `enabledPlugins` entry lands in the repo file directly — just commit it.
  - The official `claude-plugins-official` marketplace is built-in; only non-official marketplaces need an `extraKnownMarketplaces` entry.

- **Read skills from source, not the symlink** -- when reading or auditing a skill, use `configs/ai-docs/claude/skills/<name>/SKILL.md`, not `~/.claude/skills/<name>/`.
  - The symlink target can be replaced silently — same caveat as `settings.json`.
  - **Native skills** (`simplify`, `init`, `review`, `security-review`, `code-review`, `verify`) are built into Claude Code; no local file exists.
    - The local GitHub-PR review skill is `pr-review` (renamed from `code-review` to avoid shadowing the native one).
  - **Plugin skills** (`claude-hud:*`, etc.) live in plugin marketplace dirs, not in this repo.
  - If the source path is missing, check whether the skill is native or plugin-provided before assuming the file is gone.
