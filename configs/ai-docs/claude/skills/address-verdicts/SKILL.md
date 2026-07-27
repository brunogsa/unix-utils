---
name: address-verdicts
description: "Apply findings from verdict_refactor_*.md / verdict_auto-review_*.md, annotating each APPLIED/SKIPPED in place. Trigger: /address-verdicts <which ones>, \"address the verdicts\", \"apply the review findings\", \"work through the refactor verdict\"."
disable-model-invocation: false
---

## Usage

```
/address-verdicts <which ones>
```

`<which ones>` selects which findings to work. It matches, in this order:

- `all` — every finding in every located verdict file. Default when the arg is empty.
- A lens name, `refactor` or `auto-review` — every finding in that lens's file only.
- A severity floor, e.g. `high` or `high+` — every finding at or above it.
  - Only when the report actually labels severity; see §2 for when it doesn't.

- An explicit list of finding identifiers — numbers, titles, or file:line, exactly as the report names them.

## What this is

This is the apply step for the reports the deep-reviewer tail pair produces.

That pair is shared: `/implement`'s batch-end review, `/refactor`, and `/auto-review` all dispatch it.

`/implement` never applies a finding itself — it triages, presents, and stops, leaving the reports on disk.

It doesn't know this skill exists, and shouldn't.
Deciding to act on a review verdict is the human's call, so the apply step is something you invoke — never something a batch triggers on its own.

This skill is a standalone entry point.
It discovers the verdict files itself, in a fresh session, whether or not `/implement` ran first.

It never re-runs either reviewer. It only consumes reports already on disk.

A finding you don't select stays untouched and un-annotated.
The report keeps no record it was even considered.

## 1. Locate the verdict files

```bash
ls -1 verdict_refactor_*.md verdict_auto-review_*.md 2>/dev/null
```

Several timestamped generations can exist per lens — e.g. two `verdict_refactor_*.md` files from different runs.
The timestamp is embedded in the filename (`verdict_<lens>_YYYY-MM-DD_HH:MM.md`), so it sorts lexically.

- **Default**: the newest generation of each lens — the last name after a sort.
- **To work an older generation instead**: name its exact file path inside `<which ones>`.
- **A lens has no file at all**: proceed with the lens that does have one.
  - Say so plainly in the closing report (§6).
  - If `<which ones>` explicitly named the missing lens, stop instead — say no report exists for it.
  - Never fabricate one by re-running the reviewer; that isn't this skill's job.

- **Neither lens has any file**: stop with a clear message.
  - There is nothing to address yet — run `/refactor`, `/auto-review`, or `/implement`'s batch-end tails first.

## 2. Resolve `<which ones>`, and the test command

Match the arg against §1's located files, using the rules under Usage above.

Ask ONE clarifying question, with your recommended reading, on any of these:

- An identifier that matches more than one finding.
- A severity floor the report doesn't actually label.
- A lens name that looks like a typo.

Never guess past an ambiguity like these — a wrong guess silently works the wrong finding.

Applying an auto-review-lens finding also needs a test command, to run RED-then-GREEN (§4).

Infer it first: a `package.json` test script, a Makefile target, the repo's own CLAUDE.md.
Ask only when it can't be inferred — bundle that ask into §2's clarifying question if one already fires, otherwise ask it alone.

## 3. Seed the whole TaskList upfront

Before applying anything, create one entry per selected finding, in the order they will execute.

The list is this run's whole timeline — nothing appears later, out of order, as it becomes relevant.

```
 <id>. [#<returned-id>][Task] Apply <lens> finding: <short finding description>
```

Mark the first entry `in_progress`, every other one `pending`.

Add one closing `[Reminder]` entry for the final report (§6) — it survives even if the session compacts mid-run, so the wrap-up step can't get silently skipped.

## 4. Apply each finding via a pinned subagent

Dispatch one subagent per finding, in the order seeded above:

- **Refactor-lens finding** (from `verdict_refactor_*.md`):
  - `agent(subAgent=refactor, title=Apply refactor finding: <finding>)`.
  - Pass it the finding's scope and the test command from §2.
  - It applies the change itself and confirms tests are green before and after.

- **Auto-review-lens finding** (from `verdict_auto-review_*.md`):
  - `agent(subAgent=tdd-coder, title=Apply review finding: <finding>)`.
  - Strict TDD: RED before GREEN, same as any other `tdd-coder` dispatch.

Why the split: the `refactor` agent refuses any behavior change, by design.
A correctness fix can't route through it — it needs `tdd-coder`'s test-first discipline instead.

Verify each subagent's result against the artifacts — the diff, the test run — before trusting its "done."
A subagent's summary describes intent; only the artifact shows what actually landed.

## 5. Annotate the verdict file, the moment each finding lands

Write the outcome in place, next to that finding — never batched to the end of the run:

- `APPLIED (<sha>)` — the fix commit's SHA.
- `SKIPPED (<reason>)` — why it wasn't applied.

This is the durable, on-disk ledger of fixed-versus-deferred the user explicitly asked for.

Annotating as you go means a killed session still leaves an accurate ledger.
Batching it to the end would leave a pile of applied fixes with no record of which report entries they answer.

## 6. Close with a report

List: applied findings (with SHA), skipped findings (with reason), and anything that failed to apply — with exactly what it needs to retry.

State plainly, every time:

- Every finding not selected in §2 is untouched and carries no annotation.
- This run never re-ran either reviewer — it only consumed their existing reports.
