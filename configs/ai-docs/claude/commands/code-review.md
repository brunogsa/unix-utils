---
description: "Automated PR code review with context from aireview and posting via GitHub CLI"
---

# Automated Code Review

Perform a comprehensive automated code review of a GitHub Pull Request.

**IMPORTANT LANGUAGE REQUIREMENT**:
- **Instructions**: Written in English (this document)
- **All Review Output**: Must be in **Portuguese (Brazil)**
  - Comments, changelog, summary, issues, suggestions
  - Code examples and diffs can remain in original language
  - Error messages to user: English (user preference)

## Arguments

Usage: `/code-review <pr-url>`

Example:
- `/code-review https://github.com/owner/repo/pull/1597`

## Execution Steps

### 1. Generate Complete Review Context

Run `aireview` in GitHub mode with the PR URL:

```bash
# Run aireview --github to generate complete context
aireview --github "<pr-url>" > /tmp/aireview-output.txt 2>&1

# Extract bundle path from output
bundle_path=$(grep "Bundle file:" /tmp/aireview-output.txt | awk '{print $3}')
```

This single command automatically:
- Fetches PR metadata (number, title, body, base/head refs)
- Generates repository structure map (via Aider)
- Includes full content of modified files with line numbers
- Includes unified git diff (excluding lockfiles)
- Includes commit history and git stats
- Includes code conventions from CLAUDE.md
- **Adds PR description in optimal position** for LLM prompt engineering

The bundle file is now ready for review with everything in the optimal order:
1. Header (metadata)
2. Review guidelines (primes the AI)
3. **PR description** (high-level context)
4. Git context (commits, stats)
5. Git diff (actual changes)
6. Repository structure (architectural context)
7. Full file contents (deep dive)

**IMPORTANT**: The bundle file contains everything needed for review. **NEVER** try to use `gh pr diff` or run git commands directly.

### 2. Get Commit SHA for Posting Comments

Extract owner, repo, and PR number from URL, then get commit SHA:

```bash
# Extract components from URL
owner=$(echo "<pr-url>" | sed -n 's|^https://github\.com/\([^/]*\)/.*|\1|p')
repo=$(echo "<pr-url>" | sed -n 's|^https://github\.com/[^/]*/\([^/]*\)/.*|\1|p')
pr_number=$(echo "<pr-url>" | sed -n 's|^https://github\.com/[^/]*/[^/]*/pull/\([0-9]*\).*|\1|p')

# Get commit SHA for posting comments
commit_sha=$(gh pr view "$pr_number" --repo "${owner}/${repo}" --json headRefOid --jq '.headRefOid')
```

### 3. Read the Complete Bundle File

**CRITICAL REQUIREMENT**: You MUST read the ENTIRE bundle file, regardless of size. This is MANDATORY for accurate code review.

**Step 3.1: Check file size and determine reading strategy**

```bash
# Get file size in lines
bundle_lines=$(wc -l < "$bundle_path")
echo "Bundle file has $bundle_lines lines"
```

**Step 3.2: Read the entire file using appropriate strategy**

The bundle file may exceed token limits (>1500 lines). You MUST use one of these strategies to ensure the ENTIRE file is read:

**Strategy A: Multiple reads with offset (PREFERRED)**

Read the file in chunks, ensuring full coverage:

```bash
# Read first 1500 lines
# Use Read tool with: file_path=$bundle_path, offset=0, limit=1500

# Read next 1500 lines
# Use Read tool with: file_path=$bundle_path, offset=1500, limit=1500

# Continue until entire file is read
# Calculate: total_reads = ceil(bundle_lines / 1500)
```

**Strategy B: Split into multiple files**

If the file is extremely large (>10000 lines), split it:

```bash
# Split bundle into 1500-line chunks
split -l 1500 "$bundle_path" /tmp/bundle-part-

# This creates: /tmp/bundle-part-aa, /tmp/bundle-part-ab, etc.
# Then read each part sequentially using the Read tool
```

**Step 3.3: Verification**

After reading, verify you have the complete context by confirming:
- You've seen the repository structure map (at the beginning)
- You've seen all modified files' content
- You've seen the unified git diff
- You've seen the commit history
- You've seen the PR description (at the end)

**If any section is missing, you MUST go back and read the missing portions.**

### 4. Perform Code Review (in Portuguese)

After ensuring you have read the ENTIRE bundle file (which now includes PR description), analyze the changes following the guidelines from the `aireview` output and PR context.

**CRITICAL REVIEW SCOPE**:
- **ONLY review code that appears in the diff** (added, changed, or removed lines)
- **DO NOT comment on unchanged code** unless it directly relates to the changes
- Focus your review on the modifications the developer made
- If you notice issues in untouched code, mention it briefly but don't create detailed comments

