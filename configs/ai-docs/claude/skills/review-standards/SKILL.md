---
description: "Code review guidelines covering confidence thresholds, feedback format, priority tags, changelog structure, and review process"
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

[Business context: what problem this solves or feature it enables]

**Approach**: [High-level conceptual approach, PM-level explanation]

**Coverage**: [Brief mention of refactoring/tests/docs]
```

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
