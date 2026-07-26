# address-ai-comments — flow overview

Human-facing overview for auditing the flow at a glance. Non-authoritative — the numbered steps in [`../SKILL.md`](../SKILL.md) win on any conflict. Regenerate this file whenever the skill's flow changes.

```mermaid
flowchart TD
  n1(["1. /address-ai-comments &lt;path(s)&gt;<br/>or natural phrasing: 'raise/gather/check/find/see<br/>the AI?/AI! comments I left on &lt;path&gt;'"]):::start
  n2["2. Step 1 · Ask together (one message): 'Which file(s)/folder(s)<br/>to sweep?' + 'Run refactor/auto-review tails after? (default no)'"]:::gate
  n3["3. Create run-state file<br/>/tmp/address-ai-comments_&lt;session_id&gt;_&lt;ts&gt;.json;<br/>persist target(s) + toggle answer"]:::state
  n4{"4. Tails toggle on?"}
  n4a["4a. Capture BATCH_BASE_SHA = git rev-parse HEAD;<br/>persist into run-state JSON immediately"]:::state
  n5{"5. Scan fits main session cheaply?<br/>(judged once, start of step 2,<br/>before grep+read pass begins)"}
  n5a["5a. Step 2 · Grep -n for AI! and AI? in target(s)"]
  n5b["5b. Read surrounding context for each hit"]
  n5c{"5c. Classify marker"}
  n5c1["5c1. AI! -&gt; action item"]
  n5c2["5c2. AI? -&gt; question item"]
  n6["6. Cluster markers into themes;<br/>append classification + theme to run-state file as produced"]:::state
  n5d[["5d. (optional, not default) Dispatch subagents in parallel (∥)<br/>pin: general-purpose · haiku · low<br/>one per subdirectory, mechanical locate+classify only"]]:::dispatch
  n7["7. Step 3 · Create one TaskList task per cluster —<br/>metadata: file:line refs + marker text;<br/>description: theme summary.<br/>Populate full list before executing any"]:::state
  n8{"8. Clusters remaining?<br/>(loop runs sequentially — inline in main<br/>session by design, nothing to parallelize)"}
  n8a{"8a. Cluster's marker type?<br/>(mixed clusters: markers process in file order)"}
  n8a1["8a1. Step 4a · AI!: perform the action/change first"]
  n8a2["8a2. Step 4b · AI?: answer in chat first, never in the file"]
  n8b["8b. Delete the marker from source once resolved"]
  n9{"9. Step 1 toggle was on?"}
  n9a[["9a. Step 5 · Dispatch deep-reviewer x2 · agent-pinned,<br/>in parallel (∥, same turn) — simplification + correctness lenses<br/>(ref: code-review-pipeline/references/deep-reviewer-tail-pair.md);<br/>diff BATCH_BASE_SHA..working tree"]]:::dispatch
  n9b["9b. PreToolUse hook: deep-reviewer-write-guard.sh<br/>allows writes only to verdict_*.md or under /tmp;<br/>denies + aborts run otherwise"]:::hook
  n9c["9c. Triage: read both verdict reports, synthesize<br/>prioritized summary, close with apply-offer<br/>(opt-in only — never auto-applied)"]:::gate
  n9d["9d. Append tails' two report paths + top findings<br/>+ apply-offer to final report"]
  n10["10. Step 6 · Report tasks created/executed + file:line refs<br/>(single final report — no per-cluster reports)"]
  n11(["11. Done"])

  n1 --> n2
  n2 --> n3
  n3 --> n4
  n4 -->|"yes"| n4a
  n4 -->|"no"| n5
  n4a --> n5
  n5 -->|"yes, fits (default)"| n5a
  n5 -->|"no, many files/large tree"| n5d
  n5d --> n6
  n5a --> n5b
  n5b --> n5c
  n5c -->|"AI!"| n5c1
  n5c -->|"AI?"| n5c2
  n5c1 --> n6
  n5c2 --> n6
  n6 --> n7
  n7 --> n8
  n8 -->|"yes, cluster remains"| n8a
  n8a -->|"AI!"| n8a1
  n8a -->|"AI?"| n8a2
  n8a1 --> n8b
  n8a2 --> n8b
  n8b --> n8
  n8 -->|"no, all clusters done"| n9
  n9 -->|"yes"| n9a
  n9 -->|"no"| n10
  n9a -.->|"guarded by"| n9b
  n9a --> n9c
  n9c --> n9d
  n9d --> n10
  n10 --> n11

  classDef start fill:#fef3c7,stroke:#d97706,stroke-width:2px
  classDef gate fill:#fee2e2,stroke:#dc2626,stroke-width:2px
  classDef dispatch fill:#dbeafe,stroke:#2563eb,stroke-width:2px
  classDef state fill:#dcfce7,stroke:#16a34a,stroke-width:2px
  classDef skill fill:#f3e8ff,stroke:#9333ea,stroke-width:2px
  classDef hook fill:#e5e7eb,stroke:#4b5563,stroke-width:2px
```
