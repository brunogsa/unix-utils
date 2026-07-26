# implement — flow overview

Human-facing overview for auditing the flow at a glance. Non-authoritative — the numbered steps in [`../SKILL.md`](../SKILL.md) win on any conflict. Regenerate this file whenever the skill's flow changes.

```mermaid
flowchart TD
  start(["/implement &lt;task-ids&gt; | &lt;PR-label(s)&gt;<br/><br/>or natural language: 'let's implement that'<br/>(triggers when plan_&lt;slug&gt;.md exists)"]):::start
  locate["1.1 Locate plan_&lt;slug&gt;.md (+ spec)"]
  d_found{"Plan found?"}
  stop_noplan(["Stop: no plan given"])
  interview["1.2 ONE up-front interview, before<br/>any dispatch (only round until<br/>the review package):<br/><br/>- Plan pick, if multiple candidates<br/>- Run in a git worktree?<br/>- Open a draft PR at batch end?<br/>- Refactor+auto-review batch-end<br/>tails? (default yes)<br/>- Confirm base branch (shown default)"]:::gate
  d_worktree{"Worktree requested?"}
  skill_worktree["Load references/worktree-setup.md"]:::skill
  worktree_setup["1.3 EnterWorktree + symlink<br/>plan/spec/branches files,<br/>copy .env*"]
  d_prlabel{"Arg is PR-label(s)?"}
  skill_pr["Load references/pr-awareness.md<br/>(routes on to pr-branch-creation.md<br/>only when a checkout is needed)"]:::skill
  resolve_labels["1.8 Resolve EVERY PR-N in the arg<br/>to its task-id list (get-pr-tasks.sh),<br/>before any seeding"]
  seed_tasks["2.1 TaskList: one entry per task,<br/>ALL PRs upfront in execution order<br/>(PR-2 subjects prefixed 'PR-2 &middot;');<br/>1st in_progress, rest pending;<br/>status only, no metadata mirror"]:::state
  seed_remind["2.2 TaskList: after each PR's tasks,<br/>seed its 5 SEPARATE [Reminder] entries<br/>(1/5 test-presence, 2/5 repo-green,<br/>3/5 tails+triage, 4/5 metrics+package<br/>+diffview, 5/5 draft PR);<br/>no run-specific values in subjects"]:::state

  subgraph perunit ["Per unit: whole batch (task-ids run) or each PR (PR-label list)"]
    dag_recheck["Re-check PR DAG (check-pr-dag.sh)<br/>for this PR"]:::hook
    recap["1.4 Recap since base,<br/>capture BATCH_BASE_SHA<br/>(fresh per PR)"]
    d_branch{"PR-label mode:<br/>checkout needed for this PR?"}
    branch_setup["Create/adopt PR branch,<br/>merge parents if diamond"]
    state_init["1.5 State-file init:<br/>/tmp/implement_&lt;session_id&gt;.json;<br/>found existing state file to adopt<br/>per references/preflight-state.md"]:::state
    match_task["1.6 Match &lt;task-id&gt;"]
    d_ambig{"Multiple matches for<br/>&lt;task-id&gt;? (rare)"}
    ask_which["Ask user: which task-id?"]:::gate
    d_resume{"Resume or dirty run?"}
    skill_resume["Load references/resume-reconcile.md"]:::skill
    state_prompt["1.7 Ask user, per task state:<br/>Done: re-execute/skip/abort<br/>Doing: resume/restart/abort<br/>Blocked/Deferred: resume/abort<br/>Dropped: revive/abort"]:::gate
    tl_prompt["1.7 Ask user (TaskList has items):<br/>keep all / delete completed /<br/>delete all / cancel /implement"]:::gate
    mark_progress["3. TaskList: mark task in_progress<br/>+ breadcrumb (AC titles)"]:::state
    substeps["3. Subagent writes RED-GREEN<br/>checklist file:<br/>/tmp/implement_substeps_&lt;slug&gt;_&lt;id&gt;.md<br/>(a contract, not scratch)"]:::state
    dispatch_task["4. Dispatch tdd-coder<br/>(sonnet pinned, maxTurns 128,<br/>background, SERIAL across tasks)"]:::dispatch
    hook_dispatch_guards["Hooks guarding this dispatch:<br/>subagent-model-guard + git-guard"]:::hook
    timeout_stop["1h Monitor timeout expires:<br/>TaskStop the subagent<br/>(dispatch resolves as timeout)"]:::hook
    d_fork{"Mid-execution design fork?"}
    fork_resolve["4.2 tdd-coder resolves it itself,<br/>NEVER spawning a subagent<br/>(a hard fork returns blocked)"]
    d_report{"4.4 Subagent report status?"}
    verify["5.1 Verify commits, diff,<br/>checklist, verification command"]
    d_verify{"Verify passed?"}
    record_attempt["5.2 Record attempt:<br/>result=fail/timeout/blocked,<br/>signature, tokens, into state<br/>file attempts[]"]:::state
    skill_failure["Load references/failure-verdict.md"]:::skill
    d_verdict_fail{"5.2 Run implement-loop-state.sh:<br/>verdict?"}:::hook
    terminal["5.3 Mark task terminal in the state<br/>file; chain-abort dependents;<br/>TaskUpdate status=completed"]:::state
    d_next_terminal{"Another non-done/blocked<br/>task pending?"}
    advance["5.4 Advance: state file status=done;<br/>plan_&lt;slug&gt;.md [Done];<br/>TaskUpdate status=completed"]:::state
    d_verdict_pass{"5.4 Run implement-loop-state.sh:<br/>verdict?"}:::hook
    gate_dispatch["8. Dispatch deep-reviewer:<br/>batch test-presence gate<br/>(opus, effort max, maxTurns 64)"]:::dispatch
    d_gate{"All planned tests found<br/>(or every task N/A)?"}
    gate_fix["8. Re-dispatch task(s) with<br/>missing titles (tdd-coder, sonnet,<br/>try-once, same 1h Monitor cap<br/>as step 4)"]:::dispatch
    gate_regate["8. Re-gate once<br/>(deep-reviewer, opus, max)"]:::dispatch
    hook_write_guard["Hook: deep-reviewer-write-guard"]:::hook
    skill_batch_end["Load references/batch-end-review.md<br/>(expands 9.1-9.5; routes on to<br/>batch-end-pr.md only when a PR<br/>is in play)"]:::skill
    green_gate["9.1 Repo-green gate: full suite<br/>+ lint; cheap failures fixed by<br/>the orchestrator itself, its own<br/>commit (autonomous, no human<br/>gate); structural failures become<br/>[Scout] items, unfixed"]:::gate
    d_green{"Repo green?"}
    d_tails{"Tails requested?"}
    skill_tail_pair["Load code-review-pipeline/<br/>references/deep-reviewer-tail-pair.md"]:::skill
    tails["9.2 par 9.3 Dispatch refactor +<br/>auto-review deep-reviewer tails<br/>(BOTH opus, effort max, PARALLEL,<br/>mandatory, report-only)"]:::dispatch
    tails_record["Record tails report paths + tokens<br/>into the state file; complete the<br/>'Batch-end 3/5' [Reminder]"]:::state
    triage["9.4 Triage: synthesize +<br/>apply-offer both reports"]
    pr_manifest["9.5 branches_&lt;slug&gt;.md:<br/>append-branch-pr-entry.sh<br/>(PR-label runs only)"]:::state
    d_pr{"Draft PR requested<br/>AND repo green?"}
    pr_dispatch["9.5 Dispatch create-pr agent<br/>(sonnet, effort medium,<br/>draft-only scope)"]:::dispatch
    push_pr["Push branch + open or update<br/>the draft PR"]:::gate
    package["9.5 write presented_at; run<br/>implement-loop-metrics.sh; print the<br/>batch-end package; THEN open the<br/>nvim diffview pane (open-in-tmux);<br/>strike remaining [Reminder] steps"]
    d_pr_ok{"This PR/batch: all tasks Done<br/>AND gate passed?"}
  end

  red_flag["Red repo: structural failures are<br/>[Scout] items; package still prints,<br/>flagged 'repo not green'; PR suppressed"]:::gate
  d_more_pr{"PR-label mode with<br/>PRs remaining?"}
  present_final(["Present final report<br/>(phase: presented or halted)"])
  hook_stop["Stop hook: gates session stop<br/>on the run's phase"]:::hook
  d_apply{"User names findings to<br/>apply? (opt-in only,<br/>never a repeating loop)"}:::gate
  apply_dispatch["Dispatch fix per named finding:<br/>refactor-lens to refactor agent<br/>(opus, high); auto-review-lens<br/>to tdd-coder (sonnet, step 4<br/>contract)"]:::dispatch
  annotate["Annotate verdict_*.md:<br/>APPLIED (sha) or SKIPPED (reason)"]:::state
  end_done(["End of invocation"])

  start --> locate --> d_found
  d_found -->|"no"| stop_noplan
  d_found -->|"yes"| interview
  interview --> d_worktree
  d_worktree -->|"yes"| skill_worktree --> worktree_setup --> d_prlabel
  d_worktree -->|"no"| d_prlabel
  d_prlabel -->|"yes"| skill_pr --> resolve_labels --> seed_tasks
  d_prlabel -->|"no"| seed_tasks
  seed_tasks --> seed_remind
  seed_remind -->|"PR-label run"| dag_recheck --> recap
  seed_remind -->|"task-ids run"| recap
  recap --> d_branch
  d_branch -->|"yes"| branch_setup --> state_init
  d_branch -->|"no / task-ids mode"| state_init
  state_init --> match_task
  match_task --> d_ambig
  d_ambig -->|"yes"| ask_which --> d_resume
  d_ambig -->|"no"| d_resume
  d_resume -->|"yes"| skill_resume --> state_prompt --> tl_prompt --> mark_progress
  d_resume -->|"no"| mark_progress
  mark_progress --> substeps --> dispatch_task
  dispatch_task -.->|"guards"| hook_dispatch_guards
  dispatch_task -->|"1h timeout"| timeout_stop --> record_attempt
  dispatch_task --> d_fork
  d_fork -->|"yes"| fork_resolve --> d_report
  d_fork -->|"no"| d_report
  d_report -->|"blocked"| record_attempt
  d_report -->|"done"| verify
  verify --> d_verify
  d_verify -->|"pass"| advance --> d_verdict_pass
  d_verify -->|"fail"| record_attempt
  record_attempt -.->|"on demand"| skill_failure
  record_attempt --> d_verdict_fail
  d_verdict_fail -->|"retry (loads debug-standards)"| dispatch_task
  d_verdict_fail -->|"stuck"| terminal
  d_verdict_fail -->|"halt-budget"| green_gate
  d_verdict_pass -->|"next-task"| match_task
  d_verdict_pass -->|"gates"| gate_dispatch
  d_verdict_pass -->|"halt-budget"| green_gate
  terminal --> d_next_terminal
  d_next_terminal -->|"yes"| match_task
  d_next_terminal -->|"no"| gate_dispatch
  gate_dispatch -.->|"guards"| hook_write_guard
  gate_dispatch --> d_gate
  d_gate -->|"yes"| skill_batch_end
  d_gate -->|"missing"| gate_fix --> gate_regate --> skill_batch_end
  gate_regate -.->|"guards"| hook_write_guard
  skill_batch_end --> green_gate
  green_gate --> d_green
  d_green -->|"no"| red_flag --> d_tails
  d_green -->|"yes"| d_tails
  d_tails -->|"yes"| skill_tail_pair --> tails --> tails_record --> triage
  tails -.->|"guards"| hook_write_guard
  d_tails -->|"no"| triage
  triage --> package --> pr_manifest --> d_pr
  d_pr -->|"yes"| pr_dispatch --> push_pr --> d_pr_ok
  d_pr -->|"no"| d_pr_ok
  d_pr_ok -->|"no"| present_final
  d_pr_ok -->|"yes"| d_more_pr
  d_more_pr -->|"yes"| dag_recheck
  d_more_pr -->|"no"| present_final
  present_final -.->|"releases"| hook_stop
  present_final --> d_apply
  d_apply -->|"yes"| apply_dispatch --> annotate --> end_done
  d_apply -->|"no"| end_done

  classDef start fill:#fef3c7,stroke:#d97706,stroke-width:2px
  classDef gate fill:#fee2e2,stroke:#dc2626,stroke-width:2px
  classDef dispatch fill:#dbeafe,stroke:#2563eb,stroke-width:2px
  classDef state fill:#dcfce7,stroke:#16a34a,stroke-width:2px
  classDef skill fill:#f3e8ff,stroke:#9333ea,stroke-width:2px
  classDef hook fill:#e5e7eb,stroke:#4b5563,stroke-width:2px
```
