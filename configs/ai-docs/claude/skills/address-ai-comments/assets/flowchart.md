# address-ai-comments — flow overview

Human-facing overview for auditing the flow at a glance. Non-authoritative — the numbered steps in [`../SKILL.md`](../SKILL.md) win on any conflict. Regenerate this file whenever the skill's flow changes.

```mermaid
flowchart TD
  start(["/address-ai-comments &lt;path(s)&gt;<br/>or natural phrasing: 'raise/gather/check/find/see<br/>the AI?/AI! comments I left on &lt;path&gt;'"]):::start
  preflight["1. Ask together (one message): 'Which file(s)/folder(s)<br/>to sweep?' + 'Run refactor/auto-review tails after? (default no)'"]:::gate
  scratchpad["Create run-state file<br/>/tmp/address-ai-comments_&lt;session_id&gt;_&lt;ts&gt;.json;<br/>persist target(s) + toggle answer"]:::state
  togglecheck{"Tails toggle on?"}
  captureSha["Capture BATCH_BASE_SHA = git rev-parse HEAD;<br/>persist into run-state JSON immediately"]:::state
  sizecheck{"Scan fits main session cheaply?<br/>(judged once, start of step 2,<br/>before grep+read pass begins)"}
  gather["2. Grep -n for AI! and AI? in target(s)"]
  readctx["Read surrounding context for each hit"]
  classify{"Classify marker"}
  actionType["AI! -&gt; action item"]
  questionType["AI? -&gt; question item"]
  cluster["Cluster markers into themes;<br/>append classification + theme to run-state file as produced"]:::state
  subDispatch[["(optional, not default) Dispatch subagents in parallel (∥)<br/>pin: general-purpose · haiku · low<br/>one per subdirectory, mechanical locate+classify only"]]:::dispatch
  taskcreate["3. Create one TaskList task per cluster —<br/>metadata: file:line refs + marker text;<br/>description: theme summary.<br/>Populate full list before executing any"]:::state
  loopcheck{"Clusters remaining?<br/>(loop runs sequentially — inline in main<br/>session by design, nothing to parallelize)"}
  markercheck{"Cluster's marker type?<br/>(mixed clusters: markers process in file order)"}
  doAction["4a. AI!: perform the action/change first"]
  doAnswer["4b. AI?: answer in chat first, never in the file"]
  strip["Delete the marker from source once resolved"]
  tailscheck{"Step 1 toggle was on?"}
  tailsDispatch[["5. Dispatch deep-reviewer x2, own pinned model/effort,<br/>in parallel (∥, same turn) — simplification + correctness lenses<br/>(ref: code-review-pipeline/references/deep-reviewer-tail-pair.md);<br/>diff BATCH_BASE_SHA..working tree"]]:::dispatch
  hookNode["PreToolUse hook: deep-reviewer-write-guard.sh<br/>allows writes only to verdict_*.md or under /tmp;<br/>denies + aborts run otherwise"]:::hook
  triage["Triage: read both verdict reports, synthesize<br/>prioritized summary, close with apply-offer<br/>(opt-in only — never auto-applied)"]:::gate
  appendTails["Append tails' two report paths + top findings<br/>+ apply-offer to final report"]
  report["6. Report tasks created/executed + file:line refs<br/>(single final report — no per-cluster reports)"]
  done(["Done"])

  start --> preflight
  preflight --> scratchpad
  scratchpad --> togglecheck
  togglecheck -->|"yes"| captureSha
  togglecheck -->|"no"| sizecheck
  captureSha --> sizecheck
  sizecheck -->|"yes, fits (default)"| gather
  sizecheck -->|"no, many files/large tree"| subDispatch
  subDispatch --> cluster
  gather --> readctx
  readctx --> classify
  classify -->|"AI!"| actionType
  classify -->|"AI?"| questionType
  actionType --> cluster
  questionType --> cluster
  cluster --> taskcreate
  taskcreate --> loopcheck
  loopcheck -->|"yes, cluster remains"| markercheck
  markercheck -->|"AI!"| doAction
  markercheck -->|"AI?"| doAnswer
  doAction --> strip
  doAnswer --> strip
  strip --> loopcheck
  loopcheck -->|"no, all clusters done"| tailscheck
  tailscheck -->|"yes"| tailsDispatch
  tailscheck -->|"no"| report
  tailsDispatch -.->|"guarded by"| hookNode
  tailsDispatch --> triage
  triage --> appendTails
  appendTails --> report
  report --> done

  classDef start fill:#fef3c7,stroke:#d97706,stroke-width:2px
  classDef gate fill:#fee2e2,stroke:#dc2626,stroke-width:2px
  classDef dispatch fill:#dbeafe,stroke:#2563eb,stroke-width:2px
  classDef state fill:#dcfce7,stroke:#16a34a,stroke-width:2px
  classDef skill fill:#f3e8ff,stroke:#9333ea,stroke-width:2px
  classDef hook fill:#e5e7eb,stroke:#4b5563,stroke-width:2px
```
