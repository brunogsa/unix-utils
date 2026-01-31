---
description: "Code review philosophy, severity tag definitions, and Portuguese language preference for all review activities"
user-invocable: false
---

# Code Review Guidelines

Reusable review philosophy extracted from the `/code-review` command. Auto-loaded during any review activity.

## Language

- Instructions and code examples: English
- **All review output: Portuguese (Brazil)** -- comments, changelog, summary

## Review Philosophy

- **Confidence threshold**: >80% comment, 60-80% question, <60% skip
- **Structure**: Problem + Why + Fix (always explain why for learning)
- **Actionable**: guide improvements, not mere observations
- **Scope**: only review modified code (diff lines)
- **Skip low-value**: formatting/linting/test-failures/minor-naming. Catch typos.

## Severity Tags

- **MANDATORY** -- must fix before merge (correctness, security, critical bugs). Direct, assertive tone. No quote prefix.
- **RECOMMENDED** -- should address (code quality, performance, best practices). Prefix: `> Pode resolver esta thread depois de ler. Fique a vontade de faze-la ou nao!`
- **NITPICK** -- optional (minor style, subjective). Same prefix. Friendly, non-pedantic tone.
- **COMPLIMENT** -- positive feedback on excellent patterns. Same prefix. Use sparingly.
- **QUESTION** -- genuine questions about design/implementation. Standalone: no prefix (must be answered).

## Comment Format

1. **[SEVERITY]** tag
2. Optional quote prefix (based on severity)
3. **Problem**: clear, concise (one sentence)
4. **Why**: brief explanation (1-2 sentences max)
5. **Fix**: suggested solution with code snippet

Keep comments to 3-5 lines total. Be direct and educational.

## Changelog Format

Post changelog FIRST, before inline comments. Business-level summary in Portuguese.

```markdown
## Changelog (salomao.ai)

[Business context: what problem this solves]

**Abordagem**: [High-level conceptual approach]

**Cobertura**: [Brief mention of refactoring/tests/docs]
```
