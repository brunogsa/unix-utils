# Coder metrics check - what the orchestrator does around it

Loaded at the first coder dispatch of the run, in either lane (§4.0). Both coder agents run `measure-quality-metrics.py --per-unit` themselves, per their agent files, so this file covers only what a subagent cannot do.

## 1. Tool map

Coders cannot spawn the inspector, so the orchestrator builds the per-session tool map before the first dispatch that needs it.

The trigger and the dispatch are the ones in [`metrics-leg.md`](../../quality-gate/references/metrics-leg.md) section 1: dispatch the inspector only when `/tmp/quality-metrics_<session id>.json` has no entry for this repo and base ref.

Read the map once per run, never per task. Follow that file for double-checking the inspector's report and for detector edits.

## 2. Asks

A coder never asks the human. It returns each tooling problem as an `ask` record under its report's Ask field, and the orchestrator raises it.

Follow [`metrics-leg.md`](../../quality-gate/references/metrics-leg.md) section 2 for who can be asked, the `defer` default when nobody can, and what `fix now` and `defer` mean.

Relay the answer by re-dispatching the same task with the answer in its Context. A deferred metric reads pessimistic and holds no commit.

## 3. Claimed exceptions

A coder that claims an exception names the file, function, metric, saved split diff path, and split value under its report's Exceptions claimed field.

The saved diff sits in CWD. Hand each claim to the batch-end metrics leg in `/quality-gate`'s prompt, which rules on it per [`metrics-lens.md`](../../quality-gate/references/metrics-lens.md) section 3.
