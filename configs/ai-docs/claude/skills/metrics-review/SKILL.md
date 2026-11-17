---
name: metrics-review
description: "USE to measure and judge a branch's code metrics (size, complexity, coverage, duplication, dependency direction, mutants) and render a verdict. Triggers: /metrics-review, 'review the metrics', 'measure this branch'. Also /quality-gate's metrics leg."
disable-model-invocation: false
---

# Metrics Review

Measure the branch against its base with `measure-quality-metrics.py`, have a fresh-context `code-reviewer` judge the result, and render a verdict. It is the `metrics` leg of `/quality-gate`, runnable alone.

Report only: it edits no source file, limit or opt-out.

## Usage

```
/metrics-review [--base-ref <ref>]
```

- `--base-ref <ref>` - review from this ref instead of `origin/HEAD` (branch, tag, or SHA).

A caller such as `/quality-gate` pushes in `<RUN_DIR>`, `<BASE_REF>`, HEAD and `<SESSION_ID>`, so none of them is resolved a second time. Run alone, mint or resolve each:

- `<RUN_DIR>`: `mktemp -d /tmp/metrics-review.XXXXXX`.
- `<BASE_REF>`: the argument, else `~/.claude/scripts/resolve-base-ref.sh`; when detection fails, ask which branch to diff against.
- `<SESSION_ID>`: the path segment just above `scratchpad` in your scratchpad path.
  - [Why] Only the main session's id keys the per-session tool map, and the lens's subagent has another.

## 1. Run it in the main session

Main performs this skill, because the lens agent never spawns a nested reviewer and never asks the human. Read [`references/metrics-leg.md`](references/metrics-leg.md) first: it covers the inspector dispatch, tooling asks, the no-git case and a failed run.

1. Dispatch the inspector when the per-session tool map has no entry (`metrics-leg.md` §1).

2. Dispatch `agent(subAgent=code-reviewer, title=Metrics-lens review)` following [`references/metrics-lens.md`](references/metrics-lens.md), with `<RUN_DIR>`, `<BASE_REF>`, HEAD and `<SESSION_ID>` pushed in.
   - Tell it `/tmp` is writable, since the `check-reviewer-writes.sh` hook allows only `verdict_*` in CWD and its compaction-resume needs the `/tmp` persistence.

3. Raise each tooling ask the lens returns, per `metrics-leg.md` §2, then continue or re-dispatch it.

4. Confirm the outputs exist and are non-empty: `<RUN_DIR>/verdict_metrics_*.md` and `<RUN_DIR>/metrics-judge_*.md`, or `verdict_quality-gate_no-git_*.md` with no git.
   - Missing after one re-dispatch is `metrics: FAIL - leg failed (<reason>)`, never clean (`metrics-leg.md` §4).

   - Run `check-metrics-judge-coverage.py` yourself, with the arguments in `metrics-lens.md` §6; a non-zero exit after one re-dispatch fails the leg the same way.
     - [Why] The lens runs it too, but only main's own run is one the lens cannot skip or misread.

## 2. Report

Print both verdict paths, the open-violation and finding counts per severity, each deferred tooling ask with its reading (`pessimistic, tooling deferred` or `not measured: no language entry`, both failing scores), and any detector edit main committed.

Applying is not this skill's job. `/address-verdicts` applies the findings, and `/quality-gate` merges them with its other legs.

## Flowchart (human-facing)

[`assets/flowchart.md`](assets/flowchart.md) diagrams this skill's flow for the human. Don't load it - non-authoritative, the steps above win; regenerate it whenever the flow changes.
