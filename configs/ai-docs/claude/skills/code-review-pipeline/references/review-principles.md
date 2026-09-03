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

- **Emission gate (Wave 2):**
  - **>80% confidence** → emit a direct comment with clear reasoning.
  - **60-80% confidence** → emit as a clarifying question to reduce ambiguity.
  - **<60% confidence** → skip the comment entirely.

- **Validation gate (Wave 3 self-check, post-emission):**
  - **When in doubt, KEEP.** Dropping a real finding erodes trust more than keeping noise.
    - Only drop on clear, specific evidence the claim doesn't hold (cited code doesn't exist; code already does what was asked; the issue depends on behavior the file explicitly prevents).

Why they pull opposite ways: emission is cheap to abort (the comment doesn't exist yet), so its bar is "is this likely real?".

Validation is expensive to abort — the work is done, and dropping it loses the reviewer's reasoning — so its bar is "is this provably wrong?".

Avoid speculative "maybe"/"possibly"/"consider" at the emission gate without strong justification. Don't compensate at validation.

## Feedback structure: severity tag → summary line → Sugestão → Trade-off de não fazer

Every review comment opens with a bold, bracketed severity tag on its own line, then a one-sentence plain summary, then two bold-labeled sections:

- **Severity tag**: one of the five under "Priority tags" below, bracketed and bold — `**[OBRIGATÓRIO]**` in PT-BR output, `**[MANDATORY]**` in English.
  - The tag must match the finding's `severity` field 1:1 — the visible tag and the machine-readable field can never disagree.

- **Summary line**: one plain sentence naming the visible effect and its cause, with no bold label and no bullet.
  - Example: *"Fees come out 100x too high because the rate unit is wrong."*
  - It carries the whole finding on its own — a reader who stops there still knows whether this blocks them.

- **Sugestão** / **Suggestion**: the fix, shown as code whenever possible.
  - Prefer a `suggestion` fenced block whenever the replacement fits the commented lines — GitHub renders it as an applyable before/after diff, so no prose has to describe the current state.
  - Fall back to a `diff` fenced block with `-`/`+` when the change can't anchor on the commented lines, or touches another file.
  - Prose around the block: 0-1 paragraph of 1-4 sentences, OR 2-5 bullets/sub-bullets of 1-2 sentences. Drop the prose entirely when the code block speaks for itself.
  - Omit the whole section only for a QUESTION finding with no concrete fix to propose.

- **Trade-off de não fazer** / **Trade-off of not doing it**: what leaving it costs.
  - Always bullets + sub-bullets, never a paragraph. 2-5 in total, 1-2 sentences each — pick the most important.
  - Each bullet may carry an optional `[+]` / `[-]` marker, for the upside/downside of skipping the fix.
  - Name the concrete scenario being avoided; for numeric/unit issues use real values.
  - Never omitted.

Why: the problem alone leaves the author guessing about severity, and the tag fixes that immediately.

The summary line tells the reader in one pass whether to care, Sugestão shows the next step as code they can apply, and Trade-off de não fazer is what educates.

It makes the cost of ignoring the comment explicit instead of leaving it as the reviewer's taste.

Two sections instead of four because the summary line already states what is wrong; a section for that only restated the same defect at greater length.

Length budget per body: **≤512 characters**. A MANDATORY finding may go to **≤1024 characters and ≤16 lines**.

Fenced code blocks count toward neither — the visual diff is the point, and charging it against the budget pushes reviewers back to prose.

## Priority tags — match severity to tone, and each tag to an ordinal rank

The tag sets the tone. The ordinal rank beside it is what a severity floor compares.

`/address-verdicts` §2 takes floor arguments like `high` and `high+`, and a tone vocabulary orders nothing on its own.

- **MANDATORY** (`OBRIGATÓRIO`) — ordinal severity `HIGH`. Must fix before merge (correctness, security, critical bugs). Direct, assertive tone.

- **RECOMMENDED** (`RECOMENDADO`) — ordinal severity `MEDIUM`. Should address (code quality, performance, best practices).

- **NITPICK** (`NITPICK`) — ordinal severity `LOW`. Optional improvements (minor style, subjective). Friendly, non-pedantic tone.

- **OPTIONAL** (`OPCIONAL`) — ordinal severity `LOW`. Pre-existing issue surfaced for awareness only, not introduced or worsened by this diff.
  - Drop it entirely if it is one of the [low-value kinds](#skip-low-value-comments): formatting, linting, subjective refactors.

- **QUESTION** (`PERGUNTA`) — no ordinal severity, so it passes every severity floor instead of ranking under one. Standalone: must be answered. Embedded in other tags: include inline.

Why: a NITPICK with MANDATORY tone is hostile. A MANDATORY with NITPICK tone is ignored. Matching severity to tone keeps the signal honest.

Why these four ranks: the ordinal scale measures the cost of leaving a finding undone, which is the axis the tags already carry.

`HIGH` is a defect that ships or persists, `MEDIUM` a maintenance cost that compounds on the next touch, `LOW` no practical cost ever.

OPTIONAL joins NITPICK at `LOW` because an issue this diff neither introduced nor worsened costs this change nothing.

Why QUESTION is exempt rather than ranked: it asks for information instead of naming work, so it has no cost-of-leaving-it-undone to compare.

Ranking it low would let a `high` floor silently swallow a standalone question that must be answered; ranking it high would route a finding with no fix to an apply agent.

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

**UNLESS** Wave 1's repo-wide check outputs (`static-lint.txt`, `tests-*.txt`) show that lint error or test failure landing **inside the diff**.

Those become findings at MANDATORY/RECOMMENDED severity, per `references/common-preamble.md`'s "Context you have" section.

**DO** provide feedback on: typos (user-facing), misleading names, convention-breaking formatting.

Why: a linter catches formatting — surface it there, not in a comment. Reviewer attention is the scarce resource; spend it on what tools can't catch.

Why the UNLESS wins: a check failing inside the diff is evidence the author never ran it, so the tool this rule defers to has surfaced nothing.

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
