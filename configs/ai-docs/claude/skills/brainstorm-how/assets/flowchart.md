---
# performance-check budget override, not part of the diagram itself.
# One diagram carries every step, branch and stop condition of the skill,
# and trimming to the bundled default would drop steps from the flow audit.
# Parked in assets/ and never loaded by the model, so its words cost no context.
words-budget: 512
---

# brainstorm-how — flow overview

Human-facing overview for auditing the flow at a glance. Non-authoritative — the numbered steps in [`../SKILL.md`](../SKILL.md) win on any conflict. Regenerate this file whenever the skill's flow changes.

```mermaid
flowchart TD
  n1(["1. /brainstorm-how, no arguments<br/>starts from a settled problem, never a raw request.<br/>An approved spec in CWD is optional"]):::start
  n2{"2. How many spec_*.md in CWD?"}
  n2a["2a. Proceed without a spec: seed from the settled problem<br/>(conversation, investigation docs, tickets, threads).<br/>If why/what is genuinely open, suggest brainstorm-why"]
  n2b["2b. Use it, printing the resolved path"]
  n2c["2c. List them numbered, ask which one<br/>via AskUserQuestion"]:::gate
  n3["3. Seed one TaskList Reminder per step.<br/>Scaffolding only, never a go-ahead to run a step early"]
  n4["4. Step 1 · Run brainstorm-why/references/interview-engine.md.<br/>No module, no get-enabled-modules.py, no nested Skill call,<br/>never offer sdd-grill-tech.<br/>Seed: the spec when one exists, else the settled-problem sources, plus codebase read.<br/>Only how questions, grounded in the user's own conventions"]:::gate
  n5["5. Close criterion met: compose<br/>brainstorm-how-brief.md once, a real input to to-plan"]
  n6(["6. Step 2 · AskUserQuestion, recommended first:<br/>to-plan or something else, free text always open.<br/>Do not run to-plan until the user picks it. No /clear"]):::done

  n1 --> n2
  n2 -->|"none"| n2a --> n3
  n2 -->|"one"| n2b --> n3
  n2 -->|"several"| n2c --> n3
  n3 --> n4 --> n5 --> n6

  classDef start fill:#d4edda,stroke:#28a745
  classDef gate fill:#fff3cd,stroke:#d39e00
  classDef done fill:#d4edda,stroke:#28a745
```
