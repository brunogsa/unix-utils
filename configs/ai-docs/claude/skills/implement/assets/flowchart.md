# implement — flow overview

Human-facing overview for auditing the flow at a glance. Non-authoritative — the numbered steps in [`../SKILL.md`](../SKILL.md) win on any conflict. Regenerate this file whenever the skill's flow changes.

```mermaid
flowchart TD
  start(["/implement &lt;task-ids&gt; | &lt;PR-label(s)&gt;<br/><br/>or natural language: 'let's implement that'<br/>(triggers when plan_&lt;slug&gt;.md exists)"]):::start
  locate["1.1 Locate plan_&lt;slug&gt;.md (+ spec)"]
  d_found{"Plan found?"}
  stop_noplan(["Stop: no plan given"])
  interview["1.2 ONE up-front interview, before<br/>any dispatch (only round until<br/>the review package):<br/><br/>- Plan pick, if multiple candidates<br/>- Run in a git worktree?<br/>- Open a draft PR at batch end?<br/>- Pre-dispatch orchestration review?<br/>(default no)<br/>- Refactor+auto-review batch-end<br/>tails? (default yes)<br/>- Confirm base branch (shown default)"]:::gate
  d_worktree{"Worktree requested?"}
  skill_worktree["Load references/worktree-setup.md"]:::skill
  worktree_setup["1.3 EnterWorktree + symlink<br/>plan/spec/branches files,<br/>copy .env*"]
  d_review{"Pre-dispatch review requested?"}
  orch_review["2. Orchestration review<br/>(deep-reviewer, opus, high;<br/>fresh-context, adversarial)"]:::dispatch
  seed_remind["2.1 TaskList: seed ONE [Remind] task<br/>(subject = arrow chain, survives<br/>compaction):<br/>gate to tails(refactor par review) to<br/>triage to PR(create-pr, if wanted) to<br/>diffview; metadata tracks each<br/>step pending or done"]:::state
  seed_tasks["2.2 TaskList: create matched tasks<br/>(this PR's only, if PR-label run);<br/>1st in_progress, rest pending;<br/>metadata: pr_label, attempt_count=0,<br/>gate_outcome=pending"]:::state
  d_prlabel{"Arg is PR-label(s)?"}
  skill_pr["Load references/pr-awareness.md"]:::skill

  subgraph perunit ["Per unit: whole batch (task-ids run) or each PR (PR-label list)"]
    dag_recheck["Re-check PR DAG (check-pr-dag.sh),<br/>resolve PR-N to task-ids"]:::hook
    recap["1.4 Recap since base,<br/>capture BATCH_BASE_SHA"]
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
    dispatch_task["4. Dispatch tdd-coder<br/>(sonnet pinned, maxTurns 128,<br/>background, SERIAL across tasks;<br/>preloads: test-driven-development,<br/>code-standards, test-standards,<br/>doc-standards, commit-standards)"]:::dispatch
    hook_dispatch_guards["Hooks guarding this dispatch:<br/>subagent-model-guard (enforces<br/>pinned model) + git-guard (rejects<br/>a commit missing the<br/>Co-Authored-By trailer)"]:::hook
    timeout_stop["1h Monitor timeout expires:<br/>TaskStop the subagent<br/>(dispatch resolves as timeout)"]:::hook
    d_fork{"Mid-execution design fork?"}
    fork_review["4.2 Fork reviewer (opus,<br/>fresh-context; no subagent_type<br/>pinned; bound by that agent's own<br/>maxTurns, not the 1h Monitor cap)"]:::dispatch
    d_report{"4.4 Subagent report status?"}
    verify["5.1-5.2 Verify diff, checklist,<br/>planned-test presence"]
    skill_planned_test["Load references/<br/>planned-test-verification.md"]:::skill
    d_verify{"Verify passed?"}
    record_attempt["Record attempt: result=fail/timeout,<br/>signature, tokens, into state<br/>file attempts[]"]:::state
    skill_failure["Load references/failure-verdict.md"]:::skill
    d_verdict_fail{"5.3 Run implement-loop-state.sh:<br/>verdict?"}:::hook
    terminal["5.4 Mark task terminal;<br/>chain-abort dependents;<br/>TaskUpdate metadata gate_outcome=red,<br/>status=completed (both)"]:::state
    d_next_terminal{"Another non-done/blocked<br/>task pending?"}
    advance["5.5 Advance: plan_&lt;slug&gt;.md [Done];<br/>TaskUpdate metadata gate_outcome=green,<br/>fix_commit_shas, status=completed"]:::state
    d_verdict_pass{"5.5 Run implement-loop-state.sh:<br/>verdict?"}:::hook
    gate_dispatch["8. Dispatch deep-reviewer:<br/>batch test-presence gate<br/>(opus, effort high, maxTurns 64)"]:::dispatch
    d_gate{"All planned tests found<br/>(or every task N/A)?"}
    gate_fix["8. Re-dispatch task(s) with<br/>missing titles (tdd-coder, sonnet,<br/>try-once, same 1h Monitor cap<br/>as step 4)"]:::dispatch
    gate_regate["8. Re-gate once<br/>(deep-reviewer, opus, high)"]:::dispatch
    hook_write_guard["Hook: deep-reviewer-write-guard<br/>(auto-approves only verdict_*.md<br/>/ /tmp writes, denies the rest)"]:::hook
    skill_batch_end["Load references/batch-end.md<br/>(owns the whole batch-end flow)"]:::skill
    green_gate["9.1 Repo-green gate: full suite<br/>+ lint; cheap failures fixed by<br/>the orchestrator itself, its own<br/>commit (autonomous, no human<br/>gate); structural failures become<br/>[Scout] items, unfixed"]:::gate
    d_green{"Repo green?"}
    d_tails{"Tails requested?"}
    tasklist_tails["9.2-9.3 TaskList: create 2 [Side]<br/>tail tasks (simplification,<br/>correctness lenses)"]:::state
    skill_tail_pair["Load code-review-pipeline/<br/>references/deep-reviewer-tail-pair.md"]:::skill
    tails["9.2 par 9.3 Dispatch refactor +<br/>auto-review deep-reviewer tails<br/>(BOTH opus, effort high, PARALLEL,<br/>mandatory, report-only)"]:::dispatch
    tails_record["Record tails report paths + tokens<br/>into state file; TaskUpdate tail<br/>TaskList metadata; strike this<br/>[Remind] step"]:::state
    triage["9.4 Triage: synthesize +<br/>apply-offer both reports"]
    pr_manifest["9.5 branches_&lt;slug&gt;.md:<br/>append-branch-pr-entry.sh<br/>(PR-label runs only)"]:::state
    d_pr{"Draft PR requested?"}
    pr_dispatch["9.5 Dispatch create-pr agent<br/>(sonnet, effort medium,<br/>draft-only scope)"]:::dispatch
    push_pr["Push branch + gh pr create --draft<br/>(or PATCH existing PR body)"]:::gate
    package["9.5 Present batch-end package;<br/>run implement-loop-metrics.sh;<br/>strike remaining [Remind] steps<br/>as they land; write presented_at"]
    d_pr_ok{"This PR/batch: all tasks Done<br/>AND gate passed?"}
  end

  block_red(["Block: red repo —<br/>no package or PR"])
  d_more_pr{"PR-label mode with<br/>PRs remaining?"}
  present_final(["Present final report<br/>(phase: presented or halted)"])
  hook_stop["Stop hook: blocks session stop<br/>while phase is tasks, gates,<br/>or tails; releases at<br/>presented or halted"]:::hook
  d_apply{"User names findings to<br/>apply? (opt-in only,<br/>never a repeating loop)"}:::gate
  apply_dispatch["Dispatch fix per named finding:<br/>refactor-lens to refactor agent<br/>(opus, high); auto-review-lens<br/>to tdd-coder (sonnet, full<br/>SS4 contract)"]:::dispatch
  annotate["Annotate verdict_*.md:<br/>APPLIED (sha) or SKIPPED (reason)"]:::state
  end_done(["End of invocation"])

  start --> locate --> d_found
  d_found -->|"no"| stop_noplan
  d_found -->|"yes"| interview
  interview --> d_worktree
  d_worktree -->|"yes"| skill_worktree --> worktree_setup --> d_review
  d_worktree -->|"no"| d_review
  d_review -->|"yes"| orch_review --> seed_remind
  d_review -->|"no"| seed_remind
  seed_remind --> seed_tasks --> d_prlabel
  d_prlabel -->|"yes"| skill_pr --> dag_recheck --> recap
  d_prlabel -->|"no"| recap
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
  d_fork -->|"yes"| fork_review --> d_report
  d_fork -->|"no"| d_report
  d_report -->|"blocked"| terminal
  d_report -->|"done"| verify
  verify -.->|"on demand"| skill_planned_test
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
  d_green -->|"no"| block_red
  d_green -->|"yes"| d_tails
  d_tails -->|"yes"| tasklist_tails --> skill_tail_pair --> tails --> tails_record --> triage
  tails -.->|"guards"| hook_write_guard
  d_tails -->|"no"| triage
  triage --> pr_manifest --> d_pr
  d_pr -->|"yes"| pr_dispatch --> push_pr --> package
  d_pr -->|"no"| package
  package --> d_pr_ok
  d_pr_ok -->|"no"| present_final
  d_pr_ok -->|"yes"| d_more_pr
  d_more_pr -->|"yes"| dag_recheck
  d_more_pr -->|"no"| present_final
  block_red --> present_final
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
