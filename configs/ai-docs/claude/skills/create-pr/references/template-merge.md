# Merging into the repo's PR template

Read before writing a final body against a repo template — `pr-finalizer`'s merge contract. The main session never merges a template, so these rules stay out of `SKILL.md`'s always-on load.

**CRITICAL: The repo's template is the base structure, never the thing being replaced.**

- Keep every section and checkbox, sourced from the ideal description, not re-derived from the diff.

- Preserve its checklist verbatim -- never rewrite, reorder, or prune the items; the default template carries no checklist, so the repo's is the only one.

- Mark checklist items `[x]` when applicable.
  - **An item with no local evidence to back it stays unchecked, reported as a caveat.**
    - Example: an e2e/integration check that needs infra this session doesn't have.
    - Never ask whether to go run it; the reviewer verifies and flips it on GitHub.

- Add whatever the ideal description carries that the template has no slot for WITHIN it (preferred) or as an appendix, **NEVER** replacing it.

- **CRITICAL: `## Evidences` is MANDATORY** regardless of the template -- add it inside the template structure when absent.
