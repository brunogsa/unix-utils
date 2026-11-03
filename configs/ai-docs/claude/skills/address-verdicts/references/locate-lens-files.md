# Locating the verdict files - every selection except marked mode

Loaded by `SKILL.md` §1 for every selection except marked mode.

```bash
ls -1 verdict_refactor_*.md verdict_auto-review_*.md verdict_test-sdd_*.md verdict_quality-gate_*.md 2>/dev/null
```

Several timestamped generations can exist per lens, possibly across branches. The filename is `verdict_<lens>_<branch>_YYYY-MM-DD_HH:MM.md`; `quality-gate` is one more lens.

A `verdict_quality-gate_*.md` counts as a source for both `refactor` and `auto-review`. Per lens, the newest source by modification time (`ls -t`, not a lexical sort) wins, never both:

- The newest merged file's findings tagged with that lens.
- Or the newest standalone `verdict_<lens>_*.md`, whichever was modified later.

Why: `/quality-gate` moves its own standalone files away, so an older one left in CWD would be worked beside the merged file. `test-sdd` has only standalone files.

- **Default**: the winning source of each lens. Under `all`, the merged file contributes only for the lenses it wins.

- **To work an older generation instead**: name its exact file path inside `<which ones>`.

- **A lens has no source at all**: proceed with the others, saying so in the closing report (§6). A lens only a merged file covers is not missing.
  - If `<which ones>` explicitly named it, stop instead - say no report exists for it.
  - Never fabricate one by re-running the reviewer.

- **No lens has any file**: stop with a clear message - nothing to address yet, run `/quality-gate` or a single lens (`/refactor`, `/auto-review`, `/test-sdd`) first.
