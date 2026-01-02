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

`/code-review <pr-url> [jira-card-url]`

Examples:
- `/code-review https://github.com/owner/repo/pull/1597`
- `/code-review https://github.com/owner/repo/pull/1597 https://company.atlassian.net/browse/PROJ-123`

## Execution Steps

### 1. Generate Complete Review Context

```bash
# Run aireview --github (handles everything: PR metadata, repo map, files, diff, conventions, and Jira card when provided)
if [[ -n "<jira-card-url>" ]]; then
  aireview --github "<pr-url>" --jira "<jira-card-url>" > /tmp/aireview.log 2>&1
else
  aireview --github "<pr-url>" > /tmp/aireview.log 2>&1
fi

# Extract bundle path from output
bundle_path=$(grep "Bundle file:" /tmp/aireview.log | awk '{print $3}')

# Extract PR info from URL
pr_number=$(echo "<pr-url>" | sed 's|.*/pull/\([0-9][0-9]*\).*|\1|')
repo_path=$(echo "<pr-url>" | sed 's|.*github\.com/\([^/]*/[^/]*\).*|\1|')

# Get commit SHA for posting comments
commit_sha=$(gh pr view "$pr_number" --repo "$repo_path" --json headRefOid --jq '.headRefOid')
```

**What's in the bundle (optimally ordered for LLM):**
1. Review guidelines & code conventions
2. PR description (title, body)
3. Jira card (title, description, epic) - when provided
4. Git context (log, stats)
5. Git diff
6. Repository structure
7. Full file contents with line numbers

**CRITICAL**: The bundle has EVERYTHING. Never use `gh pr diff` or git commands.

### 2. Read Complete Bundle File

⚠️ **MANDATORY**: Read ENTIRE bundle file, regardless of size.

```bash
total_lines=$(wc -l < "$bundle_path")
echo "Bundle has $total_lines lines"
# Read in chunks if needed: offset 0, 2000, 4000, ...
```

**Bundle contains:**
- **Code Review Instructions** ← ⚠️ CRITICAL: Read this section first (all review philosophy from ~/.claude/CLAUDE.md)
- Code Conventions (Reference)
- PR description / Jira card
- Git context, diff, file contents with `LINE:00123|` prefixes

**Reading strategy:**
- ≤2000 lines → Read once
- >2000 lines → Read in chunks (offset: 0, 2000, 4000, ...)
- ✅ Verify seen: Code Review Instructions, Code Conventions, diff, git context

### 3. Perform Code Review (in Portuguese)

⚠️ **Apply guidelines from bundle's "Code Review Instructions" section:**

**Core principles:**
- **Confidence**: >80% → comment | 60-80% → question | <60% → skip
- **Structure**: Problem + Why + Fix (always explain why for learning)
- **Actionable**: Guide improvements, not observations
- **Scope**: ✅ Review diff only | ❌ No unchanged code (unless directly related)
- **Skip low-value**: Formatting/linting/test-failures/minor-naming | ✅ Catch typos

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

