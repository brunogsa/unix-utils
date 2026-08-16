---
name: code-review-pipeline
description: "Shared reviewer orchestrator for /auto-review (local) and /pr-review (GitHub). Local always dispatches an isolated subagent for bias isolation; GitHub runs inline by default. USE only via those callers — not directly."
user-invocable: false
---

# Reviewer Agent

You orchestrate a 7-wave code review pipeline (Waves 0-6) shared by both
modes — only Waves 1 and 5 differ fully.

**Architecture.** The orchestrator runs in one session — the caller's own or an isolated subagent, per "How callers dispatch" below — and every wave, including Wave 2, runs inside it.

Wave 2 used to fan out into eight concurrent `review-specialist` agents, one per rubric, because a serial single-context pass measured ~100k resident tokens median / 157k p90. This skill now accepts that resident-context cost instead of paying for eight separate base contexts — the fan-out traded token cost for context growth, and token cost is the constraint this rewrite optimizes for.

**Compaction resilience.** Waves 2–4 persist their output to `$work_dir` as they complete (see each wave's "Resume check" / "Persist" notes).
After a mid-pipeline compaction, re-read this SKILL.md, then load `$work_dir`'s furthest-along wave/step output instead of redoing that work.

Rubric prompts and validator rubric live in `references/`; bash glue in `scripts/`.

## How callers dispatch

`/auto-review` (local) and `/pr-review` (github) each resolve their own input header, then hand execution to this pipeline.

**Dispatch rule — auto-decided.** The mode already determines whether the calling session is biased, so never ask the user:

- `Mode: local` (`/auto-review`) → **always dispatch isolated** (subagent path below) — it runs in the session that produced the diff, so CLAUDE.md's fresh-context-subagent rule applies.

- `Mode: github` (`/pr-review`) → **runs inline by default** — review happens after the code landed, so the calling session did not write the diff.
  - `--isolate` still forces the isolated path when explicitly passed.

  - `/pr-review`'s live `review-isolation` A/B also sends roughly half of all github runs down the isolated path by PR-number parity, passing no `--isolate` — see its own A/B section.

**Order:** mode first, then isolate-or-inline, then the chosen run parses the full input header below.

**Inline — `Mode: github` without `--isolate`:** Read this SKILL.md and walk every wave (0 → 6) yourself, treating the resolved inputs as the "Parse the input header" step below.

This path also owns the one TaskList write the pipeline makes: Wave 5 files its density `[Scout]` entries here, where an isolated run can only report them upward.

See [`wave5-emit-github.md`](./references/wave5-emit-github.md) step 2.

**Isolated — `Mode: local`, or `--isolate` passed:** Spawn one `agent(subAgent=general-purpose, title=Run code-review pipeline, model=sonnet)`, unless the caller pins its own wrapper — `/auto-review` does.

Put the resolved inputs in its prompt body and tell it to read this SKILL.md and orchestrate from there; the user sees only its final summary.

Whatever Wave 5's doc-standards check flagged comes back in that summary's doc-standards-flags block, and this calling session files the `[Scout]` each offending file earns.

The sonnet pin covers the github isolated path — an accepted cost/depth tradeoff.

`Mode: local` never reaches it: `/auto-review`, the sole local caller, pins `code-reviewer` (opus) instead, because review judgment is the product it ships (see `auto-review/SKILL.md`).

## Before you start

**Parse the input header:**

- `Mode`: `github` or `local`
- `PR URL` (github only)
- `Jira URL` (github, optional)
- `Base ref` (local only; a branch name, commit SHA, or `HEAD~N` — defaults to the repo's detected default branch)
- `Language`: `Portuguese (Brazil)` (github) or `English` (local)

**Load lazily, by wave; keep loaded after.** They ground your own validation and emit decisions:

1. Read `~/.claude/skills/code-review-pipeline/references/review-principles.md` + `review-checklists.md` (Wave 0+)
2. Invoke `doc-standards` via the Skill tool (Wave 5's density check)

Invoke that standard via Skill, never Read — CLAUDE.md's Skill-tool-over-Read rule (meta-work only).

You no longer load `code-standards`, `test-standards`, the rubric files, or the changed files' `CLAUDE.md` here — Wave 2 loads them itself, once, when it runs.

Carrying all of them here meant every later wave re-read all of them on every turn, for material only Wave 2 ever used.

Wave 2 never hits GitHub or any external system — pre-built Wave 1 context only, keeping review reproducible and idempotent.

---

## Wave 0 — Early-exit guard

Deterministic check; no subagent needed. Only aborts on hard no-ops.

- **github**: run the closed/merged guard and the prior-review guard from [`references/wave0-github-guards.md`](./references/wave0-github-guards.md) — abort per its stop conditions.

- **local**: always proceed — Wave 0 is a no-op here (both guards are github-only). Empty diffs surface naturally — Wave 5 writes "auto-review: no findings".

---

## Wave 1 — Context prep

Assemble everything Wave 2 needs on disk from GitHub PR or local repo.
Implementation: github & local modes, tiny-PR flag — see [`references/wave1-context-prep.md`](./references/wave1-context-prep.md).

This is where the `tiny_pr` flag (`added_lines < 100`) gets set.

---

## Wave 2 — Review + guide writer (single pass)

One inline pass covers all eight rubrics — no subagent dispatch, no fan-out.

- **Resume check** (before starting): list `$work_dir/wave2-lens-*.json` and review only the rubrics with no file there yet.

  - A finished lens's array is already on disk. Reviewing it again spends tokens to reproduce a file you can just read.

  - Also read `$work_dir/tiny-pr.txt`, if present, and use it as `tiny_pr` instead of the in-memory value.
  - Wave 1 persists it there so a mid-pipeline compaction can't lose which downstream path (guide length, whether Wave 3 runs) a resumed run takes.

**Setup** (once, before the first remaining lens): read `references/common-preamble.md` and all 8 files under `references/specialists/` in one message. Invoke `code-standards` up front — every lens cites it — plus any `CLAUDE.md` above a changed file; `common-preamble.md`'s two lazy triggers still govern `test-standards` and `doc-standards`.

**The eight rubric lenses** — apply in this order, `review-principles.md`'s priority order, most critical first:

1. `correctness`
2. `corner-cases-and-side-effects`
3. `testing-and-type-design`
4. `security`
5. `code-design-clarity`
6. `ai-slop`
7. `docs-comments-logging`
8. `performance`

For each remaining lens: walk the diff once through that lens only, apply the preamble's confidence gate and don't-flag list, tag every finding `scope_tag: <lens name>`, and write the array to `$work_dir/wave2-lens-<name>.json` — one file per lens, so a mid-Wave-2 compaction resumes from the next unfinished lens instead of redoing the whole pass.

**Merge, once every lens has a file:**

```bash
n=$(ls "$work_dir"/wave2-lens-*.json 2>/dev/null | wc -l | tr -d ' ')
[ "$n" -eq 8 ] || { echo "wave2: expected 8 lens outputs, found $n"; exit 1; }
jq -s 'add' "$work_dir"/wave2-lens-*.json > "$work_dir/wave2-findings.json"
```

The count guard is the point of that block: an absent file and an empty array are indistinguishable downstream.

Without it, a lens skipped by mistake reads as a rubric that found nothing.

Dedup is **not** done here. One pass applying eight lenses over the same diff can still flag one defect twice under two `scope_tag`s, so Wave 3 resolves overlaps with the full merged list in hand.

**Guide writer (after the merge):**

- **Skip entirely when `Mode: local`** — go straight to Wave 3; local reports drop the guide (rationale in `references/local-review-template.md`).

- **Resume check** (github mode only): if `$work_dir/wave2-guide.md` already exists, load it and skip straight to Wave 3.
- **If `tiny_pr=true`**: skip `references/guide-writer.md`; emit a 2-sentence change summary instead. At <100 added lines the change speaks for itself.
- **Else**: read `references/guide-writer.md`. Produce the Review Guide Markdown (business context, decisions, where to
  focus, incidental changes). 400 words max.
- **Persist**: write the guide (or 2-sentence summary) to `$work_dir/wave2-guide.md`.

Resolve placeholders in each reference file against Wave 1 paths and values.

Artifact at the end of Wave 2: **one flat findings list + one Review Guide** (or 2-sentence summary when `tiny_pr=true`).

---

## Wave 3 — Batched validation pass (self-check)

Before emitting, re-read each finding against its actual file. One pass catches
hallucinations **and** tightens line anchors, so you re-load each file at most once.

**Resume check**: if `$work_dir/wave3-findings.json` already exists, load it (and `$work_dir/wave3-drop-log.txt`) and skip straight to Wave 4 — this wave already completed.

**If `tiny_pr=true`**: copy `$work_dir/wave2-findings.json` to `$work_dir/wave3-findings.json` verbatim, write an empty `$work_dir/wave3-drop-log.txt`, and go to Wave 4 — skip everything below. At <100 added lines the change is in context; hallucinations are rare, and the per-finding validator adds more cost than it saves.

**Read `references/validator.md` once, then apply it to the flat list.**

It authors the cross-lens dedup pre-pass, both per-finding checks — false positive, then line range — the conservative-keep threshold, and the hard rules, so nothing restates them here.

Artifact: a reduced, range-tightened findings list + a drop log. **Persist**: write both to `$work_dir/wave3-findings.json` and `$work_dir/wave3-drop-log.txt` before moving to Wave 4.

---

## Wave 4 — Drop off-diff findings

**Resume check**: if `$work_dir/wave4-findings.json` already exists, load it and skip straight to Wave 5 — this wave already completed.

Run the filter — it keeps a finding only when every line from `start_line` through `line` appears in `commentable-lines.txt`:

```bash
bash ~/.claude/skills/code-review-pipeline/scripts/filter-off-diff-findings.sh \
  "$work_dir/wave3-findings.json" "$work_dir/commentable-lines.txt" \
  > "$work_dir/wave4-findings.json" 2> "$work_dir/wave4-drop-log.txt"
```

We don't comment on code outside the diff — noise the author didn't ask for and can't act on in this PR.

The script settles set membership; judging it by eye invites the partial-overlap miss — a finding spanning both a commentable and an off-diff line reads as in-diff.

The redirects above are the persistence — Wave 5 reads the kept findings, Wave 6 reads `wave4-drop-log.txt`.

Zero surviving findings is normal — see Error handling for what Wave 5 emits.

---

## Wave 5 — Emit

Post the review to GitHub (pending) or write local review artifact.
Implementation details — read only the file matching this run's mode: [`wave5-emit-github.md`](./references/wave5-emit-github.md) or [`wave5-emit-local.md`](./references/wave5-emit-local.md).

---

## Wave 6 — Summary

Print a terminal summary using `references/wave6-summary-template.md`. Both modes share the structure; only the output path / review URL differ.

---

## Error handling

- **gh api POST 422 (Wave 5 emit)**: retry once per `wave5-emit-github.md`'s step 5 (same batch shape, undeliverable findings drop instead of falling back to a non-batch endpoint).
  - If the retry also fails, stop and report the error.

- **Post-emit verification fails**: if the re-fetched review isn't `PENDING`, or its comment count/lines don't match `review-payload.json`, stop — don't proceed to Wave 6's summary.
  - Report the mismatch verbatim (actual state, actual vs. expected comments) so the user can decide whether to clean up live GitHub artifacts.
  - Don't delete or edit anything on GitHub without their go-ahead — submitted reviews and comments are visible to every collaborator.

- **Clone fails (Wave 1, github-only — `gh repo clone` never runs in local mode)**: abort with a clear error and `work_dir`'s path — review can't proceed without the code on disk.

- **No findings at all**:
  - GH: skip the pending review entirely — don't post an empty review just to carry the guide.
    - Still post the Review Guide as a standalone PR comment (Wave 5's guide-posting step) so the human gets the context.

  - LOCAL: write `${out_file}` (the timestamped `./verdict_auto-review_<timestamp>` file) with "no findings" under Findings.

---

## What NOT to do

- Don't `gh pr checkout` into the user's working tree — clone into `/tmp` (Wave 1).

- Don't post inline comments via the single-comment endpoint — always the batch review endpoint, in one call (see `wave5-emit-github.md`).

- Don't submit the review, by any path (exact call list in `wave5-emit-github.md`) — submitting is the human's decision alone.

- Don't include a changelog. The Review Guide replaces it.

- Don't invent flags. The CLI surface is deliberately minimal.

## Flowchart (human-facing)

[`assets/flowchart.md`](assets/flowchart.md) diagrams this skill's flow for the human. Don't load it — non-authoritative, the waves above win; regenerate it whenever the flow changes.
