# Dispatch and apply rationale

The reasoning behind the routing and assembly rules in `SKILL.md`. The rules themselves live there and bind without this file; read this only when someone questions why a leg, the merge, or the apply step is shaped this way.

## Why each leg never spawns a nested reviewer

Each leg already is the fresh-context reviewer that the `refactor`, `auto-review`, and `test-sdd` skills would otherwise dispatch.

Nesting a reviewer inside it would spend one of the harness's four spawn-depth levels (main, leg, pipeline, lens) on a second opinion nobody asked for.

The skills a leg invokes describe dispatching a reviewer, so without the explicit override the leg would follow that text literally. That is why `SKILL.md` tells the dispatcher to state the override in every leg's prompt.

## Why a flagged run never prompts on a multi-match

Either `--auto-solve` or `--report-only` marks a skill-dispatched run with nobody standing by. That is the same premise `SKILL.md` §6 uses to force `--no-ask`.

A prompt on a multi-match would stall the `/implement` tail indefinitely, so the run proceeds without that kind, exactly as a zero match resolves.

`--no-ask` on the `/address-verdicts` call follows from the same premise: §1 already asked this run's one question, so a prompt now would re-ask it or stall a `/implement` tail.

## Why applying belongs to `/address-verdicts`

`/address-verdicts` is the apply step for every `verdict_*.md` on disk, whoever wrote it. This skill decides which findings deserve a fix, and that skill owns how every fix lands.

Duplicating its loop here would let two copies of the lens routing, commit rule, and annotation format drift apart. A human could then no longer tell which copy their report followed.

## Why `/address-verdicts` runs in this session, not a subagent

This skill sits in `/implement`'s main session for the same reason.

`/address-verdicts` commits the `refactor` agent's work, and a permission prompt only renders in the main session. It runs in this session, never in a subagent, because it commits. Its per-lens apply agents are already fresh-context subagents.

Wrapping it in another subagent would spend one of the four spawn-depth levels on a layer that decides nothing.

## Why every missing-planned-test finding applies without triage

Each names a test the plan declared and the repo lacks, so the human's plan approval already answered whether it is worth doing.

The unplanned-tests finding is one exception: it names tests the branch already added, so nothing is left to write, and the human reviews it instead.

`[Done]` on it means the developer reviewed those tests, which only the human can do, so `/address-verdicts` never dispatches or annotates it.

`get-test-sdd-dispatch-list.py` keys on the finding's exact title, so the test-sdd report schema and that script must change together.

The script reads a heading with none of its `LENS_TAGS` tags as test-sdd, so a new lens goes in `LENS_TAGS` and in the `auto-review|refactor|test-sdd|metrics|scout` regex of the quality-gate `SKILL.md` merge check together.

## Why a fresh judge, not self-triage

Main assembled the merged file and would judge it with that bias. A fresh opus reviewer loaded with the standards sees only the findings and the code. Each Skip carries the quoted rule, so the human can check it.

## Why the fix review never applies

An apply step after the review would need its own review, so the run would loop. Reporting only bounds the run at one review.

## Why report-only applies `test-sdd` only

A missing planned test is already approved by the plan, so it needs no judge. Every other finding needs the judge, and report-only runs none.

## Why the metrics tooling problems go first

The script's `tooling_metrics_*.md` is copied verbatim ahead of every finding, so a metric that never measured is the first thing a reader meets, and the PR is never blocked on it.

Only its deferred metrics, tooling asks and accepted exceptions are numbered, `1` to `k` with no severity tag, because the script owns that numbering and a merge agent renumbering them would break an exception's link to its split diff.

The full render's raw records stay in `<RUN_DIR>` as judge input. The judge turns each into a finding citing its `**Record**:` key or a dismissal, so every problem gets exactly one number.

Every other finding is numbered from `k+1` for the same reason: one run, one numbering, so `/address-verdicts` names a finding by a single number.

## Why main assembles with `cat`

The merge agent writes only `<RUN_DIR>/merged-findings.md`. Main then runs `cat <tooling> <RUN_DIR>/merged-findings.md | write-atomically.py <merged path>`.

That keeps the tooling file byte-identical to what the script wrote, which a model rewriting it could not promise. The atomic write also means a killed run leaves no partial merged verdict in CWD.

The `test-sdd` leg's verdict lands in `<RUN_DIR>` for the same reason: a quality-gate run leaves no `verdict_test-sdd_*` file in CWD, only the one merged verdict.

## Why the merge count is checked as an equality

An upper bound would let dropped findings pass, and the agent's own counts would let it hide one. Main counts the rendered file for `k` and every source itself, then requires the merged count to equal `k` plus the summed findings minus the absorbed.

## Why the merged verdict still exists with no git

With no git repo there is no base to diff against, so only the metrics leg can run, on the files the session edited. The verdict is still written, as `verdict_quality-gate_no-git_<ts>.md`, because stopping would hide a measurable result; the rendered file states which checks it skipped.

## Why the §3 legs have a 30-minute target and per-phase marks

The user waits on the run, and a 2-hour run per PR stalls a stacked series of PRs.

The target bounds the §3 legs only, from the earliest leg start to the latest leg end. The legs are the part a run's design controls, while apply time scales with how many findings get ruled Fix.

The §4.1 merge, the §4.2 judge and the §6 apply sit outside it, and the run total is reported as information, with no target.

The §3 legs are marked once per run: the scout leg never re-runs and no leg re-dispatches after §6, so the span never includes judge or apply time. A run with no measured §3 span reports `timing: not measured`.

The marks are recorded by the clock script, and its ledger exists so the user tunes the gate from where time goes across runs; its history counts runs over target by the §3 span.

## Why the scout leg runs beside the others

It runs in parallel so its in-goal scouts reach the same merge and the same single judge pass. A scout found while applying waits in the TaskList for the next run, so the run never loops.
