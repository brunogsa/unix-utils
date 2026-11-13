# Mode C - AI markers in files

Load this only when Step 1 detected Mode C: the arg mentions `AI!`, `AI?`, `AI:`, `AI markers` or `AI comments` (e.g. `AI! comments`, `AI? comments`) and does not mention `verdict`.

Optional path restriction via `on <paths>` - comma-separated, where each entry can be a **file or folder**.

`AI!`, `AI?` and `AI:` are the same markers the `address-ai-comments` skill sweeps - but that skill *executes or answers, then strips* them, whereas this one only *mines them for a learning* (read-only).

- Why: mining never conflicts with `address-ai-comments` answering an `AI?` and stripping it, and a question the user had to ask shows where the AI fell short, which is a lesson.

`TODO`/`XXX` are a different convention; do not scan them here.

Steps:

1. Resolve the base branch (same primitive as `auto-review`):
   ```bash
   ~/.claude/scripts/resolve-base-ref.sh
   ```
   It falls back from origin/HEAD to local main to local master. If detection fails (none of the three resolve), ask the user which base to diff against rather than guessing.

2. Resolve the file list:
   - **Explicit paths** (`on X, Y, Z`): expand each entry.
     - File → use as-is. Skip if it doesn't exist; warn the user.
     - Folder → list files inside via `git ls-files <folder>` (tracked) plus `git ls-files --others --exclude-standard <folder>` (untracked, respects `.gitignore`). This avoids scanning `node_modules`, `dist`, build outputs, etc.

   - **Default** (no explicit paths): union of three sets - committed branch changes, working-tree edits, untracked files.
     ```bash
     git diff --name-only <base>...HEAD          # committed branch changes
     git diff --name-only HEAD                   # uncommitted edits
     git ls-files --others --exclude-standard    # untracked
     ```

   - Drop every `verdict_*.md` from either list: an `[AI!]` there is a finding pick, which Mode D mines.

3. Scan each file for lines carrying an `AI!`, `AI?` or `AI:` marker, regardless of comment syntax.
   - Matching rule: section "3d" of [`address-pr-comments/references/fetch-cluster-propose.md`](../../address-pr-comments/references/fetch-cluster-propose.md) - strip the comment syntax (`//`, `#`, `<!--`) first, then the first non-blank, non-list-marker token on the line starts with the marker, case-insensitive; the colon is optional after `AI!`/`AI?` and required on `AI:`.
   - Catches `// AI!`, `# AI?`, `<!-- AI: ... -->`, and bare-text markers in `.md` files alike.
   - Why: the first-token rule skips prose that merely mentions a marker, such as skill docs describing it.

Per-item field hints:
- **Source** - `path/to/file.ext:LINE`.
- **Verbatim** - the full marker line (`AI!`, `AI?` or `AI:`) (you may trim leading comment markers like `//` or `<!--` for readability; do not paraphrase the body).
- **Context** - ±3 lines around the marker.
- **Outcome** - `still open` (this skill never strips AI markers).
- **Lesson drawn** - one sentence, generalizable.
