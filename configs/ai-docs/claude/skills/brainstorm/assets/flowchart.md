# brainstorm — flow overview

Human-facing overview for auditing the flow at a glance. Non-authoritative — the numbered steps in [`../SKILL.md`](../SKILL.md) win on any conflict. Regenerate this file whenever the skill's flow changes.

```mermaid
flowchart TD
  start(["User runs /brainstorm [path/to/spec_&lt;slug&gt;.md]"]):::start
  d1{"Path provided?"}
  n1["Read the provided spec file"]
  n2["Glob spec_*.md in CWD (top-level)"]
  d2{"How many matches?"}
  n3["Read the single match"]
  n4["List matches numbered; ask user which to refine"]
  n5["Zero matches: seed from session context (fresh idea)"]

  d3{"Request looks decomposable?<br/>(multiple nouns, roles, or independently-shippable features)"}
  n6["Name candidate sub-projects;<br/>ask user how they relate and which ships first"]
  d4{"User agrees to decompose?"}
  n7["Write scopes.md<br/><br/>One line per sub-project: name, purpose, dependency"]

  n8["Create /tmp/brainstorm_&lt;session_id&gt;.md scratchpad"]
  n9["Interview: ask 2-3 questions per round (prefer AskUserQuestion);<br/><br/>persist decisions + discarded alternatives + open questions live"]
  d5{"User only described the happy path?"}
  n10["Probe coverage taxonomy explicitly:<br/><br/>corner cases (empty/max/boundary) + failure modes (timeouts/partial/rate-limit)"]
  d6{"Requirements feel solid?"}

  n11["Propose 2-3 approaches with trade-offs;<br/>lead with recommendation"]
  n12["Get directional pick from user"]

  d7{"spec_&lt;slug&gt;.md already exists?"}
  n13["Update spec in place;<br/>preserve user content, fill gaps, restructure to template"]
  n14["Derive kebab-case slug, confirm with user;<br/>write new spec_&lt;slug&gt;.md"]
  n15["Fold scratchpad decisions + discarded alternatives into spec's Decisions section;<br/>discard scratchpad"]

  n16["Present spec summary for review"]
  d8{"User satisfied?"}

  dispatch{{"Dispatch plan-writer subagent (foreground)<br/><br/>inputs: spec path, plan_&lt;slug&gt;.md output path, planning-conventions file if any"}}:::dispatch
  d9{"plan-writer returned a numbered gap list?"}
  n18["Walk each gap with user; update spec_&lt;slug&gt;.md to close it<br/><br/>never invent the missing decision"]
  n19["Validate plan_&lt;slug&gt;.md: file exists, Task/PR breakdown covers every AC + requirement"]
  done(["Tell user: run /clear, then invoke /implement<br/>(don't run /implement in this session)"])

  start --> d1
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
  d5 -->|"yes"| n10
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
  classDef dispatch fill:#dbeafe,stroke:#2563eb,stroke-width:2px
```
