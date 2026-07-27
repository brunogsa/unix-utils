# Mode C — AI! comments

Load this only when Step 1 detected Mode C: the arg mentions `AI!` (e.g. `AI! comments`).

Optional path restriction via `on <paths>` — comma-separated, where each entry can be a **file or folder**.

`AI!` is the same marker the `address-ai-comments` skill sweeps — but that skill *executes and strips* it, whereas this one only *mines it for a learning* (read-only).

`AI?` questions and `TODO`/`XXX` are different conventions; do not scan them here.

Steps:

1. Resolve the base branch (same primitive as `auto-review`):
   ```bash
   git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's|refs/remotes/origin/||'
   ```
   If detection fails (no `origin/HEAD` set), ask the user which base to diff against rather than guessing.

2. Resolve the file list:
   - **Explicit paths** (`on X, Y, Z`): expand each entry.
     - File → use as-is. Skip if it doesn't exist; warn the user.
     - Folder → list files inside via `git ls-files <folder>` (tracked) plus `git ls-files --others --exclude-standard <folder>` (untracked, respects `.gitignore`). This avoids scanning `node_modules`, `dist`, build outputs, etc.

   - **Default** (no explicit paths): union of three sets — committed branch changes, working-tree edits, untracked files.
     ```bash
     git diff --name-only <base>...HEAD          # committed branch changes
     git diff --name-only HEAD                   # uncommitted edits
     git ls-files --others --exclude-standard    # untracked
     ```

3. Scan each file for the literal string `AI!`, regardless of comment syntax.
   - Catches `// AI!`, `# AI!`, `<!-- AI! ... -->`, and bare-text `AI!` in `.md` files alike.
   - Match `AI!` only — never the `AI?` question marker (that's the live-answer path `address-ai-comments` owns).

Per-item field hints:
- **Source** — `path/to/file.ext:LINE`.
- **Verbatim** — the full `AI!` comment line (you may trim leading comment markers like `//` or `<!--` for readability; do not paraphrase the body).
- **Context** — ±3 lines around the marker.
- **Outcome** — `still open` (this skill never strips AI! comments).
- **Lesson drawn** — one sentence, generalizable.
