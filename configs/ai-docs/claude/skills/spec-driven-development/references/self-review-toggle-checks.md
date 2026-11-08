# Self-review toggle checks - what each one means and what blocks

## Every line traces to an AC (toggle)

Dispatch `agent(subAgent=plan-reviewer, title=Judge machinery-to-AC traceability)` with plan and spec: every piece of machinery must trace to a spec AC or requirement.

Output: untraceable items (empty = pass); block if non-empty - cut it, or earn an AC. Exempt `[Clarify]` tasks.

## Right-sized plan (toggle)

Dispatch `agent(subAgent=plan-reviewer, title=Judge spec/plan simplicity)` with the user's request + spec + plan - no gold-plating, simplest design meeting every AC.

Advisory even at toggle "yes" - surface findings, never block.
