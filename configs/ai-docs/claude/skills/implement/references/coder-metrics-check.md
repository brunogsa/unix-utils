# Coder metrics check - what the orchestrator does around it

Loaded at the first coder dispatch of the run, in either lane (§4.0). Both coder agents run `measure-quality-metrics.py --per-unit` themselves, per their agent files, so this file covers only what a subagent cannot do.

## 1. Tool map

Coders cannot spawn the inspector, so the orchestrator builds the per-session tool map before the first dispatch that needs it.

The trigger and the dispatch are the ones in [`metrics-leg.md`](../../metrics-review/references/metrics-leg.md) section 1: dispatch the inspector only when `/tmp/quality-metrics_<session id>.json` has no entry for this repo and base ref.

Push `session-id: <your own session id>` into the Optional block of every coder dispatch, in either lane.

- [Why] The map is keyed by the orchestrator's id and a coder has another, so without it the coder's run falls back to global tools.

The session id is the path segment just above `scratchpad` in the main session's scratchpad path; the coders' session id, the implement state file's `session_id` and `<SESSION_ID>` are this one value.

Read the map once per run, never per task. Follow that file for double-checking the inspector's report and for detector edits.

## 2. Asks

A coder never asks the human. It returns each tooling problem as an `ask` record under its report's Ask field, and the orchestrator raises it.

Follow [`metrics-leg.md`](../../metrics-review/references/metrics-leg.md) section 2 for who can be asked, the `defer` default when nobody can, and what `fix now` and `defer` mean.

The ask arrives after the coder has committed, so never re-dispatch the same task: that would hand the coder a change already in HEAD.

On `fix now`, once the tool is fixed, create a follow-up task that re-runs the per-unit check on the committed task's files (`--per-unit --files <those files>`), with the answer in its Context.

On `defer`, record it with `detect-repo-metric-tools.py --repo <repo> --base <base> --session-id <id> --defer <tool>`, passing the ask's `tool` value verbatim because the map matches it by exact string.

A deferred metric reads pessimistic and holds no commit, so `defer` re-dispatches nothing.

## 3. Claimed exceptions

A coder that claims an exception names the file, function, metric, saved split diff path, and split value under its report's Exceptions claimed field and in its commit body.

The saved diff sits in CWD. Hand each claim to the batch-end metrics leg in `/quality-gate`'s prompt, which rules on it per [`metrics-lens.md`](../../metrics-review/references/metrics-lens.md) section 3.
