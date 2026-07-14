# Resolving spec/plan drift

Load this only when plan_<slug>.md and spec_<slug>.md disagree — surface each conflict before updating anything:

1. **List each drift item** — what spec_<slug>.md states, what plan_<slug>.md says, and why they conflict.

2. **Present to the user and wait** — don't update either doc yet. The user picks the direction:
   - Update spec_<slug>.md (planning uncovered a better reality).
   - Correct plan_<slug>.md (it misread the spec).
   - Add a `**QUESTION:**` marker (the trade-off is genuinely open).

3. **Apply only the agreed change** — targeted edit to whichever doc the user chose; don't refactor surrounding content.

Why: spec_<slug>.md drives PR description and auto-review — a stale spec ships wrong context downstream.

But plan_<slug>.md can also be wrong; surfacing the choice preserves intent rather than assuming the spec was outdated.
