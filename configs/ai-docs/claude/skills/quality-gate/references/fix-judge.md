# Fix judge and fix review

The briefs and checks `SKILL.md` §4.2, §5.2 and §6.1 follow. Main pushes §1 and §4 into a dispatch and runs §2 and §3 itself.

## 1. The judge's brief

You are the Fix-or-Skip judge. You rule every in-scope finding of one merged verdict, and you change nothing else.

Inputs: the merged verdict's path (a top-level `verdict_*.md` in CWD, which `hooks/check-reviewer-writes.sh` lets a reviewer write) and `<BASE_REF>`.

- Load `code-standards` and `test-standards` through the Skill tool first. The global principles are already in your context.
- Read the code each entry cites, at HEAD.
- Rule only the entries `~/.claude/scripts/get-fix-apply-list.py <merged>` lists, never a scope you derive yourself.
- Append, as the last body lines of each in-scope entry, exactly one of:

  ```
  <previous body line>

  **Standards check**: Fix

  <previous body line>

  **Standards check**: Skip - "<shortest quoted rule>"; considered fix: <named fix>

  SKIPPED (judge ruled Skip)
  ```

  The `SKIPPED` line follows only a Skip.

- Put a blank line before `**Standards check**`, and another between it and `SKIPPED (judge ruled Skip)`.

  - The prose checker reads an unseparated line as a hard-wrapped continuation.

- Quote the rule's text and never name its file (`code-standards`, `CLAUDE.md`); the checker rejects a named source.
- No ruling at all counts as Fix.
- A metrics entry whose only fix games the metric is a Skip, quoting the metrics-lens rule that says so.

  - Gaming means a hollow split, a vacuous test or an entangled test.

- Only append: never edit, reorder or delete an existing line. One line per ruling.

## 2. The apply list

- Report-only: the numbers `~/.claude/scripts/get-test-sdd-dispatch-list.py <merged>` prints, nothing else.
- Auto-solve: that list plus the numbers `~/.claude/scripts/get-fix-apply-list.py <merged>` prints.
- Candidate, ranked, exception, deferred, tooling-ask and coverage-source sections never enter. A duplication candidate enters only through a judge finding that says to extract it.
- A Skip leaves a metrics violation open and counted in the verdict, so Skip softens no gate.

- An entry whose fix cannot clear the violation, or a rejected exception, stays open and is reported first.

## 3. Main's checks after the judge

None of these reads the merged file into main.

1. `diff <RUN_DIR>/pre-judge.md <merged> | grep -c '^<'` prints 0: no line was deleted or changed, headings included.
2. `~/.claude/scripts/get-fix-apply-list.py --check <merged>` exits 0.
3. The finding-body checker exits 0 on the `## Findings` slice, catching a stray line the judge appended:

   ``awk '/^[[:space:]]*[`][`][`]/{f=!f} !f && /^## Findings/{p=1} p' <merged> | ~/.claude/skills/code-review-pipeline/scripts/check-finding-bodies.py /dev/stdin``
4. A failed check: restore `pre-judge.md` over the merged file with `~/.claude/scripts/write-atomically.py`, then re-dispatch the judge once with the failure output.
   - Fails again: restore `pre-judge.md`, apply the report-only list (`test-sdd` only), and report `judge: FAIL (<reason>)`. The judge gets fixed, then `/quality-gate` re-runs.
   - No fallback apply of `refactor`, `auto-review` or `metrics` findings.

## 4. The fix review's brief

Inputs: the merged path; the applied SHAs; M, the merged file's finding count from `SKILL.md` §4.1's count awk. The SHAs come from:

```bash
awk '/^[[:space:]]*[`][`][`]/{f=!f} !f && /^APPLIED \(/{sub(/^APPLIED \(/,""); sub(/\).*/,""); print}' <merged>
```

The reviewer loads `code-standards` and `test-standards` via the Skill tool and runs `git show` on each SHA. It reviews for:

- regressions and standards breaks,
- metric gaming in metrics fixes (the metrics-lens judgments),
- test quality in `test-sdd` commits.

It writes `<RUN_DIR>/fix-review_<ts>.md` under `## Fix review (<n>)`, with headings `### N. [SEV][auto-review|refactor] <title>` numbered from M+1 and four-part bodies as [`merge-review-verdicts.md`](merge-review-verdicts.md) defines. Use `auto-review` when behavior changed and `refactor` when only structure changed. Never `test-sdd`, and never an untagged heading: `get-test-sdd-dispatch-list.py` reads an untagged heading as `test-sdd`.

Main then checks that `check-finding-bodies.py` exits 0 on that file and that §4.1's lens-tag awk prints 0 on it. Then it appends:

```bash
cat <merged> <RUN_DIR>/fix-review_<ts>.md | ~/.claude/scripts/write-atomically.py <merged>
```

`write-atomically.py` reads all of stdin before it replaces the file.

- No findings: append nothing, and §7 says "fix review: clean".
- A check fails: keep the file in `<RUN_DIR>`, append nothing, and report `fix review: FAIL (<reason>)`.

The fix review never applies: `## Fix review` is outside every apply script's sections and nothing after §6.1 applies, so the run cannot loop. The human may tag a fix-review finding `[AI!]` for a later `/address-verdicts`.
