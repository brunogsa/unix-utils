---
name: address-verdicts
description: "Apply findings from verdict_refactor_*.md / verdict_auto-review_*.md / verdict_test-sdd_*.md, annotating each APPLIED/SKIPPED in place. Trigger: /address-verdicts <which ones>, \"address the verdicts\", \"apply the review findings\", \"work through the refactor verdict\"."
disable-model-invocation: false
---

## Usage

```
/address-verdicts <which ones> [--no-ask] [--test-cmd <cmd>]
```

`<which ones>` selects which findings to work. It matches, in this order:

- `all` — every finding in every located verdict file. Default when the arg is empty.
- A lens name, `refactor`, `auto-review`, or `test-sdd` — every finding in that lens's file only.
- A severity floor, e.g. `high` or `high+` — every finding at or above it.
  - Only when the report actually labels severity; see §2 for when it doesn't.

- An explicit list of finding identifiers — numbers, titles, or file:line, exactly as the report names them.
  - A verdict file path inside the list pins that exact generation, instead of §1's newest-per-lens default.

`--no-ask` and `--test-cmd` exist for a skill caller, which has no human standing by to answer mid-run. Both are ignored on a human invocation.

- `--no-ask` — never prompt. Any ambiguity §2 would have asked about becomes a `SKIPPED` finding with the ambiguity as its reason.
- `--test-cmd <cmd>` — the repo's test command, supplied rather than inferred, so §2 has nothing left to ask about.

## What this is

This is **the** apply step for any `verdict_*.md` on disk, whichever lens wrote it: `/refactor`, `/auto-review`, `/test-sdd`, or a `/quality-gate` run that produced all three.

It is the only place the apply loop lives.
`/quality-gate --auto-solve` decides *which* findings are worth applying and calls this skill to apply them.
The routing, commit, and annotation rules have one home rather than a copy per caller.

Two ways in, and the difference is only who picks the findings:

- **A human invokes it** — `<which ones>` is the selection, and §2 may ask a clarifying question.
- **A skill invokes it** — the caller passes an explicit finding list plus `--no-ask`, having already triaged. Nothing prompts.

This skill is a standalone entry point either way.
It discovers the verdict files itself, in a fresh session, whether or not `/implement` ran first.

It never re-runs either reviewer. It only consumes reports already on disk.

A finding you don't select stays untouched and un-annotated.
The report keeps no record it was even considered.

## 1. Locate the verdict files

```bash
ls -1 verdict_refactor_*.md verdict_auto-review_*.md verdict_test-sdd_*.md 2>/dev/null
```

Several timestamped generations can exist per lens — e.g. two `verdict_refactor_*.md` files from different runs.
The timestamp is embedded in the filename (`verdict_<lens>_YYYY-MM-DD_HH:MM.md`), so it sorts lexically.

- **Default**: the newest generation of each lens — the last name after a sort.
- **To work an older generation instead**: name its exact file path inside `<which ones>`.
- **A lens has no file at all**: proceed with the lens that does have one.
  - Say so plainly in the closing report (§6).
  - If `<which ones>` explicitly named the missing lens, stop instead — say no report exists for it.
  - Never fabricate one by re-running the reviewer; that isn't this skill's job.

- **No lens has any file**: stop with a clear message.
  - There is nothing to address yet — run `/quality-gate`, or a single lens (`/refactor`, `/auto-review`, `/test-sdd`), first.

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

**Under `--no-ask`, nothing above prompts.** Each ambiguity resolves to `SKIPPED (<the ambiguity>)` on that finding, and the run continues with the rest.

Skipping beats guessing here because the caller can re-run the finding by hand once it reads the ledger, whereas a wrong guess lands a commit nobody asked for.
A missing test command under `--no-ask` skips only the findings that need one — refactor-lens findings still apply, since the `refactor` agent brings its own green-before-and-after check.

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

- **Auto-review- or test-sdd-lens finding** (from `verdict_auto-review_*.md` / `verdict_test-sdd_*.md`):
  - `agent(subAgent=tdd-coder, title=Apply <lens> finding: <finding>)`.
  - Strict TDD: RED before GREEN, same as any other `tdd-coder` dispatch.
  - A test-sdd finding names a planned test the repo lacks, so writing that test IS the fix.
    Pass the planned title verbatim so the test lands under the name the plan declared.

Why the split: the `refactor` agent refuses any behavior change, by design.
A correctness fix or a missing test can't route through it — both need `tdd-coder`'s test-first discipline instead.

Verify each subagent's result against the artifacts — the diff, the test run — before trusting its "done."
A subagent's summary describes intent; only the artifact shows what actually landed.

Then commit, one commit per finding, before starting the next:

- `tdd-coder` commits its own work under `commit-standards` — confirm the SHA exists rather than re-committing.
- The `refactor` agent leaves its change uncommitted by design, so commit it here, in this session, where the permission prompt can render.

A finding whose apply failed or was reverted is recorded as failed, never as done, and never gets a commit.

## 5. Annotate the verdict file, the moment each finding lands

Write the outcome in place, next to that finding — never batched to the end of the run. Two marks per finding, and they do different jobs:

- **In the finding's heading**, a `[Done]` prefix right after the number, before any severity tag: `### 1. [Done][HIGH] <title>`.
  - Same prefix-after-the-number convention `/implement` uses on plan task headings, so one rule covers both surfaces.
  - This one is the machine-checkable mark: it makes a re-run skip what already landed, and `grep` count it.

- **In the finding's body**, the outcome and its evidence:
  - `APPLIED (<sha>)` — the fix commit's SHA. Pairs with a `[Done]` heading.
  - `SKIPPED (<reason>)` — why it wasn't applied. The heading stays unmarked, so a re-run reconsiders it.

This is the durable, on-disk ledger of fixed-versus-deferred the user explicitly asked for.

The heading marker alone can't say *why* or point at the fix, and the body line alone isn't greppable.
A skipped finding then reads as unfinished from either surface, which is what a re-run needs.

Annotating as you go means a killed session still leaves an accurate ledger.
Batching it to the end would leave a pile of applied fixes with no record of which report entries they answer.

## 6. Close with a report

List: applied findings (with SHA), skipped findings (with reason), and anything that failed to apply — with exactly what it needs to retry.

State plainly, every time:

- Every finding not selected in §2 is untouched and carries no annotation.
- This run never re-ran either reviewer — it only consumed their existing reports.

Invoked by a skill, hand that same list back to the caller rather than only printing it.
The caller composes the closing report the human actually reads, and can only name what it was told.

## Flowchart (human-facing)

[`assets/flowchart.md`](assets/flowchart.md) diagrams this skill's flow for the human. Don't load it — non-authoritative, the steps above win; regenerate it whenever the flow changes.
