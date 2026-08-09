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
    # A plan with no spec is a supported mode, not a missing input: a plan-only
    # run works unchanged, and the spec is simply passed nowhere.

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
        enter_worktree(symlink=[plan, spec], copy=[".env*"])    # 7b · §1.4

    if arg.is_pr_labels:                                   # 8
        load("references/pr-awareness.md")                 # 8a
        units = [get_pr_tasks(label) for label in arg.labels]   # 8b · §1.5
        # 8c · §1.5 — decide the stack mode ONCE: a PR with 2+ parents
        #      (diamond) → merge; linear AND the gh-stack extension installed
        #      → native; else merge. Recorded as a Mode: line under the plan's
        #      PR Breakdown heading — sticky for the stack's whole life.
        plan.record_stack_mode(decide_stack_mode(units))
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
            # 11a · 1/4 quality-gate tail with --auto-solve (opt-in)
            # 11b · 2/4 repo-green gate, fix-loop until green (opt-in)
            # 11c · 3/4 push the branch; record it on the PR line; PR when wanted
            # 11d · 4/4 package print, closing review notification
            # Never one chain: a combined entry has one completed flag, so a
            # step-level skip would have nowhere to land.

    # 12 · §2.3 — durable state NOW, kept current as the run goes.
    for unit in units:
        write_json(f"/tmp/implement_{session_id}{unit.suffix}.json",
                   phase="tasks", start_sha=head(), batch_base_sha="")
    write_scratchpad(f"/tmp/implement_{session_id}.md")
    # NO resume path — a leftover state file is stale: delete it and start over.

    # 36 · a task-ids run has one unit; a PR-label run repeats §3–§8 per PR, in order.
    for unit in units:
        run_unit(unit)

    return  # 39 · invocation ends
            # 39a · Stop hook releases only on
            #       phase "presented" or "halted"