**Comment structure** (Problem → Why → Fix, from bundle's "Code Review Instructions"):
1. **[SEVERITY]** tag
2. Optional quote line (based on severity)
3. **Problem**: Clear, concise statement (one sentence)
4. **Why**: Brief explanation why it matters (1-2 sentences max)
5. **Fix**: Suggested solution with code snippet

⚠️ **Keep comments concise**:
- Aim for 3-5 lines total (problem + why + fix)
- Always include "why" for learning
- Be direct and educational, not conversational or verbose

### 4. Generate Changelog (in Portuguese)

⚠️ **Post changelog FIRST, before inline comments** (see bundle's "Changelog Guidelines" for full details)

**Purpose**: Business-level summary for human reviewers, not technical details.

**Structure**:
1. **Business context**: What problem/feature? (from PR/Jira if available)
2. **High-level approach**: How was it implemented conceptually? (PM-level explanation)
3. **Coverage**: Mention refactoring (what kind), tests included, docs updated

❌ **Avoid**: File lists, technical details, grouped categories (New features/Tests/Docs)
✅ **Include**: Business need, conceptual approach, brief coverage notes

**Example format:**
```markdown
## Changelog (salomao.ai)

[Business context: what problem this solves or feature it enables]

**Abordagem**: [High-level conceptual approach, like explaining to a PM]

**Cobertura**: [Brief mention of refactoring/tests/docs]
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
# Create comment body file
cat > /tmp/comment-1-body.txt << 'EOF'
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

# Read body into variable and post inline comment
body=$(cat /tmp/comment-1-body.txt)
gh api repos/"$repo_path"/pulls/"$pr_number"/comments \
  --method POST \
  -f body="$body" \
  -f path="src/index.ts" \
  -f commit_id="$commit_sha" \
  -F start_line=148 \
  -F line=152 \
  -f side="RIGHT"
```

**CRITICAL - Correct field flags:**
- Use `-f` for **string fields**: `body`, `path`, `commit_id`, `side`
- Use `-F` for **numeric fields**: `start_line`, `line`
- **DO NOT** use `--field body@/tmp/file.md` - it doesn't work!
- **MUST** read file content into variable first: `body=$(cat /tmp/file.txt)`

**Getting line numbers (KEY TO SUCCESS):**

Bundle's "Full content of files" section has reliable line numbers: `LINE:00123| code`

**Process:**
1. Find code in bundle's diff → locate in "Full content of files" section
2. Extract from `LINE:00123|` prefix (strip leading zeros)
3. For ranges: `start_line` = first line, `line` = last line

**Example:**
```
LINE:00148| if (errorsHandler.hasFailedLines) {
LINE:00149|     logger.warn({
LINE:00150|         message: `Houve ${errorsHandler.failedLinesQuantity} erros...`,
LINE:00151|     });
LINE:00152|     process.exit(1);
LINE:00153| }
```
→ Use: `start_line=148, line=152`

**Suggestion format:**
- **```suggestion** blocks (≤8 lines): Direct replacement, one-click apply
  - MUST preserve exact indentation
  - Preferred for most changes
- **```diff** blocks (≤32 lines): For longer changes, multiple files, or conceptual explanations
  - Split into multiple diffs if >32 lines

**Important notes:**
- `commit_id`: Use the `$commit_sha` from step 1
- `start_line` + `line`: Use ranges for multi-line (PREFERRED)
- `line` only: For truly single-line issues (rare)
- `side`: Always use `"RIGHT"` to comment on new code (the PR changes)
- `path`: File path relative to repo root
- **Field flags**: `-f` for strings, `-F` for numbers (see CRITICAL section above)

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

## Critical Reminders

⚠️ **Must-follow rules:**
- Read entire bundle (multiple Read calls with offset if needed)
- Use bundle's `LINE:00123|` format for line numbers (remove leading zeros)
- ALL code feedback = inline comments | ONLY changelog = general comment
- Output in Portuguese (Brazil): comments, changelog, summary
- Prefer code ranges (`start_line` + `line`) over single lines
- Preserve exact indentation in suggestions/diffs
- Limits: Suggestions ≤8 lines | Diffs ≤32 lines
- Be educational and kind

## Error Handling

**Common error: "invalid key: body@/tmp/file.md"**
- **Cause**: Using `--field body@/tmp/file.md` syntax
- **Fix**: Read file into variable first: `body=$(cat /tmp/file.md)`, then use `-f body="$body"`

**Common error: "No subschema in oneOf matched" (HTTP 422)**
- **Cause**: Missing required fields or wrong field types
- **Fix**: Ensure all required fields present:
  - `-f body="$body"` (string)
  - `-f path="file/path.ext"` (string)
  - `-f commit_id="$commit_sha"` (string)
  - `-F line=123` (number)
  - `-F start_line=120` (number, optional)
  - `-f side="RIGHT"` (string)

**If posting comment fails with line range errors:**
1. Double-check line numbers from the `LINE:00123|` prefix in bundle (remove leading zeros)
2. Verify the code snippet matches exactly
3. Verify `commit_id` matches `$commit_sha`
4. Retry with corrected values
5. **NEVER fallback to general comments** - keep trying with correct line numbers

**If something else fails:**
1. Explain error in English
2. Show partial results
3. Suggest next manual steps
