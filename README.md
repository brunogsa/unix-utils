# unix-utils

Cross-platform system setup and configuration versioning. Installs core tools, dev dependencies, and AI tooling, then symlinks config files to their expected locations.

## Setup

```bash
./install.sh
```

The script installs core CLI utilities, clipboard manager (copyq), text expander (espanso), Docker, AWS CLI, dev tools, Claude Code with plugins, and symlinks all configs. All steps are idempotent.

## What It Manages

- **Core CLI tools** -- ripgrep, fd, jq, tree, htop, and more
- **Clipboard** (`configs/copyq/`) -- cross-platform copyq configuration
- **Text expansion** (`configs/espanso/`) -- snippet-based text expander
- **AI tooling** (`configs/ai-docs/`) -- Claude Code global config, skills, commands, hooks, and plugins
- **Desktop hotkeys** (`configs/xubuntu/`) -- Linux-only keyboard shortcuts

## Platforms

- **macOS**: tools via Homebrew, Docker via DMG, AWS CLI via pkg
- **Linux**: tools via apt, espanso via Snap, AWS CLI via zip

## Part of

Five-repo tooling stack: **unix-utils** | [oh-my-zsh](https://github.com/brunogsa/oh-my-zsh) | [tmux](https://github.com/brunogsa/tmux) | [neovim](https://github.com/brunogsa/neovim) | [ghostty](https://github.com/brunogsa/ghostty)
