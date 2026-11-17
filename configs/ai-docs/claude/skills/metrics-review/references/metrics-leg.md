# Metrics Leg

What main does around the metrics lens that the `metrics-review` skill dispatches, standalone or from `/quality-gate` §3. The leg's own prompt is [`metrics-lens.md`](metrics-lens.md); this file covers only the steps a subagent cannot take.

## 1. Inspector

Main dispatches the read-only inspector before the leg, never the leg itself.
- Reason: the leg is a `code-reviewer` that never spawns a nested reviewer, so the dispatch has to come from main.

`metrics-lens.md` names no inspector trigger, so the one trigger is the per-session tool map: dispatch only when `/tmp/quality-metrics_<session id>.json` has no entry for this repo and base ref (`quality_metrics/tool_map.py` builds it).

- Dispatch `agent(subAgent=Explore, title=Metrics tool inspector)` with [`metrics-tool-inspector.md`](metrics-tool-inspector.md) and `<BASE_REF>` pushed in.

- Double-check its report before acting: open each cited `<path>:<line>` at the base ref and confirm the quoted text is there.

- A tool it reports that no detector matches becomes a detector edit in `quality-metrics-detectors.yaml`, which main commits in the global config repo.
  - Main never edits `quality-metrics.yaml`: opt-outs and limits stay proposals the human rules on.

- Write each committed detector edit to `<RUN_DIR>/detector-edits.md` as a four-part finding the merge agent takes as a source: `### N. [Done][<SEV>][metrics] <title>`, naming the commit SHA.

- Give the leg the checked report in its prompt, so its judge findings can cite it.

## 2. Tooling asks

A subagent never asks the human. The leg returns each tooling problem as an `ask` record (`tooling_ask` in `quality_metrics/failures.py`): the `tool`, its `metric`, the `reason`, and `choices` of `fix now` and `defer`. A missing or crashed global tool and a changed code file whose language has no declaration entry both arrive this way.

**Nobody can be asked** when `--report-only` or `--auto-solve` was passed, or when `CLAUDE_CODE_ENTRYPOINT` is set to anything but `cli` (`session_can_ask` in the same file). `/implement`'s batch end always passes one of the two flags, so every tooling ask in that tail defers.

The variable decides, never your judgment. Answer `defer` without asking:
- coverage and CRAP read `pessimistic, tooling deferred` at 0%,
- a file with no language entry reads `not measured: no language entry`,
- both score as failing in the report, never neutral and never passing.

**Otherwise** raise every open ask in one `AskUserQuestion`: `fix now` or `defer`, recommending `defer` only when the fix is not yet understood, and quoting the tool and the reason.
- Relay the answer by continuing or re-dispatching the leg.

- **fix now**: fix the tool, proposing a language entry for the human to apply when an entry is missing.
  - The leg resumes only after the fixed tool runs, and the metric then reports its measured value.

  - A fix that fails asks again: fix again or defer.

- **defer**: the leg scores the metric as above, and the batch completes.
  - Before the leg re-runs, main records the deferral with `detect-repo-metric-tools.py --repo <repo> --base <base> --session-id <id> --defer <tool>`.

  - Copy `tool` verbatim from the ask, because the map matches it by exact string. Usage is in the script's header.

## 3. No git

When no git repo encloses CWD (`git rev-parse --is-inside-work-tree` fails), skip base-ref resolution. Dispatch only the metrics lens, since the other `/quality-gate` legs diff against a base.

The scout leg is not dispatched either, since it needs `git diff`, and `/quality-gate` §7 reports `scout leg: not run (no git)`.

The rendered metrics verdict states which checks it skipped (the removed-code check and base-ref reads), and a `/quality-gate` caller's merged file is `verdict_quality-gate_no-git_<ts>.md`.

## 4. A failed leg

An exit 2 from the script or the verdict render, or no rendered file after one re-dispatch, is not a clean run. Merge the other legs with k = 0 and report `metrics: FAIL - leg failed (<reason>)` in §7.

## 5. Open-violation entry numbers

The rendered verdict lists open violations under `## Open violations (<n>)` and `## Gate input violations (<n>)`, each entry as `### N. <text>`. The numbers that enter the apply list come from `~/.claude/scripts/get-fix-apply-list.py`, per `quality-gate/SKILL.md` §5.2 and [`fix-judge.md`](../../quality-gate/references/fix-judge.md) §2.

The verdict also carries `## Tooling asks (<n>)` after `## Deferred metrics` and `## Coverage sources (<n>)` before `## Code design`, each entry numbered like the rest. Neither section lists violations, so neither enters the apply list.

Those numbers are the same in the merged file, where the rendered entries come first and keep numbers 1 to k. Each judge finding is a `[metrics]` heading numbered from k+1 in the merged file.
