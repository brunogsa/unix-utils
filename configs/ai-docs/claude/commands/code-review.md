---
description: "Automated PR code review with context from aireview and posting via GitHub CLI"
---

# Automated Code Review

Perform a comprehensive automated code review of a GitHub Pull Request.

**LANGUAGE REQUIREMENT**:
- Instructions: English (this document)
- **All review output: Portuguese (Brazil)** - comments, changelog, summary
- Code examples: original language
- Error messages to user: English

## Usage

`/code-review <pr-url>`

Example: `/code-review https://github.com/owner/repo/pull/1597`

## Execution Steps

### 1. Generate Complete Review Context

```bash
# Run aireview --github (handles everything: PR metadata, repo map, files, diff, conventions)
aireview --github "<pr-url>" > /tmp/aireview.log 2>&1

# Extract bundle path from output
bundle_path=$(grep "Bundle file:" /tmp/aireview.log | awk '{print $3}')

# Extract PR info from URL
pr_number=$(echo "<pr-url>" | grep -oP 'pull/\K[0-9]+')
repo_path=$(echo "<pr-url>" | grep -oP 'github\.com/\K[^/]+/[^/]+')

# Get commit SHA for posting comments
commit_sha=$(gh pr view "$pr_number" --repo "$repo_path" --json headRefOid --jq '.headRefOid')
```

**What's in the bundle (optimally ordered for LLM):**
1. Review guidelines & code conventions
2. PR description (title, body)
3. Git context (log, stats)
4. Git diff
5. Repository structure
6. Full file contents with line numbers

**CRITICAL**: The bundle has EVERYTHING. Never use `gh pr diff` or git commands.

### 2. Read Complete Bundle File

**MANDATORY**: Read the ENTIRE bundle file, regardless of size.

```bash
# Check file size
total_lines=$(wc -l < "$bundle_path")
echo "Bundle has $total_lines lines"

# Read in chunks if needed (2000 lines per read)
# Use Read tool with offset/limit to read entire file
```

**Reading strategy:**
- File ≤2000 lines: Read once
- File >2000 lines: Read in chunks with offset (0, 2000, 4000, ...)
- Verify you've seen: repo structure, modified files, diff, git context, PR description

### 3. Perform Code Review (in Portuguese)

**Review scope - CRITICAL**:
- ✅ **ONLY review code in the diff** (added/changed/removed lines)
- ❌ **DO NOT comment on unchanged code** unless directly related to changes
- Brief mention if you notice issues in untouched code, but no detailed comments

**For each issue found, create inline comment with:**

**Severity levels:**
- **MANDATORY** - Must fix (correctness, security, critical bugs)
  - Direct, assertive tone
  - No quote line prefix

- **RECOMMENDED** - Should address (code quality, performance, best practices)
  - Add: `> Pode resolver esta thread depois de ler. Fique a vontade de fazê-la ou não!`
  - Helpful, informative tone

- **NITPICK** - Optional improvements (minor style, subjective preferences)
  - Add: `> Pode resolver esta thread depois de ler. Fique a vontade de fazê-la ou não!`
  - Friendly, conversational, non-pedantic tone

- **COMPLIMENT** - Positive feedback (excellent patterns, clever solutions)
  - Add: `> Pode resolver esta thread depois de ler. Fique a vontade de fazê-la ou não!`
  - Warm, encouraging tone (use VERY sparingly)

- **QUESTION** - Genuine questions about design/implementation
  - Standalone: no quote line (must be answered)
  - Embedded in other severity: include inline

**Comment structure:**
1. **[SEVERITY]** tag
2. Optional quote line (based on severity)
3. Clear problem explanation
4. Why it matters
5. Suggested fix with code (when applicable)

### 4. Generate Changelog (in Portuguese)

Group changes by type:

```markdown
## Changelog (salomao.ai)

### Novas funcionalidades
- Item 1

### Correções
- Item 1

### Refatorações
- Item 1

### Testes
- Item 1

### Documentação
- Item 1
```

### 5. Post Comments via GitHub API

**CRITICAL RULES**:
- **ALL code feedback = inline comments** (never general comments)
- **ONLY changelog = general comment**
- Use **code ranges** (`start_line` + `line`) for logical blocks
- Preserve **exact indentation** in suggestions

**Step 5.1: Post changelog as general comment**

