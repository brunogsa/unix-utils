# Metrics Lens

The prompt a `code-reviewer` follows when dispatched with the `metrics` lens.
You report only: never edit a source file, `~/.claude/scripts/quality-metrics.yaml`, or a limit.

quality-gate passes you a run directory, `<RUN_DIR>`. Every file you hand back lands there, except the layer map (section 2, CWD).

## 1. Run the script

Run `~/.claude/scripts/measure-quality-metrics.py` once, from the repo root, redirecting its JSON to the run directory:
- [Why] A repo-relative path resolves only inside the config repo.

```bash
~/.claude/scripts/measure-quality-metrics.py \
  --diff <BASE>...<HEAD> --layers <layer-map-file> \
  --session-id <SESSION_ID> > <RUN_DIR>/metrics-report.json
```

- `--session-id <SESSION_ID>` is the id main pushed into your prompt; omit it only when none was.
  - [Why] Only main's id keys the per-session tool map; without it every metric uses global tools.

- `--diff BASE...HEAD` measures every declared metric on the range's changed code and lists the over-limit functions it removes as resolved.
  - It cannot combine with `--files` or `--per-unit`.

- `--files FILE...` measures whole files; use it only when handed no range.

- `--layers FILE` is the layer map the dependency check reads. Without it only import cycles are checked, so always pass one.

- Exit 0 is clean.
  - Exit 1 is a violation, gate-input violation, or open ask: valid JSON, render it (section 3).
  - Exit 2 means the run did not measure: report the stderr failure, never a pass (`metrics-leg.md` §4).

Read the JSON in `<RUN_DIR>/metrics-report.json`: `measurements`, `violations`, `gate_input_violations`, `resolved`, `unclaimed_files`, `duplication_candidates`, `asks`.

Return each `asks` entry verbatim as an `ask` record in your final message; main raises it (`metrics-leg.md` §2).

The script skips `entangled_tests`; you judge it in section 4.

## 2. Infer a layer map when none is declared

1. Look for a declared map first (layers config or architecture doc); if found, convert it to the format below with `source: declared` and skip inference.

2. Otherwise read the repo tree at the base ref (`git ls-tree -r --name-only <BASE>` and the imports in the files there), never the branch head.
   - [Why] A branch that adds an import must not be able to redraw the layers that judge it.

3. List the layers from outermost to innermost, as path globs. A layer may import itself and any layer after it, never one before it.

4. Write the map in CWD, never under `/tmp`, as `layers_inferred_<timestamp>.yaml`, with a plain Write:

```yaml
source: inferred, not declared
layers:
  - name: infra
    paths: ["infra/**"]
  - name: domain
    paths: ["domain/**"]
```

5. Pass that file to `--layers`. The script rejects any `source` value other than those two.

6. Link the saved file in your report, labelled "inferred, not declared".

## 3. Exception claims

A claimed exception says a function stays over its limit because splitting it reads worse.

For each claim you were given:

1. Judge the split diff the claim names.
   - Never regenerate it from the range diff, which holds only unsplit code.
   - A claim naming no saved split is rejected.

2. Rule whether the split reads worse.
   - Worse: the exception stands. List it as an exception, not a violation.
   - Better: the claim is rejected. List the function as an unfixed violation.

3. Give the evidence: helper names, what each hides, what a reader must jump between.

4. Write the rulings as a JSON list to `<RUN_DIR>/metrics-exceptions.json`, one object per claim with the keys `file`, `function`, `metric`, `diff_path`, `split_value`, `rejected`.
   - `rejected` is true for a rejected claim, false when the exception stands.
   - [Why] `build_verdict` in `quality_metrics/report.py` reads exactly these keys; a missing one makes the render exit 2.

5. Render the verdict, passing `--exceptions` only when you wrote that file:

```bash
~/.claude/scripts/render-metrics-verdict.py --report <RUN_DIR>/metrics-report.json \
  [--exceptions <RUN_DIR>/metrics-exceptions.json] --out-dir <RUN_DIR>
```

   - Exit 2 means bad input, nothing written: report a failed run.
   - Never hand-write that verdict.

## 4. Judgments whatever the exception count

Run these on every function the branch touches and every test it adds.

- **Hollow split**: a function split into helpers that exist only to lower a metric.
  - Signs: 1-line helpers, a once-called helper whose name restates its body.

- **Vacuous test**: a test that asserts nothing about the code under test's output or effect.

- **Entangled test**: a test holding 2 or more act-then-assert pairs on one test case. Count it by these rules:
  - A pair is one call to the code under test followed by an assertion on it.
  - A guard assertion that follows no call forms no pair.
  - A parametrized test, or a `for` loop over a table, counts each case or row as its own test.

- **Uncovered lines**: read the `Uncovered lines:` line of each coverage or CRAP entry.
  - Write one `[metrics]` finding per range, naming the input or branch that reaches it and the test that would cover it.
  - A defensive branch not worth a test gets its justification in the finding instead.

- **Duplication candidate**: a clone over its limit, listed as `### N. ...` entries under the rendered verdict's `## Duplication candidates (<n>)`. You rule each one.
  - Apply `code-standards`' rule "Extract a helper for 2-4 callsites only when extraction raises BOTH the readability and cognitive-load bars", reading the clone's code at every location.
  - Extract: write one `[metrics]` finding naming the clone's locations and the helper's intended name.
  - Leave: one line of reason in the judge file, no finding.

## 5. Opt-outs are proposals

When a metric fits a language badly, propose the opt-out in your report with the evidence.
- [Why] Only the human changes a limit or opt-out; the base-ref declaration is what counts.

## 6. Finding schema

Judge findings go to `<RUN_DIR>/metrics-judge_<timestamp>.md`. The rendered verdict owns exception rulings and script violations, so list neither here.

Write each finding under the heading shape the merge routes on:

```
### N. [SEVERITY][metrics] <title>
```

Under it, give the four parts `~/.claude/skills/code-review-pipeline/scripts/check-finding-bodies.py` requires: a `**[TAG]**` severity line matching the heading ordinal, the file, function and evidence (script record, diff, or quoted lines), a `**Suggestion**` line with the fix or opt-out, and a `**Trade-off of not doing it**` line.

Name the rendered metrics verdict and judge findings paths in your return message.