def run_unit(unit):
    if unit.is_pr and need_git_checkout(plan, unit.label):  # 13
        load("references/pr-branch-creation.md")            # 13a
        create_branch(unit)   # 13b · §3.1 — ONCE, here. Never mid-loop, never a subagent.

    state.batch_base_sha = head()                          # 14 · §3.2
    recap(git_log(base_branch, "HEAD"), read="COMMIT MESSAGES, not the diff")

    tasks = exact_match(unit.task_ids, plan.headings)      # 15 · §3.3
    # A prefix matching two headings means a malformed plan, not a question — stop.

    # `while True`, never "while something is pending": an empty-looking queue is
    # NOT the gates. It empties two ways, and only 23's verdict can tell them apart.
    while True:
        # 16 · §5.4 — ask --eligible-set, NEVER the plain verdict, while anything
        #      is in flight: the plain one assumes nothing is, so mid-wave it
        #      answers "halted" and stops the run to wait for a human.
        wave = eligible_set(state_file)

        if len(wave) > 1:
            wave = run_parallel_wave(wave)                 # 16a–16h; may fall back to one
        if len(wave) == 1:
            run_one_task(wave.first)                       # 17–22

        # 23 · ONLY this script sends a unit to the gates. Never infer "gates"
        #      from an empty-looking queue — it empties two ways.
        v = implement_loop_state(state_file)
        if v == "next-task":
            continue                                       # back to 16
        elif v == "gates":
            break                                          # every task in the unit is done
        else:                                              # "halted" | "halt-budget"
            halt()

    # ---- 24–28 · §8.1–§8.2 · the two opt-in gates, in that order ----
    load("references/batch-end-review.md")                 # 24

    if answers.quality_gate_tail:                          # 25 · else skipped by request
        # 26 · §8.1 — IN THIS SESSION, never wrapped in a subagent: its legs are
        #     already fresh-context reviewers, and its commits need a permission
        #     prompt only main can render. The spec argument goes in only when
        #     §1.1 resolved one — the skill matches paths by spec_/plan_ prefix.
        run_skill("/quality-gate", spec_if_resolved, plan,
                  tasks=unit.task_ids, base_ref=state.batch_base_sha,
                  auto_solve=True)
        # 26a · inside it: refactor ∥ auto-review ∥ test-sdd legs → three
        #       verdict_*.md, then per-finding apply → commit → mark [Done].
        # 26b · hook: deep-reviewer-write-guard (only verdict_*.md writes approved).
        state.record_verdict_paths()   # 26c · PATHS, never content; every finding
        scout(quality_gate.declined)   #       it declined becomes a [Scout];
        state.phase = "tails"          #       then phase=tails

    if answers.repo_green_gate:                            # 27 · else skipped by request
        while True:
            # 28 · §8.2 — repo-wide, never scoped to the batch's own files. Runs
            #     AFTER the quality gate, so it measures a tree already holding
            #     whatever --auto-solve applied. That ordering is why no "the gate
            #     applied something, so re-run the suite" rule exists.
            if full_lint() and full_test_suite():          # 28a
                break
            # A failure the batch didn't cause is a [Scout], never a blocker.
            if not fix_attempts_left():                    # 28b
                halt()
            dispatch("tdd-coder", failure,                 # 28c · attempt recorded,
                     timeout_ms=3_600_000)                 #       RE-RUN THE FULL SUITE

    # ---- 29–35 · §8.3 · push, PR, package, finalize ----
    # 29 · Finalize step 1 — ALWAYS, on every batch end, whatever pr.wanted says.
    #      A pushed branch with no PR is the ordinary outcome, not a half state.
    if not git_push("-u", "origin", "HEAD"):               # 30 · no remote, a rejected
        halt()                                             #      non-fast-forward, no creds

    # The three batch-end-pr* files load under three separate conditions — each
    # `if` below reads only its own, so no run pays for a branch it skips.
    if unit.is_pr:                                         # 31
        load("references/batch-end-pr-branch-record.md")   # 31a
        # 32 · Finalize step 2, PR-label runs only: the Branch: clause and the
        #      PR-level [Done] marker, both on this PR's own plan line.
        plan.record_branch_clause(unit.label, current_branch())
        plan.mark_pr(unit.label, "[Done]")

    if answers.draft_pr:                                   # 33
        load("references/batch-end-pr.md")                 # 33a
        pr = dispatch("pr-creator", batch_diff)      # 33b · composes the body and
                                                     #       CREATES ONLY — 29 pushed,
                                                     #       so it must never push
        if not pr.opened:                                  # 33c
            halt()
        # Native mode + the run's last PR only: register the chain as a native
        # stack, reusing the already-created PRs. Linking runs LAST so no branch
        # is server-rebased mid-run.
        if plan.stack_mode == "native" and unit.is_last_label:
            load("references/batch-end-pr-native-link.md") # 33d
            if not gh("stack", "link"):                    # 33e · a failed link
                plan.record_stack_mode("merge")            #       downgrades Mode:
                                                           #       to merge, never halts

    print_review_package()          # 34 · Finalize step 3 — the package, closing with
                                    #      the review notification: base SHA + its
                                    #      subject, then one line per unit — label ·
                                    #      branch · commit count · PR URL when one exists
    complete_remaining_reminders()
    state.phase = "presented"                              # 35 · Finalize step 4
    delete(state_file)


