# brainstorm — flow overview

Human-facing flow audit. Non-authoritative — [`../SKILL.md`](../SKILL.md)'s numbered steps win on any conflict; regenerate whenever the flow changes.

```mermaid
flowchart TD
  n1(["1. User runs /brainstorm [path/to/spec]"]):::start

  subgraph seedHead["2. Seed the TaskList upfront — one [Reminder] per step 1-5, before step 1 runs.<br/>Only the head is knowable yet: step 1's depth answer decides what comes after step 5."]
    direction TB
    n2a["2a. Add to TaskList a [Reminder] for<br/>Step 1 · Pre-flight — depth, toggles, run state"]:::state
    n2b["2b. Add to TaskList a [Reminder] for<br/>Step 2 · Gather starting context"]:::state
    n2c["2c. Add to TaskList a [Reminder] for<br/>Step 3 · Probe scope for sub-projects"]:::state
    n2d["2d. Add to TaskList a [Reminder] for<br/>Step 4 · Interview (Socratic rounds)"]:::state
    n2e["2e. Add to TaskList a [Reminder] for<br/>Step 5 · Propose 2-3 approaches"]:::state
    n2a --> n2b --> n2c --> n2d --> n2e
  end

  n3["3. Step 1 · Ask all FOUR questions in ONE AskUserQuestion call, before any other question:<br/><br/>How much spec/plan writing? full (default) · light · none<br/>Every line traces to an AC? · Right-sized plan? · Fresh-eyes self-review (default yes)?<br/><br/>one pass even when the depth answer makes the three toggles moot —<br/>splitting it would cost two round-trips on every run to spare a rare one three dead questions"]:::gate
  n4["4. Persist all 4 answers to /tmp/sdd_&lt;session_id&gt;.json<br/><br/>the depth lands in the mode field, valued exactly full, light or none;<br/>every step below reads it back from there and never re-asks<br/><br/>at depth none the three toggles are recorded and then never read —<br/>nothing exists for them to gate"]:::state
  n5["5. Create the run scratchpad /tmp/brainstorm_&lt;session_id&gt;.md<br/><br/>decisions with their why, discarded alternatives, open questions — written as they happen<br/>on resume/after compaction: re-read it first, trust it over recalled context"]:::state

  n6{"6. Seed the rest of the TaskList — which depth did step 1 settle?<br/>seeding steps the depth then cancels would leave reminders nobody can complete"}

  subgraph seedTailDocs["6a. Depth full or light → one [Reminder] per step 6-10"]
    direction TB
    n6a1["6a1. Step 6 · fork writes the spec"]:::state
    n6a2["6a2. Step 7 · Self-review the spec"]:::state
    n6a3["6a3. Step 8 · Present the spec for review"]:::state
    n6a4["6a4. Step 9 · plan-writer writes the plan"]:::state
    n6a5["6a5. Step 10 · Self-review, hand off with /clear"]:::state
    n6a1 --> n6a2 --> n6a3 --> n6a4 --> n6a5
  end

  subgraph seedTailNone["6b. Depth none → one [Reminder] per named section of references/tasklist-only-mode.md,<br/>which replaces steps 6-10 entirely"]
    direction TB
    n6b1["6b1. Close every open question first"]:::state
    n6b2["6b2. Seed the work as TaskList entries"]:::state
    n6b3["6b3. Prove the interview's coverage landed"]:::state
    n6b4["6b4. Present the list for approval"]:::state
    n6b5["6b5. Skip every document gate, and say so once"]:::state
    n6b6["6b6. Hand off without /implement"]:::state
    n6b1 --> n6b2 --> n6b3 --> n6b4 --> n6b5 --> n6b6
  end

  n7{"7. Step 2 · Path provided?"}
  n7a["7a. Read the provided spec file"]
  n7b["7b. Glob spec_*.md in CWD (top-level)"]
  n7c{"7c. How many matches?"}
  n7c1["7c1. Read the single match"]
  n7c2["7c2. List matches numbered; ask user which to refine"]:::gate
  n7c3["7c3. Zero matches: seed from session context (fresh idea)"]

  n8["8. Step 2 · Check whether a plan already sits beside the resolved spec (the paired path);<br/>record the answer in the run scratchpad — step 9 needs it to update rather than overwrite the plan"]:::state

  n9{"9. Step 3 · Request looks decomposable?<br/>(multiple nouns, roles, or independently-shippable features)"}
  n9a["9a. Name candidate sub-projects;<br/>ask user how they relate and which ships first"]:::gate
  n9b{"9b. User agrees to decompose?"}
  n9b1{"9b1. Which depth did step 1 settle?"}
  n9b1a["9b1a. Depth full or light → write scopes.md; brainstorm only the first sub-project here<br/><br/>One line per sub-project: name, purpose, dependency;<br/>it survives the session, so the next run picks up the queue"]:::state
  n9b1b["9b1b. Depth none → record each deferred sub-project as a [Side] TaskList entry instead<br/><br/>that depth writes no files, and a TaskList entry outlives the session just as well"]:::state

  n10["10. Step 4 · Load test-standards coverage-taxonomy reference<br/>(unconditional at every depth, before the FIRST interview round —<br/>its categories shape the questions, not just a final sweep)"]:::skill
  n11["11. Step 4 · Interview: ask 2-3 Socratic questions per round<br/>(AskUserQuestion, recommended answer first)<br/><br/>categories: Background • Goal/KPIs • User Stories • Acceptance Criteria (BDD) • NFR/Technical constraints • Open Questions<br/><br/>split facts (look up yourself) from decisions (ask user)"]:::gate
  n12["12. Write each round's outcome to the scratchpad as it closes<br/><br/>decisions with their why, discarded alternatives with why they lost, open questions"]:::state
  n13["13. Push user through every taxonomy category;<br/>probe corner cases (empty/max/boundary) + failure modes (timeouts/partial/rate-limit)"]:::gate
  n14{"14. Exit criterion met?<br/>(latest round added no new requirement/constraint changes AND every taxonomy category covered or ruled out)"}

  n15["15. Step 5 · Propose 2-3 approaches with trade-offs;<br/>lead with recommendation"]
  n16["16. Get directional pick from user;<br/>the fork later records it plus the discarded alternatives in the spec's Decisions section"]:::gate

  n17{"17. Which depth did step 1 settle?<br/><br/>the branch sits here because steps 2-5 are one interview at every depth,<br/>and step 6 is the first step that needs a document to exist"}

  n17a["17a. Depth none → read references/tasklist-only-mode.md and follow it in place of steps 6-10<br/><br/>this skill's own flow in a bundled file, not a callee;<br/>full and light never read it, so only the none path pays for it"]:::skill
  n17b["17b. Close every open question — AskUserQuestion, 2-3 at a time, recommended answer first<br/><br/>stricter than the document depths: there is no Open Questions heading to park one in,<br/>so a question left open simply disappears with the session"]:::gate
  n17c["17c. Seed the work as TaskList entries — one per commit-sized unit, in execution order<br/><br/>[Sub-Step] when it ships with its parent's commit; [Side] for a deferred sub-project<br/>decision, files and verification command go in each task's metadata field<br/>subjects stand alone: no 'the approach we picked', no pronouns pointing at the interview"]:::state
  n17d["17d. Write one line per coverage-taxonomy category into the scratchpad — every category, not a sample<br/><br/>each line ends in the id of the task that owns it, or 'declined — the reason the user gave'<br/>the only checkable completion criterion this depth has: no check-ac-coverage.sh exists to catch a dropped failure mode"]:::state
  n17e["17e. Present the TaskList plus those coverage lines;<br/>ask the user whether anything is missing or wrong"]:::gate
  n17f{"17f. User satisfied?"}
  n17f1["17f1. Edit the entries, then re-present"]
  n17g["17g. Skip every document gate — no mermaid-fixer, no density-fixer,<br/>none of the four scripts, none of the judged deep-reviewer passes<br/><br/>each one parses a spec or a plan file, and neither exists<br/>state once that they were skipped because no documents were written"]:::state
  n17h(["17h. Hand off: execute from the TaskList, one task per subagent —<br/>or re-run /brainstorm at light depth to get the documents after all<br/><br/>/implement is NOT offered here: it resolves a plan by glob in CWD<br/>and stops outright when it finds none"]):::gate

  n18{"18. Step 6 · The spec already exists?"}
  n18a["18a. Derive a short kebab-case slug from the feature<br/><br/>never confirmed with the user — it only names two files that travel together,<br/>so a wrong one costs a rename; the plan inherits the same slug, which pairs the two"]
  n19{{"19. Step 6 · Dispatch: Write the spec<br/>fork · inherits session model + full context · serial · foreground<br/><br/>it reads the spec-driven-development library + spec-template, folds the<br/>scratchpad's decisions in, then writes/updates the spec<br/><br/>at depth light it also reads that library's references/light-section-set.md and writes<br/>only the sections that set keeps, omitting each dropped heading rather than filling it with N/A<br/><br/>this session never writes the spec itself — every later edit re-dispatches a fork"}}:::dispatch

  n20{"20. Step 7 · Fresh-eyes self-review toggle on?<br/>(read back from /tmp/sdd_&lt;session_id&gt;.json, never re-asked)"}
  n20a{{"20a. Dispatch: Fresh-eyes review of the spec<br/>deep-reviewer · agent-pinned · serial · foreground<br/>on the spec file ALONE — no plan exists yet<br/><br/>placeholders • contradictions • ambiguity • completeness • human-reviewable<br/>NOT scope (step 3 asked the user) and NOT PR-size/plan-contradiction (no plan)"}}:::dispatch
  n20b{{"20b. Dispatch: Apply the spec review findings<br/>fork · inherits session context · serial · foreground<br/>every blocking finding goes into the spec<br/><br/>runs once per spec-writing pass — a step-8 loop-back through step 6 rewrites<br/>the spec and earns a fresh pass; unchanged text does not, since the user<br/>reading it next is the stronger judge"}}:::dispatch
  n21["21. Step 8 · Give the user the spec's PATH and ask if anything is missing or wrong<br/><br/>no spec summary, no report of what step 7 flagged or fixed —<br/>the user reads the document itself, and a summary is a second version that can contradict it"]:::gate
  n22{"22. User satisfied?"}
  n22a{{"22a. Dispatch: Apply the spec edits<br/>fork · inherits session context · serial · foreground<br/>carrying the exact wording/detail edits"}}:::dispatch

  n23{{"23. Step 9 · Dispatch: Write the implementation plan<br/>plan-writer · agent-pinned · serial · foreground<br/><br/>inputs: spec's absolute path + slug, planning-conventions file if any,<br/>whether a plan already exists at the paired path (from Step 2)<br/>plan-writer resolves the output path itself from the slug; sees only the spec, never this interview<br/><br/>at depth light it is also told to read references/light-section-set.md and keep only<br/>that set's plan sections — PR Breakdown stays even when it reads only 'Single PR.',<br/>since check-pr-dag.sh passes on that literal, not on a missing section<br/><br/>if a plan already exists: update it in place — preserve every task status<br/>marker and everything below the decisions divider<br/><br/>a spec gap NEVER withholds the plan: it writes around the gap and<br/>records it as a **QUESTION:** under the plan's Open Questions"}}:::dispatch
  n24{"24. Returned a gap list instead of a plan?<br/>(unexpected — the agent records gaps rather than refusing)"}
  n24a{{"24a. Dispatch: Record the gaps as Open Questions in the spec<br/>fork · inherits session context · serial · foreground<br/>then re-dispatch plan-writer once — not once per gap"}}:::dispatch

  n25["25. Step 10 · Read spec-driven-development/references/self-review-checks.md now,<br/>and from the second round on also references/delta-scoped-rereview.md<br/>(scopes re-review to what diff shows changed, not both documents whole)<br/><br/>every gate below runs at BOTH full and light depth — light trims prose a human reads, never a check;<br/>that reference also tells the reviewer a section light drops is absent by design, never a finding<br/><br/>Sort self-review-checks.md's gates into two buckets:<br/>DETERMINISTIC (script/renderer verdict, free to re-run)<br/>NON-DETERMINISTIC (a deep-reviewer judges, one dispatch over both docs)"]:::skill

  n26{{"26. Step 10.1 · Dispatch: Fix the diagrams<br/>mermaid-fixer · model=sonnet · effort=high (overrides its pinned tier) · serial · foreground<br/>leads the density fixer — a repaired diagram adds lines density must then measure"}}:::dispatch
  n27{{"27. Dispatch: Fix over-cap line density<br/>density-fixer · model=sonnet · effort=high (overrides its pinned tier) · serial · foreground<br/>on the spec + plan files — no toggle switches this off"}}:::dispatch
  n28["28. Run the four deterministic scripts serially:<br/>check-ac-coverage.sh · check-test-distribution.sh<br/>check-pr-dag.sh · check-tasks-dag.sh"]
  n29{"29. All deterministic gates pass?"}
  n29a["29a. Fix the failure, then re-run that gate ALONE until it passes"]

  n30["30. Step 10.2 · Read the Open Questions section of BOTH spec and plan"]
  n31{"31. Any **QUESTION:** entry still open?"}
  n31a["31a. Interview the user to settle them<br/>(AskUserQuestion, 2-3 at a time, recommended answer first)<br/><br/>nothing expensive runs while a question is open: a judged gate reads both<br/>docs whole, so it would review a document about to change"]:::gate
  n31b{{"31b. Dispatch: Close the open questions<br/>fork · inherits session context · serial · foreground<br/>folds the answers into both docs, leaving each Open Questions section reading None"}}:::dispatch

  n32{"32. Step 10.3 · Fresh-eyes self-review toggle on?<br/>(same answer as step 7, same file, never re-asked)"}
  n32a{{"32a. Dispatch: Qualitative pass over spec + plan<br/>deep-reviewer · agent-pinned model (opus) · effort=high (overrides its max pin) · serial · foreground<br/>placeholders, contradictions, scope, PR size,<br/>ambiguity, completeness, human-reviewable"}}:::dispatch
  n32b["32b. Note 'qualitative pass skipped by request' in the self-review output"]:::state
  n33{{"33. Run the remaining judged gates serially — each dispatches<br/>deep-reviewer · agent-pinned model (opus) · effort=high (overrides its max pin) · serial · foreground<br/><br/>semantic AC-to-test coverage · 'how would this break?' ·<br/>the 2 toggled checks read from /tmp/sdd_&lt;session_id&gt;.json"}}:::dispatch

  n34{"34. Any blocking finding?"}
  n34a["34a. Step 10.4 · Snapshot both documents into /tmp/sdd-snapshots/<br/>(per delta-scoped-rereview.md) — before any fix lands"]:::state
  n34b["34b. Interview the user to resolve the finding<br/><br/>never invent the resolution, never resolve it silently"]:::gate
  n34c{{"34c. Dispatch: Apply the self-review findings<br/>fork · inherits session context · serial · foreground<br/>applies what the user decided to the spec, the plan, or both"}}:::dispatch
  n34d["34d. Re-run the DETERMINISTIC gates only<br/><br/>the fork's edits can break a DAG or an AC-coverage citation,<br/>and those are free to re-check"]
  n34e["34e. Hand the user a diff of each document against its snapshot<br/><br/>shows what the fork actually changed, and surfaces edits the user made directly"]
  n34f{"34f. Ask the user: re-run the non-deterministic gates, scoped to that diff?"}:::gate
  n35(["35. Hand off: tell the user to run /clear, then invoke /implement<br/><br/>brainstorm never runs /implement itself"]):::gate

  n1 --> n2a
  n2e --> n3
  n3 --> n4
  n4 --> n5
  n5 --> n6

  n6 -->|"full or light"| n6a1
  n6 -->|"none"| n6b1
  n6a5 --> n7
  n6b6 --> n7

  n7 -->|"yes"| n7a
  n7 -->|"no"| n7b
  n7b --> n7c
  n7c -->|"one match"| n7c1
  n7c -->|"multiple matches"| n7c2
  n7c -->|"zero matches"| n7c3

  n7a --> n8
  n7c1 --> n8
  n7c2 --> n8
  n7c3 --> n8

  n8 --> n9

  n9 -->|"yes"| n9a
  n9 -->|"no"| n10
  n9a --> n9b
  n9b -->|"yes"| n9b1
  n9b -->|"no: whole idea, no narrowing"| n10
  n9b1 -->|"full or light"| n9b1a
  n9b1 -->|"none"| n9b1b
  n9b1a --> n10
  n9b1b --> n10

  n10 --> n11
  n11 --> n12
  n12 --> n13
  n13 --> n14
  n14 -->|"no, more rounds"| n11
  n14 -->|"yes"| n15

  n15 --> n16
  n16 --> n17

  n17 -->|"none"| n17a
  n17a --> n17b
  n17b --> n17c
  n17c --> n17d
  n17d --> n17e
  n17e --> n17f
  n17f -->|"no: wording, ordering or task boundaries"| n17f1
  n17f1 --> n17e
  n17f -->|"no: missing/wrong requirements"| n11
  n17f -->|"no: approach concerns"| n15
  n17f -->|"yes"| n17g
  n17g --> n17h

  n17 -->|"full or light"| n18
  n18 -->|"yes"| n19
  n18 -->|"no"| n18a
  n18a --> n19

  n19 --> n20
  n20 -->|"yes"| n20a
  n20 -->|"no, opted out"| n21
  n20a --> n20b
  n20b --> n21

  n21 --> n22
  n22 -->|"no: wording/detail"| n22a
  n22a --> n21
  n22 -->|"no: missing/wrong requirements"| n11
  n22 -->|"no: approach concerns"| n15
  n22 -->|"yes"| n23

  n23 --> n24
  n24 -->|"yes"| n24a
  n24a --> n23
  n24 -->|"no, plan produced"| n25

  n25 --> n26
  n26 --> n27
  n27 --> n28
  n28 --> n29
  n29 -->|"no"| n29a
  n29a --> n29
  n29 -->|"yes"| n30

  n30 --> n31
  n31 -->|"yes"| n31a
  n31a --> n31b
  n31b --> n30
  n31 -->|"no, both read None"| n32

  n32 -->|"yes"| n32a
  n32 -->|"no, opted out"| n32b
  n32a --> n33
  n32b --> n33
  n33 --> n34

  n34 -->|"no"| n35
  n34 -->|"yes"| n34a
  n34a --> n34b
  n34b --> n34c
  n34c --> n34d
  n34d --> n34e
  n34e --> n34f
  n34f -->|"yes"| n32
  n34f -->|"no, accept as they stand"| n35

  classDef start fill:#fef3c7,stroke:#d97706,stroke-width:2px
  classDef gate fill:#fee2e2,stroke:#dc2626,stroke-width:2px
  classDef dispatch fill:#dbeafe,stroke:#2563eb,stroke-width:2px
  classDef state fill:#dcfce7,stroke:#16a34a,stroke-width:2px
  classDef skill fill:#f3e8ff,stroke:#9333ea,stroke-width:2px
  classDef hook fill:#e5e7eb,stroke:#4b5563,stroke-width:2px
```
