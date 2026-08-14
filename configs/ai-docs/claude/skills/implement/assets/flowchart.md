---
# performance-check budget overrides, not part of the diagram itself.
# This file's size is fixed by the number of steps the skill actually has, and
# it renders each step twice — once as pseudo-code, once as a diagram node — so
# trimming to the bundled defaults would drop steps from the flow audit or drop
# a whole rendering. Two renderings is the point: they cross-check each other.
# Parked in assets/ and never loaded by the model, so its words cost no context.
words-budget: 8192
lines-budget: 1024
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
    #     · quality-gate tail (default yes, always --report-only) · repo-green
    #     gate (default yes, runs BOTH the full-suite baseline AND the
    #     batch-end gate, or neither) · confirm base branch
    #     · PLUS 'Deliver each task as its own stacked PR?' — default NO.
    answers = ask_everything_at_once()                      # 4

    # 5-9 · §1.2 — stacked delivery (one PR per task, layered) is OPT-IN: it
    #      turns the whole unit strictly sequential, so only a run that asked
    #      for the stack pays that. On the default 'no' nothing below runs and
    #      the reference is never loaded.
    if not answers.stacked:                                 # 5
        stack_choice = not_stacked()                        # 5a · the unit ships as
                                                              #      ONE PR, its tasks
                                                              #      commits inside it
    else:
        load("references/stacked-by-task.md")               # 6 · only on a 'yes'
        if not gh("stack", "--help"):                       # 7 · exits non-zero:
            stack_choice = forced_non_stacked(              # 7a   extension missing
                reason="gh-stack extension not installed")
        else:
            verdict = run("resolve-task-order.sh", plan, arg.task_ids)   # 8
            if verdict.exit_code == 1:
                stack_choice = forced_non_stacked(          # 8a · a task has 2+
                    reason=verdict.stderr)                  #      in-scope parents
                                                              #      (a true join);
                                                              #      surfaced verbatim
            elif verdict.exit_code == 2:
                return stop(verdict.stderr)                 # 8b · usage/parse error,
                                                              #      same as any other
                                                              #      pre-flight failure
            else:
                stack_choice = stacked(layer_order=verdict.stdout)

        # 9 · §1.2 — a SECOND AskUserQuestion call, still before any dispatch:
        #     confirm or reorder the topological layer order (ties lowest-id-
        #     first; only another DAG-valid order is accepted), or — when 7a/8a
        #     fired — confirm the forced non-stacked run, naming which gate did
        #     it. Neither gate is overridable by the 'yes' already given.
        stack_choice = confirm_in_follow_up_call(stack_choice)   # 9

    # 10 · §1.3 — re-validate ALL THREE checks ONCE, before any execution.
    if not (check_tasks_dag(plan) and check_pr_dag(plan)     # 11
            and check_pr_task_projection(plan)):
        return stop(script_stderr_verbatim)                 # 11a · fix the plan, re-invoke

    if answers.worktree:                                    # 12
        load("references/worktree-setup.md")                # 12a
        enter_worktree(symlink=[plan, spec], copy=[".env*"])    # 12b · §1.4

    if arg.is_pr_labels:                                    # 13
        load("references/pr-awareness.md")                  # 13a
        units = [get_pr_tasks(label) for label in arg.labels]   # 13b · §1.5
        # 13c · §1.5 — decide the CROSS-UNIT stack mode ONCE: a PR with 2+ parents
        #      (diamond) → merge; linear AND the gh-stack extension installed
        #      → native; else merge. Independent of 5-9's per-task stack_choice,
        #      which decides delivery WITHIN one unit, not chaining BETWEEN units.
        #      Recorded as a Mode: line under the plan's PR Breakdown heading.
        plan.record_stack_mode(decide_cross_unit_stack_mode(units))
    else:
        units = [Unit(arg.task_ids)]                        # the whole batch is one unit

    # 14 · §1.6 — capture a full-suite green baseline, only when §1.2's
    #     repo-green gate toggle said yes; runs once worktree (12b) and
    #     PR-label resolution (13b) have settled.
    if answers.repo_green_gate:                             # 14
        load("references/full-suite-baseline.md")           # 14a
        state.baseline = capture_full_suite_baseline()       # 14b · full lint + full test
                                                              #      suite; log PATH + failing
                                                              #      signatures only, never content

    # 15 · §2.1 + 16 · §2.2 — seed the WHOLE run upfront, in execution order:
    #     ALL PRs, each PR's tasks before its own batch-end reminders.
    for unit in units:
        for task in unit.tasks:
            task_create(f"{unit.label} · {task.id}. {task.title}",
                        status="in_progress" if is_first_of_run(task) else "pending")
            # TaskList carries status ONLY — attempts, gates and SHAs live in the JSON.
        for step in BATCH_END_STEPS:      # FOUR separate entries:
            task_create(f"[Reminder] {step}")
            # 16a · 1/4 push the branch(es); record it in the PR entry; draft PR when wanted
            # 16b · 2/4 quality-gate tail, always report-only (opt-in)
            # 16c · 3/4 repo-green gate, fix-loop until green (opt-in)
            # 16d · 4/4 re-push + PR-body refresh when 16b/16c landed commits;
            #           package print, closing review notification
            # Never one chain: a combined entry has one completed flag, so a
            # step-level skip would have nowhere to land.

    # 17 · §2.3 — durable state NOW, kept current as the run goes.
    for unit in units:
        write_json(f"/tmp/implement_{session_id}{unit.suffix}.json",
                   phase="tasks", start_sha=head(), batch_base_sha="",
                   stack={"wanted": stack_choice.wanted,        # this unit's confirmed
                          "order": stack_choice.layer_order,    # layer order (§3.4 advances
                          "refused": stack_choice.forced_reason})  # through it) + which gate,
                                                                     # if any, forced it off
    notes = create(f"{scratchpad_dir}/notes.md")  # harness scratchpad dir, never /tmp
    # NO resume path — a leftover state file is stale: delete it and start over.

    # 45 · a task-ids run has one unit; a PR-label run repeats §3–§8 per PR, in order.
    for unit in units:
        run_unit(unit)

    return  # 48 · invocation ends
            # 48a · Stop hook releases only on
            #       phase "presented" or "halted"


