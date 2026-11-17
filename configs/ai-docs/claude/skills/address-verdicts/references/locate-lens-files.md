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

A standalone `metrics` verdict exists only on quality-gate's merge-fail fallback, where its section 4.1 moves the rendered metrics verdict back into CWD; its rendered entries carry no severity tag.

A standalone `scout` source likewise exists only on that fallback, as `scout-leg_<ts>.md` in CWD (never `verdict_`-prefixed, so marked mode's `verdict_scouts*.md` glob misses it); add it to the `ls` above only then.

- **Default**: the winning source of each lens. Under `all`, the merged file contributes only for the lenses it wins.

- **To work an older generation instead**: name its exact file path inside `<which ones>`.

- **A lens has no source at all**: proceed with the others, saying so in the closing report (§6). A lens only a merged file covers is not missing.
  - If `<which ones>` explicitly named it, stop instead - say no report exists for it.
  - Never fabricate one by re-running the reviewer.

- **No lens has any file**: stop with a clear message - nothing to address yet, run `/quality-gate` or a single lens (`/refactor`, `/auto-review`, `/test-sdd`) first.
