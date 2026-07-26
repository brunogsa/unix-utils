# brainstorm — flow overview

Human-facing overview for auditing the flow at a glance. Non-authoritative — the numbered steps in [`../SKILL.md`](../SKILL.md) win on any conflict. Regenerate this file whenever the skill's flow changes.

```mermaid
flowchart TD
  start(["User runs /brainstorm [path/to/spec_&lt;slug&gt;.md]"]):::start

  subgraph seedTaskList["Seed the TaskList once, at skill start — one [Reminder] per step, before step 1 runs.<br/>Update each as it completes; the TaskList survives compaction, so nothing is ever re-seeded."]
    direction TB
    tl1["Add to TaskList a [Reminder] for Step 1:<br/>Pre-flight — settle the run's toggles, open its state"]:::state
    tl2["Add to TaskList a [Reminder] for Step 2:<br/>Gather starting context"]:::state
    tl3["Add to TaskList a [Reminder] for Step 3:<br/>Probe scope for decomposable sub-projects"]:::state
    tl4["Add to TaskList a [Reminder] for Step 4:<br/>Interview the user (Socratic rounds)"]:::state
    tl5["Add to TaskList a [Reminder] for Step 5:<br/>Propose 2-3 approaches with trade-offs"]:::state
    tl6["Add to TaskList a [Reminder] for Step 6:<br/>Dispatch a fork to write spec_&lt;slug&gt;.md"]:::state
    tl7["Add to TaskList a [Reminder] for Step 7:<br/>Self-review the spec with fresh eyes"]:::state
    tl8["Add to TaskList a [Reminder] for Step 8:<br/>Present the spec for review"]:::state
    tl9["Add to TaskList a [Reminder] for Step 9:<br/>Dispatch plan-writer to write plan_&lt;slug&gt;.md"]:::state
    tl10["Add to TaskList a [Reminder] for Step 10:<br/>Run self-review, then hand off with /clear"]:::state
    tl1 --> tl2 --> tl3 --> tl4 --> tl5 --> tl6 --> tl7 --> tl8 --> tl9 --> tl10
  end

  preflightGate["Step 1 · Ask all 3 yes/no toggles in ONE message, before any other question:<br/><br/>Every line traces to an AC? · Right-sized plan? · Fresh-eyes self-review (default yes)?<br/>they gate how strictly steps 7 and 10 check the documents"]:::gate
  persistToggles["Persist all 3 answers to /tmp/sdd_&lt;session_id&gt;.json<br/><br/>steps 7 and 10 read them back from this file and never re-ask;<br/>settled before any document exists, so none can be waived for failing"]:::state
  makeScratch["Create the run scratchpad /tmp/brainstorm_&lt;session_id&gt;.md<br/><br/>written as things happen, never at the end; lives through spec, plan and self-review<br/>on resume/after compaction: re-read it first, trust it over recalled context"]:::state

  d1{"Step 2 · Path provided?"}
  n1["Read the provided spec file"]
  n2["Glob spec_*.md in CWD (top-level)"]
  d2{"How many matches?"}
  n3["Read the single match"]
  n4["List matches numbered; ask user which to refine"]:::gate
  n5["Zero matches: seed from session context (fresh idea)"]

  d3{"Step 3 · Request looks decomposable?<br/>(multiple nouns, roles, or independently-shippable features)"}
  n6["Name candidate sub-projects;<br/>ask user how they relate and which ships first"]:::gate
  d4{"User agrees to decompose?"}
  n7["Write scopes.md<br/><br/>One line per sub-project: name, purpose, dependency"]

  n9["Step 4 · Interview: ask 2-3 Socratic questions per round<br/>(prefer AskUserQuestion tool, recommended answer + reasoning)<br/><br/>categories: Background • Goal/KPIs • User Stories • Acceptance Criteria (BDD) • NFR/Technical constraints • Open Questions<br/><br/>split facts (look up yourself) from decisions (ask user)"]:::gate
  writeScratch["Write each round's outcome to the scratchpad as it closes<br/><br/>decisions with their why, discarded alternatives with why they lost, open questions"]:::state
  refLoad["Load test-standards coverage-taxonomy reference<br/>(unconditional, every round, before spec generation)"]:::skill
  n10["Push user through every taxonomy category;<br/>probe corner cases (empty/max/boundary) + failure modes (timeouts/partial/rate-limit)<br/><br/>ask: what should happen when X is empty/oversized/invalid/unavailable?"]:::gate
  d6{"Exit criterion met?<br/>(latest round added no new requirement/constraint changes AND every taxonomy category covered or ruled out)"}

  n11["Step 5 · Propose 2-3 approaches with trade-offs;<br/>lead with recommendation"]
  n12["Get directional pick from user;<br/>the fork later records it plus the discarded alternatives in the spec's Decisions section"]:::gate

  d7{"Step 6 · spec_&lt;slug&gt;.md already exists?"}
  n14["Derive kebab-case slug from the feature, confirm it with the user<br/><br/>the plan inherits the same slug — that shared slug is what pairs the two"]:::gate
  specFork{{"Dispatch fork · inherits this session's model AND full context (serial, foreground)<br/><br/>it reads the spec-driven-development library + spec-template, folds the scratchpad's<br/>decisions in, then writes/updates the spec and reports the resolved path<br/><br/>this session never writes the spec itself — every later edit re-dispatches a fork"}}:::dispatch

  d_selfreview{"Step 7 · Fresh-eyes self-review toggle on?<br/>(read back from /tmp/sdd_&lt;session_id&gt;.json, never re-asked)"}
  specReview{{"Dispatch deep-reviewer · agent-pinned (serial, foreground)<br/>on the spec file ALONE — no plan exists yet<br/><br/>placeholders • contradictions • ambiguity • completeness • scope • human-reviewable"}}:::dispatch
  specFix{{"Dispatch fork · inherits session context (serial)<br/>to apply every blocking finding to the spec<br/><br/>runs exactly once — never a second review round, the user reads it next"}}:::dispatch
  reviewScratch["Record in the scratchpad what was flagged and how each finding was resolved"]:::state
  skipNote["Note 'spec self-review skipped by request'<br/>to carry into the step 8 summary"]:::state

  n16["Step 8 · Present spec summary + what the review flagged and how it was fixed;<br/>ask if anything is missing or wrong"]:::gate
  d8{"User satisfied?"}
  reworkFork{{"Dispatch fork · inherits session context (serial)<br/>carrying the exact wording/detail edits"}}:::dispatch

  dispatch{{"Step 9 · Dispatch plan-writer · agent-pinned (serial, foreground)<br/><br/>inputs: spec path, plan_&lt;slug&gt;.md output path, planning-conventions file if any<br/>sees only the spec file, never this interview"}}:::dispatch
  d9{"plan-writer returned a numbered gap list?"}
  n18["Walk and close EVERY reported gap with the user first<br/><br/>the spec update goes through a fork; then re-dispatch plan-writer once (not once per gap);<br/>never invent the missing decision"]:::gate

  refSelfReview["Step 10 · Read spec-driven-development/references/self-review-checks.md<br/>(the checks run below are defined there)"]:::skill
  d_qualitative{"Fresh-eyes self-review toggle on?<br/>(same answer as step 7, same file)"}
  qualDispatch1{{"Dispatch deep-reviewer · agent-pinned (serial):<br/>qualitative pass over spec + plan — placeholders, contradictions,<br/>scope, PR size, ambiguity, completeness, human-reviewable"}}:::dispatch
  skipQual["Note 'qualitative pass skipped by request' in the self-review output"]:::state
  qualDispatch2{{"Dispatch mermaid-fixer · agent-pinned (serial)<br/>on every diagram in the spec + plan — no toggle switches this off"}}:::dispatch
  qualDispatch3{{"Dispatch density-fixer · agent-pinned (serial)<br/>on the spec + plan files — no toggle switches this off"}}:::dispatch
  formalChecksNode["Run seven formal checks in sequence<br/>(5 always-on + 2 gated by the AC-traceability and right-sized toggles,<br/>read back from /tmp/sdd_&lt;session_id&gt;.json)<br/><br/>AC-test-coverage and right-sized checks each<br/>dispatch deep-reviewer · agent-pinned (serial)"]
  d10{"All blocking checks pass?"}
  fixLoop["Fix flagged issue directly;<br/>surface spec/plan conflicts to user first, if any"]:::gate
  snapshotLoop["Snapshot spec+plan to /tmp/sdd-snapshots/<br/>for the user's annotated-diff review<br/><br/>a fresh snapshot per round of AI fixes"]:::state
  d11{"User approves the snapshot?"}:::gate
  rerunCheck["Re-run only the failed check,<br/>plus a delta-scoped re-review of what the diff shows changed<br/><br/>never the whole seven-check block"]
  done(["Hand off: tell the user to run /clear, then invoke /implement<br/><br/>brainstorm never runs /implement itself — everything downstream is the user's to drive"]):::gate

  start --> tl1
  tl10 --> preflightGate
  preflightGate --> persistToggles
  persistToggles --> makeScratch
  makeScratch --> d1

  d1 -->|"yes"| n1
  d1 -->|"no"| n2
  n2 --> d2
  d2 -->|"one match"| n3
  d2 -->|"multiple matches"| n4
  d2 -->|"zero matches"| n5

  n1 --> d3
  n3 --> d3
  n4 --> d3
  n5 --> d3

  d3 -->|"yes"| n6
  d3 -->|"no"| n9
  n6 --> d4
  d4 -->|"yes"| n7
  d4 -->|"no: whole idea, no narrowing"| n9
  n7 --> n9

  n9 --> writeScratch
  writeScratch --> refLoad
  refLoad --> n10
  n10 --> d6
  d6 -->|"no, more rounds"| n9
  d6 -->|"yes"| n11

  n11 --> n12
  n12 --> d7
  d7 -->|"yes"| specFork
  d7 -->|"no"| n14
  n14 --> specFork

  specFork --> d_selfreview
  d_selfreview -->|"yes"| specReview
  d_selfreview -->|"no, opted out"| skipNote
  specReview --> specFix
  specFix --> reviewScratch
  reviewScratch --> n16
  skipNote --> n16

  n16 --> d8
  d8 -->|"no: wording/detail"| reworkFork
  reworkFork --> n16
  d8 -->|"no: missing/wrong requirements"| n9
  d8 -->|"no: approach concerns"| n11
  d8 -->|"yes"| dispatch

  dispatch --> d9
  d9 -->|"yes, gaps found"| n18
  n18 --> dispatch
  d9 -->|"no, plan produced"| refSelfReview
  refSelfReview --> d_qualitative
  d_qualitative -->|"yes"| qualDispatch1
  d_qualitative -->|"no, opted out"| skipQual
  qualDispatch1 --> qualDispatch2
  skipQual --> qualDispatch2
  qualDispatch2 --> qualDispatch3
  qualDispatch3 --> formalChecksNode
  formalChecksNode --> d10
  d10 -->|"yes"| done
  d10 -->|"no"| fixLoop
  fixLoop --> snapshotLoop
  snapshotLoop --> d11
  d11 -->|"no: more fixes"| fixLoop
  d11 -->|"yes"| rerunCheck
  rerunCheck --> d10

  classDef start fill:#fef3c7,stroke:#d97706,stroke-width:2px
  classDef gate fill:#fee2e2,stroke:#dc2626,stroke-width:2px
  classDef dispatch fill:#dbeafe,stroke:#2563eb,stroke-width:2px
  classDef state fill:#dcfce7,stroke:#16a34a,stroke-width:2px
  classDef skill fill:#f3e8ff,stroke:#9333ea,stroke-width:2px
  classDef hook fill:#e5e7eb,stroke:#4b5563,stroke-width:2px
```
