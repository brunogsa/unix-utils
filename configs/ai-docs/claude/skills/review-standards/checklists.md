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
