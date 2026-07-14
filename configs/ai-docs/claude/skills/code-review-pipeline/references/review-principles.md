# Review Principles

Principles and paired rules for any code review. Each section pairs a principle with its rule/format.

Source-of-truth file for reviewer behavior — loaded by `code-review-pipeline`'s pipeline and by `address-pr-comments` when interpreting reviewer comments. Not a skill (no frontmatter); referenced by path.

## High confidence standard — skip below 60% on EMISSION, keep on VALIDATION

Confidence governs reviewer behavior at two gates that pull in opposite directions:

- **Emission gate (Wave 2 specialists):**
  - **>80% confidence** → emit a direct comment with clear reasoning.
  - **60-80% confidence** → emit as a clarifying question to reduce ambiguity.
  - **<60% confidence** → skip the comment entirely.
- **Validation gate (Wave 3 self-check, post-emission):**
  - **When in doubt, KEEP.** Dropping a real finding erodes trust more than keeping noise.
    - Only drop on clear, specific evidence the claim doesn't hold (cited code doesn't exist; code already does what was asked; the issue depends on behavior the file explicitly prevents).

Why two gates pull opposite ways: emission is cheap to abort (the comment doesn't exist yet), so the bar is "is this likely real?".

Validation is expensive to abort (the work is already done; dropping it loses the specialist's reasoning), so the bar is "is this provably wrong?".

One threshold can't govern both — they're not the same decision.

Avoid speculative feedback using "maybe", "possibly", or "consider" without strong justification at the emission gate. Don't compensate at validation — those are different problems.

## Feedback structure: Problem → Why → Fix

Every review comment uses bullet format:

- **Problem**: one sentence stating the issue.
- **Why**: one sentence on impact (always include — helps developers learn).
- **Fix**: code snippet, question, or concrete guidance.

Why: Problem alone leaves the author guessing about severity. Why educates. Fix removes ambiguity about what to do next. The triple is the unit of useful feedback.

Keep it concise: 3-5 lines total, max 256 characters per line. No paragraphs — bullets only.

## Priority tags — match severity to tone

- **MANDATORY** — must fix before merge (correctness, security, critical bugs). Direct, assertive tone.
- **RECOMMENDED** — should address (code quality, performance, best practices).
- **NITPICK** — optional improvements (minor style, subjective). Friendly, non-pedantic tone.
- **COMPLIMENT** — positive feedback on excellent patterns. Use sparingly.
- **QUESTION** — genuine design questions. Standalone: must be answered. Embedded in other tags: include inline.

Why: a NITPICK with MANDATORY tone is hostile. A MANDATORY with NITPICK tone is ignored. Matching severity to tone keeps the signal honest.

## Review in priority order — most critical first

1. **Correctness** — logic, bugs, race conditions, ordering.
2. **Corner cases** — edge cases, failures, timeouts, empty/large data, i18n.
3. **Testing** — expected behavior documented, corner cases covered, deterministic.
4. **Code quality** — clarity, naming, no magic numbers, high cohesion.
5. **Logging** — useful, leveled, non-PII, actionable.
6. **Design & Simplicity** — SRP, OCP, LSP, ISP, DIP; reduce unnecessary complexity, consolidate redundant code.
7. **DRY / KISS** — remove duplication, keep simple.
8. **Performance** — hot paths, Big O, I/O, memory, N+1 queries.
9. **Security** — injection, path traversal, deserialization, authn/authz, secrets, SSRF/RCE.

Why: time-boxed reviews need to surface MANDATORY issues first. If you spend the budget on NITPICK before scanning for correctness, you ship bugs.

## Only review modified code

**CRITICAL**: review lines added (+), changed (- then +), removed (-). Do NOT review untouched code.

Why: reviewing untouched code is scope creep and slows merges without value. Exception: unchanged code that creates a problem with changed code — that's in-scope because it's relevant to the change.

## Every comment leads to a clear next step

Avoid mere observations — explain what should change. Include suggestions or questions.

Why: observation-only comments ("this is interesting...") leave the author in limbo. Every comment must end with something the author can DO.

## Skip low-value comments

**Skip**: formatting/style, linting errors, test failures, minor naming preferences, subjective refactoring.

**DO** provide feedback on: typos (user-facing), misleading names, convention-breaking formatting.

Why: a linter catches formatting; surface it via the linter, not a comment. Reviewer attention is the scarce resource — spend it on what tools can't catch.

## Reference format: file:line or file:line-range

- Single line: `src/services/auth.ts:42`
- Range (preferred): `src/services/auth.ts:42-48`

Why: line numbers let the author jump to the exact spot. Range tells them how much context the comment refers to. Without these, every comment is a scavenger hunt.

## Action items grouped by file, then priority

```
## Action Items

### src/services/auth.ts
- [MANDATORY] Line 42: Validate userId before query
- [RECOMMENDED] Line 67: Extract retry logic to helper function

### src/controllers/user.ts
- [MANDATORY] Line 23: Add input sanitization for email parameter
- [NITPICK] Line 45: Consider more descriptive variable name
```

Why: file grouping minimizes context switches for the author. Priority ordering inside each file ensures MANDATORY items can't get lost among NITPICK noise.

## Read the PR in this order

1. **PR description** — understand the business context and decisions first.
2. **Test titles** — scan `it('should ...')` lines to understand expected behavior without reading implementation.
3. **Core implementation** — controller/consumer first (orchestration), then use cases/pure functions (business logic).
4. **Test bodies** — only after understanding the implementation, verify tests are meaningful.

Why: this order maximizes comprehension per minute: context → behavior → implementation → verification. Skip step 4 if short on time — steps 1-3 are sufficient for a quality review.

## Avoid these review anti-patterns

- Don't suggest broad rewrites — prefer small, surgical changes.
- Don't ask questions without explaining their impact.
- Don't provide feedback without line numbers.
- Don't suggest changes without showing a diff.
- Don't forget to prioritize feedback by severity.

Why: each anti-pattern wastes the author's time or erodes trust. Surgical changes get merged; rewrite requests get pushback. Impact-less questions get ignored.

## Output language matches the invoking context

Instructions and code examples: English. Output language: determined by the invoking context.

Why: code examples in non-English break copy-paste. But review prose must meet the author where they are — if the team works in Portuguese, the review is in Portuguese.
