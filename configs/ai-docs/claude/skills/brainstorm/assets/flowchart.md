# brainstorm — flow overview

Human-facing flow audit. Non-authoritative — [`../SKILL.md`](../SKILL.md)'s numbered steps win on any conflict; regenerate whenever the flow changes.

```mermaid
flowchart TD
  n1(["1. User runs /brainstorm [path/to/spec_&lt;slug&gt;.md]"]):::start

  subgraph seedTaskList["2. Seed the TaskList once, at skill start — one [Reminder] per step, before step 1 runs.<br/>Update each as it completes; the list survives compaction, so nothing is ever re-seeded."]
    direction TB
    n2a["2a. Step 1 · Pre-flight — toggles + run state"]:::state
    n2b["2b. Step 2 · Gather starting context"]:::state
    n2c["2c. Step 3 · Probe scope for sub-projects"]:::state
    n2d["2d. Step 4 · Interview (Socratic rounds)"]:::state
    n2e["2e. Step 5 · Propose 2-3 approaches"]:::state
    n2f["2f. Step 6 · fork writes spec_&lt;slug&gt;.md"]:::state
    n2g["2g. Step 7 · Self-review the spec"]:::state
    n2h["2h. Step 8 · Present the spec for review"]:::state
    n2i["2i. Step 9 · plan-writer writes plan_&lt;slug&gt;.md"]:::state
    n2j["2j. Step 10 · Self-review, hand off with /clear"]:::state
    n2a --> n2b --> n2c --> n2d --> n2e --> n2f --> n2g --> n2h --> n2i --> n2j
  end

  n3["3. Step 1 · Ask all 3 yes/no toggles in ONE message, before any other question:<br/><br/>Every line traces to an AC? · Right-sized plan? · Fresh-eyes self-review (default yes)?<br/>they gate how strictly steps 7 and 10 check the documents"]:::gate
  n4["4. Persist all 3 answers to /tmp/sdd_&lt;session_id&gt;.json<br/><br/>steps 7 and 10 read them back and never re-ask;<br/>settled before any document exists, so none can be waived for failing"]:::state
  n5["5. Create the run scratchpad /tmp/brainstorm_&lt;session_id&gt;.md<br/><br/>written as things happen, never at the end; lives through spec, plan and self-review<br/>on resume/after compaction: re-read it first, trust it over recalled context"]:::state

  n6{"6. Step 2 · Path provided?"}
  n6a["6a. Read the provided spec file"]
  n6b["6b. Glob spec_*.md in CWD (top-level)"]
  n6c{"6c. How many matches?"}
  n6c1["6c1. Read the single match"]
  n6c2["6c2. List matches numbered; ask user which to refine"]:::gate
  n6c3["6c3. Zero matches: seed from session context (fresh idea)"]

  n7{"7. Step 3 · Request looks decomposable?<br/>(multiple nouns, roles, or independently-shippable features)"}
  n7a["7a. Name candidate sub-projects;<br/>ask user how they relate and which ships first"]:::gate
  n7b{"7b. User agrees to decompose?"}
  n7b1["7b1. Write scopes.md<br/><br/>One line per sub-project: name, purpose, dependency"]

  n8["8. Load test-standards coverage-taxonomy reference<br/>(unconditional, before the FIRST interview round —<br/>its categories shape the questions, not just a final sweep)"]:::skill
  n9["9. Step 4 · Interview: ask 2-3 Socratic questions per round<br/>(AskUserQuestion, recommended answer first)<br/><br/>categories: Background • Goal/KPIs • User Stories • Acceptance Criteria (BDD) • NFR/Technical constraints • Open Questions<br/><br/>split facts (look up yourself) from decisions (ask user)"]:::gate
  n10["10. Write each round's outcome to the scratchpad as it closes<br/><br/>decisions with their why, discarded alternatives with why they lost, open questions"]:::state
  n11["11. Push user through every taxonomy category;<br/>probe corner cases (empty/max/boundary) + failure modes (timeouts/partial/rate-limit)"]:::gate
  n12{"12. Exit criterion met?<br/>(latest round added no new requirement/constraint changes AND every taxonomy category covered or ruled out)"}

  n13["13. Step 5 · Propose 2-3 approaches with trade-offs;<br/>lead with recommendation"]
  n14["14. Get directional pick from user;<br/>the fork later records it plus the discarded alternatives in the spec's Decisions section"]:::gate

  n15{"15. Step 6 · spec_&lt;slug&gt;.md already exists?"}
  n15a["15a. Derive kebab-case slug from the feature, confirm it with the user<br/><br/>the plan inherits the same slug, which is what pairs the two"]:::gate
  n16{{"16. Dispatch fork · inherits this session's model AND full context (serial, foreground)<br/><br/>it reads the spec-driven-development library + spec-template, folds the<br/>scratchpad's decisions in, then writes/updates the spec<br/><br/>this session never writes the spec itself — every later edit re-dispatches a fork"}}:::dispatch

  n17{"17. Step 7 · Fresh-eyes self-review toggle on?<br/>(read back from /tmp/sdd_&lt;session_id&gt;.json, never re-asked)"}
  n17a{{"17a. Dispatch deep-reviewer · agent-pinned (serial, foreground)<br/>on the spec file ALONE — no plan exists yet<br/><br/>placeholders • contradictions • ambiguity • completeness • scope • human-reviewable"}}:::dispatch
  n17b{{"17b. Dispatch fork · inherits session context (serial)<br/>to apply every blocking finding to the spec<br/><br/>runs exactly once — never a second review round, the user reads it next"}}:::dispatch
  n17c["17c. Record in the scratchpad what was flagged and how each finding was resolved"]:::state
  n17d["17d. Note 'spec self-review skipped by request'<br/>to carry into the step 8 summary"]:::state

  n18["18. Step 8 · Present spec summary + what the review flagged and how it was fixed;<br/>ask if anything is missing or wrong"]:::gate
  n19{"19. User satisfied?"}
  n19a{{"19a. Dispatch fork · inherits session context (serial)<br/>carrying the exact wording/detail edits"}}:::dispatch

  n20{{"20. Step 9 · Dispatch plan-writer · agent-pinned (serial, foreground)<br/><br/>inputs: spec path, plan_&lt;slug&gt;.md output path, planning-conventions file if any<br/>sees only the spec file, never this interview"}}:::dispatch
  n21{"21. plan-writer returned a numbered gap list?"}
  n21a["21a. Walk and close EVERY reported gap with the user first<br/><br/>the spec update goes through a fork; then re-dispatch plan-writer once (not once per gap);<br/>never invent the missing decision"]:::gate

  n22["22. Step 10 · Read spec-driven-development/references/self-review-checks.md"]:::skill
  n23{"23. Fresh-eyes self-review toggle on?<br/>(same answer as step 7, same file)"}
  n23a{{"23a. Dispatch deep-reviewer · agent-pinned (serial):<br/>qualitative pass over spec + plan — placeholders, contradictions,<br/>scope, PR size, ambiguity, completeness, human-reviewable"}}:::dispatch
  n23b["23b. Note 'qualitative pass skipped by request' in the self-review output"]:::state
  n24{{"24. Dispatch mermaid-fixer · agent-pinned (serial)<br/>on every diagram in the spec + plan — no toggle switches this off"}}:::dispatch
  n25{{"25. Dispatch density-fixer · agent-pinned (serial)<br/>on the spec + plan files — no toggle switches this off"}}:::dispatch
  n26["26. Run seven formal checks in sequence<br/>(5 always-on + 2 gated by the AC-traceability and right-sized toggles)<br/><br/>AC-test-coverage and right-sized checks each<br/>dispatch deep-reviewer · agent-pinned (serial)"]
  n27{"27. All blocking checks pass?"}
  n27a["27a. Fix flagged issue directly;<br/>surface spec/plan conflicts to user first, if any"]:::gate
  n27b["27b. Snapshot spec+plan to /tmp/sdd-snapshots/<br/>for the user's annotated-diff review<br/><br/>a fresh snapshot per round of AI fixes"]:::state
  n27c{"27c. User approves the snapshot?"}:::gate
  n27c1["27c1. Re-run only the failed check,<br/>plus a delta-scoped re-review of what the diff shows changed<br/><br/>never the whole seven-check block"]
  n28(["28. Hand off: tell the user to run /clear, then invoke /implement<br/><br/>brainstorm never runs /implement itself"]):::gate

  n1 --> n2a
  n2j --> n3
  n3 --> n4
  n4 --> n5
  n5 --> n6

  n6 -->|"yes"| n6a
  n6 -->|"no"| n6b
  n6b --> n6c
  n6c -->|"one match"| n6c1
  n6c -->|"multiple matches"| n6c2
  n6c -->|"zero matches"| n6c3

  n6a --> n7
  n6c1 --> n7
  n6c2 --> n7
  n6c3 --> n7

  n7 -->|"yes"| n7a
  n7 -->|"no"| n8
  n7a --> n7b
  n7b -->|"yes"| n7b1
  n7b -->|"no: whole idea, no narrowing"| n8
  n7b1 --> n8

  n8 --> n9
  n9 --> n10
  n10 --> n11
  n11 --> n12
  n12 -->|"no, more rounds"| n9
  n12 -->|"yes"| n13

  n13 --> n14
  n14 --> n15
  n15 -->|"yes"| n16
  n15 -->|"no"| n15a
  n15a --> n16

  n16 --> n17
  n17 -->|"yes"| n17a
  n17 -->|"no, opted out"| n17d
  n17a --> n17b
  n17b --> n17c
  n17c --> n18
  n17d --> n18

  n18 --> n19
  n19 -->|"no: wording/detail"| n19a
  n19a --> n18
  n19 -->|"no: missing/wrong requirements"| n9
  n19 -->|"no: approach concerns"| n13
  n19 -->|"yes"| n20

  n20 --> n21
  n21 -->|"yes, gaps found"| n21a
  n21a --> n20
  n21 -->|"no, plan produced"| n22
  n22 --> n23
  n23 -->|"yes"| n23a
  n23 -->|"no, opted out"| n23b
  n23a --> n24
  n23b --> n24
  n24 --> n25
  n25 --> n26
  n26 --> n27
  n27 -->|"yes"| n28
  n27 -->|"no"| n27a
  n27a --> n27b
  n27b --> n27c
  n27c -->|"no: more fixes"| n27a
  n27c -->|"yes"| n27c1
  n27c1 --> n27

  classDef start fill:#fef3c7,stroke:#d97706,stroke-width:2px
  classDef gate fill:#fee2e2,stroke:#dc2626,stroke-width:2px
  classDef dispatch fill:#dbeafe,stroke:#2563eb,stroke-width:2px
  classDef state fill:#dcfce7,stroke:#16a34a,stroke-width:2px
  classDef skill fill:#f3e8ff,stroke:#9333ea,stroke-width:2px
  classDef hook fill:#e5e7eb,stroke:#4b5563,stroke-width:2px
```
