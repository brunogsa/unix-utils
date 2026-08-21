# Step 0 pre-flight interview — candidate questions

Loaded by main at Step 0, before any other step. Run `git status --porcelain` and probe for lint/test runners with 1c's table (read-only — run nothing yet). Then
ask via **one `AskUserQuestion` call**, only the questions whose condition holds — never a freeform chat message.

Each option gets a `description` (what picking it does) and a `preview` (the detail behind "what you mean" — dirty-file list, runner candidates, what the gate runs) so
the user checks detail without a round trip. Recommended option always first, labeled "(Recommended)".

Candidate questions, in priority order (only those whose condition holds are sent):

| # | Header | Condition | Question | Options (default first) |
|---|---|---|---|---|
| 1 | `Dirty tree` | `git status --porcelain` printed output | "Working tree has uncommitted changes — what should I do before clustering?" | **Commit now (Rec.)** — commit via `commit-standards`, then continue / **Stop here** — abort so you commit/stash by hand, re-run. Both preview the dirty file list. |
| 2 | `Baseline` | always | "Record a lint+test baseline before any cluster edit, to catch pre-existing breakage?" | **No — skip (Rec.)** — faster, only worth it if the repo might already be red; preview: "1c skipped, step 5 still runs whatever gate you pick" / **Yes — capture baseline** — runs 1c's probe now, aborts if red; preview: 1c's runner table from `opt-in-gates.md`. |
| 3 | `Checker cmd` | 1c's table matched multiple markers or none | "Which lint/test commands should establish the baseline?" | One option per matched candidate (or best guess when none matched), each previewing its exact command; "Other" always lets the user type a custom command. Sent regardless of Q2's answer, consumed only if Q2 is "Yes". |
| 4 | `Green gate` | always | "Run the repo's full lint+test suite before the first cluster edit and again before push, fixing any batch-caused regression?" | **No — skip (Rec.)** — faster; preview: "step 5 goes straight from commits to step 6's push" / **Yes — gate on green** — blocks push until green, pre-existing red reported never fixed; preview: gate mechanics from `opt-in-gates.md`. |
| 5 | `Tails` | always | "After pushing, run the refactor + auto-review tail pair over this batch's commit range?" | **No — skip (Rec.)** — stop at step 8's report / **Yes — run tails** — dispatches the shared code-reviewer tail pair, report-only; preview: `code-reviewer-tail-pair.md`'s scope. |

`AskUserQuestion` caps at 4 per call. Rows 1+2+4+5 already fill 4 slots when the tree is dirty — then send row 3 (if its condition holds) as an
immediate second call, before doing anything else. Otherwise everything fits in one call.

Persist the answers the moment they arrive; steps 1b–1d consume them and never ask again.
