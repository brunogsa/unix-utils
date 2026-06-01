# Mid-flight sub-steps — insertion + ordering

Detail for §2.3 in `/implement`. Load only when a helper or drift surfaces mid-task and you need to insert new sub-steps without losing visual ordering.

## Insertion rule

If a sub-step uncovers a new helper that needs its own test, **insert** a RED-helper / GREEN-helper pair using **alphabetical suffix** right after the current step — never re-enumerate existing sub-steps.

Format: ` 3.4.1. [Sub-Step] RED — helper for case A`, ` 3.4.2. [Sub-Step] GREEN — helper for case A`. Continues `3.4.3.`, `3.4.4.`, ... if more helpers cascade.

The original numbering for `3.5`, `3.6`, ... stays intact — the suffixed IDs signal "added mid-flight after step 3.4". The numeric prefix is the canonical ordering contract.

## Re-grouping mid-flight sub-steps visually

TaskList renders in a non-deterministic order (opaque algorithm, not reliably creation-order), so mid-flight sub-steps with new IDs will typically appear at the end of the list — after their later siblings.

**CRITICAL: To keep mid-flight sub-steps visually grouped before their later siblings:**

1. Note the subjects + descriptions of all later **pending** sub-steps (e.g., 3.5, 3.6, ...) on a `/tmp` file.
2. Delete those later pending sub-steps (`TaskUpdate` → `deleted`).
3. Create the mid-flight sub-steps.
4. Immediately recreate the later sub-steps in order.
5. Make SURE you re-created everything as it was.

This ensures the later sub-steps get higher TaskList IDs than the new ones, which is the best available lever over display ordering.
