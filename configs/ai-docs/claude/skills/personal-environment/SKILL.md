---
name: personal-environment
description: "ALWAYS load when editing CLAUDE.md, SKILL.md, .zshrc, or any config in ~/.claude/, ~/oh-my-zsh/, ~/neovim/, ~/tmux/, ~/ghostty/, ~/unix-utils/, or when adding a new script or command. Symlink, canonical-path, ~/oh-my-zsh/-vs-skill placement rules."
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

A `Bash(...)` rule in `settings.json` `permissions.allow` matches the **command text as written**, not the file it resolves to — the symlink path and the canonical path are two different commands.

Why: a Bash rule "doesn't match the same program invoked in a different form" (https://code.claude.com/docs/en/permissions#bash-rule-limits) — a row for one form silently leaves the other prompting.

- `~/.claude/...` form: one row covers both platforms; `claude-prose-format-posttool-hook.sh` prints its re-run commands in this form.
- Canonical form (`realpath`): one row per platform, since home dirs differ.
  - macOS: `"Bash(/Users/brunoagostini/unix-utils/configs/ai-docs/claude/skills/.../script.sh *)"`
  - Linux: `"Bash(/home/brunogsa/unix-utils/configs/ai-docs/claude/skills/.../script.sh *)"`

- An interpreter prefix (`bash `, `python3 `) makes another form — give it its own rows.

`Read(...)`/`Edit(...)` rules differ: `~/` means the home directory, and an allow rule applies only when both the requested path and the file it resolves to match (https://code.claude.com/docs/en/permissions#symlinks).

## Platform differences (macOS vs Linux)

Home directory paths differ — `/Users/brunoagostini` on macOS, `/home/brunogsa` on Linux. Any path-based config (permissions, hooks, scripts) needs both entries.

Why: rules baked for one platform break silently on the other. Cross-platform setup requires explicit parallel entries.
