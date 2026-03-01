---
description: "Enhance Global Guidelines with Session Learnings"
disable-model-invocation: true
---

# Enhance Global Guidelines with Session Learnings

Review this coding session and identify learnings that should be added to CLAUDE.md or skills. Delegate the analysis to a **foreground subagent** to preserve the main session context window.

## Scope

- **CLAUDE.md** (`~/.claude/CLAUDE.md`) -- high-level principles, workflow rules, TL;DRs
- **Skills** (`~/.claude/skills/*/SKILL.md`) -- detailed examples, domain knowledge, tool docs

Learnings go to whichever file they belong in. Principles go to CLAUDE.md; detailed examples and domain-specific knowledge go to the relevant skill.

## Execution (Hybrid)

Subagents cannot see the parent conversation history. Use a hybrid approach:

1. **Main context** performs step 1 (extract session moments) -- lightweight, stays in the main context.
2. **Subagent** receives those moments and performs steps 2-8 (analysis, file reads, cross-checking, presenting findings, user approval, edits, verification) -- heavy, offloaded.

Spawn the subagent with `subagent_type: "general-purpose"` and `description: "Analyze session for guideline learnings"` (foreground). The subagent prompt must include **Scope**, the extracted session moments, and everything from **Subagent Process** through **Guidelines for Generalization** below.

## Step 1: Extract Session Moments (main context)

Review the conversation history and write a concise bullet list of:
- Bugs that were found and fixed
- Code patterns that were corrected
- Workflow or process feedback from the user
- Design decisions and their rationale
- Anti-patterns that were identified
- Testing strategies that worked well
- Documentation or communication improvements
- Any user correction of the AI's approach or assumptions

For each moment, include: what happened, what the user said or corrected, and the outcome. This list is passed verbatim into the subagent prompt as a `## Session Moments` section.

## Subagent Process (steps 2-8)

2. **Extract candidate learnings** - For each session moment, ask:
   - Is this a recurring pattern or a one-off situation?
   - Would this prevent future bugs or improve code quality?
   - Is it general enough to apply across projects?

3. **Generalize to language-agnostic principles** - Reframe learnings as universal principles, not language-specific syntax. Focus on the *why*, not the *how*.

4. **Determine target file** - For each learning:
   - High-level principle or workflow rule → CLAUDE.md (appropriate section)
   - Detailed code example or pattern → `skills/code-standards/SKILL.md`
   - Test example or strategy → `skills/test-standards/SKILL.md`
   - Review process improvement → `skills/review-standards/SKILL.md`
   - Domain-specific knowledge → relevant domain skill
   - New topic not covered by existing skills → propose a new skill

5. **Check against existing content** - Read the target file(s) and verify:
   - Does this learning already exist?
   - Is there a related guideline that needs clarification?
   - Would this contradict any existing content?

6. **Present findings** - Show the user:
   - What learnings were identified
   - How they were generalized
   - Target file for each (CLAUDE.md or which skill)
   - Which are new vs already covered
   - Proposed additions (if any)

7. **Apply changes only with approval** - Wait for user confirmation before modifying any file.

8. **Verify after editing** - After making changes:
   - Read the edited file
   - Check for **consistency**: no duplicate or contradictory guidelines, new items in correct section
   - Check for **proper structure**: imperative sentence format, examples where helpful, proper markdown
   - Check for **conciseness**: no verbose explanations, no redundant phrases, minimal but illustrative examples
   - Update **TL;DR sections** if adding important guidelines to CLAUDE.md
   - Report and fix any issues found

## Output Format

```
## Session Learnings Identified

1. [Learning description]
   - Context: [What happened in the session]
   - Generalized principle: [Language-agnostic version]
   - Target: [CLAUDE.md > SECTION or skills/skill-name/SKILL.md]
   - Status: [New / Already covered / Needs clarification]

## Proposed Additions

Number each proposal so the user can approve/reject by number (e.g., "Apply 1 and 3").

### CLAUDE.md > [Section: CODING/TESTING/WORKFLOW/etc.]
1. **[Guideline title]** - [Description]

### skills/[skill-name]/SKILL.md
2. **[Addition title]** - [Description]

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
