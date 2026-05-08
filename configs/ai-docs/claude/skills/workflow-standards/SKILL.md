---
name: workflow-standards
description: "Plan-driven implementation rules. USE PROACTIVELY whenever planning a non-trivial task, starting a feature, breaking work into commits, designing test titles upfront, or running a green-baseline check before new work."
user-invocable: false
---

# Workflow Standards -- Examples & Patterns

Reference examples for the WORKFLOW rules defined in CLAUDE.md.

---

## Test title design + RED-GREEN-REFACTOR cycle

For plan-driven implementation, the canonical TDD/BDD discipline lives in the `test-driven-development` skill. Load it when starting any plan task.

It covers:

- Title design before implementation.
- RED-GREEN-REFACTOR most-forcing-case-first.
- Helper-on-demand.
- Rationalization tables for drift.
- The `manual-tests-evidences.md` format.