def run_one_task(task):
    # 17 · §3.4 — the only orchestrator work between two dispatches: flip the
    #      status, hand over a breadcrumb. No checklist path is assigned.
    task_update(task, "in_progress", breadcrumb=plan.acceptance_titles(task))

    while True:   # retry loop: 21c's "retry" comes back here, not to activation
        # 18 · §4 — agent-pinned, background, 1h Monitor cap. One task, so it
        #      runs in the main tree: a worktree exists only to keep concurrent
        #      siblings off one index, and there are no siblings here.
        report = dispatch("tdd-coder", task, timeout_ms=3_600_000)
        # 18a · hooks: subagent-model-guard + git-guard
        # 18c · THE SUBAGENT owns its RED-GREEN checklist end to end: it derives
        #       the path, writes it, and resumes from it. The orchestrator never
        #       names it, reads it, or gates on it.
        if report.timed_out:
            task_stop(report.agent)                        # 18b · resolves as a timeout
            report.status = "timeout"

        if report.status == "done":                        # 19 · §4.4
            # 20 · §5.1 — the orchestrator's whole part: no dispatch, no re-run,
            #      no checklist. One `git cat-file -e <sha>^{commit}` per SHA
            #      the report named — existence only, never content.
            accepted = all_reported_commits_resolve(report)          # 21
        else:
            accepted = False  # `blocked` and `timeout` take the failure path too

        if accepted:
            return advance(task, report)                   # 22 · §5.4

        load("references/failure-and-halt.md")             # 21a
        state.record_attempt(task, result, signature)      # 21b · §5.2
        v = implement_loop_state(state_file)               # 21c
        if v != "retry":                                   # retry loads debug-standards
            break

    if v == "stuck":                                       # 21d · §5.3
        mark_terminal(task)
        chain_abort_dependents(task, transitive=True)
        plan.mark(task, "[Blocked]")
        task_update(task, "completed")
        if not next_runnable():                            # 21e
            halt()
    elif v in ("halted", "halt-budget"):
        halt()


def advance(task, report):
    state.set(task, status="done")     # 22 · §5.4 — flipped BEFORE the verdict script,
    plan.mark(task, "[Done]")          #      which picks by status: a passed task left
    task_create_scouts(report.scouts)  #      pending gets re-dispatched later.
    task_update(task, "completed")     #      §4.3 — one [Scout] task each.


def run_parallel_wave(wave):
    # Everything a worktree is for lives in the parallel-worktrees skill: the two
    # file predicates, the cap, the branch layout, the in_progress-before-spawn
    # guard, the merge order, the cleanup. Parallelism is still derived from the
    # plan's DAG rather than asked, which is why §1.2's interview never grew a
    # question for it. This function only supplies inputs and judges reports.
    load_skill("parallel-worktrees")                       # 16a

    # 16b · A DAG says ordering, never shared files, so the skill re-filters the
    #       set against each sibling's Files list AND the main tree's uncommitted
    #       paths, then caps at 4. Below 2 there are no concurrent siblings to
    #       keep off one index, so the leftover task falls through to 17 and no
    #       worktree is created at all.
    wave = parallel_worktrees.filter(wave, files_by_task,
                                     base=state.batch_base_sha, slug=slug)
    if len(wave) < 2:
        return wave        # falls back to 17 — no worktree for a single task

    # 16c · The skill writes in_progress + branch + worktree_path into OUR state
    #       file before each spawn. Its ledger is ours by necessity: --eligible-set
    #       is what reads that mark back to skip a task already in flight.
    reports = parallel_worktrees.create_and_dispatch(wave, agent="tdd-coder")

    for r in reports:                                      # 16d · §5.1 per report, as each
        if all_reported_commits_resolve(r):                #       lands — so a failure
            advance(r.task, r)                             #       re-dispatches (into its
        else:                                              #       OWN worktree) while its
            handle_failure(r)   # 21a-21e, unchanged       #       siblings still work

    # 16e · Ascending task-id order, rebase inside each worktree then --ff-only in
    #       the main tree, cleanup per merge. A conflict means a file predicate was
    #       wrong for that pair, and the skill keeps every worktree on the way out
    #       — halt() below is already the no-cleanup path, so nothing extra here.
    if not parallel_worktrees.merge_back(wave):
        halt()
    return []


def halt():
    # RAISES, never returns: every call site above is terminal at whatever depth
    # it sits, and a returned halt would be discarded by run_one_task's caller
    # and misread as the next `wave` by run_parallel_wave's.
    load("references/failure-and-halt.md")                 # 37
    set_halted_phase_on_all_units()                        # 38 · §5.5
    scratchpad.write(what_each_blocker_needs)
    leave_pending(remaining_reminders)
    # Cleanup stops entirely on the way out: an unmerged branch holds work only
    # a human can resolve, so every worktree stays and the halt names each one.
    raise Halted    # run NOTHING further; wait for the human
