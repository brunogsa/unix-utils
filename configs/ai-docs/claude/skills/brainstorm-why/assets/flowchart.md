---
# performance-check budget override, not part of the diagram itself.
# One diagram carries every step, branch and stop condition of the skill,
# and trimming to the bundled default would drop steps from the flow audit.
# Parked in assets/ and never loaded by the model, so its words cost no context.
words-budget: 512
---

# brainstorm-why — flow overview

Human-facing overview for auditing the flow at a glance. Non-authoritative — the numbered steps in [`../SKILL.md`](../SKILL.md) win on any conflict. Regenerate this file whenever the skill's flow changes.

```mermaid
flowchart TD
  n1(["1. /brainstorm-why, no arguments<br/>a run always starts from an idea, never a document"]):::start
  n1a["1a. Seed one TaskList Reminder per step.<br/>Scaffolding only, never a go-ahead to run a step early"]
  n2["2. Step 1 · Run get-enabled-modules.py<br/>and read the arco= line"]
  n3{"3. arco=true?"}
  n3a["3a. No module selected.<br/>Never show the opt-in question"]
  n3b{"3b. AskUserQuestion, recommended first:<br/>finish with the sdd-grill module?"}
  n4["4. Step 2 · Run references/interview-engine.md.<br/>Seed: raw request plus codebase read.<br/>Notes: scratchpad notes.md throughout.<br/>Only why and what questions, never the how"]:::gate
  n4a["4a. Request looks decomposable:<br/>follow references/decompose-scope.md"]
  n5["5. Close criterion met: compose<br/>brainstorm-why-brief.md once"]
  n6{"6. Step 3 · Module selected?"}
  n7["7. Seed two Reminders with the resolved scratchpad path inline:<br/>Persist the grill findings into notes.md and the brief,<br/>Offer to-spec. State the CLAUDE.md-wins override as a pointer"]
  n8{"8. Invoke sdd-grill as this skill's LAST ACT.<br/>Module unavailable or failing?"}
  n8a["8a. Tell the user loudly, never abort, never fail closed.<br/>Run this skill's own interview from step 2 to its close,<br/>then complete the Persist and Offer reminders"]:::gate
  n9(["9. Step 4 · AskUserQuestion, recommended first:<br/>to-spec or something else, free text always open.<br/>Do not run to-spec until the user picks it. No /clear"]):::done

  n1 --> n1a --> n2 --> n3
  n3 -->|"no"| n3a --> n4
  n3 -->|"yes"| n3b
  n3b -->|"declined"| n3a
  n3b -->|"accepted"| n4
  n4 --> n4a --> n5
  n4 --> n5
  n5 --> n6
  n6 -->|"no"| n9
  n6 -->|"yes"| n7 --> n8
  n8 -->|"works"| n9
  n8 -->|"fails"| n8a --> n9

  classDef start fill:#d4edda,stroke:#28a745
  classDef gate fill:#fff3cd,stroke:#d39e00
  classDef done fill:#d4edda,stroke:#28a745
```
