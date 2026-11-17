# Locating the verdict files - every selection except marked mode

Loaded by `SKILL.md` §1 for every selection except marked mode.

```bash
ls -1 verdict_refactor_*.md verdict_auto-review_*.md verdict_test-sdd_*.md verdict_quality-gate_*.md verdict_metrics_*.md 2>/dev/null
```

Several timestamped generations can exist per lens, possibly across branches. The filename is `verdict_<lens>_<branch>_YYYY-MM-DD_HH:MM.md`; `quality-gate` is one more lens.

A `verdict_quality-gate_*.md` counts as a source for all five lenses: `refactor`, `auto-review`, `test-sdd`, `metrics` and `scout`. Per lens, the newest source by modification time (`ls -t`, not a lexical sort) wins, never both:

- The newest merged file's findings tagged with that lens - the `[test-sdd]`, `[metrics]` and `[scout]` entries included.
- Or the newest standalone `verdict_<lens>_*.md`, whichever was modified later.

Why: `/quality-gate` moves its own standalone files away, so an older one left in CWD would be worked beside the merged file. Only `/test-sdd` run alone writes a standalone `test-sdd` file, which is the fallback for that lens.

A standalone `metrics` verdict exists only on quality-gate's merge-fail fallback, where its section 4.1 moves the rendered metrics verdict and the judge file `metrics-judge_<ts>.md` back into CWD.

The rendered verdict holds no fix: its numbered deferred, tooling-ask and exception entries carry no severity tag, and its raw records are unnumbered bullets. The fixes are the judge file's `[SEV][metrics]` findings, each citing its record keys; a judge dismissal is its Skip for a raw record. The listing above does not glob the judge file.

The `scout` lens has no standalone source: on that fallback `scout-leg_<ts>.md` stays in quality-gate's `<RUN_DIR>`, and its tasks stay pending for the next gate run.

- **Default**: the winning source of each lens. Under `all`, the merged file contributes only for the lenses it wins.

- **To work an older generation instead**: name its exact file path inside `<which ones>`.

- **A lens has no source at all**: proceed with the others, saying so in the closing report (§6). A lens only a merged file covers is not missing.
  - If `<which ones>` explicitly named it, stop instead - say no report exists for it.
  - Never fabricate one by re-running the reviewer.

- **No lens has any file**: stop with a clear message - nothing to address yet, run `/quality-gate` or a single lens (`/refactor`, `/auto-review`, `/test-sdd`) first.