```

## Flowchart

```mermaid
flowchart TD
  n1(["1. /implement &lt;task-ids&gt; | &lt;PR-label(s)&gt;<br/><br/>or natural language ('let's implement that')<br/>when plan_&lt;slug&gt;.md exists"]):::start
  n2["2. Step 1.1 · Locate plan_&lt;slug&gt;.md (+ the spec when one<br/>exists — a plan-only run is a supported mode)"]
  n3{"3. Plan found?"}
  n3a(["3a. Stop: no plan given"])
  n4["4. Step 1.2 · ONE up-front interview —<br/>the only round until the<br/>review package:<br/><br/>- Plan pick, if multiple candidates<br/>- Plan path, if none found (§1.1)<br/>- Run in a git worktree?<br/>- Open a draft PR at batch end?<br/>- Quality-gate tail? (default yes)<br/>- Capture a full-suite green baseline first?<br/>- Repo-green gate? (default yes)<br/>- Confirm the base branch"]:::gate
  n5["5. Step 1.3 · Re-validate BOTH graphs ONCE,<br/>before any execution:<br/>check-tasks-dag.sh + check-pr-dag.sh"]:::hook
  n6{"6. Both graphs valid?"}
  n6a(["6a. Stop: surface the script's stderr;<br/>fix the plan, re-invoke"])
  n7{"7. Worktree requested?"}
  n7a["7a. Load references/worktree-setup.md"]:::skill
  n7b["7b. Step 1.4 · EnterWorktree + symlink<br/>the plan and its spec, copy .env*"]
  n8{"8. Arg is PR-label(s)?"}
  n8a["8a. Load references/pr-awareness.md"]:::skill
  n8b["8b. Step 1.5 · Resolve EVERY PR-N to its<br/>task-id list (get-pr-tasks.sh),<br/>before any seeding"]
  n8c["8c. Step 1.5 · Decide the stack mode ONCE:<br/>diamond (a PR with 2+ parents) -&gt; merge;<br/>linear AND gh-stack extension installed -&gt; native;<br/>else merge. Record a Mode: line under the plan's<br/>PR Breakdown heading — sticky for the stack's life"]:::state
  n9{"9. Full-suite baseline requested?"}
  n9a["9a. Load references/full-suite-baseline.md"]:::skill
  n9b["9b. Step 1.6 · Capture the baseline: full lint +<br/>full test suite, once worktree (7b) and<br/>PR-label resolution (8b) have settled;<br/>save the log PATH + failing signatures into<br/>state.baseline (never the log content)"]:::state
  n10["10. Step 2.1 · TaskList: one entry per task,<br/>ALL PRs upfront in execution order<br/>(subjects prefixed 'PR-2 &middot;');<br/>1st in_progress, rest pending;<br/>status only"]:::state

  subgraph seedRemind["11. Step 2.2 · After each PR's task entries, seed that batch's 4 batch-end [Reminder]s — separate entries, never one chain:<br/>a combined entry has one completed flag, so a step-level skip would have nowhere to land."]
    direction TB
    n11a["11a. Add to TaskList a [Reminder] for<br/>Batch-end 1/4: quality-gate tail with --auto-solve<br/>(only when opted in)"]:::state
    n11b["11b. Add to TaskList a [Reminder] for<br/>Batch-end 2/4: repo-green gate, fix-loop until green<br/>(only when opted in)"]:::state
    n11c["11c. Add to TaskList a [Reminder] for<br/>Batch-end 3/4: push the branch; record it on the<br/>PR line; open the PR via pr-creator when wanted"]:::state
    n11d["11d. Add to TaskList a [Reminder] for<br/>Batch-end 4/4: package print,<br/>closing review notification"]:::state
    n11a --> n11b --> n11c --> n11d
  end

  n12["12. Step 2.3 · Write durable state NOW,<br/>kept current as the run goes:<br/>one /tmp/implement_&lt;session_id&gt;[_prN].json<br/>per unit (phase=tasks, start_sha=HEAD)<br/>+ /tmp/implement_&lt;session_id&gt;.md scratchpad.<br/>NO resume path — a leftover file is stale"]:::state

  subgraph perunit ["Per unit: the whole batch (task-ids run), or each PR in turn (PR-label list)"]
    n13{"13. PR-label run: checkout needed?<br/>(need-git-checkout.sh)"}:::hook
    n13a["13a. Load references/pr-branch-creation.md"]:::skill
    n13b["13b. Step 3.1 · Orchestrator creates this<br/>PR's branch — ONCE, here; never<br/>mid-loop, never by a subagent"]
    n14["14. Step 3.2 · Capture BATCH_BASE_SHA into<br/>the state file; recap the base from<br/>COMMIT MESSAGES, not the diff"]:::state
    n15["15. Step 3.3 · Exact-match this unit's task-ids<br/>(a collision means a malformed plan)"]
    n16{"16. Step 5.4 · How many tasks are eligible right now?<br/>(implement-loop-state.sh --eligible-set — NEVER the plain<br/>verdict while anything is in flight: the plain one assumes<br/>nothing is, so mid-wave it answers 'halted' and stops the<br/>run to wait for a human)"}:::hook
    n16a["16a. Load the parallel-worktrees skill, handing it the eligible<br/>ids, each task's Files list, batch_base_sha and the plan slug.<br/>Every worktree, branch, dispatch and merge below is its flow,<br/>authored in its own file: this run supplies those four inputs<br/>and judges the reports, and owns nothing else in the wave"]:::skill
    n16b{"16b. After its own two file predicates and its cap of 4,<br/>does the set still hold 2 or more? (a DAG says ordering,<br/>never shared files, so undeclared-independent tasks can<br/>still collide — and 1 task needs no worktree at all)"}
    n16c["16c. It opens one worktree + branch per task and dispatches<br/>one tdd-coder into each (agent-pinned, background, ∥),<br/>marking every task in_progress in THIS state file first —<br/>its ledger is ours, because --eligible-set is what reads<br/>that mark back to skip a task already in flight"]:::dispatch
    n16d["16d. Step 5.1 · Accept each report as it lands, so a failure<br/>re-dispatches — into its OWN worktree — while its siblings<br/>still work. A failure or block is that task's alone"]
    n16e["16e. Once every task is accepted it merges each branch back<br/>in ascending task-id order and removes that worktree per<br/>merge, leaving history identical to a sequential run's"]:::state
    n17["17. Step 3.4 · Activate a task: TaskUpdate<br/>in_progress + breadcrumb.<br/>NO checklist path is assigned"]:::state
    n18["18. Step 4 · Dispatch tdd-coder (agent-pinned,<br/>background, 1h Monitor cap). One task, so it runs<br/>in the main tree: a worktree exists only to keep<br/>concurrent siblings off one index, and there are none"]:::dispatch
    n18a["18a. Hooks: subagent-model-guard + git-guard"]:::hook
    n18b["18b. 1h Monitor expires: TaskStop the<br/>subagent (resolves as timeout)"]:::hook
    n18c["18c. THE SUBAGENT owns its RED-GREEN checklist<br/>end to end: it derives the path, writes it,<br/>and resumes from it. The orchestrator never<br/>names it, reads it, or gates on it"]:::state
    n19{"19. Step 4.4 · Subagent report status?"}
    n20["20. Step 5.1 · Accept the result: the orchestrator<br/>dispatches no reviewer, re-runs nothing and reads no<br/>checklist — its whole part is one<br/>git cat-file -e &lt;sha&gt;^{commit} per reported SHA"]
    n21{"21. Every reported commit resolves?<br/>(a 'done' reporting none fails too;<br/>existence only, never content)"}
    n21a["21a. Load references/failure-and-halt.md"]:::skill
    n21b["21b. Step 5.2 · Record the attempt<br/>(fail/timeout/blocked + signature)<br/>into the state file"]:::state
    n21c{"21c. Step 5.2 · implement-loop-state.sh:<br/>verdict?"}:::hook
    n21d["21d. Step 5.3 · Mark the task terminal;<br/>chain-abort dependents transitively;<br/>plan [Blocked]; TaskUpdate completed"]:::state
    n21e{"21e. Step 5.3 · Any runnable task left?"}
    n22["22. Step 5.4 · Advance: state file status=done<br/>(flipped BEFORE the verdict script, which picks by<br/>status — a passed task left pending is re-dispatched);<br/>plan [Done]; TaskCreate [Scout] items; TaskUpdate completed"]:::state
    n23{"23. Step 5.4 · implement-loop-state.sh: verdict?<br/>ONLY this script sends a unit to the gates"}:::hook
    n24["24. Load references/batch-end-review.md"]:::skill
    n25{"25. Quality-gate tail requested?"}
    n26["26. Step 8.1 · Invoke /quality-gate [&lt;spec&gt;] &lt;plan&gt;<br/>--tasks &lt;this unit's ids&gt; --auto-solve,<br/>base ref = BATCH_BASE_SHA. The spec argument goes in<br/>only when §1.1 resolved one.<br/>IN THIS SESSION, never wrapped in a subagent:<br/>its legs are already fresh-context reviewers, and<br/>its commits need a prompt only main can render"]:::skill
    n26a["26a. Inside it: refactor ∥ auto-review ∥ test-sdd legs<br/>→ three verdict_*.md, then per-finding<br/>apply → commit → mark [Done]"]:::dispatch
    n26b["26b. Hook: deep-reviewer-write-guard<br/>(only verdict_*.md writes are approved)"]:::hook
    n26c["26c. Record each verdict PATH into the state file<br/>(never its content); every finding it declined<br/>becomes a [Scout]; then phase=tails"]:::state
    n27{"27. Repo-green gate requested?"}
    n28["28. Step 8.2 · Repo-green GATE: full lint + full test<br/>suite, repo-wide, never scoped to the batch's own<br/>files. Runs AFTER the quality gate, so it measures a<br/>tree already holding whatever --auto-solve applied —<br/>which is why no 'it applied something,<br/>so re-run the suite' rule exists"]:::gate
    n28a{"28a. Green? (a failure the batch didn't<br/>cause is a [Scout], never a blocker)"}
    n28b{"28b. Fix attempts left?"}
    n28c["28c. Step 8.2 · Dispatch tdd-coder to fix it<br/>(agent-pinned, 1h Monitor cap, attempt<br/>recorded); RE-RUN THE FULL SUITE"]:::dispatch
    n29["29. Step 8.3 · Finalize step 1 · git push -u origin HEAD<br/>— ALWAYS, on every batch end, whatever pr.wanted<br/>says. A pushed branch with no PR is the ordinary<br/>outcome, not a half-finished state"]:::gate
    n30{"30. Push succeeded?<br/>(no remote / rejected non-fast-forward /<br/>missing credentials)"}
    n31{"31. PR-label run?"}
    n31a["31a. Load references/batch-end-pr-branch-record.md"]:::skill
    n32["32. Step 8.3 · Finalize step 2 · Record the Branch:<br/>clause + the PR-level [Done] marker on this PR's<br/>own plan line (PR-label runs only)"]:::state
    n33{"33. Draft PR requested?"}
    n33a["33a. Load references/batch-end-pr.md"]:::skill
    n33b["33b. Step 8.3 · Dispatch the pr-creator agent<br/>(agent-pinned): it composes the body and CREATES<br/>the PR ONLY — step 29 already pushed,<br/>so it must never push or force-push"]:::dispatch
    n33c{"33c. PR opened or updated?"}
    n33d["33d. Native mode + the run's LAST PR only (skipped<br/>otherwise): load references/batch-end-pr-native-link.md"]:::skill
    n33e["33e. gh stack link registers the chain as a native stack,<br/>reusing the already-created PRs. Linking runs LAST so no<br/>branch is server-rebased mid-run; a failed link downgrades<br/>the plan's Mode: to merge and continues — never a halt"]
    n34["34. Step 8.3 · Finalize step 3 · Print the review<br/>package, closing with the review notification:<br/>base SHA + its subject, then one line per unit —<br/>label · branch · commit count · PR URL when one<br/>exists; complete the remaining [Reminder]s"]
    n35["35. Step 8.3 · Finalize step 4 · phase=presented;<br/>DELETE this unit's state file"]:::state
  end

  n36{"36. PR-label run with PRs remaining?"}
  n37["37. Load references/failure-and-halt.md"]:::skill
  n38(["38. Step 5.5 · HALT and wait for the human:<br/>phase=halted on all units; write what each blocker<br/>needs into the scratchpad; leave remaining<br/>[Reminder]s pending. Cleanup stops entirely here —<br/>an unmerged branch holds work only a human can<br/>resolve, so every worktree stays and the halt names<br/>each one; run NOTHING further"]):::gate
  n39(["39. Invocation ends"])
  n39a["39a. Stop hook: releases only on<br/>phase presented or halted"]:::hook

  n1 --> n2 --> n3
  n3 -->|"no"| n3a
  n3 -->|"yes"| n4 --> n5 --> n6
  n6 -->|"no"| n6a
  n6 -->|"yes"| n7
  n7 -->|"yes"| n7a --> n7b --> n8
  n7 -->|"no"| n8
  n8 -->|"yes"| n8a --> n8b --> n8c --> n9
  n8 -->|"no"| n9
  n9 -->|"yes"| n9a --> n9b --> n10
  n9 -->|"no"| n10
  n10 --> n11a
  n11d --> n12 --> n13
  n13 -->|"yes"| n13a --> n13b --> n14
  n13 -->|"no / task-ids run"| n14
  n14 --> n15 --> n16
  n16 -->|"2 or more"| n16a --> n16b
  n16b -->|"no — filtered down to 1"| n17
  n16b -->|"yes"| n16c --> n16d --> n16e --> n22
  n16d -->|"a task fails, blocks or times out"| n21a
  n16e -->|"it hits a rebase conflict and halts: the<br/>file-disjointness predicate was wrong for<br/>that pair, so it keeps every worktree"| n37
  n16 -->|"1 (or a run with no independent tasks)"| n17 --> n18
  n18 -.->|"guards"| n18a
  n18 -.->|"owns"| n18c
  n18 -->|"1h timeout"| n18b --> n21a
  n18 --> n19
  n19 -->|"blocked"| n21a
  n19 -->|"done"| n20 --> n21
  n21 -->|"yes"| n22
  n21 -->|"no"| n21a
  n21a --> n21b --> n21c
  n21c -->|"retry (loads debug-standards)"| n18
  n21c -->|"stuck"| n21d --> n21e
  n21c -->|"halt-budget"| n37
  n21e -->|"yes"| n16
  n21e -->|"no"| n37
  n22 --> n23
  n23 -->|"next-task"| n16
  n23 -->|"gates"| n24
  n23 -->|"halted / halt-budget"| n37
  n24 --> n25
  n25 -->|"yes"| n26 --> n26a --> n26c --> n27
  n26a -.->|"guards"| n26b
  n25 -->|"no, skipped by request"| n27
  n27 -->|"yes"| n28 --> n28a
  n28a -->|"no"| n28b
  n28b -->|"no"| n37
  n28b -->|"yes"| n28c --> n28
  n28a -->|"yes"| n29
  n27 -->|"no, skipped by request"| n29
  n29 --> n30
  n30 -->|"no"| n37
  n30 -->|"yes"| n31
  n31 -->|"yes"| n31a --> n32 --> n33
  n31 -->|"no / task-ids run"| n33
  n33 -->|"yes"| n33a --> n33b --> n33c
  n33c -->|"no"| n37
  n33c -->|"yes"| n33d --> n33e --> n34
  n33 -->|"no"| n34
  n34 --> n35 --> n36
  n36 -->|"yes"| n13
  n36 -->|"no"| n39
  n37 --> n38 --> n39
  n39 -.->|"releases"| n39a

  classDef start fill:#fef3c7,stroke:#d97706,stroke-width:2px
  classDef gate fill:#fee2e2,stroke:#dc2626,stroke-width:2px
  classDef dispatch fill:#dbeafe,stroke:#2563eb,stroke-width:2px
  classDef state fill:#dcfce7,stroke:#16a34a,stroke-width:2px
  classDef skill fill:#f3e8ff,stroke:#9333ea,stroke-width:2px
  classDef hook fill:#e5e7eb,stroke:#4b5563,stroke-width:2px
```
