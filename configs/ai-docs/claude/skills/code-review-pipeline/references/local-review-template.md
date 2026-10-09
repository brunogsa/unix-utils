# Local Review Output Template

Used by Wave 5 (local mode) to write `${out_file}` (branch + timestamp, e.g. `./verdict_auto-review_feat-my-branch_2026-04-26_14-32.md`) to the user's CWD. The branch segment distinguishes runs across branches; the timestamp preserves ordering across runs within a branch.

Placeholders resolved by the orchestrator:
- `<branch>`, `<base-branch>`: current and base branch names
- Findings are numbered sequentially, ordered by severity
- Action items are grouped by file, then severity

- `[SEVERITY]`: the finding's ordinal rank - `HIGH` / `MEDIUM` / `LOW` - or `QUESTION` for a finding that carries no rank
  - Read it off the priority tag via the "Priority tags" section of [`review-principles.md`](review-principles.md), which owns that mapping.
  - Emit the ordinal, never the priority tag: `/address-verdicts`' severity floor compares ranks, and a tag it cannot rank drops this lens out of every floored selection.

Local mode carries no Review Guide block - Wave 2's guide-writer step doesn't run for `Mode: local` (see `SKILL.md`'s Wave 2).

The guide only exists to post as a standalone PR comment in github mode.

---

```markdown
# Auto Review: <branch> vs <base-branch>

## Findings

<for each finding, numbered sequentially by severity order>
### N. [SEVERITY] `path:start_line-line`
<body>
```

No signature footer needed - the file belongs to the user.

This template is also the shared shape for the `refactor` lens's verdict file.

## Body parts

Each finding's body holds exactly four parts: the bold priority tag, a one-sentence summary, **Suggestion**, **Trade-off of not doing it**.

- Leave out verification labels (CONFIRMED/PLAUSIBLE), "How it happens"/"Scenario"/"Spec gap" sections, a fix-or-skip prior, and scope or Scout notes.
  - Out-of-diff or pre-existing items go in the Wave 6 terminal summary instead, or become their own OPTIONAL finding when they sit in the diff.

## Worked example

````markdown
### 1. [HIGH] `src/billing/fees.ts:42-42`

**[MANDATORY]**

Fees come out 100x too high because `ratePercent` (e.g. `3.11`) is multiplied as if it were a fraction.

**Suggestion**

```suggestion
  const fee = subtotal * (ratePercent / 100);
```

**Trade-off of not doing it**

- [-] A R$200 subtotal at 3.11% charges R$622 instead of R$6.22.
  - [-] Every invoice built since this change carries the same factor.
- [+] None - a one-line fix with no caller change.

### 2. [MEDIUM] `src/orders/validate.ts:18-31`

**[RECOMMENDED]**

`validateOrder` re-implements the postal-code check that `isValidPostalCode` in `src/shared/address.ts:12` already owns.

**Suggestion**

```diff
-  const ok = /^\d{5}-?\d{3}$/.test(order.zip);
-  if (!ok) throw new InvalidZipError(order.zip);
+  if (!isValidPostalCode(order.zip)) throw new InvalidZipError(order.zip);
```

**Trade-off of not doing it**

- [-] The two regexes drift on the next format change, so one flow accepts what the other rejects.
- [+] No behavior change today - both regexes match the same inputs.
````
