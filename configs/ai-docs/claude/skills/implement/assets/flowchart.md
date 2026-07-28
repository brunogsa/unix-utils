---
# performance-check budget overrides, not part of the diagram itself.
# This file's size is fixed by the number of steps the skill actually has, and
# it renders each step twice — once as pseudo-code, once as a diagram node — so
# trimming to the bundled defaults would drop steps from the flow audit or drop
# a whole rendering. Two renderings is the point: they cross-check each other.
# Parked in assets/ and never loaded by the model, so its words cost no context.
words-budget: 4096
lines-budget: 512
---

# implement — flow overview

Human-facing overview for auditing the flow at a glance. Non-authoritative — the numbered steps in [`../SKILL.md`](../SKILL.md) win on any conflict. Regenerate this file whenever the skill's flow changes.

Two renderings of the same flow, kept cross-checkable on purpose. The `# N` comments in the pseudo-code are the diagram's node ids, so an id with no matching comment is drift.

## Pseudo-code

Python-shaped for readability only; nothing here is runnable, and the function names stand for orchestrator actions, not real APIs.

```python
# 1 · Entry: /implement <task-ids> | <PR-label(s)>
#     or natural language ("let's implement that") when plan_<slug>.md exists.
def implement(arg):
    plan, spec = locate_plan_and_spec()                    # 2 · §1.1, CWD top-level glob
    if not plan:
        return stop("no plan given")                       # 3a

    # 4 · §1.2 — ONE up-front interview, the only round until the review package:
    #     plan pick · worktree · draft PR · quality-gate tail (default yes)
    #     · repo-green gate (default yes) · confirm the base branch.
    answers = ask_everything_at_once()

    # 5 · §1.3 — re-validate BOTH graphs ONCE, before any execution.
    if not (check_tasks_dag(plan) and check_pr_dag(plan)):  # 6
        return stop(script_stderr_verbatim)                # 6a · fix the plan, re-invoke

    if answers.worktree:                                   # 7
        load("references/worktree-setup.md")               # 7a
        enter_worktree(symlink=[plan, spec, branches_file],     # 7b · §1.4
                       copy=[".env*"])

    if arg.is_pr_labels:                                   # 8
        load("references/pr-awareness.md")                 # 8a
        units = [get_pr_tasks(label) for label in arg.labels]   # 8b · §1.5
    else:
        units = [Unit(arg.task_ids)]                       # the whole batch is one unit

    # 9 · §2.1 + 10 · §2.2 — seed the WHOLE run upfront, in execution order:
    #     ALL PRs, each PR's tasks before its own batch-end reminders.
    for unit in units:
        for task in unit.tasks:
            task_create(f"{unit.label} · {task.id}. {task.title}",
                        status="in_progress" if is_first_of_run(task) else "pending")
            # TaskList carries status ONLY — attempts, gates and SHAs live in the JSON.
        for step in BATCH_END_STEPS:      # FOUR separate entries:
            task_create(f"[Reminder] {step}")
            # 10a · 1/4 repo-green gate, fix-loop until green
            # 10b · 2/4 quality-gate tail with --auto-solve
            # 10c · 3/4 push + open the PR via create-pr
            # 10d · 4/4 package print, diffview pane
            # Never one chain: a combined entry has one completed flag, so a
            # step-level skip would have nowhere to land.

    # 11 · §2.3 — durable state NOW, kept current as the run goes.
    for unit in units:
        write_json(f"/tmp/implement_{session_id}{unit.suffix}.json",
                   phase="tasks", start_sha=head(), batch_base_sha="")
    write_scratchpad(f"/tmp/implement_{session_id}.md")
    # NO resume path — a leftover state file is stale: delete it and start over.

    # 32 · a task-ids run has one unit; a PR-label run repeats §3–§8 per PR, in order.
    for unit in units:
        run_unit(unit)

    return  # 35 · invocation ends. 35a · Stop hook releases only on
            #      phase "presented" or "halted".


def run_unit(unit):
    if unit.is_pr and need_git_checkout(plan, unit.label, worktree):    # 12
        create_branch(unit)   # 12a · §3.1 — ONCE, here. Never mid-loop, never a subagent.

    state.batch_base_sha = head()                          # 13 · §3.2
    recap(git_log(base_branch, "HEAD"), read="COMMIT MESSAGES, not the diff")

    tasks = exact_match(unit.task_ids, plan.headings)      # 14 · §3.3
    # A prefix matching two headings means a malformed plan, not a question — stop.

    task = tasks.first
    while task:
        # 15 · §3.4 — the only orchestrator work between two dispatches.
        task_update(task, "in_progress", breadcrumb=plan.acceptance_titles(task))
        checklist = f"/tmp/implement_substeps_{slug}_{task.id}.md"

        while True:   # retry loop: 19c's "retry" comes back here, not to activation
            # 16 · §4 — agent-pinned, background, SERIAL across tasks, 1h Monitor cap.
            report = dispatch("tdd-coder", task, checklist, timeout_ms=3_600_000)
            # 16a · hooks: subagent-model-guard + git-guard
            # 16c · THE SUBAGENT writes its own RED-GREEN checklist + evidence;
            #       the orchestrator only checks that the file exists.
            if report.timed_out:
                task_stop(report.agent)                    # 16b · resolves as a timeout
                report.status = "timeout"

            if report.status == "done":                    # 17 · §4.4
                # 18 · §5.1 — fresh general-purpose (sonnet · high), FOREGROUND.
                #             It judges the checklist + evidence, re-running nothing.
                verify = dispatch("general-purpose", checklist, report,
                                  model="sonnet", effort="high", background=False)
            else:
                verify = "fail"   # `blocked` and `timeout` take the failure path too

            if verify == "pass":                           # 19
                state.set(task, status="done")             # 20 · §5.4 — before the script
                plan.mark(task, "[Done]")
                record_scout_notes(report.scouts)
                task_update(task, "completed")
            else:
                load("references/failure-and-halt.md")     # 19a
                state.record_attempt(task, verify, signature)    # 19b · §5.2

            # 19c / 21 · ONLY this script sends a unit to the gates. Never infer
            #            "gates" from an empty-looking queue — it empties two ways.
            v = implement_loop_state(state_file)
            if v != "retry":                               # retry loads debug-standards
                break

        if v == "stuck":                                   # 19d · §5.3
            mark_terminal(task)
            chain_abort_dependents(task, transitive=True)
            plan.mark(task, "[Blocked]")
            task_update(task, "completed")
            task = next_runnable()                         # 19e
            if not task:
                return halt()
        elif v == "next-task":
            task = v.task                                  # back to 15
        elif v == "gates":
            break                                          # every task in the unit is done
        else:                                              # "halted" | "halt-budget"
            return halt()

    # ---- 22–26 · §8 · batch-end gates ----
    load("references/batch-end-review.md")                 # 22

    if answers.repo_green_gate:                            # 23 · else skipped by request
        while True:
            # 24 · §8.1 — repo-wide, never scoped to the batch's own files.
            if full_lint() and full_test_suite():          # 24a
                break
            # A failure the batch didn't cause is a [Scout], never a blocker.
            if not fix_attempts_left():                    # 24b
                return halt()
            dispatch("tdd-coder", failure,                 # 24c · attempt recorded,
                     timeout_ms=3_600_000)                 #       RE-RUN THE FULL SUITE

    if answers.quality_gate_tail:                          # 25 · else skipped by request
        # 26 · §8.2 — IN THIS SESSION, never wrapped in a subagent: its legs are
        #     already fresh-context reviewers, and its commits need a permission
        #     prompt only main can render.
        run_skill("/quality-gate", tasks=unit.task_ids,
                  base_ref=state.batch_base_sha, auto_solve=True)
        # 26a · inside it: refactor ∥ auto-review ∥ test-sdd legs → three
        #       verdict_*.md, then per-finding apply → commit → mark [Done].
        # 26b · hook: deep-reviewer-write-guard (only verdict_*.md writes approved).
        state.record_verdict_paths()   # 26c · PATHS, never content; every finding
        scout(quality_gate.declined)   #       it declined becomes a [Scout]
        if quality_gate.applied_anything:                  # 26d
            full_test_suite(); full_lint()   # 26e · a fix nobody re-ran is a claim,
                                             #       not a green repo

    # ---- 27–31 · §8.3 · PR + package ----
    load("references/batch-end-pr.md")   # 27 · skipped entirely when this is neither a
                                         #      PR-label run nor an opted-in draft PR
    write_manifest_entry(branches_file)  # 28 · + PR-level status marker, PR-label only
    if answers.draft_pr:                                   # 29
        pr = dispatch("create-pr", batch_diff)   # 29a · composes the body, pushes the
                                                 #       branch AND opens the PR
        if not pr.opened:                                  # 29b
            return halt()

    print_review_package()               # 30 · package FIRST, then the pane
    open_in_tmux("nvim diffview")
    complete_remaining_reminders()
    state.phase = "presented"                              # 31
    delete(state_file)


def halt():
    load("references/failure-and-halt.md")                 # 33
    state.phase = "halted"                                 # 34 · §5.5
    scratchpad.write(what_each_blocker_needs)
    leave_pending(remaining_reminders)
    # Run NOTHING further; wait for the human.
```

