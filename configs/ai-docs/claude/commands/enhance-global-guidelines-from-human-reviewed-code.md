# Enhance Global Guidelines from Human-Reviewed Code

Extract learnings from the user's actual GitHub PR review comments and update CLAUDE.md or skills accordingly.

## Usage

`/enhance-global-guidelines-from-human-reviewed-code <pr-url> [pr-url-2] ...`

Accepts one or more PR URLs. The command fetches **only comments authored by brunogsa** on those PRs.

## Scope

- **CLAUDE.md** (`~/.claude/CLAUDE.md`) -- high-level principles, workflow rules, TL;DRs
- **Skills** (`~/.claude/skills/*/SKILL.md`) -- detailed examples, domain knowledge, tool docs
- **`/code-review` command** (`~/.claude/commands/code-review.md`) + **code-review-guidelines skill** (`~/.claude/skills/code-review-guidelines/SKILL.md`) -- format and tone alignment

Learnings go to whichever file they belong in. Principles go to CLAUDE.md; detailed examples go to the relevant skill. Format/tone adjustments go to the code-review command or guidelines skill.

## Process

### 1. Fetch Review Comments

For each PR URL, extract repo and PR number, then fetch the user's comments:

```bash
# Extract repo and PR number
repo_path=$(echo "<pr-url>" | sed 's|.*github\.com/\([^/]*/[^/]*\).*|\1|')
pr_number=$(echo "<pr-url>" | sed 's|.*/pull/\([0-9][0-9]*\).*|\1|')

# Fetch PR review comments (inline) by brunogsa
gh api "repos/$repo_path/pulls/$pr_number/comments" --paginate \
  --jq '[.[] | select(.user.login == "brunogsa") | {path, line, start_line, body, created_at}]'

# Fetch PR issue comments (general) by brunogsa
gh api "repos/$repo_path/issues/$pr_number/comments" --paginate \
  --jq '[.[] | select(.user.login == "brunogsa") | {body, created_at}]'
```

Read all fetched comments carefully before proceeding.

### 2. Analyze Comment Patterns

Review the fetched comments and identify:

- **Coding patterns enforced** -- what code quality issues does the user flag?
- **Review style & tone** -- how does the user phrase feedback? What format, structure, severity tags?
- **Recurring themes** -- patterns that appear across multiple comments or PRs
- **Testing expectations** -- what the user expects from test coverage
- **Anti-patterns called out** -- what the user consistently rejects

### 3. Cross-Check `/code-review` Format

Read the current `/code-review` command (`~/.claude/commands/code-review.md`) and the code-review-guidelines skill (`~/.claude/skills/code-review-guidelines/SKILL.md`).

Compare the user's actual comment style against the automated review format:

- **Severity tag usage** -- does the user use the same tags? Different ones?
- **Comment structure** -- does the user follow Problem → Why → Fix? Different order?
- **Tone and language** -- does the automated tone match the user's natural tone?
- **Quote prefixes** -- does the user use the same dismissal prefixes?
- **Code suggestions format** -- how does the user suggest fixes?
- **Conciseness** -- are the user's comments shorter/longer than the automated format prescribes?

Flag any mismatches for the user to review.

### 4. Extract Candidate Learnings

For each potential learning from the comments, ask:

- Is this a recurring pattern or a one-off situation?
- Would this prevent future bugs or improve code quality?
- Is it general enough to apply across projects?
- Does it reflect a preference not yet captured in CLAUDE.md or skills?

### 5. Generalize to Language-Agnostic Principles

Reframe learnings as universal principles, not language-specific syntax. Focus on the *why*, not the *how*.

### 6. Determine Target File

For each learning:

- High-level principle or workflow rule → CLAUDE.md (appropriate section)
- Detailed code example or pattern → `skills/code-standards/SKILL.md`
- Test example or strategy → `skills/test-standards/SKILL.md`
- Review format/tone adjustment → `commands/code-review.md` or `skills/code-review-guidelines/SKILL.md`
- Review process improvement → `skills/review-standards/SKILL.md`
- Domain-specific knowledge → relevant domain skill
- New topic not covered by existing skills → propose a new skill

### 7. Check Against Existing Content

Read the target file(s) and verify:

- Does this learning already exist?
- Is there a related guideline that needs clarification?
- Would this contradict any existing content?

### 8. Present Findings

Show the user everything before making changes. Use the output format below.

### 9. Apply Changes Only with Approval

Wait for user confirmation before modifying any file.

### 10. Verify After Editing

After making changes:

- Read the edited file
- Check for **consistency**: no duplicate or contradictory guidelines, new items in correct section
- Check for **proper structure**: imperative sentence format, examples where helpful, proper markdown
- Check for **conciseness**: no verbose explanations, no redundant phrases, minimal but illustrative examples
- Update **TL;DR sections** if adding important guidelines to CLAUDE.md
- Report and fix any issues found

## Output Format

```
## Comments Analyzed

- PR #<number> (<repo>): X inline comments, Y general comments
- [repeat for each PR]

## Review Format Alignment

### Matches
- [What already matches between user's style and /code-review format]

### Mismatches
- [Mismatch description]: User does [X], /code-review prescribes [Y]
  - Proposed adjustment: [change to make]
  - Target: [commands/code-review.md or skills/code-review-guidelines/SKILL.md]

## Learnings Identified

1. [Learning description]
   - Evidence: [Quote or paraphrase from user's comments]
   - Generalized principle: [Language-agnostic version]
   - Target: [CLAUDE.md > SECTION or skills/skill-name/SKILL.md]
   - Status: [New / Already covered / Needs clarification]

## Proposed Additions

### CLAUDE.md > [Section: CODING/TESTING/WORKFLOW/etc.]
1. **[Guideline title]** -- [Description]

### skills/[skill-name]/SKILL.md
1. **[Addition title]** -- [Description]

### commands/code-review.md or skills/code-review-guidelines/SKILL.md
1. **[Adjustment title]** -- [Description]

## Already Covered

- [Existing guideline/skill content that covers this]

## Post-Edit Verification

- Consistency: [OK / Issues found: ...]
- Structure: [OK / Issues found: ...]
- Conciseness: [OK / Issues found: ...]
- TL;DR updated: [Yes / No / Not needed]
```

## Guidelines for Generalization

- Focus on the underlying principle, not syntax
- Describe *what* to do and *why*, not language-specific *how*
- Keep guidelines concise (1-2 sentences max)
- Principles go to CLAUDE.md; examples and domain knowledge go to skills
- Format/tone adjustments go to the code-review command or guidelines skill
