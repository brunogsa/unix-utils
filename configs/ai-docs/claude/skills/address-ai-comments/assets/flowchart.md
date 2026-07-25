# address-ai-comments — flow overview

Human-facing overview for auditing the flow at a glance. Non-authoritative — the numbered steps in [`../SKILL.md`](../SKILL.md) win on any conflict. Regenerate this file whenever the skill's flow changes.

```mermaid
flowchart TD
  start(["/address-ai-comments target(s) invoked"]):::start
  preflight["1. Ask together: target(s) + tails toggle (default no)"]
  scratchpad["Create run-state scratchpad file keyed by session id + run timestamp; persist answers"]
  togglecheck{"Tails toggle on?"}
  captureSha["Capture BATCH_BASE_SHA = git rev-parse HEAD"]
  gather["2. Grep -n for AI! and AI? in target(s)"]
  readctx["Read surrounding context for each hit"]
  classify{"Classify marker"}
  actionType["AI! -&gt; action item"]
  questionType["AI? -&gt; question item"]
  cluster["Cluster markers into themes; append to scratchpad as produced"]
  sizecheck{"Scan fits main session cheaply?"}
  subDispatch[["Dispatch parallel subagents: locate+classify only, one per subdirectory"]]:::dispatch
  inline["Continue gather+classify inline (default path)"]
  taskcreate["3. Create one TaskList task per cluster; populate full list before executing any"]
  loopcheck{"Clusters remaining?"}
  markercheck{"Cluster's marker type?"}
  doAction["4a. AI!: perform the action/change first"]
  doAnswer["4b. AI?: answer in chat first, never in the file"]
  strip["Delete the marker from source once resolved"]
  tailscheck{"Step 1 toggle was on?"}
  tailsDispatch[["5. Dispatch shared deep-reviewer tail pair: refactor + auto-review"]]:::dispatch
  report["6. Report tasks created/executed + file:line refs"]
  appendTails["Append tails' two report paths + top findings"]
  done(["Done"])

  start --> preflight
  preflight --> scratchpad
  scratchpad --> togglecheck
  togglecheck -->|"yes"| captureSha
  togglecheck -->|"no"| gather
  captureSha --> gather
  gather --> readctx
  readctx --> classify
  classify -->|"AI!"| actionType
  classify -->|"AI?"| questionType
  actionType --> cluster
  questionType --> cluster
  cluster --> sizecheck
  sizecheck -->|"yes, fits"| inline
  sizecheck -->|"no, many files/large tree"| subDispatch
  subDispatch --> inline
  inline --> taskcreate
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
  tailsDispatch --> appendTails
  appendTails --> report
  report --> done

  classDef start fill:#fef3c7,stroke:#d97706,stroke-width:2px
  classDef dispatch fill:#dbeafe,stroke:#2563eb,stroke-width:2px
```
