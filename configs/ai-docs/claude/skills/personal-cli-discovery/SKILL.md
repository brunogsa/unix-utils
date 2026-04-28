---
name: personal-cli-discovery
description: "Discover Bruno's personal CLI commands in ~/oh-my-zsh. USE when user says 'use my script/utility/func' that does X, or when needing a shell utility — an existing command likely already does it. Also for unknown command names."
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
- **Data processing**: `jsonl-distribution-table.js`, `jsonl-merge-and-sort-by-field.js`, `anonymize-txt`, `gen-schema-from-json`, `json-deep-sort.js`
- **Diff/comparison**: `diff-sorted-jsons`, `diff-sorted-txt`
- **Clipboard**: `copy` (cross-platform), `aicopy` (bulk file contents), `aiyank` (paths)
- **Git/review**: `vimreview`, `git-worktree-add`
- **Mermaid diagrams**: `render-ascii-mermaid`, `compile-mermaid`, `compile-gantt-mermaid`
- **AWS**: `aws-get-dlq-summary`
- **Vim/editor**: `search-replace-vim`
- **Tmux**: `tmux-pane-words-picker`, `tmux-extract-claude-change-place`
- **Notifications**: `notify`
- **System**: `detect-os`, `command-exists`, `list-project-paths`

## Key principles

- **Always use `--help` at runtime** -- never memorize static docs. Commands evolve; `--help` is the source of truth.
- **Search before creating** -- before writing a new script, check if one already exists here.
- **Don't read entire scripts to understand usage** -- use `--help` first, only read source if the help output is insufficient.
- **Node.js scripts** (`.js` files) are invoked with `node` and accept `--help` too.