For each issue found:

**Comment format:**
- `path`: file path
- `start_line` + `line`: **ALWAYS use code ranges** for logical blocks (not just the last line)
- `line` only: Only for truly single-line issues
- `body`: text in **Portuguese** with:
  - **[SEVERITY]** `MANDATORY` | `RECOMMENDED` | `NITPICK` | `COMPLIMENT` | `QUESTION`
    - **MANDATORY**: Direct and assertive, no quote line
    - **RECOMMENDED**: Add quote line at start: `> Pode resolver esta thread depois de ler. Fique a vontade de fazê-la ou não!`
    - **NITPICK**: Add quote line at start: `> Pode resolver esta thread depois de ler. Fique a vontade de fazê-la ou não!` (friendly, conversational, non-pedantic tone)
    - **COMPLIMENT**: Add quote line at start: `> Pode resolver esta thread depois de ler. Fique a vontade de fazê-la ou não!` (warm, encouraging tone - use sparingly for excellent work)
    - **QUESTION**: If standalone, no quote line (must be answered); if embedded in other severity types, include inline
  - Clear explanation of the problem
  - Why it matters
  - Suggested fix with code (when applicable):
    - **GitHub suggestions**: Max 16 lines, MUST preserve exact indentation
    - **Unified diffs**: Max 32 lines each, split into multiple if needed

### 5. Generate Changelog and Summary (in Portuguese)

Create a summary in **Portuguese** with:

**Changelog (grouped by type) - in Portuguese:**
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

### 6. Publish Individual Inline Comments via GitHub API

Post **individual inline comments** directly on specific code lines/ranges (like clicking "Add single comment" in GitHub UI, not "Start a review").

**CRITICAL REQUIREMENTS**:
- **NEVER post code feedback as general comments** - ALL code-related feedback MUST be inline comments on specific lines
- Use **individual comment API** (not review API)
- Prefer **code ranges** over single lines when applicable
- Use **GitHub suggestions** for better UX when suggesting code changes
- **ONLY the Changelog summary goes in the general comment section** (Step 1 below)
- **ALL other feedback MUST be inline comments** (Step 2 below)

**Workflow:**

**Step 1: Create summary markdown file and post it**

```bash
# Create summary file
cat > /tmp/review-summary.md << 'EOF'
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
EOF

# Post summary comment (conversation tab)
gh pr comment {pr_number} --body-file /tmp/review-summary.md
```

**Step 2: Create markdown files for each inline comment**

For each issue, create a markdown file and post as individual inline comment:

```bash
# Example 1: MANDATORY comment with GitHub suggestion
cat > /tmp/comment-1.md << 'EOF'
**[MANDATORY]**

**Exit codes hardcoded sem constantes**

O código usa `process.exit(1)` diretamente, violando a convenção de evitar magic numbers.

**Correção sugerida:**
```suggestion
enum ExitCode {
    SUCCESS = 0,
    VALIDATION_ERROR = 1,
    PROCESSING_ERROR = 2,
}

if (errorsHandler.hasFailedLines) {
    logger.warn({
        message: `Houve ${errorsHandler.failedLinesQuantity} erros...`,
    });
    process.exit(ExitCode.VALIDATION_ERROR);
}
```

**Por que isso importa:**
- Melhora a legibilidade e manutenibilidade do código
- Facilita a automação e tratamento de erros por scripts externos
EOF

# Post inline comment on CODE RANGE (not just last line)
gh api repos/{owner}/{repo}/pulls/{pr_number}/comments \
  --method POST \
  --field body@/tmp/comment-1.md \
  --field path="scripts/transform-return-csv/src/index.ts" \
  --field commit_id="{commit_sha}" \
  --field start_line=148 \
  --field line=152 \
  --field side="RIGHT"
```

```bash
# Example 2: RECOMMENDED comment with quote line
cat > /tmp/comment-2.md << 'EOF'
**[RECOMMENDED]**

> Pode resolver esta thread depois de ler. Fique a vontade de fazê-la ou não!

**Falta sanitização de inputs do CSV**

Os valores são usados diretamente sem trim() ou normalização.

**Sugestão:**
```suggestion
private setValues(rawItemLine: RawItemLine & { lineNumber?: number }): void {
    this.externalId = rawItemLine["Pedido de Devolucao"]?.trim();
    this.linkedOrderNumber = rawItemLine["Pedido Vinculado"]?.trim();
    this.orderTimestamp = rawItemLine["Data do Pedido de Devolucao"];
    this.quantity = parseInt(rawItemLine["Quantidade"]?.trim());
    this.schoolDocNumber = rawItemLine["CNPJ da Escola"]?.trim().replace(/\D/g, "");
    this.sku = rawItemLine["SKU"]?.trim().toUpperCase();
}
```

**Por que isso pode ajudar:**
- Previne erros causados por espaços extras nos dados
- Normaliza CNPJ removendo caracteres não numéricos
EOF

# Post on CODE RANGE (entire logical block)
gh api repos/{owner}/{repo}/pulls/{pr_number}/comments \
  --method POST \
  --field body@/tmp/comment-2.md \
  --field path="src/return-item-line.ts" \
  --field commit_id="{commit_sha}" \
  --field start_line=74 \
  --field line=85 \
  --field side="RIGHT"
```

