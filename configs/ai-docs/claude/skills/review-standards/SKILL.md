---
name: review-standards
description: "Code-review confidence bar and feedback rules. USE PROACTIVELY before commenting on a PR, running /auto-review or /code-review, or giving any code-review feedback — including phrases like 'review this' or 'look at my changes'."
user-invocable: false
---

# Review Standards

Complete review guidelines. Auto-loaded during code review activities.

---

## Language

- Instructions and code examples: English
- Output language is determined by the invoking context

---

## High Confidence Standard

Only provide feedback when you have sufficient confidence:

- **>80% confidence** -- make a direct comment with clear reasoning
- **60-80% confidence** -- ask a clarifying question to reduce ambiguity
- **<60% confidence** -- skip the comment entirely

Avoid speculative feedback using "maybe", "possibly", or "consider" without strong justification.

---

## Feedback Structure: Problem -> Why -> Fix

Every review comment uses bullet format:

- **Problem**: one sentence stating the issue
- **Why**: one sentence on impact (always include -- helps developers learn)
- **Fix**: code snippet, question, or concrete guidance

Keep it concise: 3-5 lines total, max 256 characters per line. No paragraphs -- bullets only. Avoid verbose explanations without educational value.

---

## Priority Tags

- **MANDATORY** -- must fix before merge (correctness, security, critical bugs). Direct, assertive tone.
- **RECOMMENDED** -- should address (code quality, performance, best practices).
- **NITPICK** -- optional improvements (minor style, subjective). Friendly, non-pedantic tone.
- **COMPLIMENT** -- positive feedback on excellent patterns. Use sparingly.
- **QUESTION** -- genuine design questions. Standalone: must be answered. Embedded in other tags: include inline.

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

## Recommended Reading Order

Before writing any comments, read the PR in this order:

1. **PR description** -- understand the business context and decisions first
2. **Test titles** -- scan `it('should ...')` lines to understand expected behavior without reading implementation
3. **Core implementation** -- controller/consumer first (orchestration), then use cases/pure functions (business logic)
4. **Test bodies** -- only after understanding the implementation, verify tests are meaningful

This order maximizes comprehension per minute: context → behavior → implementation → verification. Skip step 4 if short on time — steps 1-3 are sufficient for a quality review.

---

## Anti-Patterns

- Don't suggest broad rewrites -- prefer small, surgical changes
- Don't ask questions without explaining their impact
- Don't provide feedback without line numbers
- Don't suggest changes without showing a diff
- Don't forget to prioritize feedback by severity
