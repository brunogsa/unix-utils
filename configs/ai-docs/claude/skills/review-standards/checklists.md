# Review Checklists

Supplementary checklists for code review. Referenced by the review-standards skill.

---

## Corner Cases to Verify

- Empty inputs (null, undefined, "", [], {})
- Large inputs (pagination limits, memory constraints)
- Boundary values (0, -1, max int, max length)
- Invalid types or formats
- Timeout and retry scenarios
- Concurrent access and race conditions
- Internationalization (encoding, locale, timezone)

---

## Security Checklist

- SQL injection (parameterized queries)
- Command injection (input sanitization)
- XSS (output encoding)
- Deserialization vulnerabilities
- Authentication and authorization checks
- Secret and credential exposure
- SSRF/RCE risks
- Unsafe eval or dynamic code execution

---

## Testing Checklist

- Tests document expected behavior clearly
- Corner cases are covered
- Tests are deterministic (no flakiness)
- Tests are minimal and focused
- Mock only external dependencies
- Test names describe what and why, BDD-like if possible
- Missing tests for high-impact paths (rate gaps by: critical > important > edge case > nice-to-have)
- Tests coupled to implementation details (would break if implementation changes but behavior stays?)

---

## Silent Failure Checklist

- Catch blocks that swallow errors (empty catch, catch with only console.log)
- Fallback values that hide real failures (default returns masking bugs)
- Error logging without re-throwing or propagating
- Catch blocks that are too broad (catching Error instead of specific types)
- Missing error handling on async operations (unhandled promise rejections)
- User-facing error messages that leak internals or are unhelpful
- Error messages not actionable (reader can't determine what went wrong or how to fix it)
- Hidden failures via default values (`result || []` silently masking a real failure)

---

## Comment & Documentation Checklist

- Comments that contradict the actual code behavior
- Outdated comments referencing removed/renamed code
- TODO/FIXME/HACK comments without context or tracking
- Misleading function/param docstrings
- Comments explaining "what" instead of "why"
- Side effects and critical assumptions not documented in function/method comments
- Comments that will become stale when code changes (comment rot risk -- prefer tests/logs instead)

---

## Type Design Checklist

- Types that allow invalid states (prefer types that make illegal states unrepresentable)
- Missing readonly/immutability on data that shouldn't change
- Overly permissive types (string where union/enum fits)
- Types without enforced invariants (e.g., non-empty arrays typed as regular arrays)
- Unnecessary optional fields that are always present in practice
- Type invariants not explicitly named (what invariants does each type maintain?)
- Construction-time validation missing (does the constructor/factory enforce valid state?)

---

## Code Design Checklist

- Global mutable state (prefer params and return values)
- I/O in use-case/business layer (layered architecture violation)
- Deep nesting where guard clauses would simplify
- Inheritance where composition fits better
- Falsiness checks where null/undefined checks are needed
- Data not normalized at entry point (string dates, numbers-as-strings)
- Functions with 2+ positional params instead of named-param object
- Unused code not cleaned up (dead imports, orphaned functions)
- Unpinned dependency versions (ranges instead of exact)
- Loops with I/O missing progress logging
