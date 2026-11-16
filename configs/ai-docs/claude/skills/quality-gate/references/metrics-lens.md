# Metrics Lens

The prompt a `code-reviewer` follows when dispatched with the `metrics` lens. You are a fresh-context judge, not the code's author, so the rulings below are yours and never the author's.

You report only. Never edit a source file, the declaration `configs/ai-docs/claude/scripts/quality-metrics.yaml`, or a limit.

## 1. Run the script

Run `configs/ai-docs/claude/scripts/measure-quality-metrics.py` once, from the repo root, over the range you were given:

```bash
configs/ai-docs/claude/scripts/measure-quality-metrics.py \
  --diff <BASE>...<HEAD> --layers <layer-map-file>
```

- `--diff BASE...HEAD` measures every declared metric on the code the committed range changes, and lists the over-limit functions the range removes as resolved.
  - It cannot combine with `--files` or `--per-unit`.

- `--files FILE...` measures whole files with no git diff; use it only when you were handed files and no range.

- `--layers FILE` is the layer map the dependency check reads. Without it only import cycles are checked, so always pass one (section 2).

- `--declaration FILE` names another declaration; leave it at the default.

- Exit 0 is clean, 1 is a violation, 2 means the run did not measure: read stderr, report the failure, and never read exit 2 as a pass.

Read the JSON it prints: `measurements`, `violations`, `gate_input_violations`, `resolved`, `unclaimed_files`.

The script skips `entangled_tests` by design, so its absence from the output means nothing. You judge it in section 4.

## 2. Infer a layer map when none is declared

A repo with no declared layers still gets layer checks, because you infer the map.

1. Look for a declared map first (the repo's own layers config or architecture doc). If one exists, convert it to the map format below with `source: declared` and skip inference.

2. Otherwise read the repo tree at the base ref (`git ls-tree -r --name-only <BASE>` and the imports in the files there), never the branch head.
   - [Why] A branch that adds an import must not be able to redraw the layers that judge it.

3. List the layers from outermost to innermost, as path globs. A layer may import itself and any layer after it, never one before it.

4. Save the map in CWD, never under `/tmp`, as `layers_inferred_<timestamp>.yaml`, through `configs/ai-docs/claude/scripts/write-atomically.py` (the reviewer write guard denies a direct Write of this name):

```bash
configs/ai-docs/claude/scripts/write-atomically.py layers_inferred_<timestamp>.yaml <<'EOF'
source: inferred, not declared
layers:
  - name: infra
    paths: ["infra/**"]
  - name: domain
    paths: ["domain/**"]
EOF
```

5. Pass that file to `--layers`. The `source` line must read exactly `inferred, not declared`; the script rejects any other label.

6. Link the saved file in your report, labelled "inferred, not declared".

## 3. Exception claims

A claimed exception says a function stays over its limit because splitting it reads worse. The author never rules on that.

For each claim you were given:

1. Save the split the author tried as `split_<function>_<timestamp>.diff` in CWD, linked from your report, never under `/tmp`:

```bash
git diff <BASE>...<HEAD> -- <file> | configs/ai-docs/claude/scripts/write-atomically.py split_<function>_<timestamp>.diff
```

2. Read the split and rule whether it reads worse than the unsplit function.
   - Worse: the exception stands. List it as an exception, not a violation.
   - Better: the claim is rejected. List the function as an unfixed violation.

3. Give the evidence for the ruling: the helper names, what each hides, and what a reader must jump between.

## 4. Judgments whatever the exception count

Run these on every function the branch touches and every test it adds, even when no exception was claimed.

- **Hollow split**: a function split into helpers that exist only to lower a metric.
  - Signs are 1-line helpers, and a helper called once whose name restates its body.

- **Vacuous test**: a test that asserts nothing about the code under test's output or effect, so it passes whatever the code does.

- **Entangled test**: a test holding 2 or more act-then-assert pairs on one test case. Count it by these rules:
  - A parametrized or table-driven test counts each case as its own test, so 3 cases each calling once then asserting is 3 clean tests.
  - A hand-written `for` loop over a table counts the same way, one test per row.
  - A pair is one call to the code under test followed by an assertion on it.
  - A guard assertion that follows no call, such as a fixture being non-empty, forms no pair.
  - A plain test calling twice and asserting after each call has 2 pairs and is entangled.

## 5. Opt-outs are proposals

When a metric fits a language badly, propose the opt-out in your report with the evidence. Never edit `quality-metrics.yaml` or any limit.
- [Why] Only the human changes a limit or an opt-out; the declaration is read as committed at the base ref, so an edit would not count anyway.

## 6. Finding schema

Write each finding under the heading shape the merge step routes on:

```
### N. [SEVERITY][metrics] <title>
```

Under it, give the file and function, the evidence (script record, diff, or quoted lines), and the proposed fix or opt-out.

Report in this order:
- the saved layer map link labelled "inferred, not declared", when you inferred one
- exception rulings, each with its split diff link
- script violations, worst first
- hollow splits, vacuous tests and entangled tests
- proposed opt-outs, marked as proposals
