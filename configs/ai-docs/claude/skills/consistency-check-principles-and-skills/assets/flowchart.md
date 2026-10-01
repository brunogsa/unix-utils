# consistency-check-principles-and-skills — flow overview

Human-facing overview for auditing the flow at a glance. Non-authoritative — the numbered steps in [`../SKILL.md`](../SKILL.md) win on any conflict. Regenerate this file whenever the skill's flow changes.

```mermaid
flowchart TD
  n1(["1. /consistency-check-principles-and-skills, optional path or skill names"]):::start
  n2["2. Wave 1 step 1 · Run gen-shard-manifest.sh.<br/>It always emits every shard: one per skill dir plus a claude-md shard"]
  n3{"3. Scoped invocation?"}
  n3a["3a. Keep only the shards whose slug matches the named skills or paths"]
  n3b["3b. No argument: keep every shard.<br/>Never narrow the corpus or stop early because the count looks expensive"]
  n4["4. Step 2 · Dispatch consistency-shard-orchestrator per shard,<br/>at most 4 in flight. Refill the instant any digest lands.<br/>Forward each shard's own file list verbatim"]:::dispatch
  n5["5. Each orchestrator dispatches 3 consistency-ensemble-child in one message,<br/>runs the 2-of-3 vote and returns a fixed-schema digest.<br/>A child never spawns further children"]:::dispatch
  n6["6. Step 3 · Collect each digest: STATUS, BLOCKING count and lines, ADVISORY count, GOVERNS"]
  n7["7. Wave 2 step 4 · Pair shards whose GOVERNS activities or paths overlap.<br/>Cap of 5 pairs per run"]
  n8["8. Step 5 · Re-dispatch the orchestrator per pair at the union of both file lists.<br/>Same 3-child vote, deduped against wave-1 findings"]:::dispatch
  n9["9. Step 6 · Sum BLOCKING across every shard and pair that returned OK.<br/>Emit the BLOCKING count trailer"]
  n10{"10. Any shard or pair with all children dead,<br/>a malformed digest, or BLOCKING findings failing the citation gate?"}
  n10a["10a. Step 8 · Run STATUS is INCOMPLETE, naming the shard or pair.<br/>Never reported as 0 BLOCKING"]:::gate
  n11["11. Step 7 · Rank ADVISORY from all shards and pairs by confidence then heuristic priority.<br/>Keep the top 5 for the whole run"]
  n12["12. Strip the KEY lines and render the merged report.<br/>Report only, never auto-fix"]
  n13{"13. BLOCKING count above 0 after the user applies fixes?"}
  n13a["13a. Re-run, capped at 5 rounds"]
  n14(["14. Hand the report back to the user"]):::done

  subgraph child["Ensemble child lifecycle, on its own shard only"]
    c1["Read the shard's files plus CLAUDE.md in full, load skill-standards"]
    c2["Scan each heuristic and collect draft findings"]
    c3["Adversarial check: one sentence defending the current state.<br/>If it cites the rule's mechanism, downgrade one tier"]
    c4["Apply gates: drop LOW, keep MEDIUM and HIGH with file:line and a 1-line diff"]
    c5["Render findings numbered section.index, with a KEY line each"]
    c1 --> c2 --> c3 --> c4 --> c5
  end

  n1 --> n2 --> n3
  n3 -->|"yes"| n3a --> n4
  n3 -->|"no"| n3b --> n4
  n4 --> n5
  n5 -.-> c1
  n5 --> n6 --> n7 --> n8 --> n9 --> n10
  n10 -->|"yes"| n10a --> n11
  n10 -->|"no"| n11
  n11 --> n12 --> n13
  n13 -->|"yes"| n13a --> n2
  n13 -->|"no"| n14

  classDef start fill:#d4edda,stroke:#28a745
  classDef gate fill:#fff3cd,stroke:#d39e00
  classDef dispatch fill:#d6e9f8,stroke:#2f7fc1
  classDef done fill:#d4edda,stroke:#28a745
```
