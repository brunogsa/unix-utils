# Enhance Global Guidelines with Session Learnings

Review this coding session and identify learnings that should be added to the global CLAUDE.md guidelines.

## Process

1. **Analyze the session** - Review the conversation history for:
   - Bugs that were found and fixed
   - Code patterns that were corrected
   - Feedback from the user on better approaches
   - Anti-patterns that were identified
   - Testing strategies that worked well

2. **Extract candidate learnings** - For each potential learning, ask:
   - Is this a recurring pattern or a one-off situation?
   - Would this prevent future bugs or improve code quality?
   - Is it general enough to apply across projects?

3. **Generalize to language-agnostic principles** - Reframe learnings as universal principles, not language-specific syntax. Focus on the *why*, not the *how*.

4. **Check against existing guidelines** - Read the global CLAUDE.md and verify:
   - Does this learning already exist?
   - Is there a related guideline that needs clarification?
   - Would this contradict any existing guideline?

5. **Present findings** - Show the user:
   - What learnings were identified
   - How they were generalized
   - Which are new vs already covered
   - Proposed additions (if any)

6. **Apply changes only with approval** - Wait for user confirmation before modifying CLAUDE.md.

## Output Format

```
## Session Learnings Identified

1. [Learning description]
   - Context: [What happened in the session]
   - Generalized principle: [Language-agnostic version]
   - Status: [New / Already covered / Needs clarification]

## Proposed Additions

### [Section: CODE/TESTS/DESIGN/etc.]
- **[Guideline title]** - [Description]

## Already Covered

- [Existing guideline that covers this]
```

## Guidelines for Generalization

- Focus on the underlying principle, not syntax
- Describe *what* to do and *why*, not language-specific *how*
- Keep guidelines concise (1-2 sentences max)
