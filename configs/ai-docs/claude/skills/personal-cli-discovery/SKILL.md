---
name: personal-cli-discovery
description: "Discover Bruno's personal CLI commands in ~/oh-my-zsh, plus the rtk command proxy. USE when user says 'use my script/utility/func' for X, when a shell utility is needed, for unknown command names, or for any `rtk` command (gain, discover, proxy)."
user-invocable: false
---

# Personal CLI Discovery

Bruno maintains personal CLI commands in `~/oh-my-zsh/commands/` and `~/oh-my-zsh/lib/`. These are tools he uses from the terminal -- and you can use them too.

## How to discover commands

1. List available commands: `ls ~/oh-my-zsh/commands/`
2. List library functions: `ls ~/oh-my-zsh/lib/`
3. Learn usage: run `<command> --help` or `<command> -h`
4. If no help flag exists, read the comment header: `head -20 ~/oh-my-zsh/commands/<script>`

Commands in `commands/` define a shell function with the same name as the file (minus `.sh`). They are auto-sourced by `.zshrc` and available globally.

## Category hints

These are hints to help you find the right tool -- not exhaustive documentation. Always run `--help` for current usage.

- **AI tools**: `ai-request`, `ai-changelog`, `aigitcommit`, `aicmd`, `aicopy`, `aiyank`, `aiappend`, `estimate_tokens`

- **Data processing**: `jsonl-distribution-table.js`, `jsonl-merge-and-sort-by-field.js`, `anonymize-txt`, `gen-schema-from-json`, `json-deep-sort.js` (lives at `~/oh-my-zsh/json-deep-sort.js`, outside `commands/` and `lib/`)

- **Diff/comparison**: `diff-sorted-jsons`, `diff-sorted-txt`
- **Clipboard**: `copy` (cross-platform), `aicopy` (bulk file contents), `aiyank` (paths)
- **Git/review**: `vimreview`, `git-worktree-add`
- **Mermaid diagrams**: `render-ascii-mermaid`, `compile-mermaid`, `compile-gantt-mermaid`
- **AWS**: `aws-get-dlq-summary`
- **Vim/editor**: `search-replace-vim`
- **Tmux**: `tmux-pane-words-picker`
- **Notifications**: `notify`
- **System**: `detect-os`, `command-exists`, `list-project-paths`

## Key principles

- **Always use `--help` at runtime** -- never memorize static docs. Commands evolve; `--help` is the source of truth.
- **Search before creating** -- before writing a new script, check if one already exists here.
- **Don't read entire scripts to understand usage** -- use `--help` first, only read source if the help output is insufficient.
- **Node.js scripts** (`.js` files) are invoked with `node` and accept `--help` too.

## The rtk command proxy

A `PreToolUse` hook rewrites every Bash call to run through `rtk`, so you write the plain command and never type the prefix yourself.

rtk's own meta commands are the one exception — the hook only rewrites *other* tools' commands, so these have no unprefixed form and must be typed with `rtk`:

```bash
rtk gain              # token savings analytics
rtk gain --history    # per-command usage history with savings
rtk discover          # mine Claude Code history for missed opportunities
rtk proxy <cmd>       # run <cmd> raw, bypassing rtk's filtering
```

Route a `find` carrying compound predicates (`-o`, `-a`, or parenthesized groups) through `rtk proxy find`.

Why: `rtk find` rejects compound predicates outright, so the plain form just fails and `rtk proxy` is the documented way back to real `find`.
