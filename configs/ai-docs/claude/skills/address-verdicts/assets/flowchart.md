---
# performance-check budget override, not part of the diagram itself.
# This file renders one flow twice - once as pseudo-code, once as a diagram - so
# its size is fixed by the skill's step count, and trimming to the bundled default
# would drop steps from the flow audit or drop a whole rendering.
# The same two renderings also overrun the default line cap, so lines-budget is raised too.
# Parked in assets/ and never loaded by the model, so its words and lines cost no context.
words-budget: 8192
lines-budget: 1024
---

# address-verdicts - flow overview

Human-facing overview for auditing the flow at a glance. Non-authoritative - the numbered steps in [`../SKILL.md`](../SKILL.md) win on any conflict. Regenerate this file whenever the skill's flow changes.

Two renderings of the same flow, kept cross-checkable on purpose. The `# N` comments in the pseudo-code are the diagram's node ids, so an id with no matching comment is drift.

## Pseudo-code

Python-shaped for readability only; nothing here runs, and the function names stand for steps this skill performs, not real APIs.

```python
# 1 · Entry: /address-verdicts <which ones> [--no-ask] [--test-cmd <cmd>].
#     A human invokes it, or a skill dispatches it - /quality-gate passes an
#     explicit finding list plus --no-ask, having already triaged.
def address_verdicts(arg):
    # 1a · Step 1 - an empty arg or `marked` selects MARKED MODE: only
    #      findings the human tagged [AI!], across a whole PR stack. Every
    #      other selection (all, a lens, a severity floor, an explicit list)
    #      is the unchanged single-branch, no-push flow from 2 onward.
    if arg.which_ones in ("", "marked"):                   # 1a
        findings = run_marked_stack(arg)                   # 1b-1x
        return close_with_report(arg, findings)            # 19
    # 2 · Step 1 - several timestamped generations can exist per lens. A
    #     verdict_quality-gate_*.md counts as a source for both refactor and
    #     auto-review.
    files = glob("verdict_refactor_*.md", "verdict_auto-review_*.md",
                 "verdict_test-sdd_*.md", "verdict_quality-gate_*.md")

    if not files:                                          # 3
        # 3a · Nothing to address yet - run /quality-gate, or a single lens
        #      first. NEVER fabricate a report by re-running a reviewer;
        #      this skill only consumes reports already on disk.
        return stop("no verdict file for any lens")        # 3a

    for lens in lenses_with_no_source(files):              # 4
        if arg.names_explicitly(lens):
            return stop(f"no report exists for the {lens} lens")   # 4a
        # 4 · Otherwise proceed with the lenses that DO have a source,
        #     and say which one was missing in step 6's report. A lens only
        #     a merged file covers is not missing.

    # 5 · Step 1 - per lens, the newest source by mtime wins: the newest
    #     merged file's findings tagged with that lens, or the newest
    #     standalone file, never both. A verdict file path inside
    #     <which ones> pins an older generation instead.
    selected_files = newest_source_per_lens(files, pinned=arg.paths)

    # 6 · Step 2 - match in this order: all (the default when the arg is
    #     empty), a lens name, a severity floor, then an explicit list of
    #     finding identifiers.
    findings = match(arg.which_ones, selected_files)

    # 7 · Step 2 - needed to run RED-then-GREEN in step 4. Taken from
    #     --test-cmd, else inferred from a package.json test script, a
    #     Makefile target, or the repo's own CLAUDE.md.
    test_cmd = arg.test_cmd or infer_test_command()

    # 8 · Step 2 - an identifier matching more than one finding, a severity
    #     floor the report never labels, a lens name that looks like a typo,
    #     or a test command that would not infer. Never guess past one: a
    #     wrong guess silently works the wrong finding.
    for ambiguity in ambiguities(findings, test_cmd):
        if arg.no_ask:                                     # 8a
            # 8a1 · Skipping beats guessing here, because the caller can
            #       re-run the finding by hand once it reads the ledger,
            #       whereas a wrong guess lands a commit nobody asked for.
            #       A missing test command skips only the findings that need
            #       one - refactor-lens findings still apply, since the
            #       refactor agent brings its own green-before-and-after check.
            mark_skipped(ambiguity.finding, reason=ambiguity)      # 8a1
        else:
            # 8a2 · ONE question, carrying your recommended reading. The
            #       test-command ask bundles into it when one already fires,
            #       and is asked alone otherwise.
            resolve(ask(ambiguity))                        # 8a2

    # 9 · Step 3 - group findings by lens; ONE TaskList entry per lens that
    #     contributed at least one finding, NEVER one per finding - seeded in
    #     the FIXED order test-sdd, auto-review, refactor (also step 4's
    #     dispatch order - each stage hands the next a stronger test safety
    #     net). Shaped "Apply all N <lens> findings". First entry
    #     in_progress, every other one pending. A real run yields 30-50
    #     findings but at most 3 entries. A merged-file finding joins the
    #     entry its heading lens tag names, never a quality-gate entry.
    lens_entries = group_by_lens(findings,
                                  order=["test-sdd", "auto-review", "refactor"])
    tasklist.seed([f"[Task] Apply all {len(e.findings)} {e.lens} findings"
                   for e in lens_entries],
                  first="in_progress", rest="pending")     # 9
    # 10 · Step 3 - survives a mid-run compaction, so the wrap-up step
    #      cannot get silently skipped.
    tasklist.add("[Reminder] Close with the report (step 6)")       # 10

    for entry in lens_entries:                             # 18 · outer loop, serial in the
                                                             #      seeded order - NEVER parallel,
                                                             #      since every dispatch commits to
                                                             #      the same branch
        # 21 · Step 4 - classify each finding by what it EDITS, not by which
        #      lens found it. The per-lens routing below is only the default
        #      for a code finding; a non-code target overrides it, because a
        #      test over prose costs more to author and maintain than the
        #      regressions it would catch.
        code, non_code = split_by_target(entry.findings)       # 21
        for f in non_code:
            if entry.lens == "test-sdd" and f.planned_test_covers_prose:
                # 22 · NOT written at all: the one place this skill overrules
                #      /quality-gate's "every test-sdd finding applies
                #      unconditionally" - CLAUDE.md forbids the test.
                f.skipped, f.reason = True, "tests prose, which CLAUDE.md forbids"  # 22
        prose = [f for f in non_code if not f.skipped]
        if prose:
            # 23 · Doc, spec, plan, prompt-markdown, SKILL.md, agent file,
            #      comment, rename, file move, config or frontmatter value:
            #      direct-coder, whichever lens reported it. It commits its
            #      own work. A lens with ONLY non-code findings dispatches its
            #      own agent zero times - a correct outcome, not a failure.
            result = agent("direct-coder", title=f"Apply {entry.lens} prose findings",
                            findings=prose)                    # 23

        # 11 · Step 4 - each dispatch carries ALL of this lens's selected
        #      code findings at once. The refactor agent refuses any behavior
        #      change BY DESIGN, so a correctness fix or a missing test
        #      cannot route through it; both need tdd-coder's test-first
        #      discipline instead.
        match entry.lens if code else None:
            case "test-sdd":
                # 11a · A test-sdd finding names a planned test the repo
                #       lacks, so writing that test IS the fix. Every
                #       planned title is passed verbatim so each test lands
                #       under the name the plan declared.
                result = agent("tdd-coder", title="Apply all test-sdd findings",
                                findings=code, test_cmd=test_cmd)  # 11a
            case "auto-review":
                # 11b · Strict TDD, RED before GREEN, once per finding -
                #       same as any other tdd-coder dispatch.
                result = agent("tdd-coder", title="Apply all auto-review findings",
                                findings=code, test_cmd=test_cmd)  # 11b
            case "refactor":
                # 11c · It applies the changes itself and confirms the
                #       tests are green before and after.
                result = agent("refactor", title="Apply all refactor findings",
                                findings=code, test_cmd=test_cmd)  # 11c

        # 12 · Step 4 - one verify per dispatch, covering every finding in
        #      the batch. A subagent's summary describes intent; only the
        #      artifact shows what actually landed.
        verify_against_artifacts(result)                   # 12

        for f in entry.findings:                           # 17 · inner loop, per finding
                                                             #      in this lens's batch
            # 13 · Step 4 - scored per finding, never per lens: a dispatch
            #      that landed 6 of its 9 findings is 6 applied, 3 failed.
            if f.skipped:                                   # 22 · straight to annotation
                pass
            elif not landed(result, f):                     # 13
                # 13a · Recorded as failed, never as done, and never
                #       committed.
                f.outcome = failed(result, f)               # 13a
            else:
                # 14 · Step 4 - one commit per finding still holds inside a
                #      batched dispatch: the saving is fewer agent spawns,
                #      not a coarser diff - who commits this one?
                if f.agent != "refactor":
                    # 14a · tdd-coder and direct-coder commit their own work
                    #       under commit-standards, so confirm the SHA exists
                    #       rather than re-committing - even for a refactor-lens
                    #       finding that direct-coder took.
                    f.sha = confirm_commit_exists(result, f)   # 14a
                else:
                    # 14b · The refactor agent leaves its change uncommitted
                    #       by design, so commit it HERE, in this session,
                    #       where the permission prompt can render.
                    f.sha = commit(f)                        # 14b

            # ---- 15/16 · Step 5 - written in place the MOMENT this lens's
            #      dispatch returns, never held back until the last lens
            #      finishes: a killed session mid-run then still leaves an
            #      accurate ledger for the lenses already processed. ----
            if f.sha:
                # 15 · The machine-checkable mark - a re-run skips it and
                #      grep counts it. Same prefix-after-the-number
                #      convention /implement uses on plan task headings, so
                #      one rule covers both surfaces. A skipped or failed
                #      finding is left unmarked - except in marked mode,
                #      where [AI!] or [AI!: msg] is REPLACED by [Done]
                #      (never stacked; the msg moves to the APPLIED line)
                #      and a skipped or failed finding KEEPS its tag, so the
                #      next marked run retries it.
                stamp_heading(f, "[Done]")                   # 15
            # 16 · The evidence. APPLIED pairs with a [Done] heading;
            #      SKIPPED leaves the heading unmarked, so a re-run
            #      reconsiders it. The heading alone cannot say WHY or
            #      point at the fix, and the body line alone is not
            #      greppable - hence both.
            write_body_line(f, f"APPLIED ({f.sha})" if f.sha
                               else f"SKIPPED ({f.reason})")   # 16

    # 18a · Loop exit. Single-branch flow: straight to the report. In marked
    #       mode the same loop body runs inside run_marked_stack (1q), and
    #       control returns THERE (to 1r) instead of reaching 19.
    return close_with_report(arg, findings)                 # 19


def close_with_report(arg, findings):
    # 19 · Step 6 - applied findings with their SHAs, skipped findings with
    #      their reasons, and anything that failed to apply with exactly
    #      what it needs to retry. Each finding line names its verdict file
    #      (quality-gate#N repeats across files). Marked mode adds one line
    #      per chain branch: merged-from, applied/skipped counts, pushed sha,
    #      CI result, plus every [AI!] tag ignored in a non-quality-gate file.
    ledger = compose_ledger(findings)                       # 19

    if arg.invoked_by_skill:                                # 20
        # 20b · Hand it back rather than only printing it: the caller
        #       composes the report the human actually reads, and can only
        #       name what it was told.
        return ledger                                       # 20b

    # 20a · Print it, and state plainly EVERY time: every finding step 2 did
    #       not select is untouched and carries no annotation, and this run
    #       never re-ran a reviewer. Marked mode also says every finding
    #       still tagged [AI!] is retried by the next marked run, and that
    #       deleting the tag drops it.
    print(ledger, untouched_note(), never_re_ran_note())    # 20a


class StopChain(Exception):
    pass


def halt(branch, step, cause):
    # 24 · Many edges converge here, so it is one named helper. Any failure
    #      stops the chain ON the stopped branch: no merge left in progress
    #      (a conflicted merge is aborted first), branches already pushed
    #      stay pushed, branches above stay untouched, and the repo is NEVER
    #      returned to the starting branch - the human resumes from where it
    #      broke. Raised as an exception so it propagates out of the helpers.
    raise StopChain(f"{branch}: {step}: {cause}")           # 24


def run_marked_stack(arg):
    # 1b · Step 1 - read references/stack-mode.md and follow it. EVERY
    #      verdict_quality-gate_*.md counts (not the newest per lens); other
    #      verdict files never fire here. Headings listed fence-aware, since
    #      a finding may quote a heading inside a code fence.
    files = glob("verdict_quality-gate_*.md")               # 1b
    marked = {f: awk_marked_headings(f) for f in files}     # 1b

    if not any(marked.values()):                            # 1c
        # 1c1 · NEVER fall back to `all` - tell the human to tag a heading
        #       `### N. [AI!][...]` first.
        return stop("nothing is marked")                    # 1c1

    # 1d · Fetch once, FIRST, so every branch check and remote comparison is
    #      fresh. Each file's branch comes from its first header line, never
    #      its filename (the filename turned / into -), and must pass
    #      `git rev-parse --verify origin/<branch>`. The stack comes from ONE
    #      gh pr list (--limit 1000), never a gh pr view per branch: walk down
    #      each PR's baseRefName to the trunk, walk up to the top. The chain is
    #      the WHOLE stack, from the branch directly above the trunk to the
    #      top, including branches below the lowest marked one, so a re-run
    #      after a stop still carries forward what the stopped run pushed.
    git("fetch", "origin")                                  # 1d
    branch_of = {f: branch_from_header_line(f) for f in files}   # 1d
    prs = gh_pr_list_once(limit=1000)                       # 1d
    chain = build_chain(branch_of, prs)                     # 1d

    # 1e · Stop on an unparsable header, a branch origin/<branch> rejects, a
    #      PR count equal to the limit (a cut-off list can drop a middle PR),
    #      a marked branch with no open PR, two open PRs sharing one base (a
    #      fork, not a stack), or marked branches in two different stacks.
    if not chain.is_one_valid_stack or len(prs) == 1000:    # 1e
        halt("(preflight)", "resolve stack", chain.problem) # 1e

    # 1f · git refuses a checkout of a branch held by another worktree.
    if any(b in worktree_list() for b in chain.branches):   # 1f
        halt("(preflight)", "worktree check", "branch checked out elsewhere")  # 1f

    start_branch = current_branch()                         # 1g
    # 1g · Record the tracked modifications as the NEVER-STAGE list: never
    #      stash them (the stash stack is shared across worktrees), never
    #      discard them, and every dispatch prompt carries the list since a
    #      subagent's `git add -A` would sweep them in. Stage explicit file
    #      paths only, never a directory holding a listed file.
    never_stage = tracked_modifications()                   # 1g

    # 1g1 · A listed file that differs between chain branches makes checkout
    #       refuse to carry it.
    if differs_between(chain.branches[0], chain.branches[-1], never_stage):   # 1g1
        halt("(preflight)", "never-stage files", "differ between chain branches")  # 1g1

    # 1g2 · The repo's documented pre-test setup (its CLAUDE.md names it, e.g.
    #       starting and migrating a test DB), run once for the whole chain.
    run_pre_test_setup()                                    # 1g2

    # 1g3 · The gate workflow is the one whose on.pull_request.branches lists
    #       the trunk. A workflow with no branches filter is never the gate -
    #       it runs on every PR, so its pass says nothing about the full gate.
    #       None found: CI is never watched, and the report says so.
    gate = resolve_gate_workflow(trunk=chain.trunk)         # 1g3

    # 1h · Step 2 - ALL questions for ALL marked findings, in one
    #      AskUserQuestion: a question asked mid-chain blocks a run that has
    #      already pushed half the stack.
    answers = ask_all_questions_upfront(marked)             # 1h

    # 1i · Step 3 - per chain branch, in chain order: "Merge forward <branch>",
    #      then one entry per lens with marked findings on it (lens order),
    #      then "Validate, push, watch CI <branch>" so it is not done before
    #      the push it names; plus one closing [Reminder] for the report. The
    #      count is only known at runtime, so it is a single node. Progress
    #      (pre-merge SHA, branch-start SHA, pushed SHA, CI run id and result)
    #      goes in task metadata the moment it happens, so a compaction
    #      mid-chain loses nothing.
    tasklist.seed(entries_per_branch(chain, marked))        # 1i

    findings, i = [], 0
    while True:                                             # 1w · loop-check, bottom-up
        branch = chain.branches[i]
        # 1j · Untracked verdict files survive the checkout, so step 5's
        #      annotations keep landing in CWD.
        git("checkout", branch)                             # 1j
        # 1k · A diverged branch stops the chain.
        if not git_ok("merge", "--ff-only", f"origin/{branch}"):    # 1k
            halt(branch, "ff-only", "local branch diverged from origin")  # 1k
        # 1j · Then the repo's documented build steps (its CLAUDE.md names
        #      them, e.g. a library build and a generated client), since the
        #      previous branch's build outputs do not match this one's sources.
        run_build_steps()                                   # 1j

        pre_merge_sha = head_sha()
        if i > 0:                                           # 1l
            # 1m · Merge forward: the chain branch below, on every branch
            #      except the one directly above the trunk. The trunk is never
            #      merged into the stack.
            merged = git_ok("merge", "--no-edit", chain.branches[i - 1])   # 1m
            if not merged:                                  # 1n
                # 1n · Any merge failure, not only a conflict: a refusal over
                #      local changes stops too.
                if merge_in_progress():
                    git("merge", "--abort")                 # 1n
                halt(branch, "merge forward", "merge failed")   # 1n
            # 1o · Re-run the build steps when the merge touched the paths
            #      they cover.
            run_build_steps_if_paths_changed(changed_since(pre_merge_sha))   # 1o
            # 1p · Validate only when the merge changed anything: lint plus
            #      the specs covering the merged diff. The apply agents need
            #      a green start to tell their own RED from an inherited one.
            if changed_since(pre_merge_sha) and not lint_and_specs_green(pre_merge_sha):   # 1p
                halt(branch, "validate merge", "red")       # 1p

        branch_start_sha = head_sha()
        if marked_for(branch, marked):                      # 1q
            # 1q · Steps 3-5 - the SAME lens loop as 21-18 above, run on this
            #      branch's marked findings only, annotating each lens as it
            #      returns. Control comes back here at 18a. Re-run the build
            #      steps when an apply touched the paths they cover, before
            #      the next dispatch.
            findings += apply_lens_entries(branch, marked, never_stage, answers)   # 1q -> 21
            # 1r · Validate the branch: lint plus the specs covering what
            #      the apply commits changed.
            if not lint_and_specs_green(branch_start_sha):  # 1r
                halt(branch, "validate branch", "red")      # 1r

        pushed = False
        # 1s · Skip the push when HEAD already equals origin/<branch>.
        if head_sha() != origin_sha(branch):                # 1s
            # 1s1 · The tree must be clean apart from the never-stage list;
            #       a change left by a failed apply stops the chain.
            if not clean_apart_from(never_stage):           # 1s1
                halt(branch, "clean tree", "change left by a failed apply")  # 1s1
            # 1t · NEVER --force, and never asked in chat. A rejection
            #      stops the chain.
            if not git_ok("push"):                          # 1t
                halt(branch, "push", "rejected")            # 1t
            pushed = True

        # 1u · Watch CI only when step 1t pushed and the PR's base is the
        #      trunk the gate workflow triggers on (no gate workflow: never).
        if pushed and gate and pr_base_is_gate_trunk(branch):   # 1u
            # 1v · Poll `gh run list --workflow <gate> --commit <pushed sha>`
            #      until it prints a run id, timing out after 10 minutes
            #      (keying on the SHA keeps the previous commit's green run
            #      from counting). Then `gh run watch <id> --exit-status` in
            #      the background (a full gate outlives the Bash foreground
            #      cap), and WAIT for it before the next branch. A failed run
            #      or a poll timeout stops the chain.
            if not watch_ci_in_background(gate, head_sha()):    # 1v
                halt(branch, "CI", "failed run or poll timeout")  # 1v

        i += 1
        if i == len(chain.branches):                        # 1w
            break

    # 1x · Clean finish only: return to where the run started.
    git("checkout", start_branch)                           # 1x
    return findings