```bash
# Example 3: NITPICK comment with friendly tone
cat > /tmp/comment-3.md << 'EOF'
**[NITPICK]**

> Pode resolver esta thread depois de ler. Fique a vontade de fazê-la ou não!

**Magic number sem explicação**

O valor `FIRST_LINE_NUMBER = 2` poderia ter um comentário explicando o porquê.

**Sugestão:**
```suggestion
// Linha 1 é o cabeçalho do CSV, então os dados começam na linha 2
const FIRST_LINE_NUMBER = 2;
```
EOF

# Single line is OK for truly single-line issues
gh api repos/{owner}/{repo}/pulls/{pr_number}/comments \
  --method POST \
  --field body@/tmp/comment-3.md \
  --field path="src/index.ts" \
  --field commit_id="{commit_sha}" \
  --field line=87 \
  --field side="RIGHT"
```

```bash
# Example 4: COMPLIMENT comment
cat > /tmp/comment-4.md << 'EOF'
**[COMPLIMENT]**

> Pode resolver esta thread depois de ler. Fique a vontade de fazê-la ou não!

**Excelente implementação do padrão Circuit Breaker!**

O código demonstra bom entendimento de sistemas distribuídos:
- Fallback strategy bem definida
- Timeouts configuráveis
- Métricas para observabilidade

Continue com este nível de qualidade!
EOF

gh api repos/{owner}/{repo}/pulls/{pr_number}/comments \
  --method POST \
  --field body@/tmp/comment-4.md \
  --field path="src/services/api-client.ts" \
  --field commit_id="{commit_sha}" \
  --field start_line=45 \
  --field line=67 \
  --field side="RIGHT"
```

```bash
# Example 5: QUESTION comment (standalone - no quote line)
cat > /tmp/comment-5.md << 'EOF'
**[QUESTION]**

**Por que usar polling ao invés de webhooks?**

Notei que o sistema usa polling a cada 30 segundos para verificar mudanças.

Considerou usar webhooks? Isso poderia:
- Reduzir latência de resposta
- Diminuir carga no servidor
- Economizar requisições de API

Existe alguma limitação técnica que justifica o polling?
EOF

gh api repos/{owner}/{repo}/pulls/{pr_number}/comments \
  --method POST \
  --field body@/tmp/comment-5.md \
  --field path="src/sync-service.ts" \
  --field commit_id="{commit_sha}" \
  --field line=123 \
  --field side="RIGHT"
```

**When to use unified diff vs GitHub suggestion:**

- **GitHub suggestion** (```suggestion): When suggesting a **replacement** for existing code
  - MUST preserve exact indentation from original code
  - Max 8 lines
  - Author can apply with one click
  - Shows clean before/after comparison
  - PREFERRED for most code changes when conditions are met

- **Unified diff** (```diff): When:
  - Suggestion would be >8 lines (max 32 lines per diff, split if needed)
  - Multiple files involved
  - Conceptual/educational explanation
  - Unsure about exact indentation (prefer diff over wrong-indentation suggestion)
  - Still preserve exact indentation in the diff

**Why use markdown files in /tmp:**
- **No escaping needed**: Backticks, quotes, and special characters work naturally
- **Easier to read**: Clean markdown without backslashes
- **Better UX**: Comments render correctly on GitHub
- **Simpler debugging**: Can inspect files before posting
- Use pattern: `/tmp/comment-{number}.md` for inline comments

**Important notes:**
- **`body@/tmp/file.md`**: The `@` prefix tells `gh` to read from file (no escaping needed!)
- **`commit_id`**: Get from `gh pr view {pr_number} --json headRefOid` → `.headRefOid`
- **`start_line` + `line`**: Use ranges (e.g., 74-85) for multi-line comments (PREFERRED)
- **`line` only**: For single-line comments (use sparingly)
- **`side: "RIGHT"`**: Comment on new code (the PR changes)
- **`path`**: File path relative to repo root
- Each API call creates an **independent inline comment** (not part of a review)
- Comments can be marked as "Resolved" by the PR author
- All comment bodies must be in **Portuguese**
- Create separate markdown files: `/tmp/review-summary.md`, `/tmp/comment-1.md`, `/tmp/comment-2.md`, etc.

