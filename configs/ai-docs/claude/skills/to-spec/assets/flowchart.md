---
# performance-check budget override, not part of the diagram itself.
# One diagram carries every step, branch and stop condition of the skill,
# and trimming to the bundled default would drop steps from the flow audit.
# Parked in assets/ and never loaded by the model, so its words cost no context.
words-budget: 512
---

# to-spec — flow overview

Human-facing overview for auditing the flow at a glance. Non-authoritative — the numbered steps in [`../SKILL.md`](../SKILL.md) win on any conflict. Regenerate this file whenever the skill's flow changes.

```mermaid
flowchart TD
  n1(["1. /to-spec, no arguments<br/>typed by the user, or model-invoked after brainstorm-why"]):::start
  n2["2. Step 1 · Ground from live context, notes.md<br/>and brainstorm-why-brief.md, nothing else"]
  n3{"3. Brief present in the scratchpad?"}
  n3a(["3a. STOP — tell the user brainstorm-why has not run,<br/>offer it. Never rebuild the brief from the conversation"])
  n4["4. Step 2 · ONE AskUserQuestion: qualitative_pass?<br/>Persist as a boolean to /tmp/sdd_session.json,<br/>never into the spec. An absent sdd-grill section is not a gap"]:::gate
  n5["5. Step 3 · Derive the kebab-case slug yourself,<br/>dispatch spec-writer in the background and wait"]:::dispatch
  n6{"6. Dispatch errored, or spec_slug.md<br/>missing on disk?"}
  n6a(["6a. STOP — report the failure with the agent's error.<br/>Offer nothing: no brainstorm-how, no retry"])
  n7["7. Step 4 · Read self-review-checks.md, then run<br/>check-deterministic-gates.sh --spec-only"]
  n8{"8. Runner exit code?"}
  n8a["8a. Exit 1 — a finding: fix each miss through spec-editor"]:::dispatch
  n8b(["8b. Exit 2 — a gate could not run. Report it to the user,<br/>never route it to spec-editor, never count the spec as gated"])
  n9["9. Dispatch spec-reviewer, effort high, in the background.<br/>Always: how would this break?<br/>Only when qualitative_pass is true: the qualitative checklist"]:::dispatch
  n10["10. Decide each finding yourself, dispatch spec-editor<br/>with the accepted ones. Runs once per spec, never twice"]:::dispatch
  n11["11. Report every finding in one block, applied or skipped<br/>with the reason, naming any check skipped by toggle"]
  n12(["12. Step 5 · Give the spec path and offer brainstorm-how.<br/>Do not run it in this session"]):::done

  n1 --> n2 --> n3
  n3 -->|"no"| n3a
  n3 -->|"yes"| n4 --> n5 --> n6
  n6 -->|"yes"| n6a
  n6 -->|"no"| n7 --> n8
  n8 -->|"0"| n9
  n8 -->|"1"| n8a --> n9
  n8 -->|"2"| n8b
  n9 --> n10 --> n11 --> n12

  classDef start fill:#d4edda,stroke:#28a745
  classDef gate fill:#fff3cd,stroke:#d39e00
  classDef dispatch fill:#d6e9f8,stroke:#2f7fc1
  classDef done fill:#d4edda,stroke:#28a745
```