```

## Flowchart

```mermaid
flowchart TD
  n1(["1. /address-verdicts &lt;which ones&gt;<br/>[--no-ask] [--test-cmd &lt;cmd&gt;]<br/><br/>A human's invocation, or a skill's dispatch -<br/>/quality-gate passes an explicit finding list<br/>plus --no-ask, having already triaged"]):::start
  n1a{"1a. Step 1 · Is &lt;which ones&gt; empty or 'marked'?<br/>Yes = MARKED MODE: only findings the human tagged [AI!],<br/>across a whole PR stack, with push. Any other selection<br/>(all, a lens, a severity floor, an explicit list) is the<br/>single-branch, no-push flow from node 2"}
  n2["2. Step 1 · Glob CWD for verdict_refactor_*.md,<br/>verdict_auto-review_*.md, verdict_test-sdd_*.md,<br/>verdict_quality-gate_*.md (a source for both refactor<br/>and auto-review). Several timestamped generations<br/>can exist per lens"]
  n3{"3. Step 1 · Any verdict file at all?"}
  n3a(["3a. STOP - nothing to address yet. Run /quality-gate,<br/>or a single lens, first. NEVER fabricate a report by<br/>re-running a reviewer; this skill only consumes<br/>reports already on disk"])
  n4{"4. Step 1 · A lens has no source (a merged file covers<br/>refactor and auto-review) - did &lt;which ones&gt;<br/>name that lens explicitly?"}
  n4a(["4a. STOP - say no report exists for that lens"])
  n5["5. Step 1 · Per lens, the newest source by mtime wins: the<br/>newest merged file's findings tagged with that lens, or<br/>the newest standalone file, never both. A verdict file<br/>path inside &lt;which ones&gt; pins an older generation.<br/>A lens with no source is dropped, and named in step 6"]
  n6["6. Step 2 · Match &lt;which ones&gt; in this order: all (the<br/>default when empty), a lens name, a severity floor,<br/>then an explicit list of finding identifiers"]
  n7["7. Step 2 · Resolve the test command, needed to run<br/>RED-then-GREEN in step 4: --test-cmd if given, else<br/>infer from a package.json script, a Makefile target,<br/>or the repo's own CLAUDE.md"]
  n8{"8. Step 2 · Any ambiguity left? An identifier matching<br/>more than one finding, a severity floor the report<br/>never labels, a lens name that looks like a typo,<br/>or a test command that would not infer"}
  n8a{"8a. Was --no-ask passed?"}
  n8a1["8a1. Resolve it to SKIPPED (the ambiguity) on that finding<br/>and carry on with the rest. Skipping beats guessing:<br/>the caller re-runs it by hand after reading the ledger,<br/>where a wrong guess lands a commit nobody asked for.<br/>A missing test command skips only the findings that need<br/>one - refactor-lens findings still apply, since that<br/>agent brings its own green-before-and-after check"]
  n8a2["8a2. Ask ONE question, carrying your recommended reading.<br/>Never guess past an ambiguity - a wrong guess silently<br/>works the wrong finding. The test-command ask bundles<br/>into this one when it already fires, else is asked alone"]:::gate
  n9["9. Step 3 · Group findings by lens. Add to TaskList ONE<br/>[Task] entry per contributing lens - NEVER one per<br/>finding - shaped 'Apply all N &lt;lens&gt; findings', seeded<br/>in the FIXED order test-sdd, auto-review, refactor<br/>(also step 4's dispatch order - each stage hands the<br/>next a stronger test safety net). First entry<br/>in_progress, every other one pending. A real run<br/>yields 30-50 findings but at most 3 entries. A merged-file<br/>finding joins the entry its heading lens tag names;<br/>no tag is an ambiguity (ask, or SKIPPED (no lens tag))"]:::state
  n10["10. Step 3 · Add to TaskList one closing [Reminder]<br/>entry for step 6's report, so a mid-run compaction<br/>cannot silently skip the wrap-up"]:::state
  n21{"21. Step 4 · Classify each finding in this entry by what it EDITS,<br/>not by which lens found it. The per-lens routing below is only<br/>the default for a code finding - a non-code target overrides it"}
  n22["22. NOT written at all: a test-sdd finding whose planned test<br/>covers prose is annotated SKIPPED (tests prose, which CLAUDE.md<br/>forbids). The one place this skill overrules /quality-gate's<br/>every-test-sdd-finding-applies rule - the forbidden test wins"]
  n23["23. Dispatch direct-coder (agent-pinned, background, serial) for a<br/>doc, spec, plan, prompt-markdown, SKILL.md, agent file, comment,<br/>rename, file move, config or frontmatter value, whichever lens<br/>reported it. A test over prose costs more to author and maintain<br/>than the regressions it would catch. A lens with only non-code<br/>findings dispatches its own agent zero times - correct, not a failure"]:::dispatch
  n11{"11. Step 4 · Which lens does this seeded entry dispatch?<br/>Each dispatch carries ALL of that lens's selected<br/>findings at once, serially in the seeded order - NEVER<br/>in parallel, since every dispatch commits to the same<br/>branch. The refactor agent refuses any behavior change<br/>BY DESIGN, so a correctness fix or a missing test cannot<br/>route through it - both need tdd-coder's test-first<br/>discipline instead"}

  n11a["11a. Dispatch tdd-coder (agent-pinned, background, serial)<br/>title: Apply all test-sdd findings. A test-sdd finding<br/>names a planned test the repo lacks, so writing that<br/>test IS the fix - pass every planned title verbatim so<br/>each lands under the name the plan declared"]:::dispatch
  n11b["11b. Dispatch tdd-coder (agent-pinned, background, serial)<br/>title: Apply all auto-review findings (from the auto-review<br/>file or [auto-review]-tagged merged findings). Strict TDD, RED<br/>before GREEN, once per finding - same as any other<br/>tdd-coder dispatch"]:::dispatch
  n11c["11c. Dispatch refactor (agent-pinned, background, serial)<br/>title: Apply all refactor findings (from the refactor file<br/>or [refactor]-tagged merged findings). It applies the<br/>changes itself and confirms the tests are green<br/>before and after"]:::dispatch

  n12["12. Step 4 · Verify the dispatch's result against the<br/>artifacts - the diff, the test run - before trusting<br/>its done. One verify per dispatch, covering every<br/>finding in the batch; a summary describes intent,<br/>only the artifact shows what actually landed"]
  n13{"13. Step 4 · Did this finding's fix land? Scored per<br/>finding, never per lens - a dispatch that landed 6 of<br/>its 9 findings is 6 applied, 3 failed"}
  n13a["13a. Record it as failed, never as done.<br/>No commit, and no [Done] mark"]
  n14{"14. Step 4 · One commit per finding still holds inside a<br/>batched dispatch - the saving is fewer agent spawns,<br/>not a coarser diff - who commits this one?"}
  n14a["14a. tdd-coder and direct-coder commit their own work under<br/>commit-standards, so confirm the SHA exists rather than<br/>re-committing - even for a refactor-lens finding direct-coder took"]
  n14b["14b. The refactor agent leaves its change uncommitted<br/>by design, so commit it HERE, in this session,<br/>where the permission prompt can render"]:::gate

  n1b["1b. Step 1 · Marked mode: read references/stack-mode.md and<br/>follow it. Read EVERY verdict_quality-gate_*.md (not the<br/>newest per lens; other verdict files never fire here) and<br/>list each file's [AI!] / [AI!: msg] headings, fence-aware since a finding<br/>may quote a heading inside a code fence"]
  n1c{"1c. Step 1 · Is any finding marked [AI!] in any file?"}
  n1c1(["1c1. STOP - nothing is marked; tag a heading<br/>### N. [AI!][...] first. NEVER fall back to all"])
  n1d["1d. Step 1 · git fetch origin once, FIRST, so every check below is fresh.<br/>Resolve each file's branch from its first header line (never its<br/>filename, which turned / into -); git rev-parse --verify<br/>origin/&lt;branch&gt; must accept it. Build the stack from ONE<br/>gh pr list --limit 1000, never a gh pr view per branch: walk down<br/>each PR's base to the trunk, walk up to the top. The chain is the<br/>WHOLE stack, from the branch directly above the trunk to the top,<br/>including branches below the lowest marked one"]
  n1e{"1e. Step 1 · Is it one valid stack? Stop on an unparsable<br/>header, a branch origin/&lt;branch&gt; rejects, a PR count equal to<br/>the limit (a cut-off list can drop a middle PR), a marked branch<br/>with no open PR, two open PRs sharing one base (a fork), or<br/>marked branches in two different stacks"}
  n1f{"1f. Preflight · Is a chain branch checked out in another<br/>worktree? git refuses that checkout"}
  n1g["1g. Preflight · Record the starting branch, and record the tracked<br/>modifications as the NEVER-STAGE list: never stash them (the stash<br/>stack is shared across worktrees), never discard them, stage explicit<br/>file paths only, and every dispatch prompt carries the list since<br/>a subagent's git add -A would sweep them in"]
  n1g1{"1g1. Preflight · Does a never-stage file differ between the first and<br/>last chain branch? checkout refuses to carry it"}
  n1g2["1g2. Preflight · Run the repo's documented pre-test setup once<br/>(its CLAUDE.md names it, e.g. start and migrate a test DB)"]
  n1g3["1g3. Preflight · Resolve the gate workflow: the one whose<br/>on.pull_request.branches lists the trunk. A workflow with no<br/>branches filter is never the gate. None found = CI is never<br/>watched, and the report says so"]
  n1h["1h. Step 2 · Ask ALL questions for ALL marked findings, upfront,<br/>in one AskUserQuestion - a question asked mid-chain blocks a<br/>run that has already pushed half the stack"]:::gate
  n1i["1i. Step 3 · Add to TaskList, per chain branch in chain order:<br/>'Merge forward &lt;branch&gt;', then one entry per lens with marked<br/>findings (lens order), then 'Validate, push, watch CI &lt;branch&gt;';<br/>plus one closing [Reminder]. Runtime-sized, so one node.<br/>Progress (pre-merge SHA, branch-start SHA, pushed SHA, CI run id<br/>and result) goes in task metadata the moment it happens"]:::state

  subgraph chain_loop["Per chain branch, bottom-up - any failure stops the chain on that branch"]
    direction TB
    n1j["1j. git checkout the branch, then git merge --ff-only<br/>origin/&lt;branch&gt;, then run the repo's documented build steps<br/>(its CLAUDE.md names them), since the previous branch's build<br/>outputs do not match this one's sources. Untracked verdict<br/>files survive the checkout, so step 5's annotations keep<br/>landing in CWD"]
    n1k{"1k. Step 1 · Did the branch diverge from origin?"}
    n1l{"1l. Step 1 · Is this the branch directly above the trunk?"}
    n1m["1m. Merge forward: git merge --no-edit the chain branch below,<br/>on every branch except the one directly above the trunk.<br/>The trunk is never merged into the stack"]
    n1n{"1n. Step 1 · Did the merge fail (a conflict, or a refusal<br/>over local changes)?"}
    n1o["1o. Re-run the repo's documented build steps, only when<br/>the merge touched the paths they cover"]
    n1p{"1p. Step 1 · Did the merge change anything, and is lint plus<br/>the specs covering the merged diff red? The apply agents<br/>need a green start to tell their own RED from an inherited one"}
    n1q{"1q. Steps 3-5 · Does this branch have marked findings?<br/>Yes = apply them through the same lens loop (nodes 21-18),<br/>annotating each lens as it returns, re-running the build steps<br/>when an apply touched their paths. A branch with none still<br/>gets the merge, push and CI steps, so the fixes below<br/>reach every PR above them"}
    n1r{"1r. Step 1 · Is lint plus the specs covering this branch's<br/>apply commits red?"}
    n1s{"1s. Step 1 · Is HEAD already equal to origin/&lt;branch&gt;?"}
    n1s1{"1s1. Step 1 · Is the tree clean apart from the never-stage list?<br/>A change left by a failed apply stops the chain"}
    n1t{"1t. Step 1 · git push - NEVER --force, never asked in chat.<br/>Was it accepted?"}
    n1u{"1u. Step 1 · Did 1t push, does a gate workflow exist, and is the PR's<br/>base the trunk it triggers on?"}
    n1v{"1v. Step 1 · Poll gh run list --workflow &lt;gate&gt; --commit &lt;pushed sha&gt;<br/>until it prints a run id (10-minute timeout; keying on the SHA<br/>keeps the previous commit's green run from counting). Then<br/>gh run watch &lt;id&gt; --exit-status in the background (a full gate<br/>outlives the Bash foreground cap) and WAIT for it. Did it pass?"}
    n1w{"1w. Step 1 · More chain branches left above this one?"}
  end

  n1x(["1x. Clean finish only: git checkout the starting branch,<br/>then go to the report"])
  n24(["24. STOP the chain ON the stopped branch: abort a conflicted merge<br/>first, leave no merge in progress, name the branch, the step and<br/>the cause. Branches already pushed stay pushed, branches above<br/>stay untouched, and NEVER return to the starting branch -<br/>the human resumes from where it broke"])

  subgraph annotate["15/16. Step 5 · Written in place the MOMENT this lens's dispatch returns, never held back until the last lens finishes - a killed session mid-run then still leaves an accurate ledger for the lenses already processed."]
    direction TB
    n15["15. In the finding's HEADING, stamp a [Done] prefix right<br/>after the number, before the severity and lens tags. The<br/>machine-checkable mark: a re-run skips it and grep counts<br/>it. Same prefix-after-the-number convention /implement<br/>uses on plan task headings, so one rule covers both.<br/>A skipped or failed finding is left unmarked. Marked mode:<br/>[AI!] or [AI!: msg] is REPLACED by [Done], never stacked, the msg<br/>kept in the APPLIED line; a skipped or failed finding KEEPS<br/>its tag so the next marked run retries it"]:::state
    n16["16. In the finding's BODY, write the outcome and its<br/>evidence: APPLIED (sha), or SKIPPED (reason) with the<br/>heading left unmarked so a re-run reconsiders it.<br/>The heading alone cannot say WHY or point at the fix,<br/>and the body line alone is not greppable"]:::state
    n15 --> n16
  end

  n17{"17. Step 4 · More findings left in this lens's batch?"}
  n18{"18. Step 4 · More seeded lens entries left,<br/>in the fixed order?"}
  n18a{"18a. Step 4 · Running in marked mode?<br/>Yes = this branch's lens loop is done, so control<br/>returns to the stack loop; no = go straight to the report"}
  n19["19. Step 6 · Compose the ledger: applied findings with<br/>their SHAs, skipped findings with their reasons, and<br/>anything that failed to apply with exactly what<br/>it needs to retry. Each finding line names its verdict file.<br/>Marked mode adds one line per chain branch: merged-from,<br/>applied/skipped counts, pushed sha, CI result, plus every [AI!]<br/>tag ignored in a non-quality-gate file"]
  n20{"20. Step 6 · Who invoked this run?"}
  n20a(["20a. Print it, and state plainly EVERY time: every finding<br/>step 2 did not select is untouched and carries no<br/>annotation, and this run never re-ran a reviewer.<br/>Marked mode also says every finding still tagged [AI!]<br/>is retried by the next marked run, and deleting the tag<br/>drops it"])
  n20b(["20b. Hand the same ledger back to the caller rather than<br/>only printing it - the caller composes the report the<br/>human actually reads, and can only name what it was told"])

  n1 --> n1a
  n1a -->|"yes, marked mode"| n1b --> n1c
  n1a -->|"no, any other selection"| n2
  n1c -->|"no"| n1c1
  n1c -->|"yes"| n1d --> n1e
  n1e -->|"no"| n24
  n1e -->|"yes"| n1f
  n1f -->|"yes"| n24
  n1f -->|"no"| n1g --> n1g1
  n1g1 -->|"yes, differs"| n24
  n1g1 -->|"no"| n1g2 --> n1g3 --> n1h --> n1i --> n1j --> n1k
  n1k -->|"yes, diverged"| n24
  n1k -->|"no"| n1l
  n1l -->|"yes, first"| n1q
  n1l -->|"no"| n1m --> n1n
  n1n -->|"yes, git merge --abort when in progress"| n24
  n1n -->|"no"| n1o --> n1p
  n1p -->|"red"| n24
  n1p -->|"green, or nothing merged"| n1q
  n1q -->|"yes"| n21
  n1q -->|"no"| n1s
  n1r -->|"red"| n24
  n1r -->|"green"| n1s
  n1s -->|"yes, nothing to push"| n1w
  n1s -->|"no"| n1s1
  n1s1 -->|"no, dirty"| n24
  n1s1 -->|"yes, clean"| n1t
  n1t -->|"rejected"| n24
  n1t -->|"accepted"| n1u
  n1u -->|"no, CI not run"| n1w
  n1u -->|"yes"| n1v
  n1v -->|"run failed or poll timed out"| n24
  n1v -->|"pass"| n1w
  n1w -->|"yes, next branch up"| n1j
  n1w -->|"no"| n1x --> n19
  n2 --> n3
  n3 -->|"no file for any lens"| n3a
  n3 -->|"at least one"| n4
  n4 -->|"yes"| n4a
  n4 -->|"no"| n5
  n5 --> n6 --> n7 --> n8
  n8 -->|"no"| n9
  n8 -->|"yes"| n8a
  n8a -->|"yes"| n8a1 --> n9
  n8a -->|"no"| n8a2 --> n9
  n9 --> n10 --> n21
  n21 -->|"code finding"| n11
  n21 -->|"prose test-sdd finding"| n22 --> n15
  n21 -->|"other non-code finding"| n23 --> n12
  n11 -->|"test-sdd lens"| n11a --> n12
  n11 -->|"auto-review lens"| n11b --> n12
  n11 -->|"refactor lens"| n11c --> n12
  n12 --> n13
  n13 -->|"no"| n13a --> n15
  n13 -->|"yes"| n14
  n14 -->|"tdd-coder or direct-coder"| n14a --> n15
  n14 -->|"refactor agent"| n14b --> n15
  n16 --> n17
  n17 -->|"yes, next finding in this batch"| n13
  n17 -->|"no"| n18
  n18 -->|"yes, next lens entry"| n21
  n18 -->|"no"| n18a
  n18a -->|"no, single-branch flow"| n19
  n18a -->|"yes, back to the stack loop"| n1r
  n19 --> n20
  n20 -->|"a human"| n20a
  n20 -->|"a skill"| n20b

  classDef start fill:#fef3c7,stroke:#d97706,stroke-width:2px
  classDef gate fill:#fee2e2,stroke:#dc2626,stroke-width:2px
  classDef dispatch fill:#dbeafe,stroke:#2563eb,stroke-width:2px
  classDef state fill:#dcfce7,stroke:#16a34a,stroke-width:2px
  classDef skill fill:#f3e8ff,stroke:#9333ea,stroke-width:2px
  classDef hook fill:#e5e7eb,stroke:#4b5563,stroke-width:2px
```
