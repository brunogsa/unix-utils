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
    if not plan:                                            # 3
        return stop("no plan given")                       # 3a

    # 4 · §1.2 — ONE up-front interview, the only round until the review package:
    #     plan pick · plan path, if none found (§1.1) · worktree · draft PR
    #     · quality-gate tail (default yes) · full-suite green baseline
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

    # 9 · §1.6 — capture a full-suite green baseline, only when §1.2 said yes;
    #     runs once worktree (7b) and PR-label resolution (8b) have settled.
    if answers.baseline:                                   # 9
        load("references/full-suite-baseline.md")          # 9a
        state.baseline = capture_full_suite_baseline()      # 9b · full lint + full test
                                                             #      suite; log PATH + failing
                                                             #      signatures only, never content

    # 10 · §2.1 + 11 · §2.2 — seed the WHOLE run upfront, in execution order:
    #     ALL PRs, each PR's tasks before its own batch-end reminders.
    for unit in units:
        for task in unit.tasks:
            task_create(f"{unit.label} · {task.id}. {task.title}",
                        status="in_progress" if is_first_of_run(task) else "pending")
            # TaskList carries status ONLY — attempts, gates and SHAs live in the JSON.
        for step in BATCH_END_STEPS:      # FOUR separate entries:
            task_create(f"[Reminder] {step}")
            # 11a · 1/4 repo-green gate, fix-loop until green
            # 11b · 2/4 quality-gate tail with --auto-solve
            # 11c · 3/4 push + open the PR via create-pr
            # 11d · 4/4 package print, diffview pane
            # Never one chain: a combined entry has one completed flag, so a
            # step-level skip would have nowhere to land.

    # 12 · §2.3 — durable state NOW, kept current as the run goes.
    for unit in units:
        write_json(f"/tmp/implement_{session_id}{unit.suffix}.json",
                   phase="tasks", start_sha=head(), batch_base_sha="")
    write_scratchpad(f"/tmp/implement_{session_id}.md")
    # NO resume path — a leftover state file is stale: delete it and start over.

    # 33 · a task-ids run has one unit; a PR-label run repeats §3–§8 per PR, in order.
    for unit in units:
        run_unit(unit)

    return  # 36 · invocation ends
            # 36a · Stop hook releases only on
            #       phase "presented" or "halted"


