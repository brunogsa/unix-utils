# spec-driven-development — flow overview

Human-facing overview for auditing the flow at a glance. Non-authoritative — the numbered steps in [`../SKILL.md`](../SKILL.md) win on any conflict. Regenerate this file whenever the skill's flow changes.

```mermaid
flowchart TD
  start(["User invokes<br/>spec-driven-development"]):::start
  preflight["Pre-flight interview:<br/>ask 2 toggles<br/>(AC-traceability? Right-sized?)"]:::gate
  persistToggles["Persist toggle answers to<br/>/tmp/sdd_&lt;session_id&gt;.json"]:::state
  mirrorRemind["Mirror lifecycle steps 0-9<br/>as TaskList [Reminder] entries"]:::state
  designDocsSkill["Load design-docs skill:<br/>ownership + altitude rules<br/>(spec/plan vs ADR/HLD/LLD)"]:::skill
  createSpec["Step 0: user creates spec_&lt;slug&gt;.md<br/>(or /brainstorm refines it)"]
  specOnDisk{"spec_&lt;slug&gt;.md<br/>exists on disk?"}
  writeInSession["Write plan_&lt;slug&gt;.md in-session<br/>(spec-only prompt, exception path)"]
  dispatchPlanWriter["Dispatch plan-writer subagent<br/>(opus, high effort, serial):<br/>writes plan_&lt;slug&gt;.md from spec alone"]:::dispatch
  qualitativePass["Dispatch deep-reviewer · opus · max<br/>(fresh-eyes, serial):<br/>placeholders, contradictions, scope,<br/>PR size, ambiguity, completeness,<br/>human-reviewable, artifacts, density"]:::dispatch
  scopeHidden{"Hidden decomposition<br/>revealed by interview?"}
  brainstormSkill["Load brainstorm skill:<br/>scope-probe step"]:::skill
  writeScopes["Write/update scopes.md"]
  prSizeLarge{"Work fits one<br/>reviewable PR?"}
  prSizeGate{"Oversized PR: plan split,<br/>or user waives<br/>for this run?"}:::gate
  prBreakdown["PR Breakdown: split into<br/>ordered vertical PR sequence"]
  mermaidValid{"Any mermaid diagrams<br/>valid via mmdc?"}
  dispatchMermaidFixer["Dispatch mermaid-fixer subagent<br/>(haiku, default effort, serial)"]:::dispatch
  dispatchDensityFixer["Dispatch density-fixer subagent<br/>(haiku, default effort, serial):<br/>runs check-density.sh until exit 0"]:::dispatch
  normalizeBreadcrumbs["scripts/normalize-list-breadcrumbs.sh:<br/>upgrade bare it() titles<br/>to breadcrumbs"]:::hook
  formalChecks["Run seven formal checks in sequence<br/>(5 always-on + 2 toggled)"]
  checkACTest["Every AC has a test:<br/>check-ac-coverage.sh first;<br/>if it passes, dispatch<br/>deep-reviewer · opus · max<br/>for semantic match"]:::dispatch
  checkTestTask["Every test has a task:<br/>check-test-distribution.sh"]:::hook
  checkHowBreak["How would this break?<br/>checklist + inversion sweep<br/>(fail-closed, always runs)"]
  checkPRDag["PR dependencies form a DAG:<br/>check-pr-dag.sh"]:::hook
  checkTaskDag["Task dependencies form a DAG:<br/>check-tasks-dag.sh"]:::hook
  toggleTraceability{"Toggle: every line traces<br/>to an AC? (read from<br/>/tmp/sdd_&lt;session_id&gt;.json)"}
  checkTraceability["Check untraceable machinery<br/>(blocks if non-empty)"]
  toggleRightSized{"Toggle: right-sized<br/>plan check?"}
  checkRightSized["Right-sized plan check:<br/>dispatch deep-reviewer · opus · max<br/>(advisory, never blocks)"]:::dispatch
  allChecksPass{"All blocking<br/>checks pass?"}
  conflictSurfaced{"spec/plan<br/>disagree?"}
  resolveDrift["Surface each conflict to user<br/>and wait for their pick"]:::gate
  fixIssue["Fix flagged issue directly"]
  deltaRereview["Load delta-scoped-rereview.md:<br/>scope gates to diff only<br/>(round 2+)"]:::skill
  snapshotDocs["Snapshot spec+plan to<br/>/tmp/sdd-snapshots/<br/>(re-snapshot each hand-back)"]:::state
  humanSnapshotReview{"User re-reviews fresh<br/>snapshot: approved?"}:::gate
  rerunFailedCheck["Re-run only the failed check<br/>+ its delta re-review<br/>(never the full 7-check block)"]
  userApprove["Step 3: user reviews<br/>and approves"]:::gate
  clearImplement["/clear then /implement<br/>in fresh session<br/>(re-grounds from disk)"]:::skill
  taskCreateItems["Step 4: each plan task<br/>becomes a TaskCreate item"]:::state
  tddSkill["Load test-driven-development skill<br/>(BDD/TDD default per task,<br/>opt-out via DECISION line)"]:::skill
  updateDocs["Step 5: update both docs<br/>as work progresses (append-only)"]
  refactorReview["Step 6: /refactor<br/>then /auto-review"]:::skill
  manualReview["Step 7: user manual review,<br/>more fixes if any"]:::gate
  createPR["Step 8: /create-pr generates<br/>rich PR description"]:::skill
  improveLoop["Step 9: /improve-from-user<br/>then english-coach"]:::skill
  shipped(["Feature shipped"])

  start --> preflight
  preflight --> persistToggles
  persistToggles --> mirrorRemind
  mirrorRemind --> designDocsSkill
  designDocsSkill --> createSpec
  createSpec --> specOnDisk
  specOnDisk -->|"no: spec-only prompt"| writeInSession
  specOnDisk -->|"yes"| dispatchPlanWriter
  writeInSession --> qualitativePass
  dispatchPlanWriter --> qualitativePass
  qualitativePass --> scopeHidden
  scopeHidden -->|"yes"| brainstormSkill
  brainstormSkill --> writeScopes
  writeScopes --> qualitativePass
  scopeHidden -->|"no"| prSizeLarge
  prSizeLarge -->|"no: too large"| prSizeGate
  prSizeGate -->|"user waives"| mermaidValid
  prSizeGate -->|"split plan"| prBreakdown
  prSizeLarge -->|"yes"| mermaidValid
  prBreakdown --> mermaidValid
  mermaidValid -->|"no"| dispatchMermaidFixer
  dispatchMermaidFixer --> mermaidValid
  mermaidValid -->|"yes / n-a"| dispatchDensityFixer
  dispatchDensityFixer --> normalizeBreadcrumbs
  normalizeBreadcrumbs --> formalChecks
  formalChecks --> checkACTest
  checkACTest --> checkTestTask
  checkTestTask --> checkHowBreak
  checkHowBreak --> checkPRDag
  checkPRDag --> checkTaskDag
  checkTaskDag --> toggleTraceability
  toggleTraceability -->|"on"| checkTraceability
  toggleTraceability -->|"off"| toggleRightSized
  checkTraceability --> toggleRightSized
  toggleRightSized -->|"on"| checkRightSized
  toggleRightSized -->|"off"| allChecksPass
  checkRightSized --> allChecksPass
  allChecksPass -->|"no"| conflictSurfaced
  conflictSurfaced -->|"yes"| resolveDrift
  conflictSurfaced -->|"no"| fixIssue
  resolveDrift --> deltaRereview
  fixIssue --> deltaRereview
  deltaRereview --> snapshotDocs
  snapshotDocs --> humanSnapshotReview
  humanSnapshotReview -->|"no: more annotations"| fixIssue
  humanSnapshotReview -->|"yes"| rerunFailedCheck
  rerunFailedCheck --> allChecksPass
  allChecksPass -->|"yes"| userApprove
  userApprove --> clearImplement
  clearImplement --> taskCreateItems
  taskCreateItems --> tddSkill
  tddSkill --> updateDocs
  updateDocs --> refactorReview
  refactorReview --> manualReview
  manualReview --> createPR
  createPR --> improveLoop
  improveLoop --> shipped

  classDef start fill:#fef3c7,stroke:#d97706,stroke-width:2px
  classDef gate fill:#fee2e2,stroke:#dc2626,stroke-width:2px
  classDef dispatch fill:#dbeafe,stroke:#2563eb,stroke-width:2px
  classDef state fill:#dcfce7,stroke:#16a34a,stroke-width:2px
  classDef skill fill:#f3e8ff,stroke:#9333ea,stroke-width:2px
  classDef hook fill:#e5e7eb,stroke:#4b5563,stroke-width:2px
```