def run_unit(unit):
    if unit.is_pr and need_git_checkout(plan, unit.label):  # 18
        load("references/pr-branch-creation.md")            # 18a
        create_branch(unit)   # 18b · §3.1 — ONCE, here. Never mid-loop, never a subagent.

    state.batch_base_sha = head()                           # 19 · §3.2
    recap(git_log(base_branch, "HEAD"), read="COMMIT MESSAGES, not the diff")

    tasks = exact_match(unit.task_ids, plan.headings)       # 20 · §3.3
    # A prefix matching two headings means a malformed plan, not a question — stop.

    # `while True`, never "while something is pending": an empty-looking queue is
    # NOT the gates. It empties two ways, and only 29's verdict can tell them apart.
    while True:
        # 21 · §5.4 — route by delivery shape for the WHOLE unit, every iteration,
        #      never just the first: a stacked unit is strictly sequential and
        #      never calls --eligible-set or the parallel-worktrees skill at all,
        #      because each layer branches off the previous layer's tip and two
        #      parallel siblings would leave no single tip to stack the next one on.
        if state.stack.wanted:
            task_id = state.stack.order[next_unresolved_index()]   # 21a · from
                                                                     #  stack.order,
                                                                     #  NEVER the
                                                                     #  verdict
                                                                     #  script's
                                                                     #  own ordering
            if not is_stack_order_first_entry(task_id):             # 21b
                create_layer_branch(task_id)     # 21c · git checkout -b
                                                  #      <layer-1-branch>-t<task-id>
                                                  #      from the previous layer's
                                                  #      tip; existing-branch adopt
                                                  #      check first; branch recorded
                                                  #      into this task's state entry
            run_one_task(task_id)                            # -> 23-28
        else:
            # 22 · ask --eligible-set, NEVER the plain verdict, while anything
            #      is in flight: the plain one assumes nothing is, so mid-wave it
            #      answers "halted" and stops the run to wait for a human.
            wave = eligible_set(state_file)

            if len(wave) > 1:
                wave = run_parallel_wave(wave)               # 22a–22e; may fall back to one
            if len(wave) == 1:
                run_one_task(wave.first)                     # 23–28

        # 29 · ONLY this script sends a unit to the gates. Never infer "gates"
        #      from an empty-looking queue — it empties two ways.
        v = implement_loop_state(state_file)
        if v == "next-task":
            continue                                        # back to 21 — re-checks
                                                              # stack.wanted every time,
                                                              # never straight to 22
        elif v == "gates":
            break                                            # every task in the unit is done
        else:                                                # "halted" | "halt-budget"
            halt()

    # ---- 30–38 · §8.1 · push, branch record & the draft PR, ahead of both gates ----
    load("references/batch-end-review.md")                  # 30

    # 31 · §8.1 step 1 — ALWAYS, on every batch end, whatever pr.wanted says.
    #      It leads batch end so a gate that never terminates cannot strand
    #      delivered work: two audited batches sat with the repo-green gate
    #      in_progress and no verdict, leaving 9 and 16 commits local across
    #      ~40 hours because push waited behind it.
    #      A pushed branch with no PR is the ordinary outcome, not a half state.
    #      A stacked unit pushes EVERY layer branch, in layer order, in one
    #      command; a non-stacked unit pushes its own single branch, as before.
    branches = unit.layer_branches if state.stack.wanted else [current_branch()]
    if not git_push("-u", "origin", *branches):             # 32 · no remote, a rejected
        halt()                                              #      non-fast-forward, no creds

    # The three batch-end-pr* files load under three separate conditions — each
    # `if` below reads only its own, so no run pays for a branch it skips.
    if unit.is_pr:                                          # 33
        load("references/batch-end-pr-branch-record.md")    # 33a
        # 34 · §8.1 step 2, PR-label runs only: the Branch: clause (the
        #      unit's LAST layer's branch when stacked, else the unit's own
        #      branch) + the PR-level [Done] marker, both on this PR's own
        #      plan line.
        plan.record_branch_clause(unit.label, unit.last_layer_branch_or_own())
        plan.mark_pr(unit.label, "[Done]")

    if state.stack.wanted:                                  # 35
        # 35a · EACH layer's branch, on its own task heading beside the [Done]
        #      marker §6 already writes there. A plain <task-ids> run has no
        #      PR Breakdown entry (33 never ran for it), so it records only
        #      this per-layer half.
        for task in unit.stack.order:
            plan.record_task_branch(task, task.layer_branch)

    if answers.draft_pr:                                    # 36
        load("references/batch-end-pr.md")                  # 36a
        # Every PR here opens as a DRAFT describing the pre-gate diff; 43
        # refreshes that body once the gates have landed whatever they land.
        if state.stack.wanted:                               # 36b
            # 36b1 · one pr-creator dispatch per layer, bottom-up, so every
            #       parent PR exists before its child targets it. --base is
            #       the PREVIOUS layer's branch; layer 1's --base is whatever
            #       batch-end-pr.md already resolves for the unit. Each body
            #       is scoped to that task's own plan slice and cross-links
            #       the chain (Stack: #A ← #B ← current).
            prs = [dispatch("pr-creator", task_diff(layer),
                            base=layer.previous_branch_or_unit_base(),
                            body_path=f"./pr_{slug}_t{layer.task_id}.final.md")
                   for layer in unit.stack.order]            # serial, bottom-up
            if not all(pr.opened for pr in prs):             # 36b2
                halt()
            # 36b2a · once per unit, at THIS unit's own batch end — never
            #        deferred to the run's last PR-label, unlike 37 below.
            #        `gh stack link --help` checked first; a failed link is a
            #        platform-limit note in the package, never a halt.
            gh("stack", "link", layer=prs.topmost)
        else:
            pr = dispatch("pr-creator", batch_diff)          # 36b3 · composes the body and
                                                              #       CREATES ONLY — 32 pushed,
                                                              #       so it must never push
            if not pr.opened:                                # 36b4
                halt()
        # Native mode + the run's last PR only: register the CROSS-UNIT chain,
        # reusing the already-created PRs. Linking runs LAST so no branch is
        # server-rebased mid-run. Independent of 36b2a, which registers only
        # THIS unit's own layers — both can fire on the same run.
        if plan.stack_mode == "native" and unit.is_last_label:
            load("references/batch-end-pr-native-link.md") # 37
            if not gh("stack", "link"):                     # 38 · a failed link
                plan.record_stack_mode("merge")             #      downgrades Mode:
                                                             #      to merge, never halts

    # ---- 39–42 · §8.2–§8.3 · the two opt-in gates, in that order ----
    if answers.quality_gate_tail:                           # 39 · else skipped by request
        # 40 · §8.2 — IN THIS SESSION, never wrapped in a subagent: its legs are
        #     already fresh-context reviewers, and its commits need a permission
        #     prompt only main can render. The spec argument goes in only when
        #     §1.1 resolved one — the skill matches paths by spec_/plan_ prefix.
        run_skill("/quality-gate", spec_if_resolved, plan,
                  tasks=unit.task_ids, base_ref=state.batch_base_sha,
                  # ALWAYS report_only — omitting it drops into
                  # /quality-gate's own interview, stalling on a
                  # prompt nobody is watching. The human applies
                  # verdicts manually afterward via /address-verdicts.
                  report_only=True)
        # 40a · inside it: refactor ∥ auto-review ∥ test-sdd legs → three
        #       verdict_*.md, then per-finding apply → commit → mark [Done].
        # 40b · hook: deep-reviewer-write-guard (only verdict_*.md writes approved).
        state.record_verdict_paths()   # 40c · PATHS, never content; every finding
        scout(quality_gate.declined)   #       it declined becomes a [Scout];
        state.phase = "tails"          #       then phase=tails

    if answers.repo_green_gate:                             # 41 · else skipped by request
        while True:
            # 42 · §8.3 — repo-wide, never scoped to the batch's own files. Runs
            #     AFTER the quality gate, so it measures a tree already holding
            #     whatever this tail applied — true under EITHER flag, since the
            #     test-sdd leg writes the plan's missing tests on every run of it.
            #     That's why no "the gate applied something, so re-run the suite"
            #     rule exists.
            if full_lint() and full_test_suite():           # 42a
                break
            # A failure the batch didn't cause is a [Scout], never a blocker.
            if not fix_attempts_left():                     # 42b
                halt()
            dispatch("tdd-coder", failure,                  # 42c · attempt recorded,
                     timeout_ms=3_600_000)                   #       RE-RUN THE FULL SUITE

    # ---- 43–44a · §8.4 · re-push, refresh the PR body, package, finalize ----
    # 43 · §8.4 step 1 — fires ONLY when 39–42 landed commits, decided from the
    #      tree and never from memory. Skipped outright otherwise: a no-op push
    #      and a rewritten body saying nothing each cost the reviewer a diff to
    #      discover that.
    if git_rev_list_count("@{u}..HEAD") > 0:                # 43
        if not git_push("origin", *branches):               # 43a · halts on 32's terms
            halt()
        if answers.draft_pr:                                # 43b · the gate commits land
            dispatch("pr-creator", batch_diff,               #       under "Unexpected extras"
                     update_existing=True)

    print_review_package()          # 44 · §8.4 step 2 — the package, closing with
                                    #      the review notification: base SHA + its
                                    #      subject, then one line per unit — label ·
                                    #      branch · commit count · PR URL when one exists
    complete_remaining_reminders()
    state.phase = "presented"       # 44a · §8.4 step 3, written HERE and nowhere
    delete(state_file)              #       earlier: above the gates it would free
                                    #       the Stop hook with them unrun and a PR
                                    #       already open


