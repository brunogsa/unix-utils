---
name: quality-gate
description: "USE to run the full quality sweep over a branch — refactor lens, auto-review, and planned-test presence — in parallel, then optionally auto-solve the findings. Triggers: /quality-gate, 'run the quality gate', 'full review pass', or another skill's batch-end dispatch."
disable-model-invocation: false
words-budget: 2048
---

# Quality Gate

Run every review lens this setup has over one branch, in parallel, then either hand the reports to the human or apply what is safely applicable.

Three legs, each a fresh-context reviewer writing its own timestamped verdict file in CWD:

| Leg | Lens | Verdict file |
|---|---|---|
| `refactor` | structure, duplication, dead code, naming | `verdict_refactor_<ts>.md` |
| `auto-review` | correctness, edge cases, contract and spec conformance | `verdict_auto-review_<ts>.md` |
| `test-sdd` | planned tests the plan declared but the repo lacks | `verdict_test-sdd_<ts>.md` |

The third leg runs only when a plan resolves — without a plan there are no planned tests to check.

## Usage

```
/quality-gate [spec] [plan] [--tasks <ids>] [--auto-solve]
```

- `spec` / `plan` — paths, in either order; each is recognised by its `spec_`/`plan_` filename prefix, so position never decides which is which. Omit either to discover it in CWD.

- `--tasks <ids>` — comma-list of plan task ids, `1,2,5`, forwarded to the `test-sdd` leg to narrow its scope. Omitted, that leg checks every task in the plan.

- `--auto-solve` — skip the opening interview and go straight to applying findings.

Examples:

- `/quality-gate` — discover spec and plan in CWD, ask before applying anything.
- `/quality-gate spec_itgd-3374.md plan_itgd-3374.md --auto-solve` — explicit paths, apply without asking.
- `/quality-gate --tasks 1,2 --auto-solve` — check only tasks 1 and 2 for planned tests; used by `/implement` to scope the leg to its own batch.

## When to invoke

Direct `/quality-gate` invocation, phrases like "run the quality gate" / "full review pass" / "review and fix what's safe", or dispatch from another skill's flow.
`/implement`'s batch-end tail runs this with `--auto-solve`.

## 1. Ask about auto-solve — first, before anything else

**Skip this step entirely when `--auto-solve` was passed.** The flag is the answer.

Otherwise ask one `AskUserQuestion`, before resolving files or dispatching anything:

- **Report only** (recommended default) — the three verdict files land in CWD and the run stops. The human decides later, by hand or via `/address-verdicts`.

- **Auto-solve** — after the reports land, this session triages them and applies the findings it judges safe, one commit each.

Ask first rather than after the reports, so a human who wanted only a report is never surprised by commits, and one who wanted fixes never has to re-invoke.

## 2. Resolve the spec and the plan

Use any path given in the arguments as-is. For each of `spec` and `plan` not given, glob CWD, top-level only:

```bash
ls -1 spec_*.md plan_*.md 2>/dev/null
```

- **Exactly one spec and one plan** → use both; print the resolved paths, no prompt.
- **Zero of a kind** → proceed without it, and say so plainly.
  - No spec: the `auto-review` leg runs without spec-conformance context.
  - No plan: the `test-sdd` leg does not run at all, and the run has two legs instead of three.

- **More than one of a kind** → prompt with a numbered list and let the user pick; never guess which spec or plan was meant.

Also resolve `<BASE_BRANCH>` for the `auto-review` leg:

```bash
git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's|refs/remotes/origin/||'
```

If detection fails, ask which branch to diff against rather than guessing. A caller dispatching this skill may pass its own base ref instead — `/implement` passes `BATCH_BASE_SHA`.

## 3. Dispatch the legs in parallel

Spawn every leg as `agent(subAgent=deep-reviewer, …)`, all in the **same turn**, all in the background. They are independent report-only passes with no ordering dependency.

- `agent(subAgent=deep-reviewer, title=Refactor-lens review)` — reads `~/.claude/skills/refactor/SKILL.md` and executes it.
- `agent(subAgent=deep-reviewer, title=Auto-review pipeline)` — reads `~/.claude/skills/auto-review/SKILL.md` and orchestrates from there, with `<BASE_BRANCH>` and the resolved spec/plan paths pushed in so it needs no interactive resolution.

- `agent(subAgent=deep-reviewer, title=Planned-test presence check)` — reads `~/.claude/skills/test-sdd/SKILL.md` and executes it, with the resolved plan path and any `--tasks` ids pushed in. Only when a plan resolved.

**Each leg performs its skill's reviewer role itself and never spawns a nested reviewer.**
The leg already *is* the fresh-context reviewer those skills would otherwise dispatch.
Nesting would buy a second opinion nobody asked for and spend the harness's only remaining nesting level.