def run_unit(unit):
    if unit.is_pr and need_git_checkout(plan, unit.label, worktree):    # 13
        load("references/pr-branch-creation.md")            # 13a
        create_branch(unit)   # 13b · §3.1 — ONCE, here. Never mid-loop, never a subagent.

    state.batch_base_sha = head()                          # 14 · §3.2
    recap(git_log(base_branch, "HEAD"), read="COMMIT MESSAGES, not the diff")

    tasks = exact_match(unit.task_ids, plan.headings)      # 15 · §3.3
    # A prefix matching two headings means a malformed plan, not a question — stop.

    task = tasks.first
    while task:
        # 16 · §3.4 — the only orchestrator work between two dispatches.
        task_update(task, "in_progress", breadcrumb=plan.acceptance_titles(task))
        checklist = f"/tmp/implement_substeps_{slug}_{task.id}.md"

        while True:   # retry loop: 20c's "retry" comes back here, not to activation
            # 17 · §4 — agent-pinned, background, SERIAL across tasks, 1h Monitor cap.
            report = dispatch("tdd-coder", task, checklist, timeout_ms=3_600_000)
            # 17a · hooks: subagent-model-guard + git-guard
            # 17c · THE SUBAGENT writes its own RED-GREEN checklist + evidence;
            #       the orchestrator only checks that the file exists.
            if report.timed_out:
                task_stop(report.agent)                    # 17b · resolves as a timeout
                report.status = "timeout"

            if report.status == "done":                    # 18 · §4.4
                # 19 · §5.1 — the orchestrator's whole part: no dispatch, no re-run.
                accepted = exists(checklist)               # 20 · file present?
            else:
                accepted = False  # `blocked` and `timeout` take the failure path too

            if accepted:
                state.set(task, status="done")             # 21 · §5.4 — before the script
                plan.mark(task, "[Done]")
                record_scout_notes(report.scouts)
                task_update(task, "completed")
            else:
                load("references/failure-and-halt.md")     # 20a
                state.record_attempt(task, result, signature)    # 20b · §5.2

            # 20c / 22 · ONLY this script sends a unit to the gates. Never infer
            #            "gates" from an empty-looking queue — it empties two ways.
            v = implement_loop_state(state_file)
            if v != "retry":                               # retry loads debug-standards
                break

        if v == "stuck":                                   # 20d · §5.3
            mark_terminal(task)
            chain_abort_dependents(task, transitive=True)
            plan.mark(task, "[Blocked]")
            task_update(task, "completed")
            task = next_runnable()                         # 20e
            if not task:
                return halt()
        elif v == "next-task":
            task = v.task                                  # back to 16
        elif v == "gates":
            break                                          # every task in the unit is done
        else:                                              # "halted" | "halt-budget"
            return halt()

    # ---- 23–27 · §8 · batch-end gates ----
    load("references/batch-end-review.md")                 # 23

    if answers.repo_green_gate:                            # 24 · else skipped by request
        while True:
            # 25 · §8.1 — repo-wide, never scoped to the batch's own files.
            if full_lint() and full_test_suite():          # 25a
                break
            # A failure the batch didn't cause is a [Scout], never a blocker.
            if not fix_attempts_left():                    # 25b
                return halt()
            dispatch("tdd-coder", failure,                 # 25c · attempt recorded,
                     timeout_ms=3_600_000)                 #       RE-RUN THE FULL SUITE

    if answers.quality_gate_tail:                          # 26 · else skipped by request
        # 27 · §8.2 — IN THIS SESSION, never wrapped in a subagent: its legs are
        #     already fresh-context reviewers, and its commits need a permission
        #     prompt only main can render.
        run_skill("/quality-gate", tasks=unit.task_ids,
                  base_ref=state.batch_base_sha, auto_solve=True)
        # 27a · inside it: refactor ∥ auto-review ∥ test-sdd legs → three
        #       verdict_*.md, then per-finding apply → commit → mark [Done].
        # 27b · hook: deep-reviewer-write-guard (only verdict_*.md writes approved).
        state.record_verdict_paths()   # 27c · PATHS, never content; every finding
        scout(quality_gate.declined)   #       it declined becomes a [Scout]
        if quality_gate.applied_anything:                  # 27d
            full_test_suite(); full_lint()   # 27e · a fix nobody re-ran is a claim,
                                             #       not a green repo

    # ---- 28–32 · §8.3 · PR + package ----
    load("references/batch-end-pr.md")   # 28 · skipped entirely when this is neither a
                                         #      PR-label run nor an opted-in draft PR
    write_manifest_entry(branches_file)  # 29 · + PR-level status marker, PR-label only
    if answers.draft_pr:                                   # 30
        pr = dispatch("create-pr", batch_diff)   # 30a · composes the body, pushes the
                                                 #       branch AND opens the PR
        if not pr.opened:                                  # 30b
            return halt()

    print_review_package()               # 31 · package FIRST, then the pane
    open_in_tmux("nvim diffview")
    complete_remaining_reminders()
    state.phase = "presented"                              # 32
    delete(state_file)


