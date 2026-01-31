---
description: "Code review guidelines covering confidence thresholds, feedback format, priority tags, changelog structure, and review process"
user-invocable: false
---

# Review Standards

Complete review guidelines. Auto-loaded during code review activities.

---

## High Confidence Standard

Only provide feedback when you have sufficient confidence:

- **>80% confidence** -- make a direct comment with clear reasoning
- **60-80% confidence** -- ask a clarifying question to reduce ambiguity
- **<60% confidence** -- skip the comment entirely

Avoid speculative feedback using "maybe", "possibly", or "consider" without strong justification.

---

## Feedback Structure: Problem -> Why -> Fix

Every review comment follows this flow:

1. **State the problem** -- one sentence
2. **Explain why it matters** -- 1-2 sentences max (always include for learning)
3. **Suggest the fix** -- code snippet, question, or guidance

Keep it concise: aim for 3-5 lines total.

---

## Priority Tags

- **MANDATORY** -- must fix before merge (correctness, security, critical bugs). Direct, assertive tone.
- **RECOMMENDED** -- should address (code quality, performance, best practices). Prefix with: `> Pode resolver esta thread depois de ler. Fique a vontade de faze-la ou nao!`
- **NITPICK** -- optional improvements (minor style, subjective). Same prefix. Friendly, non-pedantic tone.
- **COMPLIMENT** -- positive feedback on excellent patterns. Same prefix. Use sparingly.
- **QUESTION** -- genuine questions about design decisions. Standalone: no prefix (must be answered). Embedded in other tags: include inline.

---

## Review Priority Order

Review in this sequence (most to least critical):

1. **Correctness** -- logic, bugs, race conditions, ordering
2. **Corner cases** -- edge cases, failures, timeouts, empty/large data, i18n
3. **Testing** -- expected behavior documented, corner cases covered, deterministic
4. **Code quality** -- clarity, naming, no magic numbers, high cohesion
5. **Logging** -- useful, leveled, non-PII, actionable
6. **Design & Simplicity** -- SRP, OCP, LSP, ISP, DIP; reduce unnecessary complexity, consolidate redundant code
7. **DRY / KISS** -- remove duplication, keep simple
8. **Performance** -- hot paths, Big O, I/O, memory, N+1 queries
9. **Security** -- injection, path traversal, deserialization, authn/authz, secrets, SSRF/RCE

---

## Review Scope

**CRITICAL**: Only review modified code:
- Review: lines added (+), changed (- then +), removed (-)
- DO NOT review: untouched code
- Exception: unchanged code that creates a problem with changed code

---

## Review Process

1. **Start with a Changelog** -- business-level summary, posted first
2. **Post inline comments** -- following priority order
3. **End with action items** -- grouped by file, then priority

---

## Changelog Guidelines

**Purpose**: Business/product level summary, not technical details.

**Structure**:
- Business context: what problem/feature?
- High-level approach: conceptual explanation (PM-level)
- Coverage: mention refactoring, tests, docs

**Avoid**: file lists, technical details, generic groupings.

**Example:**
```markdown
## Changelog

Adds user authentication timeout to prevent session hijacking.
When users are inactive for 30 minutes, they're automatically logged out.

**Approach**: Sliding-window session tracking on backend with client-side activity monitoring.

**Coverage**: Includes refactoring of session middleware, adequate test coverage, updated API docs.
```

---

## Conciseness with Purpose

- State the issue concisely
- Explain why it matters (brief reasoning helps developers learn)
- Show the fix (examples or code snippets)
- Avoid verbose explanations without educational value

---

## Actionable Focus

- Every comment should lead to a clear next step
- Avoid mere observations -- explain what should change
- Include suggestions or questions

---

## Low-Value Comments to Avoid

Skip: formatting/style, linting errors, test failures, minor naming preferences, subjective refactoring.

DO provide feedback on: typos (user-facing), misleading names, convention-breaking formatting.

---

## Reference Format

- Single line: `src/services/auth.ts:42`
- Range (preferred): `src/services/auth.ts:42-48`

---

## Diffs & Suggestions

- **GitHub Suggestions** (```suggestion): <=16 lines, exact indentation, one-click apply
- **Unified Diffs** (```diff): >16 lines, multiple files, or unsure about indentation. Max 32 lines per diff.

Rules:
- MANDATORY: preserve exact indentation
- Prefer code ranges over single lines
- Many small diffs > one large diff
- Keep diffs surgical and minimal

---

## PR Requirements

- Small, focused PRs -- one baby step per PR
- Clear description -- link issues, summarize what and why

---

## Action Items Format

Group by file, then priority:

```
## Action Items

### src/services/auth.ts
- [MANDATORY] Line 42: Validate userId before query
- [RECOMMENDED] Line 67: Extract retry logic to helper function

### src/controllers/user.ts
- [MANDATORY] Line 23: Add input sanitization for email parameter
- [NITPICK] Line 45: Consider more descriptive variable name
```

---

## Anti-Patterns

- Don't suggest broad rewrites -- prefer small, surgical changes
- Don't ask questions without explaining their impact
- Don't provide feedback without line numbers
- Don't suggest changes without showing a diff
- Don't forget to prioritize feedback by severity
