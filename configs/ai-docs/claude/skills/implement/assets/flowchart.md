# implement — flow overview

Human-facing overview for auditing the flow at a glance. Non-authoritative — the numbered steps in [`../SKILL.md`](../SKILL.md) win on any conflict. Regenerate this file whenever the skill's flow changes.

```mermaid
flowchart TD
  start(["/implement &lt;task-ids&gt; | &lt;PR-label(s)&gt;"]):::start
  locate["1.1 Locate plan_&lt;slug&gt;.md (+ spec)"]
  d_found{"Plan found?"}
  stop_noplan(["Stop: no plan given"])
  interview["1.2 Up-front interview:<br/>worktree? draft PR? pre-dispatch review?<br/>tails? base branch?"]
  d_worktree{"Worktree requested?"}
  worktree_setup["1.3 Create worktree + symlink files"]
  d_review{"Pre-dispatch review requested?"}
  orch_review["2. Orchestration review<br/>(fresh-context, adversarial)"]:::dispatch
  seed_remind["2.1 Seed batch-end [Remind] task"]
  seed_tasks["2.2 Create all matched tasks in TaskList"]
  d_prlabel{"Arg is PR-label(s)?"}

  subgraph perunit ["Per unit: whole batch (task-ids run) or each PR (PR-label list)"]
    dag_recheck["Re-check PR DAG,<br/>resolve PR-N to task-ids"]
    recap["1.4 Recap since base,<br/>capture BATCH_BASE_SHA"]
    d_branch{"PR-label mode:<br/>checkout needed for this PR?"}
    branch_setup["Create/adopt PR branch,<br/>merge parents if diamond"]
    state_init["1.5 State-file init / resume-adopt"]
    match_task["1.6 Match &lt;task-id&gt;"]
    d_resume{"Resume or dirty run?"}
    reconcile["1.7 Reconcile existing task status"]
    substeps["3. Subagent writes RED-GREEN checklist file"]
    dispatch_task["4. Dispatch task subagent<br/>(tdd-coder, background)"]:::dispatch
    d_fork{"Mid-execution design fork?"}
    fork_review["4.2 Fork reviewer<br/>(opus, fresh-context)"]:::dispatch
    d_report{"4.4 Subagent report status?"}
    verify["5.1-5.2 Verify diff, checklist,<br/>planned-test presence"]
    d_verify{"Verify passed?"}
    d_verdict_fail{"5.3 Run implement-loop-state.sh:<br/>verdict?"}
    terminal["5.4 Mark task terminal,<br/>chain-abort dependents"]
    d_next_terminal{"Another non-done/blocked<br/>task pending?"}
    advance["5.5 Advance task to done"]
    d_verdict_pass{"5.5 Run implement-loop-state.sh:<br/>verdict?"}
    gate_dispatch["8. Dispatch deep-reviewer:<br/>batch test-presence gate"]:::dispatch
    d_gate{"All planned tests found<br/>(or every task N/A)?"}
    gate_fix["8. Re-dispatch task(s)<br/>with missing titles (try-once)"]
    gate_regate["8. Re-gate once<br/>(deep-reviewer)"]:::dispatch
    green_gate["9.1 Repo-green gate:<br/>full suite + lint"]
    d_green{"Repo green?"}
    d_tails{"Tails requested?"}
    tails["9.2 ∥ 9.3 Dispatch refactor +<br/>auto-review tails (parallel)"]:::dispatch
    triage["9.4 Triage: synthesize +<br/>apply-offer findings"]
    d_pr{"Draft PR requested?"}
    pr_dispatch["9.5 Dispatch create-pr agent<br/>(draft only)"]:::dispatch
    package["9.5 Present batch-end package"]
    d_pr_ok{"This PR/batch: all tasks Done<br/>AND gate passed?"}
  end

  block_red(["Block: red repo —<br/>no package or PR"])
  d_more_pr{"PR-label mode with<br/>PRs remaining?"}
  present_final(["Present final report<br/>(phase: presented or halted)"])

  start --> locate --> d_found
  d_found -->|"no"| stop_noplan
  d_found -->|"yes"| interview
  interview --> d_worktree
  d_worktree -->|"yes"| worktree_setup --> d_review
  d_worktree -->|"no"| d_review
  d_review -->|"yes"| orch_review --> seed_remind
  d_review -->|"no"| seed_remind
  seed_remind --> seed_tasks --> d_prlabel
  d_prlabel -->|"yes"| dag_recheck --> recap
  d_prlabel -->|"no"| recap
  recap --> d_branch
  d_branch -->|"yes"| branch_setup --> state_init
  d_branch -->|"no / task-ids mode"| state_init
  state_init --> match_task --> d_resume
  d_resume -->|"yes"| reconcile --> substeps
  d_resume -->|"no"| substeps
  substeps --> dispatch_task --> d_fork
  d_fork -->|"yes"| fork_review --> d_report
  d_fork -->|"no"| d_report
  d_report -->|"blocked"| terminal
  d_report -->|"done"| verify --> d_verify
  d_verify -->|"pass"| advance --> d_verdict_pass
  d_verify -->|"fail / timeout"| d_verdict_fail
  d_verdict_fail -->|"retry"| dispatch_task
  d_verdict_fail -->|"stuck"| terminal
  d_verdict_fail -->|"halt-budget"| green_gate
  d_verdict_pass -->|"next-task"| match_task
  d_verdict_pass -->|"gates"| gate_dispatch
  d_verdict_pass -->|"halt-budget"| green_gate
  terminal --> d_next_terminal
  d_next_terminal -->|"yes"| match_task
  d_next_terminal -->|"no"| gate_dispatch
  gate_dispatch --> d_gate
  d_gate -->|"yes"| green_gate
  d_gate -->|"missing"| gate_fix --> gate_regate --> green_gate
  green_gate --> d_green
  d_green -->|"no"| block_red
  d_green -->|"yes"| d_tails
  d_tails -->|"yes"| tails --> triage
  d_tails -->|"no"| triage
  triage --> d_pr
  d_pr -->|"yes"| pr_dispatch --> package
  d_pr -->|"no"| package
  package --> d_pr_ok
  d_pr_ok -->|"no"| present_final
  d_pr_ok -->|"yes"| d_more_pr
  d_more_pr -->|"yes"| dag_recheck
  d_more_pr -->|"no"| present_final
  block_red --> present_final

  classDef start fill:#fef3c7,stroke:#d97706,stroke-width:2px
  classDef dispatch fill:#dbeafe,stroke:#2563eb,stroke-width:2px
```
