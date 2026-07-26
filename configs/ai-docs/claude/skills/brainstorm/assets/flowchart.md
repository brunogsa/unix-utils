# brainstorm — flow overview

Human-facing flow audit. Non-authoritative — [`../SKILL.md`](../SKILL.md)'s numbered steps win on any conflict; regenerate whenever the flow changes.

```mermaid
flowchart TD
  n1(["1. User runs /brainstorm [path/to/spec_&lt;slug&gt;.md]"]):::start

  subgraph seedTaskList["2. Seed the TaskList once, at skill start — one [Reminder] per step, before step 1 runs.<br/>Update each as it completes; the list survives compaction, so nothing is ever re-seeded."]
    direction TB
    n2a["2a. Add to TaskList a [Reminder] for<br/>Step 1 · Pre-flight — toggles + run state"]:::state
    n2b["2b. Add to TaskList a [Reminder] for<br/>Step 2 · Gather starting context"]:::state
    n2c["2c. Add to TaskList a [Reminder] for<br/>Step 3 · Probe scope for sub-projects"]:::state
    n2d["2d. Add to TaskList a [Reminder] for<br/>Step 4 · Interview (Socratic rounds)"]:::state
    n2e["2e. Add to TaskList a [Reminder] for<br/>Step 5 · Propose 2-3 approaches"]:::state
    n2f["2f. Add to TaskList a [Reminder] for<br/>Step 6 · fork writes spec_&lt;slug&gt;.md"]:::state
    n2g["2g. Add to TaskList a [Reminder] for<br/>Step 7 · Self-review the spec"]:::state
    n2h["2h. Add to TaskList a [Reminder] for<br/>Step 8 · Present the spec for review"]:::state
    n2i["2i. Add to TaskList a [Reminder] for<br/>Step 9 · plan-writer writes plan_&lt;slug&gt;.md"]:::state
    n2j["2j. Add to TaskList a [Reminder] for<br/>Step 10 · Self-review, hand off with /clear"]:::state
    n2a --> n2b --> n2c --> n2d --> n2e --> n2f --> n2g --> n2h --> n2i --> n2j
  end

  n3["3. Step 1 · Ask all 3 yes/no toggles in ONE message, before any other question:<br/><br/>Every line traces to an AC? · Right-sized plan? · Fresh-eyes self-review (default yes)?<br/>they gate how strictly steps 7 and 10 check the documents"]:::gate
  n4["4. Persist all 3 answers to /tmp/sdd_&lt;session_id&gt;.json<br/><br/>steps 7 and 10 read them back and never re-ask;<br/>settled before any document exists, so none can be waived for failing"]:::state
  n5["5. Create the run scratchpad /tmp/brainstorm_&lt;session_id&gt;.md<br/><br/>decisions with their why, discarded alternatives, open questions — written as they happen<br/>on resume/after compaction: re-read it first, trust it over recalled context"]:::state

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
  n7b1["7b1. Write scopes.md; brainstorm only the first sub-project here<br/><br/>One line per sub-project: name, purpose, dependency;<br/>it survives the session, so the next run picks up the queue"]:::state

  n8["8. Step 4 · Load test-standards coverage-taxonomy reference<br/>(unconditional, before the FIRST interview round —<br/>its categories shape the questions, not just a final sweep)"]:::skill
  n9["9. Step 4 · Interview: ask 2-3 Socratic questions per round<br/>(AskUserQuestion, recommended answer first)<br/><br/>categories: Background • Goal/KPIs • User Stories • Acceptance Criteria (BDD) • NFR/Technical constraints • Open Questions<br/><br/>split facts (look up yourself) from decisions (ask user)"]:::gate
  n10["10. Write each round's outcome to the scratchpad as it closes<br/><br/>decisions with their why, discarded alternatives with why they lost, open questions"]:::state
  n11["11. Push user through every taxonomy category;<br/>probe corner cases (empty/max/boundary) + failure modes (timeouts/partial/rate-limit)"]:::gate
  n12{"12. Exit criterion met?<br/>(latest round added no new requirement/constraint changes AND every taxonomy category covered or ruled out)"}

  n13["13. Step 5 · Propose 2-3 approaches with trade-offs;<br/>lead with recommendation"]
  n14["14. Get directional pick from user;<br/>the fork later records it plus the discarded alternatives in the spec's Decisions section"]:::gate

  n15{"15. Step 6 · spec_&lt;slug&gt;.md already exists?"}
  n15a["15a. Derive a short kebab-case slug from the feature<br/><br/>never confirmed with the user — it only names two files that travel together,<br/>so a wrong one costs a rename; the plan inherits the same slug, which pairs the two"]
  n16{{"16. Step 6 · Dispatch: Write the spec<br/>fork · inherits session model + full context · serial · foreground<br/><br/>it reads the spec-driven-development library + spec-template, folds the<br/>scratchpad's decisions in, then writes/updates the spec<br/><br/>this session never writes the spec itself — every later edit re-dispatches a fork"}}:::dispatch

  n17{"17. Step 7 · Fresh-eyes self-review toggle on?<br/>(read back from /tmp/sdd_&lt;session_id&gt;.json, never re-asked)"}
  n17a{{"17a. Dispatch: Fresh-eyes review of the spec<br/>deep-reviewer · agent-pinned · serial · foreground<br/>on the spec file ALONE — no plan exists yet<br/><br/>placeholders • contradictions • ambiguity • completeness • human-reviewable<br/>NOT scope (step 3 asked the user) and NOT PR-size/plan-contradiction (no plan)"}}:::dispatch
  n17b{{"17b. Dispatch: Apply the spec review findings<br/>fork · inherits session context · serial · foreground<br/>every blocking finding goes into the spec<br/><br/>runs exactly once — never a second review round, the user reads it next"}}:::dispatch
  n18["18. Step 8 · Give the user the spec's PATH and ask if anything is missing or wrong<br/><br/>no spec summary, no report of what step 7 flagged or fixed —<br/>the user reads the document itself, and a summary is a second version that can contradict it"]:::gate
  n19{"19. User satisfied?"}
  n19a{{"19a. Dispatch: Apply the spec edits<br/>fork · inherits session context · serial · foreground<br/>carrying the exact wording/detail edits"}}:::dispatch

  n20{{"20. Step 9 · Dispatch: Write the implementation plan<br/>plan-writer · agent-pinned · serial · foreground<br/><br/>inputs: spec path, plan_&lt;slug&gt;.md output path, planning-conventions file if any<br/>sees only the spec file, never this interview<br/><br/>a spec gap NEVER withholds the plan: it writes around the gap and<br/>records it as a **QUESTION:** under the plan's Open Questions"}}:::dispatch
  n21{"21. Returned a gap list instead of a plan?<br/>(unexpected — the agent records gaps rather than refusing)"}
  n21a{{"21a. Dispatch: Record the gaps as Open Questions in the spec<br/>fork · inherits session context · serial · foreground<br/>then re-dispatch plan-writer once — not once per gap"}}:::dispatch

  n22["22. Step 10 · Read spec-driven-development/references/self-review-checks.md<br/>and sort its gates into two buckets:<br/><br/>DETERMINISTIC (script/renderer verdict, free to re-run)<br/>NON-DETERMINISTIC (a deep-reviewer judges, one dispatch over both docs)"]:::skill

  n23{{"23. Step 10.1 · Dispatch: Fix the diagrams<br/>mermaid-fixer · agent-pinned · serial · foreground<br/>leads the density fixer — a repaired diagram adds lines density must then measure"}}:::dispatch
  n24{{"24. Dispatch: Fix over-cap line density<br/>density-fixer · agent-pinned · serial · foreground<br/>on the spec + plan files — no toggle switches this off"}}:::dispatch
  n25["25. Run the four deterministic scripts serially:<br/>check-ac-coverage.sh · check-test-distribution.sh<br/>check-pr-dag.sh · check-tasks-dag.sh"]
  n26{"26. All deterministic gates pass?"}
  n26a["26a. Fix the failure, then re-run that gate ALONE until it passes"]

  n27["27. Step 10.2 · Read the Open Questions section of BOTH spec and plan"]
  n28{"28. Any **QUESTION:** entry still open?"}
  n28a["28a. Interview the user to settle them<br/>(AskUserQuestion, 2-3 at a time, recommended answer first)<br/><br/>nothing expensive runs while a question is open: a judged gate reads both<br/>docs whole, so it would review a document about to change"]:::gate
  n28b{{"28b. Dispatch: Close the open questions<br/>fork · inherits session context · serial · foreground<br/>folds the answers into both docs, leaving each Open Questions section reading None"}}:::dispatch

  n29{"29. Step 10.3 · Fresh-eyes self-review toggle on?<br/>(same answer as step 7, same file, never re-asked)"}
  n29a{{"29a. Dispatch: Qualitative pass over spec + plan<br/>deep-reviewer · agent-pinned · serial · foreground<br/>placeholders, contradictions, scope, PR size,<br/>ambiguity, completeness, human-reviewable"}}:::dispatch
  n29b["29b. Note 'qualitative pass skipped by request' in the self-review output"]:::state
  n30{{"30. Run the remaining judged gates serially — each dispatches<br/>deep-reviewer · agent-pinned · serial · foreground<br/><br/>semantic AC-to-test coverage · 'how would this break?' ·<br/>the 2 toggled checks read from /tmp/sdd_&lt;session_id&gt;.json"}}:::dispatch

  n31{"31. Any blocking finding?"}
  n31a["31a. Step 10.4 · Interview the user to resolve it<br/><br/>never invent the resolution, never resolve it silently"]:::gate
  n31b{{"31b. Dispatch: Apply the self-review findings<br/>fork · inherits session context · serial · foreground<br/>applies what the user decided to the spec, the plan, or both"}}:::dispatch
  n31c["31c. Re-run the DETERMINISTIC gates only<br/><br/>the fork's edits can break a DAG or an AC-coverage citation,<br/>and those are free to re-check"]
  n31d{"31d. Ask the user: re-run the non-deterministic gates?"}:::gate
  n32(["32. Hand off: tell the user to run /clear, then invoke /implement<br/><br/>brainstorm never runs /implement itself"]):::gate

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
  n17 -->|"no, opted out"| n18
  n17a --> n17b
  n17b --> n18

  n18 --> n19
  n19 -->|"no: wording/detail"| n19a
  n19a --> n18
  n19 -->|"no: missing/wrong requirements"| n9
  n19 -->|"no: approach concerns"| n13
  n19 -->|"yes"| n20

  n20 --> n21
  n21 -->|"yes"| n21a
  n21a --> n20
  n21 -->|"no, plan produced"| n22

  n22 --> n23
  n23 --> n24
  n24 --> n25
  n25 --> n26
  n26 -->|"no"| n26a
  n26a --> n26
  n26 -->|"yes"| n27

  n27 --> n28
  n28 -->|"yes"| n28a
  n28a --> n28b
  n28b --> n27
  n28 -->|"no, both read None"| n29

  n29 -->|"yes"| n29a
  n29 -->|"no, opted out"| n29b
  n29a --> n30
  n29b --> n30
  n30 --> n31

  n31 -->|"no"| n32
  n31 -->|"yes"| n31a
  n31a --> n31b
  n31b --> n31c
  n31c --> n31d
  n31d -->|"yes"| n29
  n31d -->|"no, accept as they stand"| n32

  classDef start fill:#fef3c7,stroke:#d97706,stroke-width:2px
  classDef gate fill:#fee2e2,stroke:#dc2626,stroke-width:2px
  classDef dispatch fill:#dbeafe,stroke:#2563eb,stroke-width:2px
  classDef state fill:#dcfce7,stroke:#16a34a,stroke-width:2px
  classDef skill fill:#f3e8ff,stroke:#9333ea,stroke-width:2px
  classDef hook fill:#e5e7eb,stroke:#4b5563,stroke-width:2px
```
