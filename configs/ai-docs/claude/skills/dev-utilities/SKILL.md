---
description: "Developer shell utilities for text anonymization, mermaid diagrams, clipboard, JSON diffs, schema generation, and vim workflows"
user-invocable: false
---

# Dev Utilities

Shell scripts at `~/oh-my-zsh/func-utilities/` for general development tasks.

## Scripts

### copy
Cross-platform clipboard copy using copyq. Pipe text to it.
```
echo "text" | copy
cat file.txt | copy
```

### anonymize-txt
Replaces PII patterns (CPF, CNPJ, UUID, dates, IPs, CEP, numbers, hashes) with placeholders via sed.
```
echo "..." | anonymize-txt
cat logs.txt | anonymize-txt | grep -Eo '<CPF>' | sort | uniq -c
```

### compile-mermaid
Compiles a Mermaid file to PNG, auto-detecting dimensions from SVG viewBox.
```
compile-mermaid diagram.mmd
```
Requires: `mmdc` (mermaid-cli)

### compile-gantt-mermaid
Same as compile-mermaid but optimized for Gantt charts. Accepts optional width override.
```
compile-gantt-mermaid gantt.mmd [width]
```

### diff-sorted-jsons
Deep-sorts two JSON files (optionally by specific fields), then opens them in meld for comparison.
```
diff-sorted-jsons fileA.json fileB.json [field1,field2,...]
```
Requires: `~/oh-my-zsh/json-deep-sort.js`, `meld`

### diff-sorted-txt
Sorts two text files and opens them in meld for comparison.
```
diff-sorted-txt fileA.txt fileB.txt
```

### gen-schema-from-json
Generates a JSON Schema from a sample JSON file using quicktype.
```
gen-schema-from-json input.json
```
Output: `input.schema.json`. Requires: `npx quicktype`

### node-debug-reminder
Prints a quick reference for Node.js debugging with `--inspect-brk` and Jest.
```
node-debug-reminder
```

### search-replace-vim
Finds files matching a pattern via ripgrep, then opens each in neovim with search-and-replace pre-filled. Interactive (y/n/q per file).
```
search-replace-vim <search_pattern> <replace_pattern>
```

### vimreview
Opens neovim with Diffview showing staged changes or comparing against a ref. Also accepts piped diffs. Opens the most recently modified file first.
```
vimreview              # staged changes
vimreview HEAD~3       # compare against ref
git diff ... | vimreview  # piped diff
```

### tmux-extract-claude-change-place
Tmux hotkey script (`prefix + g`). Scrapes the focused pane for the last Claude Code edit, copies `nvim +<line> <file>` to clipboard. Paste in any terminal to jump to the change location.
```
# Press Ctrl+a, g while the Claude Code pane is focused
# Then paste the clipboard in a terminal to open nvim at the edit
```