def halt():
    load("references/failure-and-halt.md")                 # 34
    set_halted_phase_on_all_units()                        # 35 · §5.5
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
  n4["4. Step 1.2 · ONE up-front interview —<br/>the only round until the<br/>review package:<br/><br/>- Plan pick, if multiple candidates<br/>- Plan path, if none found (§1.1)<br/>- Run in a git worktree?<br/>- Open a draft PR at batch end?<br/>- Quality-gate tail? (default yes)<br/>- Capture a full-suite green baseline first?<br/>- Repo-green gate? (default yes)<br/>- Confirm the base branch"]:::gate
  n5["5. Step 1.3 · Re-validate BOTH graphs ONCE,<br/>before any execution:<br/>check-tasks-dag.sh + check-pr-dag.sh"]:::hook
  n6{"6. Both graphs valid?"}
  n6a(["6a. Stop: surface the script's stderr;<br/>fix the plan, re-invoke"])
  n7{"7. Worktree requested?"}
  n7a["7a. Load references/worktree-setup.md"]:::skill
  n7b["7b. Step 1.4 · EnterWorktree + symlink<br/>plan/spec/branches files,<br/>copy .env*"]
  n8{"8. Arg is PR-label(s)?"}
  n8a["8a. Load references/pr-awareness.md"]:::skill
  n8b["8b. Step 1.5 · Resolve EVERY PR-N to its<br/>task-id list (get-pr-tasks.sh),<br/>before any seeding"]
  n9{"9. Full-suite baseline requested?"}
  n9a["9a. Load references/full-suite-baseline.md"]:::skill
  n9b["9b. Step 1.6 · Capture the baseline: full lint +<br/>full test suite, once worktree (7b) and<br/>PR-label resolution (8b) have settled;<br/>save the log PATH + failing signatures into<br/>state.baseline (never the log content)"]:::state
  n10["10. Step 2.1 · TaskList: one entry per task,<br/>ALL PRs upfront in execution order<br/>(subjects prefixed 'PR-2 &middot;');<br/>1st in_progress, rest pending;<br/>status only"]:::state

  subgraph seedRemind["11. Step 2.2 · After each PR's task entries, seed that batch's 4 batch-end [Reminder]s — separate entries, never one chain:<br/>a combined entry has one completed flag, so a step-level skip would have nowhere to land."]
    direction TB
    n11a["11a. Add to TaskList a [Reminder] for<br/>Batch-end 1/4: repo-green gate, fix-loop until green"]:::state
    n11b["11b. Add to TaskList a [Reminder] for<br/>Batch-end 2/4: quality-gate tail with --auto-solve"]:::state
    n11c["11c. Add to TaskList a [Reminder] for<br/>Batch-end 3/4: push + open the PR via create-pr"]:::state
    n11d["11d. Add to TaskList a [Reminder] for<br/>Batch-end 4/4: package print, diffview pane"]:::state
    n11a --> n11b --> n11c --> n11d
  end

  n12["12. Step 2.3 · Write durable state NOW,<br/>kept current as the run goes:<br/>one /tmp/implement_&lt;session_id&gt;[_prN].json<br/>per unit (phase=tasks, start_sha=HEAD)<br/>+ /tmp/implement_&lt;session_id&gt;.md scratchpad.<br/>NO resume path — a leftover file is stale"]:::state

  subgraph perunit ["Per unit: the whole batch (task-ids run), or each PR in turn (PR-label list)"]
    n13{"13. PR-label run: checkout needed?<br/>(need-git-checkout.sh)"}:::hook
    n13a["13a. Load references/pr-branch-creation.md"]:::skill
    n13b["13b. Step 3.1 · Orchestrator creates this<br/>PR's branch — ONCE, here; never<br/>mid-loop, never by a subagent"]
    n14["14. Step 3.2 · Capture BATCH_BASE_SHA into<br/>the state file; recap the base from<br/>COMMIT MESSAGES, not the diff"]:::state
    n15["15. Step 3.3 · Exact-match this unit's task-ids<br/>(a collision means a malformed plan)"]
    n16["16. Step 3.4 · Activate a task: TaskUpdate<br/>in_progress + breadcrumb;<br/>assign the checklist path"]:::state
    n17["17. Step 4 · Dispatch tdd-coder<br/>(agent-pinned, background,<br/>SERIAL across tasks, 1h Monitor cap)"]:::dispatch
    n17a["17a. Hooks: subagent-model-guard + git-guard"]:::hook
    n17b["17b. 1h Monitor expires: TaskStop the<br/>subagent (resolves as timeout)"]:::hook
    n17c["17c. THE SUBAGENT writes its own RED-GREEN<br/>checklist + evidence:<br/>/tmp/implement_substeps_&lt;slug&gt;_&lt;id&gt;.md<br/>(the orchestrator only checks it exists)"]:::state
    n18{"18. Step 4.4 · Subagent report status?"}
    n19["19. Step 5.1 · Accept the result: the orchestrator<br/>dispatches no reviewer and re-runs nothing —<br/>its whole part is one existence check"]
    n20{"20. Checklist file present at the assigned path?"}
    n20a["20a. Load references/failure-and-halt.md"]:::skill
    n20b["20b. Step 5.2 · Record the attempt<br/>(fail/timeout/blocked + signature)<br/>into the state file"]:::state
    n20c{"20c. Step 5.2 · implement-loop-state.sh:<br/>verdict?"}:::hook
    n20d["20d. Step 5.3 · Mark the task terminal;<br/>chain-abort dependents transitively;<br/>plan [Blocked]; TaskUpdate completed"]:::state
    n20e{"20e. Step 5.3 · Any runnable task left?"}
    n21["21. Step 5.4 · Advance: state file status=done;<br/>plan [Done]; record [Scout] notes;<br/>TaskUpdate completed"]:::state
    n22{"22. Step 5.4 · implement-loop-state.sh: verdict?<br/>ONLY this script sends a unit to the gates"}:::hook
    n23["23. Load references/batch-end-review.md"]:::skill
    n24{"24. Repo-green gate requested?"}
    n25["25. Step 8.1 · Repo-green GATE: full lint +<br/>full test suite, repo-wide, never<br/>scoped to the batch's own files"]:::gate
    n25a{"25a. Green? (a failure the batch didn't<br/>cause is a [Scout], never a blocker)"}
    n25b{"25b. Fix attempts left?"}
    n25c["25c. Step 8.1 · Dispatch tdd-coder to fix it<br/>(agent-pinned, 1h Monitor cap, attempt<br/>recorded); RE-RUN THE FULL SUITE"]:::dispatch
    n26{"26. Quality-gate tail requested?"}
    n27["27. Step 8.2 · Invoke /quality-gate --tasks &lt;this unit's ids&gt;<br/>--auto-solve, base ref = BATCH_BASE_SHA.<br/>IN THIS SESSION, never wrapped in a subagent:<br/>its legs are already fresh-context reviewers, and<br/>its commits need a prompt only main can render"]:::skill
    n27a["27a. Inside it: refactor ∥ auto-review ∥ test-sdd legs<br/>→ three verdict_*.md, then per-finding<br/>apply → commit → mark [Done]"]:::dispatch
    n27b["27b. Hook: deep-reviewer-write-guard<br/>(only verdict_*.md writes are approved)"]:::hook
    n27c["27c. Record each verdict PATH into the state file<br/>(never its content); every finding it<br/>declined becomes a [Scout]"]:::state
    n27d{"27d. Did it apply anything?"}
    n27e["27e. Re-run §8.1's full suite + lint —<br/>a fix nobody re-ran is a claim,<br/>not a green repo"]:::gate
    n28["28. Load references/batch-end-pr.md<br/>(skip entirely when neither a PR-label<br/>run nor an opted-in draft PR)"]:::skill
    n29["29. Step 8.3 · branches_&lt;slug&gt;.md manifest<br/>entry + PR-level status marker<br/>(PR-label runs only)"]:::state
    n30{"30. Draft PR requested?"}
    n30a["30a. Step 8.3 · Dispatch the create-pr agent<br/>(agent-pinned): it composes the body,<br/>pushes the branch AND opens the PR"]:::dispatch
    n30b{"30b. PR opened?"}
    n31["31. Step 8.3 · Print the review package,<br/>THEN the nvim diffview pane<br/>(open-in-tmux); complete the<br/>remaining [Reminder]s"]
    n32["32. Step 8.3 · phase=presented;<br/>DELETE this unit's state file"]:::state
  end

  n33{"33. PR-label run with PRs remaining?"}
  n34["34. Load references/failure-and-halt.md"]:::skill
  n35(["35. Step 5.5 · HALT and wait for the human:<br/>phase=halted on all units; write what each blocker<br/>needs into the scratchpad; leave<br/>remaining [Reminder]s pending;<br/>run NOTHING further"]):::gate
  n36(["36. Invocation ends"])
  n36a["36a. Stop hook: releases only on<br/>phase presented or halted"]:::hook

  n1 --> n2 --> n3
  n3 -->|"no"| n3a
  n3 -->|"yes"| n4 --> n5 --> n6
  n6 -->|"no"| n6a
  n6 -->|"yes"| n7
  n7 -->|"yes"| n7a --> n7b --> n8
  n7 -->|"no"| n8
  n8 -->|"yes"| n8a --> n8b --> n9
  n8 -->|"no"| n9
  n9 -->|"yes"| n9a --> n9b --> n10
  n9 -->|"no"| n10
  n10 --> n11a
  n11d --> n12 --> n13
  n13 -->|"yes"| n13a --> n13b --> n14
  n13 -->|"no / task-ids run"| n14
  n14 --> n15 --> n16 --> n17
  n17 -.->|"guards"| n17a
  n17 -.->|"writes"| n17c
  n17 -->|"1h timeout"| n17b --> n20a
  n17 --> n18
  n18 -->|"blocked"| n20a
  n18 -->|"done"| n19 --> n20
  n20 -->|"yes"| n21
  n20 -->|"no"| n20a
  n20a --> n20b --> n20c
  n20c -->|"retry (loads debug-standards)"| n17
  n20c -->|"stuck"| n20d --> n20e
  n20c -->|"halt-budget"| n34
  n20e -->|"yes"| n16
  n20e -->|"no"| n34
  n21 --> n22
  n22 -->|"next-task"| n16
  n22 -->|"gates"| n23
  n22 -->|"halted / halt-budget"| n34
  n23 --> n24
  n24 -->|"yes"| n25 --> n25a
  n24 -->|"no, skipped by request"| n26
  n25a -->|"no"| n25b
  n25b -->|"no"| n34
  n25b -->|"yes"| n25c --> n25
  n25a -->|"yes"| n26
  n26 -->|"yes"| n27 --> n27a --> n27c --> n27d
  n27a -.->|"guards"| n27b
  n27d -->|"yes"| n27e --> n28
  n27d -->|"no"| n28
  n26 -->|"no, skipped by request"| n28
  n28 --> n29 --> n30
  n30 -->|"yes"| n30a --> n30b
  n30b -->|"no"| n34
  n30b -->|"yes"| n31
  n30 -->|"no"| n31
  n31 --> n32 --> n33
  n33 -->|"yes"| n13
  n33 -->|"no"| n36
  n34 --> n35 --> n36
  n36 -.->|"releases"| n36a

  classDef start fill:#fef3c7,stroke:#d97706,stroke-width:2px
  classDef gate fill:#fee2e2,stroke:#dc2626,stroke-width:2px
  classDef dispatch fill:#dbeafe,stroke:#2563eb,stroke-width:2px
  classDef state fill:#dcfce7,stroke:#16a34a,stroke-width:2px
  classDef skill fill:#f3e8ff,stroke:#9333ea,stroke-width:2px
  classDef hook fill:#e5e7eb,stroke:#4b5563,stroke-width:2px
```
