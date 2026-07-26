# Resolving spec/plan drift

Load this only when the plan and the spec disagree — surface each conflict before updating anything:

1. **List each drift item** — what the spec states, what the plan says, and why they conflict.

2. **Present to the user and wait** — don't update either doc yet. The user picks the direction:
   - Update the spec (planning uncovered a better reality).
   - Correct the plan (it misread the spec).
   - Add a `**QUESTION:**` marker (the trade-off is genuinely open).

3. **Apply only the agreed change** — targeted edit to whichever doc the user chose; don't refactor surrounding content.

Why: the spec drives PR description and auto-review — a stale spec ships wrong context downstream.

But the plan can also be wrong; surfacing the choice preserves intent rather than assuming the spec was outdated.