def run_one_task(task):
    # 23 · §3.4 — the only orchestrator work between two dispatches: flip the
    #      status, hand over a breadcrumb. No checklist path is assigned.
    task_update(task, "in_progress", breadcrumb=plan.acceptance_titles(task))

    while True:   # retry loop: 27c's "retry" comes back here, not to activation
        # 24 · §4 — agent-pinned, background, 1h Monitor cap. One task, so it
        #      runs in the main tree: a worktree exists only to keep concurrent
        #      siblings off one index, and there are no siblings here.
        report = dispatch("tdd-coder", task, timeout_ms=3_600_000)
        # 24a · hooks: subagent-model-guard + git-guard
        # 24c · THE SUBAGENT owns its RED-GREEN checklist end to end: it derives
        #       the path, writes it, and resumes from it. The orchestrator never
        #       names it, reads it, or gates on it.
        if report.timed_out:
            task_stop(report.agent)                        # 24b · resolves as a timeout
            report.status = "timeout"

        if report.status == "done":                        # 25 · §4.4
            # 26 · §5.1 — the orchestrator's whole part: no dispatch, no re-run,
            #      no checklist. One `git cat-file -e <sha>^{commit}` per SHA
            #      the report named — existence only, never content.
            accepted = all_reported_commits_resolve(report)          # 27
        else:
            accepted = False  # `blocked` and `timeout` take the failure path too

        if accepted:
            return advance(task, report)                   # 28 · §5.4

        load("references/failure-and-halt.md")             # 27a
        state.record_attempt(task, result, signature)      # 27b · §5.2
        v = implement_loop_state(state_file)               # 27c
        if v != "retry":                                   # retry loads debug-standards
            break

    if v == "stuck":                                        # 27d · §5.3
        mark_terminal(task)
        chain_abort_dependents(task, transitive=True)
        plan.mark(task, "[Blocked]")
        task_update(task, "completed")
        if not next_runnable():                            # 27e
            halt()
    elif v in ("halted", "halt-budget"):
        halt()