**Handling Line Range Errors:**

If posting a comment fails with line range errors (e.g., "line not found", "invalid range"), follow this process:

1. **Extract the clone path from aireview output**:
   ```bash
   # Look for "Cloned at: /tmp/aireview.repo-name.XXXXX/repo-name"
   grep "Cloned at:" /tmp/aireview-output.txt
   ```

2. **Read the actual file with line numbers**:
   ```bash
   # Use Read tool on: /tmp/aireview.repo-name.XXXXX/repo-name/path/to/file.ts
   # This shows the actual file with accurate line numbers
   ```

3. **Cross-reference with the diff**:
   - The bundle's "Git Diff Output" section shows which lines changed
   - The bundle's "Modified Files Content" section shows the full file with line numbers (via cat -n)
   - Match the code snippet from the diff to the line numbers in the full file

4. **Verify commit SHA**:
   ```bash
   # Ensure you're using the correct commit SHA
   gh pr view {pr_number} --json headRefOid
   # Use the .headRefOid value
   ```

5. **Retry with corrected values**:
   - Update `start_line` and `line` to match the actual file
   - Ensure `commit_id` matches the PR head SHA
   - Verify `path` is correct relative to repo root

6. **NEVER fallback to general comments**:
   - Keep trying with corrected line numbers
   - If code truly doesn't exist in the PR, skip that specific comment
   - All code feedback MUST be inline

**Common causes of line range errors**:
- Using diff line numbers instead of actual file line numbers
- Wrong commit SHA (not using headRefOid)
- File path incorrect (not relative to repo root)
- Commenting on code that was deleted or not in the HEAD commit

**Line Number Mapping Strategy:**

To accurately map diff changes to file line numbers:

1. **Understand diff format**:
   - Diff shows: `@@ -old_start,old_count +new_start,new_count @@`
   - `+new_start` indicates the line number in the NEW version of the file
   - This is the line number to use for comments

2. **Use the bundle's "Modified Files Content" section**:
   - This section has the COMPLETE file with line numbers (via `cat -n`)
   - Find your code snippet in this section
   - The line number prefix is the EXACT line number to use

3. **For multi-line comments (code ranges)**:
   - Find the first line of the logical block in "Modified Files Content"
   - Find the last line of the logical block
   - Use `start_line` = first line, `line` = last line

**Example**:
```
Modified Files Content shows:
    42    function validateUser(userId) {
    43      if (!userId) {
    44        throw new Error("Invalid user");
    45      }
    46      return db.findUser(userId);
    47    }

Comment should use: start_line=42, line=47
```

### 7. Display Results

After publishing, show (in Portuguese):

```
╔════════════════════════════════════════════════════════╗
║           ✅ Code Review Completo                      ║
╚════════════════════════════════════════════════════════╝

📍 PR #1597: <título do PR>
🔗 <URL do PR>

📊 Resumo da Revisão:
- 📁 Arquivos alterados: X
- ➕ Linhas adicionadas: Y
- ➖ Linhas removidas: Z

💬 Comentários postados: N
- ❌ Obrigatórios: M
- ⚠️ Recomendados: P
- 💡 Nitpicks: Q
- 👍 Compliments: R
- ❓ Questions: S
```

## Important Guidelines

- **MANDATORY: Read the ENTIRE bundle file** - regardless of size, you MUST read every line using multiple Read calls with offset/limit if needed (see Step 3)
- **MANDATORY: NEVER post code feedback as general comments** - ALL code-related feedback MUST be inline comments on specific lines. Only the Changelog summary goes in general comments.
- **MANDATORY: Fix line range errors** - if posting fails due to line range issues, read the actual file from the /tmp checkout (path in aireview output) to find correct line numbers and retry. NEVER give up and post as general comment.
- **ALL OUTPUT in Portuguese (Brazil)** - comments, changelog, summary, everything
- **Follow `aireview` output** for review criteria
- **ALWAYS use code ranges** (`start_line` + `line`) for logical blocks, not just the last line
- **Preserve exact indentation** in both suggestions and diffs (CRITICAL)
- **Length limits**: Suggestions max 16 lines, diffs max 32 lines (split if needed)
- **Severity formatting**:
  - MANDATORY: No extra tags, direct and assertive
  - RECOMMENDED/NITPICK/COMPLIMENT: Add quote line, appropriate tone for each
  - QUESTION: No quote line if standalone (must be answered), inline if embedded
- **Be educational and kind** in feedback
- **Provide code examples** with proper indentation
- **Focus on valuable feedback** (don't be too pedantic, especially for nitpicks)

## Error Handling

If something fails:
1. Explain the error in English (user's preference)
2. Show partial results obtained
3. Suggest next manual steps