Tell each leg this explicitly in its prompt — the skills it reads describe dispatching a reviewer, and without the override it would follow that literally.

Every leg mints its own `verdict_*.md` timestamp per its own skill, so repeated runs accumulate rather than collide.

The `deep-reviewer-write-guard.sh` hook backs the report-only contract at the tool layer: a write to a `verdict_*.md` basename is auto-approved, everything else denied.

## 4. Collect the reports

When each leg returns, confirm its verdict file exists in CWD and is non-empty. Record the three resolved paths.

- **A leg's file is missing or empty** → re-dispatch that leg once. Still missing → flag it in the summary, let the other legs' reports stand, and move on.

- **Never report from a leg's return message.** Return messages are capped and truncate long finding lists; the file is the source of truth.

- **Never retry more than once.** A leg that fails twice is for the human to look at, not for a retry loop to grind on.

## 5. Report-only run — stop here

When step 1 resolved to report-only, print a compact index and stop:

- One section per leg: its verdict file path and its finding count.
- One line per finding: `<lens> #N [severity] <file>:<lines> — <one-line title>`.
- The closing line: findings are applied by `/address-verdicts`, or by re-running `/quality-gate --auto-solve`.

**Nothing is applied on a report-only run**, including findings that look trivially safe. The opt-in came from step 1, and its absence is an answer.

## 6. Auto-solve — triage, then apply one finding at a time

Entry: step 1 resolved to auto-solve, or `--auto-solve` was passed.

### 6.1. Decide which findings are addressable

Read all three verdict files **in full** — not the return summaries — and sort every finding into addressable or not.

- **Addressable** — small, well-scoped, clearly evidenced, low blast radius: a missing planned test, a local simplification, a correctness fix with an obvious forcing case.
- **Not addressable** — design tradeoffs, cross-cutting risk, anything a leg flagged as uncertain, anything whose fix needs a product decision.

Print the accepted list before applying anything, one line per finding with the reason it was accepted, and the rejected list with the reason it was not.
The relevance call is judgment, so it gets shown, not just its result.

### 6.2. Seed the whole TaskList upfront

Create one entry per addressable finding, in execution order, before applying any of them — the list is this run's whole timeline.

```
 <id>. [#<returned-id>][Task] Apply <lens> finding <N>: <short description>
```

Give each entry a breadcrumb naming its three sub-steps: dispatch the apply agent, commit, mark `[Done]` on the finding.

Close with one `[Reminder]` entry for the final report (§7), so a mid-run compaction cannot silently drop the wrap-up.

### 6.3. Work each finding, in series

One finding at a time, in the seeded order. Serial, never parallel: two agents editing overlapping scope produce a conflict neither can see.

1. **`TaskUpdate` the entry to `in_progress`.**

2. **Dispatch the apply agent**, routed by the finding's lens:
   - **Refactor lens** → `agent(subAgent=refactor, title=Apply refactor finding <N>: <short>)`, given the finding's scope and the repo's test command.
   - **Auto-review or test-sdd lens** → `agent(subAgent=tdd-coder, title=Apply <lens> finding <N>: <short>)`, which writes the test RED before making it GREEN.

   Why the split: the `refactor` agent refuses behavior changes by design, so a correctness fix or a missing test routed through it could never land.
   And a pure structural finding has no failing test for `tdd-coder` to start from.

3. **Verify against the artifacts** — read the diff and the agent's test output.
   A summary describes intent; only the artifact shows what landed.
   A failed or reverted apply is recorded as such, never as done.

4. **Commit.** `tdd-coder` commits its own work under `commit-standards`; confirm the SHA exists.
   The `refactor` agent leaves its change uncommitted, so commit it here, in this session, where the permission prompt can render.

5. **Mark the finding `[Done]` in its verdict file, immediately** — insert the marker right after the finding's number, before any severity tag: `### 1. [Done][HIGH] <title>`.
   - Same prefix-after-the-number convention `/implement` uses on plan task headings, so one rule covers both surfaces.
   - Write it the moment the commit lands, never batched to the end. A killed session then still leaves an accurate ledger of what was fixed.

6. **`TaskUpdate` the entry to `completed`**, and move to the next finding.

A finding whose apply fails keeps its entry open, gets no `[Done]` marker, and is reported in §7 with exactly what it needs to retry.

## 7. Close with a report

- The three verdict file paths, plus any leg that failed to produce one.
- Applied findings, each with its commit SHA.
- Findings judged not addressable, each with the reason — they stay unmarked in their verdict files.

- Findings whose apply failed, each with what it needs to retry.
- The plain statement that unmarked findings are untouched, and that `/address-verdicts` is how they get worked later.

## Flowchart (human-facing)

[`assets/flowchart.md`](assets/flowchart.md) diagrams this skill's flow for the human. Don't load it — non-authoritative, the steps above win; regenerate it whenever the flow changes.