## Flowchart

```mermaid
flowchart TD
  n1(["1. /implement &lt;task-ids&gt; | &lt;PR-label(s)&gt;<br/><br/>or natural language ('let's implement that')<br/>when plan_&lt;slug&gt;.md exists"]):::start
  n2["2. Step 1.1 · Locate plan_&lt;slug&gt;.md (+ spec)"]
  n3{"3. Plan found?"}
  n3a(["3a. Stop: no plan given"])
  n4["4. Step 1.2 · ONE up-front interview —<br/>the only round until the<br/>review package:<br/><br/>- Plan pick, if multiple candidates<br/>- Run in a git worktree?<br/>- Open a draft PR at batch end?<br/>- Quality-gate tail? (default yes)<br/>- Repo-green gate? (default yes)<br/>- Confirm the base branch"]:::gate
  n5["5. Step 1.3 · Re-validate BOTH graphs ONCE,<br/>before any execution:<br/>check-tasks-dag.sh + check-pr-dag.sh"]:::hook
  n6{"6. Both graphs valid?"}
  n6a(["6a. Stop: surface the script's stderr;<br/>fix the plan, re-invoke"])
  n7{"7. Worktree requested?"}
  n7a["7a. Load references/worktree-setup.md"]:::skill
  n7b["7b. Step 1.4 · EnterWorktree + symlink<br/>plan/spec/branches files,<br/>copy .env*"]
  n8{"8. Arg is PR-label(s)?"}
  n8a["8a. Load references/pr-awareness.md"]:::skill
  n8b["8b. Step 1.5 · Resolve EVERY PR-N to its<br/>task-id list (get-pr-tasks.sh),<br/>before any seeding"]
  n9["9. Step 2.1 · TaskList: one entry per task,<br/>ALL PRs upfront in execution order<br/>(subjects prefixed 'PR-2 &middot;');<br/>1st in_progress, rest pending;<br/>status only"]:::state

  subgraph seedRemind["10. Step 2.2 · After each PR's task entries, seed that batch's 4 batch-end [Reminder]s — separate entries, never one chain:<br/>a combined entry has one completed flag, so a step-level skip would have nowhere to land."]
    direction TB
    n10a["10a. Add to TaskList a [Reminder] for<br/>Batch-end 1/4: repo-green gate, fix-loop until green"]:::state
    n10b["10b. Add to TaskList a [Reminder] for<br/>Batch-end 2/4: quality-gate tail with --auto-solve"]:::state
    n10c["10c. Add to TaskList a [Reminder] for<br/>Batch-end 3/4: push + open the PR via create-pr"]:::state
    n10d["10d. Add to TaskList a [Reminder] for<br/>Batch-end 4/4: package print, diffview pane"]:::state
    n10a --> n10b --> n10c --> n10d
  end

  n11["11. Step 2.3 · Write durable state NOW,<br/>kept current as the run goes:<br/>one /tmp/implement_&lt;session_id&gt;[_prN].json<br/>per unit (phase=tasks, start_sha=HEAD)<br/>+ /tmp/implement_&lt;session_id&gt;.md scratchpad.<br/>NO resume path — a leftover file is stale"]:::state

  subgraph perunit ["Per unit: the whole batch (task-ids run), or each PR in turn (PR-label list)"]
    n12{"12. PR-label run: checkout needed?<br/>(need-git-checkout.sh)"}:::hook
    n12a["12a. Step 3.1 · Orchestrator creates this<br/>PR's branch — ONCE, here; never<br/>mid-loop, never by a subagent"]
    n13["13. Step 3.2 · Capture BATCH_BASE_SHA into<br/>the state file; recap the base from<br/>COMMIT MESSAGES, not the diff"]:::state
    n14["14. Step 3.3 · Exact-match this unit's task-ids<br/>(a collision means a malformed plan)"]
    n15["15. Step 3.4 · Activate a task: TaskUpdate<br/>in_progress + breadcrumb;<br/>assign the checklist path"]:::state
    n16["16. Step 4 · Dispatch tdd-coder<br/>(agent-pinned, background,<br/>SERIAL across tasks, 1h Monitor cap)"]:::dispatch
    n16a["16a. Hooks: subagent-model-guard + git-guard"]:::hook
    n16b["16b. 1h Monitor expires: TaskStop the<br/>subagent (resolves as timeout)"]:::hook
    n16c["16c. THE SUBAGENT writes its own RED-GREEN<br/>checklist + evidence:<br/>/tmp/implement_substeps_&lt;slug&gt;_&lt;id&gt;.md<br/>(the orchestrator only checks it exists)"]:::state
    n17{"17. Step 4.4 · Subagent report status?"}
    n18["18. Step 5.1 · Delegate the verify to a fresh<br/>general-purpose (sonnet · high), FOREGROUND —<br/>it judges the checklist + evidence,<br/>re-running nothing"]:::dispatch
    n19{"19. Verify verdict?"}
    n19a["19a. Load references/failure-and-halt.md"]:::skill
    n19b["19b. Step 5.2 · Record the attempt<br/>(fail/timeout/blocked + signature)<br/>into the state file"]:::state
    n19c{"19c. Step 5.2 · implement-loop-state.sh:<br/>verdict?"}:::hook
    n19d["19d. Step 5.3 · Mark the task terminal;<br/>chain-abort dependents transitively;<br/>plan [Blocked]; TaskUpdate completed"]:::state
    n19e{"19e. Step 5.3 · Any runnable task left?"}
    n20["20. Step 5.4 · Advance: state file status=done;<br/>plan [Done]; record [Scout] notes;<br/>TaskUpdate completed"]:::state
    n21{"21. Step 5.4 · implement-loop-state.sh: verdict?<br/>ONLY this script sends a unit to the gates"}:::hook
    n22["22. Load references/batch-end-review.md"]:::skill
    n23{"23. Repo-green gate requested?"}
    n24["24. Step 8.1 · Repo-green GATE: full lint +<br/>full test suite, repo-wide, never<br/>scoped to the batch's own files"]:::gate
    n24a{"24a. Green? (a failure the batch didn't<br/>cause is a [Scout], never a blocker)"}
    n24b{"24b. Fix attempts left?"}
    n24c["24c. Step 8.1 · Dispatch tdd-coder to fix it<br/>(agent-pinned, 1h Monitor cap, attempt<br/>recorded); RE-RUN THE FULL SUITE"]:::dispatch
    n25{"25. Quality-gate tail requested?"}
    n26["26. Step 8.2 · Invoke /quality-gate --tasks &lt;this unit's ids&gt;<br/>--auto-solve, base ref = BATCH_BASE_SHA.<br/>IN THIS SESSION, never wrapped in a subagent:<br/>its legs are already fresh-context reviewers, and<br/>its commits need a prompt only main can render"]:::skill
    n26a["26a. Inside it: refactor ∥ auto-review ∥ test-sdd legs<br/>→ three verdict_*.md, then per-finding<br/>apply → commit → mark [Done]"]:::dispatch
    n26b["26b. Hook: deep-reviewer-write-guard<br/>(only verdict_*.md writes are approved)"]:::hook
    n26c["26c. Record each verdict PATH into the state file<br/>(never its content); every finding it<br/>declined becomes a [Scout]"]:::state
    n26d{"26d. Did it apply anything?"}
    n26e["26e. Re-run §8.1's full suite + lint —<br/>a fix nobody re-ran is a claim,<br/>not a green repo"]:::gate
    n27["27. Load references/batch-end-pr.md<br/>(skip entirely when neither a PR-label<br/>run nor an opted-in draft PR)"]:::skill
    n28["28. Step 8.3 · branches_&lt;slug&gt;.md manifest<br/>entry + PR-level status marker<br/>(PR-label runs only)"]:::state
    n29{"29. Draft PR requested?"}
    n29a["29a. Step 8.3 · Dispatch the create-pr agent<br/>(agent-pinned): it composes the body,<br/>pushes the branch AND opens the PR"]:::dispatch
    n29b{"29b. PR opened?"}
    n30["30. Step 8.3 · Print the review package,<br/>THEN the nvim diffview pane<br/>(open-in-tmux); complete the<br/>remaining [Reminder]s"]
    n31["31. Step 8.3 · phase=presented;<br/>DELETE this unit's state file"]:::state
  end

  n32{"32. PR-label run with PRs remaining?"}
  n33["33. Load references/failure-and-halt.md"]:::skill
  n34(["34. Step 5.5 · HALT and wait for the human:<br/>phase=halted; write what each blocker<br/>needs into the scratchpad; leave<br/>remaining [Reminder]s pending;<br/>run NOTHING further"]):::gate
  n35(["35. Invocation ends"])
  n35a["35a. Stop hook: releases only on<br/>phase presented or halted"]:::hook

  n1 --> n2 --> n3
  n3 -->|"no"| n3a
  n3 -->|"yes"| n4 --> n5 --> n6
  n6 -->|"no"| n6a
  n6 -->|"yes"| n7
  n7 -->|"yes"| n7a --> n7b --> n8
  n7 -->|"no"| n8
  n8 -->|"yes"| n8a --> n8b --> n9
  n8 -->|"no"| n9
  n9 --> n10a
  n10d --> n11 --> n12
  n12 -->|"yes"| n12a --> n13
  n12 -->|"no / task-ids run"| n13
  n13 --> n14 --> n15 --> n16
  n16 -.->|"guards"| n16a
  n16 -.->|"writes"| n16c
  n16 -->|"1h timeout"| n16b --> n19a
  n16 --> n17
  n17 -->|"blocked"| n19a
  n17 -->|"done"| n18 --> n19
  n19 -->|"pass"| n20
  n19 -->|"fail"| n19a
  n19a --> n19b --> n19c
  n19c -->|"retry (loads debug-standards)"| n16
  n19c -->|"stuck"| n19d --> n19e
  n19c -->|"halt-budget"| n33
  n19e -->|"yes"| n15
  n19e -->|"no"| n33
  n20 --> n21
  n21 -->|"next-task"| n15
  n21 -->|"gates"| n22
  n21 -->|"halted / halt-budget"| n33
  n22 --> n23
  n23 -->|"yes"| n24 --> n24a
  n23 -->|"no, skipped by request"| n25
  n24a -->|"no"| n24b
  n24b -->|"no"| n33
  n24b -->|"yes"| n24c --> n24
  n24a -->|"yes"| n25
  n25 -->|"yes"| n26 --> n26a --> n26c --> n26d
  n26a -.->|"guards"| n26b
  n26d -->|"yes"| n26e --> n27
  n26d -->|"no"| n27
  n25 -->|"no, skipped by request"| n27
  n27 --> n28 --> n29
  n29 -->|"yes"| n29a --> n29b
  n29b -->|"no"| n33
  n29b -->|"yes"| n30
  n29 -->|"no"| n30
  n30 --> n31 --> n32
  n32 -->|"yes"| n12
  n32 -->|"no"| n35
  n33 --> n34 --> n35
  n35 -.->|"releases"| n35a

  classDef start fill:#fef3c7,stroke:#d97706,stroke-width:2px
  classDef gate fill:#fee2e2,stroke:#dc2626,stroke-width:2px
  classDef dispatch fill:#dbeafe,stroke:#2563eb,stroke-width:2px
  classDef state fill:#dcfce7,stroke:#16a34a,stroke-width:2px
  classDef skill fill:#f3e8ff,stroke:#9333ea,stroke-width:2px
  classDef hook fill:#e5e7eb,stroke:#4b5563,stroke-width:2px
```