def advance(task, report):
    state.set(task, status="done")     # 28 · §5.4 — flipped BEFORE the verdict script,
    plan.mark(task, "[Done]")          #      which picks by status: a passed task left
    task_create_scouts(report.scouts)  #      pending gets re-dispatched later.
    task_update(task, "completed")     #      §4.3 — one [Scout] task each.


def run_parallel_wave(wave):
    # Everything a worktree is for lives in the parallel-worktrees skill: the two
    # file predicates, the cap, the branch layout, the in_progress-before-spawn
    # guard, the merge order, the cleanup. Parallelism is still derived from the
    # plan's DAG rather than asked, which is why §1.2's interview never grew a
    # question for it. This function only supplies inputs and judges reports.
    # NEVER entered for a stacked unit — 21 routes those away before this call.
    load_skill("parallel-worktrees")                        # 22a

    # 22b · A DAG says ordering, never shared files, so the skill re-filters the
    #       set against each sibling's Files list AND the main tree's uncommitted
    #       paths, then caps at 4. Below 2 there are no concurrent siblings to
    #       keep off one index, so the leftover task falls through to 23 and no
    #       worktree is created at all.
    wave = parallel_worktrees.filter(wave, files_by_task,
                                     base=state.batch_base_sha, slug=slug)
    if len(wave) < 2:
        return wave        # falls back to 23 — no worktree for a single task

    # 22c · The skill writes in_progress + branch + worktree_path into OUR state
    #       file before each spawn. Its ledger is ours by necessity: --eligible-set
    #       is what reads that mark back to skip a task already in flight.
    reports = parallel_worktrees.create_and_dispatch(wave, agent="tdd-coder")

    for r in reports:                                       # 22d · §5.1 per report, as each
        if all_reported_commits_resolve(r):                 #       lands — so a failure
            advance(r.task, r)                               #       re-dispatches (into its
        else:                                                #       OWN worktree) while its
            handle_failure(r)   # 27a-27e, unchanged        #       siblings still work

    # 22e · Ascending task-id order, rebase inside each worktree then --ff-only in
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
    load("references/failure-and-halt.md")                 # 46
    set_halted_phase_on_all_units()                        # 47 · §5.5
    notes.write(what_each_blocker_needs)  # <scratchpad>/notes.md, per blocked task
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
  n4["4. Step 1.2 · ONE up-front interview, one call:<br/><br/>- Plan pick, if multiple candidates<br/>- Plan path, if none found (§1.1)<br/>- Run in a git worktree?<br/>- Open a draft PR at batch end?<br/>- Quality-gate tail? (default yes)<br/>- Repo-green gate? (default yes,<br/>runs both the full-suite baseline<br/>and the batch-end gate, or neither)<br/>- Confirm the base branch<br/>- Deliver each task as its own stacked PR?<br/>(yes/no, default NO)"]:::gate
  n5{"5. Step 1.2 · Stacked answered yes? Stacked is<br/>OPT-IN because it turns the whole unit strictly<br/>sequential — no parallel dispatch for the run"}
  n5a["5a. Default 'no': the unit ships as ONE PR,<br/>its tasks commits inside it — nothing else in<br/>step 1.2 runs, and stacked-by-task.md is<br/>never loaded"]
  n6["6. Step 1.2 · Load references/stacked-by-task.md<br/>— only on a 'yes', before its two gates below"]:::skill
  n7{"7. Step 1.2 · Gate 1 · Does 'gh stack --help'<br/>exit 0? (gh-stack extension installed —<br/>without it a stack can be built but never registered)"}:::hook
  n7a["7a. Gate 1 fired: gh-stack extension not installed"]
  n8{"8. Step 1.2 · Gate 2 (checked only once Gate 1<br/>passes) · resolve-task-order.sh &lt;plan-file&gt; &lt;task-ids&gt;<br/>— exit code?"}:::hook
  n8a["8a. Gate 2 fired (exit 1): a task in scope has<br/>2+ in-scope parents (a true join) — surface every<br/>offending task + its parents verbatim"]
  n8b(["8b. Stop (exit 2): usage/parse error —<br/>fix the plan/args and re-invoke, like any<br/>other pre-flight failure"])
  n9["9. Step 1.2 · A SECOND AskUserQuestion call,<br/>still before any dispatch: confirm or reorder<br/>resolve-task-order.sh's topological layer order<br/>(ties lowest-id-first; an order putting a task<br/>before an in-scope parent is rejected) — or, when<br/>7a / 8a fired, confirm the forced non-stacked run<br/>naming that gate, which the 'yes' cannot override"]:::gate
  n10["10. Step 1.3 · Re-validate ALL THREE checks ONCE,<br/>before any execution: check-tasks-dag.sh +<br/>check-pr-dag.sh + check-pr-task-projection.py"]:::hook
  n11{"11. All three checks valid?"}
  n11a(["11a. Stop: surface the script's stderr;<br/>fix the plan, re-invoke"])
  n12{"12. Worktree requested?"}
  n12a["12a. Load references/worktree-setup.md"]:::skill
  n12b["12b. Step 1.4 · EnterWorktree + symlink<br/>the plan and its spec, copy .env*"]
  n13{"13. Arg is PR-label(s)?"}
  n13a["13a. Load references/pr-awareness.md"]:::skill
  n13b["13b. Step 1.5 · Resolve EVERY PR-N to its<br/>task-id list (get-pr-tasks.sh),<br/>before any seeding"]
  n13c["13c. Step 1.5 · Decide the CROSS-UNIT stack mode<br/>ONCE — between PR-N units, independent of 5-9's<br/>per-task stack choice within one unit: diamond<br/>(a PR with 2+ parents) -&gt; merge; linear AND<br/>gh-stack extension installed -&gt; native; else merge.<br/>Record a Mode: line under the plan's PR Breakdown<br/>heading — sticky for the stack's whole life"]:::state
  n14{"14. §1.2's repo-green gate toggle answered yes?"}
  n14a["14a. Load references/full-suite-baseline.md"]:::skill
  n14b["14b. Step 1.6 · Capture the baseline: full lint +<br/>full test suite, once worktree (12b) and<br/>PR-label resolution (13b) have settled;<br/>save the log PATH + failing signatures into<br/>state.baseline (never the log content)"]:::state
  n15["15. Step 2.1 · TaskList: one entry per task,<br/>ALL PRs upfront in execution order<br/>(subjects prefixed 'PR-2 &middot;');<br/>1st in_progress, rest pending;<br/>status only"]:::state

  subgraph seedRemind["16. Step 2.2 · After each PR's task entries, seed that batch's [Reminder]s — N of up to 4, per §2.2 — separate entries, never one chain:<br/>a combined entry has one completed flag, so a step-level skip would have nowhere to land."]
    direction TB
    n16a["16a. Add to TaskList a [Reminder] for<br/>Batch-end (push): push the branch(es); record it in the<br/>PR entry; open the draft PR via pr-creator when wanted"]:::state
    n16b["16b. Add to TaskList a [Reminder] for<br/>Batch-end (quality-gate tail), always<br/>report-only (only when opted in)"]:::state
    n16c["16c. Add to TaskList a [Reminder] for<br/>Batch-end (repo-green gate), fix-loop until green<br/>(only when opted in)"]:::state
    n16d["16d. Add to TaskList a [Reminder] for<br/>Batch-end (package): re-push and refresh the PR body when<br/>16b/16c landed commits; package print,<br/>closing review notification"]:::state
    n16a --> n16b --> n16c --> n16d
  end

  n17["17. Step 2.3 · Write durable state NOW,<br/>kept current as the run goes:<br/>one /tmp/implement_&lt;session_id&gt;[_prN].json<br/>per unit (phase=tasks, start_sha=HEAD,<br/>stack: {wanted, order, refused} from 4-9)<br/>+ &lt;scratchpad&gt;/notes.md in the harness<br/>scratchpad directory (never /tmp).<br/>NO resume path — a leftover file is stale"]:::state

  subgraph perunit ["Per unit: the whole batch (task-ids run), or each PR in turn (PR-label list)"]
    n18{"18. PR-label run: checkout needed?<br/>(need-git-checkout.sh)"}:::hook
    n18a["18a. Load references/pr-branch-creation.md"]:::skill
    n18b["18b. Step 3.1 · Orchestrator creates this<br/>PR's branch — ONCE, here; never<br/>mid-loop, never by a subagent"]
    n19["19. Step 3.2 · Capture BATCH_BASE_SHA into<br/>the state file; recap the base from<br/>COMMIT MESSAGES, not the diff"]:::state
    n20["20. Step 3.3 · Exact-match this unit's task-ids<br/>(a collision means a malformed plan)"]
    n21{"21. Step 5.4 · Unit stacked (state.stack.wanted)?<br/>Checked EVERY loop iteration, never just the first —<br/>a stacked unit is strictly sequential and never<br/>calls --eligible-set or parallel-worktrees at all"}
    n21a["21a. Take the next task id from stack.order<br/>— NEVER the verdict script's own ordering"]
    n21b{"21b. Is this task stack.order's first<br/>entry (layer 1)?"}
    n21c["21c. Create this layer's branch:<br/>git checkout -b &lt;layer-1-branch&gt;-t&lt;task-id&gt;<br/>from the previous layer's tip (existing-branch<br/>adopt check first); branch recorded into<br/>this task's state-file entry"]:::state
    n22{"22. Step 5.4 · How many tasks are eligible right now?<br/>(implement-loop-state.py --eligible-set — NEVER the plain<br/>verdict while anything is in flight: the plain one assumes<br/>nothing is, so mid-wave it answers 'halted' and stops the<br/>run to wait for a human)"}:::hook
    n22a["22a. Load the parallel-worktrees skill, handing it the eligible<br/>ids, each task's Files list, batch_base_sha and the plan slug.<br/>Every worktree, branch, dispatch and merge below is its flow,<br/>authored in its own file: this run supplies those four inputs<br/>and judges the reports, and owns nothing else in the wave"]:::skill
    n22b{"22b. After its own two file predicates and its cap of 4,<br/>does the set still hold 2 or more? (a DAG says ordering,<br/>never shared files, so undeclared-independent tasks can<br/>still collide — and 1 task needs no worktree at all)"}
    n22c["22c. It opens one worktree + branch per task and dispatches<br/>one tdd-coder into each (agent-pinned, background, ∥),<br/>marking every task in_progress in THIS state file first —<br/>its ledger is ours, because --eligible-set is what reads<br/>that mark back to skip a task already in flight"]:::dispatch
    n22d["22d. Step 5.1 · Accept each report as it lands, so a failure<br/>re-dispatches — into its OWN worktree — while its siblings<br/>still work. A failure or block is that task's alone"]
    n22e["22e. Once every task is accepted it merges each branch back<br/>in ascending task-id order and removes that worktree per<br/>merge, leaving history identical to a sequential run's"]:::state
    n23["23. Step 3.4 · Activate a task: TaskUpdate<br/>in_progress + breadcrumb.<br/>NO checklist path is assigned"]:::state
    n24["24. Step 4 · Dispatch tdd-coder (agent-pinned,<br/>background, 1h Monitor cap). One task, so it runs<br/>in the main tree: a worktree exists only to keep<br/>concurrent siblings off one index, and there are none"]:::dispatch
    n24a["24a. Hooks: subagent-model-guard + git-guard"]:::hook
    n24b["24b. 1h Monitor expires: TaskStop the<br/>subagent (resolves as timeout)"]:::hook
    n24c["24c. THE SUBAGENT owns its RED-GREEN checklist<br/>end to end: it derives the path, writes it,<br/>and resumes from it. The orchestrator never<br/>names it, reads it, or gates on it"]:::state
    n25{"25. Step 4.4 · Subagent report status?"}
    n26["26. Step 5.1 · Accept the result: the orchestrator<br/>dispatches no reviewer, re-runs nothing and reads no<br/>checklist — its whole part is one<br/>git cat-file -e &lt;sha&gt;^{commit} per reported SHA"]
    n27{"27. Every reported commit resolves?<br/>(a 'done' reporting none fails too;<br/>existence only, never content)"}
    n27a["27a. Load references/failure-and-halt.md"]:::skill
    n27b["27b. Step 5.2 · Record the attempt<br/>(fail/timeout/blocked + signature)<br/>into the state file"]:::state
    n27c{"27c. Step 5.2 · implement-loop-state.py:<br/>verdict?"}:::hook
    n27d["27d. Step 5.3 · Mark the task terminal;<br/>chain-abort dependents transitively;<br/>plan [Blocked]; TaskUpdate completed"]:::state
    n27e{"27e. Step 5.3 · Any runnable task left?"}
    n28["28. Step 5.4 · Advance: state file status=done<br/>(flipped BEFORE the verdict script, which picks by<br/>status — a passed task left pending is re-dispatched);<br/>plan [Done]; TaskCreate [Scout] items; TaskUpdate completed"]:::state
    n29{"29. Step 5.4 · implement-loop-state.py: verdict?<br/>ONLY this script sends a unit to the gates"}:::hook
    n30["30. Load references/batch-end-review.md"]:::skill
    n31["31. Step 8.1 · git push -u origin &lt;branch(es)&gt; —<br/>ALWAYS, on every batch end, whatever pr.wanted says, and<br/>BEFORE either gate: two audited batches sat with the<br/>repo-green gate in_progress and no verdict, stranding 9<br/>and 16 local commits for ~40 hours because push waited<br/>behind it. A stacked unit pushes EVERY layer branch, in<br/>layer order, in one command; else just the unit's single<br/>branch. A pushed branch with no PR is the ordinary<br/>outcome, not a half-finished state. Record the SHA it<br/>pushed — step 43 reads it back"]:::gate
    n32{"32. Push succeeded?<br/>(no remote / rejected non-fast-forward /<br/>missing credentials)"}
    n33{"33. PR-label run?"}
    n33a["33a. Load references/batch-end-pr-branch-record.md"]:::skill
    n34["34. Step 8.1 · Record the Branch:<br/>clause (the unit's LAST layer's branch when stacked,<br/>else the unit's own branch) + the PR-level [Done]<br/>marker on this PR's own plan line (PR-label runs only)"]:::state
    n35{"35. Unit stacked (state.stack.wanted)?"}
    n35a["35a. Record EACH layer's branch on its own task<br/>heading, beside its [Done] marker (a plain<br/>&lt;task-ids&gt; run has no PR Breakdown entry — 33 never<br/>ran for it — so it records only this per-layer half)"]:::state
    n36{"36. Draft PR requested?"}
    n36a["36a. Load references/batch-end-pr.md"]:::skill
    n36b{"36b. Unit stacked (state.stack.wanted)?"}
    n36b1["36b1. Open one PR per layer, bottom-up: one<br/>pr-creator dispatch each (serial), so every parent<br/>PR exists before its child targets it. --base is the<br/>PREVIOUS layer's branch; layer 1's --base is whatever<br/>batch-end-pr.md resolves for the unit. Each body is<br/>scoped to that task's own plan slice, cross-linking<br/>the chain (Stack: #A ← #B ← current)"]:::dispatch
    n36b2{"36b2. Every layer's PR opened?"}
    n36b2a["36b2a. Register THIS unit's chain: gh stack link<br/>from the topmost layer (gh stack link --help checked<br/>first). Once per unit, at this unit's own batch end —<br/>never deferred to the run's last PR-label, unlike 37.<br/>A failed link is a platform-limit note in the<br/>package, never a halt"]
    n36b3["36b3. Dispatch the pr-creator agent (agent-pinned):<br/>it composes the body and CREATES the PR ONLY —<br/>step 32 already pushed, so it must never push<br/>or force-push. It opens as a DRAFT describing the<br/>pre-gate diff, which step 43 refreshes"]:::dispatch
    n36b4{"36b4. PR opened or updated?"}
    n37["37. Native mode + the run's LAST PR only (skipped<br/>otherwise): load references/batch-end-pr-native-link.md.<br/>Registers the CROSS-UNIT chain — independent of 36b2a,<br/>which registers only this unit's own layers; both can<br/>fire on the same run"]:::skill
    n38["38. gh stack link registers the cross-unit chain,<br/>reusing the already-created PRs. Linking runs LAST so no<br/>branch is server-rebased mid-run; a failed link downgrades<br/>the plan's Mode: to merge and continues — never a halt"]
    n39{"39. Quality-gate tail requested?"}
    n40["40. Step 8.2 · Invoke /quality-gate [&lt;spec&gt;] &lt;plan&gt;<br/>--tasks &lt;this unit's ids&gt;, base ref = BATCH_BASE_SHA,<br/>always carrying --report-only (never omitted — that<br/>drops /quality-gate into its own interview and stalls<br/>the batch on an unwatched prompt). The human applies<br/>verdicts manually afterward via /address-verdicts.<br/>Spec argument goes in only when §1.1 resolved one.<br/>IN THIS SESSION, never wrapped in a subagent:<br/>its legs are already fresh-context reviewers, and<br/>its commits need a prompt only main can render"]:::skill
    n40a["40a. Inside it: refactor ∥ auto-review ∥ test-sdd leg<br/>→ three verdict_*.md, then per-finding<br/>apply → commit → mark [Done]"]:::dispatch
    n40b["40b. Hook: deep-reviewer-write-guard<br/>(only verdict_*.md writes are approved)"]:::hook
    n40c["40c. Record each verdict PATH into the state file<br/>(never its content); every finding it declined<br/>becomes a [Scout]; then phase=tails"]:::state
    n41{"41. Repo-green gate requested?"}
    n42["42. Step 8.3 · Repo-green GATE: full lint + full test<br/>suite, repo-wide, never scoped to the batch's own<br/>files. Runs AFTER the quality gate, so it measures a<br/>tree already holding the test-sdd leg's written tests<br/>— the tail's other two legs, refactor and auto-review,<br/>are always report-only and never touch the tree. Why<br/>no 'it applied something, so re-run the suite' rule<br/>exists"]:::gate
    n42a{"42a. Green? (a failure the batch didn't<br/>cause is a [Scout], never a blocker)"}
    n42b{"42b. Fix attempts left?"}
    n42c["42c. Step 8.3 · Dispatch tdd-coder to fix it<br/>(agent-pinned, 1h Monitor cap, attempt<br/>recorded); RE-RUN THE FULL SUITE"]:::dispatch
    n43{"43. Step 8.4 · Did 39–42 land any commit?<br/>git rev-list --count @{u}..HEAD &gt; 0, read off the<br/>tree and never from memory. Nothing landed: skip both<br/>halves below, since a no-op push and a body rewritten<br/>to say nothing each cost the reviewer a diff to<br/>discover that"}
    n43a["43a. Step 8.4 · git push origin &lt;branch(es)&gt;, so the<br/>remote carries the gate fixes before anything<br/>describes them"]:::gate
    n43b{"43b. Re-push succeeded?<br/>(halts on 32's terms)"}
    n43c{"43c. Did 36 open a draft PR?"}
    n43d["43d. Refresh that PR's body through the same<br/>pr-creator dispatch: the gate commits land under its<br/>'Unexpected extras' section"]:::dispatch
    n44["44. Step 8.4 · Print the review<br/>package, closing with the review notification:<br/>base SHA + its subject, then one line per unit —<br/>label · branch · commit count · PR URL when one<br/>exists; complete the remaining [Reminder]s"]
    n44a["44a. Step 8.4 · phase=presented — written HERE and<br/>nowhere earlier: set above the gates it would free the<br/>Stop hook with them unrun and a PR already open.<br/>Then DELETE this unit's state file"]:::state
  end

  n45{"45. PR-label run with PRs remaining?"}
  n46["46. Load references/failure-and-halt.md"]:::skill
  n47(["47. Step 5.5 · HALT and wait for the human:<br/>phase=halted on all units; write what each blocker<br/>needs into &lt;scratchpad&gt;/notes.md; leave remaining<br/>[Reminder]s pending. Cleanup stops entirely here —<br/>an unmerged branch holds work only a human can<br/>resolve, so every worktree stays and the halt names<br/>each one; run NOTHING further"]):::gate
  n48(["48. Invocation ends"])
  n48a["48a. Stop hook: releases only on<br/>phase presented or halted"]:::hook

  n1 --> n2 --> n3
  n3 -->|"no"| n3a
  n3 -->|"yes"| n4 --> n5
  n5 -->|"no (default)"| n5a --> n10
  n5 -->|"yes"| n6 --> n7
  n7 -->|"no"| n7a --> n9
  n7 -->|"yes"| n8
  n8 -->|"1 (join)"| n8a --> n9
  n8 -->|"2 (usage/parse error)"| n8b
  n8 -->|"0 (pass)"| n9
  n9 --> n10 --> n11
  n11 -->|"no"| n11a
  n11 -->|"yes"| n12
  n12 -->|"yes"| n12a --> n12b --> n13
  n12 -->|"no"| n13
  n13 -->|"yes"| n13a --> n13b --> n13c --> n14
  n13 -->|"no"| n14
  n14 -->|"yes"| n14a --> n14b --> n15
  n14 -->|"no"| n15
  n15 --> n16a
  n16d --> n17 --> n18
  n18 -->|"yes"| n18a --> n18b --> n19
  n18 -->|"no / task-ids run"| n19
  n19 --> n20 --> n21
  n21 -->|"yes (stacked)"| n21a --> n21b
  n21b -->|"no — layer 2+"| n21c --> n23
  n21b -->|"yes — layer 1, no new branch"| n23
  n21 -->|"no"| n22
  n22 -->|"2 or more"| n22a --> n22b
  n22b -->|"no — filtered down to 1"| n23
  n22b -->|"yes"| n22c --> n22d --> n22e --> n28
  n22d -->|"a task fails, blocks or times out"| n27a
  n22e -->|"it hits a rebase conflict and halts: the<br/>file-disjointness predicate was wrong for<br/>that pair, so it keeps every worktree"| n46
  n22 -->|"1 (or a run with no independent tasks)"| n23 --> n24
  n24 -.->|"guards"| n24a
  n24 -.->|"owns"| n24c
  n24 -->|"1h timeout"| n24b --> n27a
  n24 --> n25
  n25 -->|"blocked"| n27a
  n25 -->|"done"| n26 --> n27
  n27 -->|"yes"| n28
  n27 -->|"no"| n27a
  n27a --> n27b --> n27c
  n27c -->|"retry (loads debug-standards)"| n24
  n27c -->|"stuck"| n27d --> n27e
  n27c -->|"halt-budget"| n46
  n27e -->|"yes"| n21
  n27e -->|"no"| n46
  n28 --> n29
  n29 -->|"next-task"| n21
  n29 -->|"gates"| n30
  n29 -->|"halted / halt-budget"| n46
  n30 --> n31 --> n32
  n32 -->|"no"| n46
  n32 -->|"yes"| n33
  n33 -->|"yes"| n33a --> n34 --> n35
  n33 -->|"no / task-ids run"| n35
  n35 -->|"yes"| n35a --> n36
  n35 -->|"no"| n36
  n36 -->|"yes"| n36a --> n36b
  n36b -->|"yes"| n36b1 --> n36b2
  n36b2 -->|"no"| n46
  n36b2 -->|"yes"| n36b2a --> n37
  n36b -->|"no"| n36b3 --> n36b4
  n36b4 -->|"no"| n46
  n36b4 -->|"yes"| n37
  n37 --> n38 --> n39
  n36 -->|"no"| n39
  n39 -->|"yes"| n40 --> n40a --> n40c --> n41
  n40a -.->|"guards"| n40b
  n39 -->|"no, skipped by request"| n41
  n41 -->|"yes"| n42 --> n42a
  n42a -->|"no"| n42b
  n42b -->|"no"| n46
  n42b -->|"yes"| n42c --> n42
  n42a -->|"yes"| n43
  n41 -->|"no, skipped by request"| n43
  n43 -->|"yes"| n43a --> n43b
  n43b -->|"no"| n46
  n43b -->|"yes"| n43c
  n43c -->|"yes"| n43d --> n44
  n43c -->|"no"| n44
  n43 -->|"no, nothing landed"| n44
  n44 --> n44a --> n45
  n45 -->|"yes"| n18
  n45 -->|"no"| n48
  n46 --> n47 --> n48
  n48 -.->|"releases"| n48a

  classDef start fill:#fef3c7,stroke:#d97706,stroke-width:2px
  classDef gate fill:#fee2e2,stroke:#dc2626,stroke-width:2px
  classDef dispatch fill:#dbeafe,stroke:#2563eb,stroke-width:2px
  classDef state fill:#dcfce7,stroke:#16a34a,stroke-width:2px
  classDef skill fill:#f3e8ff,stroke:#9333ea,stroke-width:2px
  classDef hook fill:#e5e7eb,stroke:#4b5563,stroke-width:2px
```
