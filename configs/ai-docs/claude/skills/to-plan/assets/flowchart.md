---
# performance-check budget override, not part of the diagram itself.
# One diagram carries every step, branch and stop condition of the skill,
# and trimming to the bundled default would drop steps from the flow audit.
# Parked in assets/ and never loaded by the model, so its words cost no context.
words-budget: 512
---

# to-plan — flow overview

Human-facing overview for auditing the flow at a glance. Non-authoritative — the numbered steps in [`../SKILL.md`](../SKILL.md) win on any conflict. Regenerate this file whenever the skill's flow changes.

```mermaid
flowchart TD
  n1(["1. /to-plan, no arguments<br/>typed by the user, or model-invoked after brainstorm-how"]):::start
  n2["2. Step 1 · Ground plan-writer in live context and notes.md,<br/>plus spec_slug.md and the two briefs where they exist.<br/>A spec is a bonus, never a precondition.<br/>An ungroundable section goes to Open Questions, never invented"]
  n3["3. Step 2 · ONE AskUserQuestion, three toggles:<br/>traces_to_ac, right_sized, qualitative_pass.<br/>Persist as booleans to /tmp/sdd_session.json, never into the plan"]:::gate
  n4["4. Step 3 · Derive the kebab-case slug yourself,<br/>dispatch plan-writer in the background and wait.<br/>Machine-facing section bodies go in a collapsed details block"]:::dispatch
  n5{"5. Dispatch errored, or plan_slug.md<br/>missing on disk?"}
  n5a(["5a. STOP — report the failure with the agent's error.<br/>Offer nothing: no sdd-to-linear, no retry"])
  n6{"6. Every machine-facing section body inside<br/>a collapsed details block?"}
  n6a["6a. Fix each miss through plan-editor"]:::dispatch
  n7["7. Step 4 · Read self-review-checks.md, then run<br/>check-deterministic-gates.sh, passing the spec when one exists"]
  n8{"8. Runner exit code?"}
  n8a["8a. Exit 1 — a finding: fix each miss through plan-editor"]:::dispatch
  n8b(["8b. Exit 2 — a gate could not run. Report it to the user,<br/>never route it to plan-editor, never count the plan as gated"])
  n9["9. Dispatch plan-reviewer, effort high, in the background.<br/>Qualitative leg only when qualitative_pass is true;<br/>fail-closed judged checks run regardless"]:::dispatch
  n10["10. Decide each finding yourself, dispatch plan-editor<br/>with the accepted ones. Runs once per plan, never twice"]:::dispatch
  n11["11. Report every finding in one block, applied or skipped<br/>with the reason, naming any check skipped by toggle"]
  n12(["12. Step 5 · Give the plan path and offer sdd-to-linear,<br/>free-text something-else always open. Do not run it"]):::done

  n1 --> n2 --> n3 --> n4 --> n5
  n5 -->|"yes"| n5a
  n5 -->|"no"| n6
  n6 -->|"no"| n6a --> n7
  n6 -->|"yes"| n7
  n7 --> n8
  n8 -->|"0"| n9
  n8 -->|"1"| n8a --> n9
  n8 -->|"2"| n8b
  n9 --> n10 --> n11 --> n12

  classDef start fill:#d4edda,stroke:#28a745
  classDef gate fill:#fff3cd,stroke:#d39e00
  classDef dispatch fill:#d6e9f8,stroke:#2f7fc1
  classDef done fill:#d4edda,stroke:#28a745
```
