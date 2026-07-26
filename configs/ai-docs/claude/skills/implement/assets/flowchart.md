# implement — flow overview

Human-facing overview for auditing the flow at a glance. Non-authoritative — the numbered steps in [`../SKILL.md`](../SKILL.md) win on any conflict. Regenerate this file whenever the skill's flow changes.

```mermaid
flowchart TD
  n1(["1. /implement &lt;task-ids&gt; | &lt;PR-label(s)&gt;<br/><br/>or natural language: 'let's implement that'<br/>(triggers when plan_&lt;slug&gt;.md exists)"]):::start
  n2["2. Step 1.1 · Locate plan_&lt;slug&gt;.md (+ spec)"]
  n3{"3. Plan found?"}
  n3a(["3a. Stop: no plan given"])
  n4["4. Step 1.2 · ONE up-front interview, before<br/>any dispatch (only round until<br/>the review package):<br/><br/>- Plan pick, if multiple candidates<br/>- Run in a git worktree?<br/>- Open a draft PR at batch end?<br/>- Refactor+auto-review batch-end<br/>tails? (default yes)<br/>- Confirm base branch (shown default)"]:::gate
  n5{"5. Worktree requested?"}
  n5a["5a. Load references/worktree-setup.md"]:::skill
  n5b["5b. Step 1.3 · EnterWorktree + symlink<br/>plan/spec/branches files,<br/>copy .env*"]
  n6{"6. Arg is PR-label(s)?"}
  n6a["6a. Load references/pr-awareness.md<br/>(routes on to pr-branch-creation.md<br/>only when a checkout is needed)"]:::skill
  n6b["6b. Step 1.8 · Resolve EVERY PR-N in the arg<br/>to its task-id list (get-pr-tasks.sh),<br/>before any seeding"]
  n7["7. Step 2.1 · TaskList: one entry per task,<br/>ALL PRs upfront in execution order<br/>(PR-2 subjects prefixed 'PR-2 &middot;');<br/>1st in_progress, rest pending;<br/>status only, no metadata mirror"]:::state

  subgraph seedRemind["8. Step 2.2 · After each PR's task entries, seed that batch's 5 batch-end [Reminder]s — separate entries, never one chain.<br/>A combined entry has a single completed flag, so a step-level skip or failure would have nowhere to land.<br/>Prefixed 'PR-N &middot;' on a PR-label run; no run-specific values (BATCH_BASE_SHA lives in the state file)."]
    direction TB
    n8a["8a. Add to TaskList a [Reminder] for<br/>Batch-end 1/5: planned-test presence gate"]:::state
    n8b["8b. Add to TaskList a [Reminder] for<br/>Batch-end 2/5: repo-green gate — full suite + full lint"]:::state
    n8c["8c. Add to TaskList a [Reminder] for<br/>Batch-end 3/5: review tails ∥ then triage"]:::state
    n8d["8d. Add to TaskList a [Reminder] for<br/>Batch-end 4/5: package print, diffview pane"]:::state
    n8e["8e. Add to TaskList a [Reminder] for<br/>Batch-end 5/5: draft PR via create-pr (only when pr.wanted)"]:::state
    n8a --> n8b --> n8c --> n8d --> n8e
  end

  subgraph perunit ["Per unit: whole batch (task-ids run) or each PR (PR-label list)"]
    n8e1["8e1. Re-check PR DAG (check-pr-dag.sh)<br/>for this PR"]:::hook
    n9["9. Step 1.4 · Recap since base,<br/>capture BATCH_BASE_SHA<br/>(fresh per PR)"]
    n10{"10. PR-label mode:<br/>checkout needed for this PR?"}
    n10a["10a. Create/adopt PR branch,<br/>merge parents if diamond"]
    n11["11. Step 1.5 · State-file init:<br/>/tmp/implement_&lt;session_id&gt;.json;<br/>found existing state file to adopt<br/>per references/preflight-state.md"]:::state
    n12["12. Step 1.6 · Match &lt;task-id&gt;"]
    n13{"13. Multiple matches for<br/>&lt;task-id&gt;? (rare)"}
    n13a["13a. Ask user: which task-id?"]:::gate
    n14{"14. Resume or dirty run?"}
    n14a["14a. Load references/resume-reconcile.md"]:::skill
    n14b["14b. Step 1.7 · Ask user, per task state:<br/>Done: re-execute/skip/abort<br/>Doing: resume/restart/abort<br/>Blocked/Deferred: resume/abort<br/>Dropped: revive/abort"]:::gate
    n14c["14c. Step 1.7 · Ask user (TaskList has items):<br/>keep all / delete completed /<br/>delete all / cancel /implement"]:::gate
    n15["15. Step 3 · TaskList: mark task in_progress<br/>+ breadcrumb (AC titles)"]:::state
    n16["16. Step 3 · Subagent writes RED-GREEN<br/>checklist file:<br/>/tmp/implement_substeps_&lt;slug&gt;_&lt;id&gt;.md<br/>(a contract, not scratch)"]:::state
    n17["17. Step 4 · Dispatch tdd-coder<br/>(agent-pinned, background,<br/>SERIAL across tasks)"]:::dispatch
    n17a["17a. Hooks guarding this dispatch:<br/>subagent-model-guard + git-guard"]:::hook
    n17b["17b. 1h Monitor timeout expires:<br/>TaskStop the subagent<br/>(dispatch resolves as timeout)"]:::hook
    n19{"19. Mid-execution design fork?"}
    n19a["19a. Step 4.2 · tdd-coder resolves it itself,<br/>NEVER spawning a subagent<br/>(a hard fork returns blocked)"]
    n20{"20. Step 4.4 · Subagent report status?"}
    n21["21. Step 5.1 · Verify commits, diff,<br/>checklist, verification command"]
    n22{"22. Verify passed?"}
    n18["18. Step 5.2 · Record attempt:<br/>result=fail/timeout/blocked,<br/>signature, into state<br/>file attempts[]"]:::state
    n18a["18a. Load references/failure-verdict.md"]:::skill
    n25{"25. Step 5.2 · Run implement-loop-state.sh:<br/>verdict?"}:::hook
    n26["26. Step 5.3 · Mark task terminal in the state<br/>file; chain-abort dependents;<br/>TaskUpdate status=completed"]:::state
    n29{"29. Another non-done/blocked<br/>task pending?"}
    n23["23. Step 5.4 · Advance: state file status=done;<br/>plan_&lt;slug&gt;.md [Done];<br/>TaskUpdate status=completed"]:::state
    n24{"24. Step 5.4 · Run implement-loop-state.sh:<br/>verdict?"}:::hook
    n28["28. Step 8 · Dispatch deep-reviewer:<br/>batch test-presence gate<br/>(agent-pinned, serial)"]:::dispatch
    n30{"30. All planned tests found<br/>(or every task N/A)?"}
    n30a["30a. Step 8 · Re-dispatch task(s) with<br/>missing titles (tdd-coder, agent-pinned,<br/>try-once, same 1h Monitor cap<br/>as step 4)"]:::dispatch
    n30b["30b. Step 8 · Re-gate once<br/>(deep-reviewer, agent-pinned)"]:::dispatch
    n28a["28a. Hook: deep-reviewer-write-guard"]:::hook
    n31["31. Load references/batch-end-review.md<br/>(expands 9.1-9.5; routes on to<br/>batch-end-pr.md only when a PR<br/>is in play)"]:::skill
    n27["27. Step 9.1 · Repo-green gate: full suite<br/>+ lint; cheap failures fixed by<br/>the orchestrator itself, its own<br/>commit (autonomous, no human<br/>gate); structural failures become<br/>[Scout] items, unfixed"]:::gate
    n32{"32. Repo green?"}
    n33{"33. Tails requested?"}
    n33a["33a. Load code-review-pipeline/<br/>references/deep-reviewer-tail-pair.md"]:::skill
    n33b["33b. Step 9.2 par 9.3 · Dispatch refactor +<br/>auto-review deep-reviewer tails<br/>(BOTH agent-pinned, PARALLEL,<br/>mandatory, report-only)"]:::dispatch
    n33c["33c. Record tails report paths<br/>into the state file; complete the<br/>'Batch-end 3/5' [Reminder]"]:::state
    n34["34. Step 9.4 · Triage: synthesize +<br/>apply-offer both reports"]
    n36["36. Step 9.5 · branches_&lt;slug&gt;.md:<br/>append-branch-pr-entry.sh<br/>(PR-label runs only)"]:::state
    n37{"37. Draft PR requested<br/>AND repo green?"}
    n37a["37a. Step 9.5 · Dispatch create-pr agent<br/>(agent-pinned,<br/>draft-only scope)"]:::dispatch
    n37b["37b. Push branch + open or update<br/>the draft PR"]:::gate
    n35["35. Step 9.5 · Print the batch-end package;<br/>THEN open the nvim diffview pane<br/>(open-in-tmux); strike remaining<br/>[Reminder] steps"]
    n38{"38. This PR/batch: all tasks Done<br/>AND gate passed?"}
  end

  n32a["32a. Red repo: structural failures are<br/>[Scout] items; package still prints,<br/>flagged 'repo not green'; PR suppressed"]:::gate
  n40{"40. PR-label mode with<br/>PRs remaining?"}
  n39(["39. Present final report<br/>(phase: presented or halted)"])
  n39a["39a. Stop hook: gates session stop<br/>on the run's phase"]:::hook
  n41{"41. User names findings to<br/>apply? (opt-in only,<br/>never a repeating loop)"}:::gate
  n41a["41a. Dispatch fix per named finding:<br/>refactor-lens to refactor agent<br/>(agent-pinned); auto-review-lens<br/>to tdd-coder (agent-pinned, step 4<br/>contract)"]:::dispatch
  n41b["41b. Annotate verdict_*.md:<br/>APPLIED (sha) or SKIPPED (reason)"]:::state
  n42(["42. End of invocation"])

  n1 --> n2 --> n3
  n3 -->|"no"| n3a
  n3 -->|"yes"| n4
  n4 --> n5
  n5 -->|"yes"| n5a --> n5b --> n6
  n5 -->|"no"| n6
  n6 -->|"yes"| n6a --> n6b --> n7
  n6 -->|"no"| n7
  n7 --> n8a
  n8e -->|"PR-label run"| n8e1 --> n9
  n8e -->|"task-ids run"| n9
  n9 --> n10
  n10 -->|"yes"| n10a --> n11
  n10 -->|"no / task-ids mode"| n11
  n11 --> n12
  n12 --> n13
  n13 -->|"yes"| n13a --> n14
  n13 -->|"no"| n14
  n14 -->|"yes"| n14a --> n14b --> n14c --> n15
  n14 -->|"no"| n15
  n15 --> n16 --> n17
  n17 -.->|"guards"| n17a
  n17 -->|"1h timeout"| n17b --> n18
  n17 --> n19
  n19 -->|"yes"| n19a --> n20
  n19 -->|"no"| n20
  n20 -->|"blocked"| n18
  n20 -->|"done"| n21
  n21 --> n22
  n22 -->|"pass"| n23 --> n24
  n22 -->|"fail"| n18
  n18 -.->|"on demand"| n18a
  n18 --> n25
  n25 -->|"retry (loads debug-standards)"| n17
  n25 -->|"stuck"| n26
  n25 -->|"halt-budget"| n27
  n24 -->|"next-task"| n12
  n24 -->|"gates"| n28
  n24 -->|"halt-budget"| n27
  n26 --> n29
  n29 -->|"yes"| n12
  n29 -->|"no"| n28
  n28 -.->|"guards"| n28a
  n28 --> n30
  n30 -->|"yes"| n31
  n30 -->|"missing"| n30a --> n30b --> n31
  n30b -.->|"guards"| n28a
  n31 --> n27
  n27 --> n32
  n32 -->|"no"| n32a --> n33
  n32 -->|"yes"| n33
  n33 -->|"yes"| n33a --> n33b --> n33c --> n34
  n33b -.->|"guards"| n28a
  n33 -->|"no"| n34
  n34 --> n35 --> n36 --> n37
  n37 -->|"yes"| n37a --> n37b --> n38
  n37 -->|"no"| n38
  n38 -->|"no"| n39
  n38 -->|"yes"| n40
  n40 -->|"yes"| n8e1
  n40 -->|"no"| n39
  n39 -.->|"releases"| n39a
  n39 --> n41
  n41 -->|"yes"| n41a --> n41b --> n42
  n41 -->|"no"| n42

  classDef start fill:#fef3c7,stroke:#d97706,stroke-width:2px
  classDef gate fill:#fee2e2,stroke:#dc2626,stroke-width:2px
  classDef dispatch fill:#dbeafe,stroke:#2563eb,stroke-width:2px
  classDef state fill:#dcfce7,stroke:#16a34a,stroke-width:2px
  classDef skill fill:#f3e8ff,stroke:#9333ea,stroke-width:2px
  classDef hook fill:#e5e7eb,stroke:#4b5563,stroke-width:2px
```