```bash
cat > /tmp/changelog.md << 'EOF'
## Changelog (salomao.ai)
[... your changelog ...]
EOF

gh pr comment "$pr_number" --repo "$repo_path" --body-file /tmp/changelog.md
```

**Step 5.2: Post inline comments**

For each issue, create markdown file and post:

```bash
# Create comment file
cat > /tmp/comment-1.md << 'EOF'
**[MANDATORY]**

**Exit codes hardcoded sem constantes**

O código usa `process.exit(1)` diretamente, violando a convenção de evitar magic numbers.

**Correção sugerida:**
```suggestion
enum ExitCode {
    SUCCESS = 0,
    VALIDATION_ERROR = 1,
}
process.exit(ExitCode.VALIDATION_ERROR);
```

**Por que isso importa:**
- Melhora legibilidade e manutenibilidade
- Facilita automação e tratamento de erros
EOF

# Post inline comment
gh api repos/"$repo_path"/pulls/"$pr_number"/comments \
  --method POST \
  --field body@/tmp/comment-1.md \
  --field path="src/index.ts" \
  --field commit_id="$commit_sha" \
  --field start_line=148 \
  --field line=152 \
  --field side="RIGHT"
```

**Getting correct line numbers (THE KEY TO SUCCESS):**

The bundle's "Modified Files Content" section contains files with **reliable line numbers** in the format `LINE:00123| code` (5-digit zero-padded to preserve indentation).

**Process:**
1. Find the code snippet in bundle's diff section
2. Locate the same code in the "Full content of files" section
3. Extract line numbers from the `LINE:00123|` prefix (just the digits)
4. Use those line numbers for `start_line` and `line`
5. For ranges: `start_line` = first line of logical block, `line` = last line

**Example from bundle:**
```
### `src/index.ts`
```
LINE:00148| if (errorsHandler.hasFailedLines) {
LINE:00149|     logger.warn({
LINE:00150|         message: `Houve ${errorsHandler.failedLinesQuantity} erros...`,
LINE:00151|     });
LINE:00152|     process.exit(1);
LINE:00153| }
```

For this block, use: `start_line=148, line=152` (remove leading zeros)

**Suggestion format:**
- **```suggestion** blocks (≤8 lines): Direct replacement, one-click apply
  - MUST preserve exact indentation
  - Preferred for most changes
- **```diff** blocks (≤32 lines): For longer changes, multiple files, or conceptual explanations
  - Split into multiple diffs if >32 lines

**Important notes:**
- `body@/tmp/file.md`: The `@` tells gh to read from file (no escaping!)
- `commit_id`: Use the `$commit_sha` from step 1
- `start_line` + `line`: Use ranges for multi-line (PREFERRED)
- `line` only: For truly single-line issues (rare)
- `side: "RIGHT"`: Comment on new code (the PR changes)
- `path`: File path relative to repo root

### 6. Display Results (in Portuguese)

```
╔════════════════════════════════════════════════════════╗
║           ✅ Code Review Completo                      ║
╚════════════════════════════════════════════════════════╝

📍 PR #<number>: <título>
🔗 <pr-url>

📊 Resumo:
- 📁 Arquivos: X
- ➕ Adicionadas: Y
- ➖ Removidas: Z

💬 Comentários: N
- ❌ Obrigatórios: M
- ⚠️ Recomendados: P
- 💡 Nitpicks: Q
- 👍 Compliments: R
- ❓ Questions: S
```

## Important Guidelines

- **MANDATORY: Read entire bundle** - use multiple Read calls with offset/limit if needed
- **MANDATORY: Use bundle line numbers** - extract from `LINE:00123|` format (5-digit zero-padded) in "Full content of files" section
- **MANDATORY: All code feedback as inline comments** - never post code feedback as general comments
- **All output in Portuguese (Brazil)** - comments, changelog, summary
- **Always use code ranges** (`start_line` + `line`) for logical blocks
- **Preserve exact indentation** in suggestions and diffs (CRITICAL)
- **Length limits**: Suggestions max 8 lines, diffs max 32 lines
- **Be educational and kind** - provide code examples with proper indentation

## Error Handling

If posting comment fails with line range errors:
1. Double-check line numbers from the `LINE:00123|` prefix in bundle (remove leading zeros)
2. Verify the code snippet matches exactly
3. Verify `commit_id` matches `$commit_sha`
4. Retry with corrected values
5. **NEVER fallback to general comments** - keep trying with correct line numbers

If something else fails:
1. Explain error in English
2. Show partial results
3. Suggest next manual steps
