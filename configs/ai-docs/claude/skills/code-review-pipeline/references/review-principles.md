---
# performance-check budget override, not review content.
# The real redundancy was already trimmed out (1187 -> 1108 words). What remains is the nine
# review dimensions with their scope examples and the five severity tags with PT-BR mappings —
# cutting further deletes reviewer scope. Doubled from the 1024w bundled default.
words-budget: 2048
---
# Review Principles

Each section pairs a review principle with its rule or format.

Source of truth for reviewer behavior, loaded by `code-review-pipeline` and by `address-pr-comments` when interpreting reviewer comments.

Not a skill — its frontmatter carries only the performance-check budget override, no skill fields. Referenced by path, never invoked.

## High confidence standard — skip below 60% on EMISSION, keep on VALIDATION

Confidence governs reviewer behavior at two gates that pull in opposite directions:

- **Emission gate (Wave 2 specialists):**
  - **>80% confidence** → emit a direct comment with clear reasoning.
  - **60-80% confidence** → emit as a clarifying question to reduce ambiguity.
  - **<60% confidence** → skip the comment entirely.
- **Validation gate (Wave 3 self-check, post-emission):**
  - **When in doubt, KEEP.** Dropping a real finding erodes trust more than keeping noise.
    - Only drop on clear, specific evidence the claim doesn't hold (cited code doesn't exist; code already does what was asked; the issue depends on behavior the file explicitly prevents).

Why they pull opposite ways: emission is cheap to abort (the comment doesn't exist yet), so its bar is "is this likely real?".

Validation is expensive to abort — the work is done, and dropping it loses the specialist's reasoning — so its bar is "is this provably wrong?".

Avoid speculative "maybe"/"possibly"/"consider" at the emission gate without strong justification. Don't compensate at validation.

## Feedback structure: severity tag → O que → Por que → Sugestão

Every review comment opens with a bold, bracketed severity tag on its own line, then three bold-labeled sections, each a short bullet list (not paragraphs):

- **Severity tag**: one of the five under "Priority tags" below, bracketed and bold — `**[OBRIGATÓRIO]**` in PT-BR output, `**[MANDATORY]**` in English.
  - The tag must match the finding's `severity` field 1:1 — the visible tag and the machine-readable field can never disagree.
- **O que** / **What**: the problem, stated concretely. Quote the relevant code (1-2 lines) inline.
- **Por que** / **Why**: the impact — always include, it's what helps developers learn. For numeric/unit issues, use a worked example with concrete values.
- **Sugestão** / **Suggestion**: the fix — a `suggestion` diff block when it fits a single hunk and you're confident in the exact replacement, otherwise a short bullet describing the change.
  - Omit only for a QUESTION finding with no concrete fix to propose.

Why: the problem alone leaves the author guessing about severity — the tag fixes that immediately, Why educates, and Suggestion removes ambiguity about what to do next.

Suggestion gets its own bold section rather than folding into the problem prose, so each part stays independently scannable.

Keep bullets short, simple enough for an intern unfamiliar with the module, max 256 characters per line.

## Priority tags — match severity to tone

- **MANDATORY** (`OBRIGATÓRIO`) — must fix before merge (correctness, security, critical bugs). Direct, assertive tone.
- **RECOMMENDED** (`RECOMENDADO`) — should address (code quality, performance, best practices).
- **NITPICK** (`NITPICK`) — optional improvements (minor style, subjective). Friendly, non-pedantic tone.
- **OPTIONAL** (`OPCIONAL`) — pre-existing issue surfaced for awareness only, not introduced or worsened by this diff. Drop it entirely if it is one of the [low-value kinds](#skip-low-value-comments): formatting, linting, subjective refactors.
- **QUESTION** (`PERGUNTA`) — genuine design questions. Standalone: must be answered. Embedded in other tags: include inline.

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

Why: reviewing untouched code is scope creep that slows merges without value. Exception: unchanged code that breaks against the changed code — the change is what made it relevant.

## Every comment leads to a clear next step

Avoid mere observations — explain what should change. Include suggestions or questions.

Why: observation-only comments ("this is interesting...") leave the author in limbo. Every comment must end with something the author can DO.

## Skip low-value comments

**Skip**: formatting/style, linting errors, test failures, minor naming preferences, subjective refactoring.

**DO** provide feedback on: typos (user-facing), misleading names, convention-breaking formatting.

Why: a linter catches formatting — surface it there, not in a comment. Reviewer attention is the scarce resource; spend it on what tools can't catch.

## Reference format: file:line or file:line-range

- Single line: `src/services/auth.ts:42`
- Range (preferred): `src/services/auth.ts:42-48`

Why: a line number lets the author jump to the exact spot, and a range tells them how much context the comment covers. Without them, every comment is a scavenger hunt.

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

1. **PR description** — business context and decisions first.
2. **Test titles** — scan `it('should ...')` lines for expected behavior, without reading implementation.
3. **Core implementation** — controller/consumer first (orchestration), then use cases and pure functions (business logic).
4. **Test bodies** — once the implementation is understood, verify the tests are meaningful.

Why: this order maximizes comprehension per minute — context → behavior → implementation → verification. Short on time? Steps 1-3 suffice.

## Avoid these review anti-patterns

- Don't suggest broad rewrites — prefer small, surgical changes.
- Don't ask questions without explaining their impact.

Why: surgical changes get merged while rewrite requests get pushback, and an impact-less question gets ignored.

## Output language matches the invoking context

Instructions and code examples: English. Output language: determined by the invoking context.

Why: code examples in non-English break copy-paste. But review prose must meet the author where they are — if the team works in Portuguese, the review is in Portuguese.
