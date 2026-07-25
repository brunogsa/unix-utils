# brainstorm — flow overview

Human-facing overview for auditing the flow at a glance. Non-authoritative — the numbered steps in [`../SKILL.md`](../SKILL.md) win on any conflict. Regenerate this file whenever the skill's flow changes.

```mermaid
flowchart TD
  start(["User runs /brainstorm [path/to/spec_&lt;slug&gt;.md]"]):::start
  skillLoad["Load spec-driven-development skill alongside brainstorm<br/><br/>spec template + marker conventions"]:::skill
  taskList["Mirror steps 1-8 as TaskList entries (category [Remind]);<br/>update each as it completes"]:::state
  d1{"Path provided?"}
  n1["Read the provided spec file"]
  n2["Glob spec_*.md in CWD (top-level)"]
  d2{"How many matches?"}
  n3["Read the single match"]
  n4["List matches numbered; ask user which to refine"]:::gate
  n5["Zero matches: seed from session context (fresh idea)"]

  d3{"Request looks decomposable?<br/>(multiple nouns, roles, or independently-shippable features)"}
  n6["Name candidate sub-projects;<br/>ask user how they relate and which ships first"]:::gate
  d4{"User agrees to decompose?"}
  n7["Write scopes.md<br/><br/>One line per sub-project: name, purpose, dependency"]

  n8["Create /tmp/brainstorm_&lt;session_id&gt;.md scratchpad<br/><br/>persist decisions+why, discarded alternatives+why, open questions as they happen<br/>on resume/after compaction: re-read this file first, trust over recalled context"]:::state
  n9["Interview: ask 2-3 Socratic questions per round<br/>(prefer AskUserQuestion tool, recommended answer + reasoning)<br/><br/>categories: Background • Goal/KPIs • User Stories • Acceptance Criteria (BDD) • NFR/Technical constraints • Open Questions<br/><br/>split facts (look up yourself) from decisions (ask user)"]:::gate
  d5{"User only described the happy path?"}
  refLoad["Load test-standards coverage-taxonomy reference"]:::skill
  n10["Probe explicitly: corner cases (empty/max/boundary) + failure modes (timeouts/partial/rate-limit)<br/><br/>ask: what should happen when X is empty/oversized/invalid/unavailable?"]:::gate
  d6{"Requirements feel solid?"}

  n11["Propose 2-3 approaches with trade-offs;<br/>lead with recommendation"]
  n12["Get directional pick from user;<br/>capture outcome + discarded alternatives in spec's Decisions section"]:::gate

  d7{"spec_&lt;slug&gt;.md already exists?"}
  n13["Update spec in place;<br/>preserve user content, fill gaps, restructure to template"]
  n14["Derive kebab-case slug, confirm with user;<br/>write new spec_&lt;slug&gt;.md"]:::gate
  n15["Fold scratchpad decisions + discarded alternatives into spec's Decisions section;<br/>discard scratchpad"]:::state

  n16["Present spec summary for review;<br/>ask if anything is missing or wrong"]:::gate
  d8{"User satisfied?"}

  dispatch{{"Dispatch plan-writer subagent (serial, foreground)<br/><br/>subagent_type: plan-writer — model/effort inherits its own frontmatter pin<br/>inputs: spec path, plan_&lt;slug&gt;.md output path, planning-conventions file if any"}}:::dispatch
  d9{"plan-writer returned a numbered gap list?"}
  n18["Walk each gap with user; update spec_&lt;slug&gt;.md to close it<br/><br/>never invent the missing decision"]:::gate
  n19["Validate plan_&lt;slug&gt;.md: file exists, Task/PR breakdown covers every AC + requirement"]
  done(["Tell user: run /clear, then invoke /implement<br/>(don't run /implement in this session)"]):::gate

  start --> skillLoad
  skillLoad --> taskList
  taskList --> d1
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
  d3 -->|"no"| n8
  n6 --> d4
  d4 -->|"yes"| n7
  d4 -->|"no"| n8
  n7 --> n8

  n8 --> n9
  n9 --> d5
  d5 -->|"yes"| refLoad
  refLoad --> n10
  d5 -->|"no"| d6
  n10 --> d6
  d6 -->|"no, more rounds"| n9
  d6 -->|"yes"| n11

  n11 --> n12
  n12 --> d7
  d7 -->|"yes"| n13
  d7 -->|"no"| n14
  n13 --> n15
  n14 --> n15

  n15 --> n16
  n16 --> d8
  d8 -->|"no, revise + re-present"| n16
  d8 -->|"yes"| dispatch

  dispatch --> d9
  d9 -->|"yes, gaps found"| n18
  n18 --> dispatch
  d9 -->|"no, plan produced"| n19
  n19 --> done

  classDef start fill:#fef3c7,stroke:#d97706,stroke-width:2px
  classDef gate fill:#fee2e2,stroke:#dc2626,stroke-width:2px
  classDef dispatch fill:#dbeafe,stroke:#2563eb,stroke-width:2px
  classDef state fill:#dcfce7,stroke:#16a34a,stroke-width:2px
  classDef skill fill:#f3e8ff,stroke:#9333ea,stroke-width:2px
  classDef hook fill:#e5e7eb,stroke:#4b5563,stroke-width:2px
```
