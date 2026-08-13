---
name: code-review-pipeline
description: "Shared reviewer orchestrator for /auto-review (local) and /pr-review (GitHub). Local always dispatches an isolated subagent for bias isolation; GitHub runs inline by default. USE only via those callers — not directly."
user-invocable: false
---

# Reviewer Agent

You orchestrate a 7-wave code review pipeline (Waves 0-6) shared by both
modes — only Waves 1 and 5 differ fully, plus one guide-writer skip in Wave 2 for local mode.

**Architecture.** The orchestrator runs in one session — the caller's own or an isolated subagent, per "How callers dispatch" below — and every wave but Wave 2 runs inside it.

Wave 2 fans its eight specialists out as concurrent `review-specialist` agents, one rubric each.

Serial passes shared one warm cache but grew one context: measured runs sat at ~100k resident tokens median and 157k at p90, re-reading all of it every turn.

Eight isolated contexts each carry one rubric instead of eight, and that read saving is what pays for the eight base-context writes the fan-out adds.

Dedup moved to Wave 3 along with it — a specialist that cannot see its siblings cannot skip what they raised.

**Compaction resilience.** Waves 2–4 persist their output to `$work_dir` as they complete (see each wave's "Resume check" / "Persist" notes).
After a mid-pipeline compaction, re-read this SKILL.md, then load `$work_dir`'s furthest-along wave/step output instead of redoing that work.

Specialist prompts and validator rubric live in `references/`; bash glue in `scripts/`.

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

The isolated run cannot: a subagent's TaskList write never reaches the user who triages it.

The sonnet pin covers the github isolated path — an accepted cost/depth tradeoff, reached by `--isolate` or by the A/B's parity assignment.

`Mode: local` never reaches it: `/auto-review`, the sole local caller, pins `deep-reviewer` (opus) instead, because review judgment is the product it ships (see `auto-review/SKILL.md`).

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

You no longer load `code-standards`, `test-standards`, the specialist rubrics, or the changed files' `CLAUDE.md` — each Wave 2 specialist loads its own, scoped to its rubric.

Carrying all of them here meant every later wave re-read all of them on every turn, for material only Wave 2 ever used.

Specialists never hit GitHub or any external system — pre-built Wave 1 context only, keeping review reproducible and idempotent.

---

## Wave 0 — Early-exit guard

Deterministic check; no subagent needed. Only aborts on hard no-ops.

- **github**: `state=$(gh pr view "$pr_number" --repo "$repo" --json state --jq .state)`. If `state` is `CLOSED` or `MERGED`, print `abort: PR <state>` and stop.
- **github — prior-review guard**: check whether this PR already carries a review from this pipeline, pending or submitted, before spending tokens on a duplicate:
  ```bash
  prior_count=$(gh api repos/"$repo"/pulls/"$pr_number"/comments \
    --jq '[.[] | select(.body | test("gerado por IA, revisado pelo usuário|comentário gerado automaticamente por IA"))] | length')
  ```
  If `prior_count > 0`, print `abort: prior review detected` and stop.
  - Every inline comment this pipeline posts carries the Wave 5 signature, so any match means a run already reviewed this PR.
  - The pattern matches the prior signature text too, catching PRs reviewed before that text changed.

- **local**: always proceed — Wave 0 is a no-op here (both guards are github-only). Empty diffs surface naturally — Wave 5 writes "auto-review: no findings".

---

## Wave 1 — Context prep

Assemble everything specialists need on disk from GitHub PR or local repo.
Implementation: github & local modes, tiny-PR fast-path — see [`references/wave1-context-prep.md`](./references/wave1-context-prep.md).

This is where the `tiny_pr` flag (`added_lines < 100`) gets set.

---

## Wave 2 — Specialist review + guide writer (parallel fan-out)

**If `tiny_pr=true`, use the fast-path at the end of this section instead
of the fan-out below.** If a mid-pipeline compaction dropped
`tiny_pr` from memory, the Resume check below recovers it from disk.

Dispatch all eight specialists in **one turn**, as eight `agent(subAgent=review-specialist, title=Review: <name>)` calls.

Each loads its own preamble, rubric, and standards and writes its own JSON array — you load none of them, and you never see a finding until the merge.

- **Resume check** (before dispatching): list `$work_dir/specialist-*.json` and dispatch only the specialists with no file there.

  - A finished specialist's array is already on disk. Re-running it spends a second opus context to reproduce a file you can just read.

  - Also read `$work_dir/tiny-pr.txt`, if present, and use it as `tiny_pr` instead of the in-memory value.
  - Wave 1 persists it there so a mid-pipeline compaction can't lose which path a resumed run takes.

**The eight rubrics** — order no longer matters, since they run concurrently:

1. `correctness`
2. `corner-cases-and-side-effects`
3. `testing-and-type-design`
4. `security`
5. `code-design-clarity`
6. `ai-slop`
7. `docs-comments-logging`
8. `performance`

**Each dispatch's prompt carries exactly these** — `review-specialist.md` states everything else:

- **Rubric name**: the list entry, matching `references/specialists/<name>.md`.
- **Work dir**: `$work_dir`.
- **Repo root**: `{repo_root}`.
- **Mode**: `github` or `local` — it decides body language and whether permalinks apply.
- **`{pr_context}`**: the resolved PR title/body plus optional Jira snippet, or the local spec and plan paths.
- **Output path**: `$work_dir/specialist-<name>.json`.

**Merge, once every dispatch has returned:**

```bash
n=$(ls "$work_dir"/specialist-*.json 2>/dev/null | wc -l | tr -d ' ')
[ "$n" -eq 8 ] || { echo "wave2: expected 8 specialist outputs, found $n"; exit 1; }
jq -s 'add' "$work_dir"/specialist-*.json > "$work_dir/wave2-findings.json"
```

The count guard is the point of that block: an absent file and an empty array are indistinguishable downstream.

Without it, a specialist that died silently reads as a rubric that found nothing.

Dedup is **not** done here. Eight isolated specialists cannot see each other, so overlapping findings are expected and Wave 3 resolves them with all eight arrays in hand.

**Guide writer (after all 8 specialists):**

- **Skip entirely when `Mode: local`** — go straight to Wave 3; local reports drop the guide (rationale in `references/local-review-template.md`).

- **Resume check** (github mode only): if `$work_dir/wave2-guide.md` already exists, load it and skip straight to Wave 3.
- Read `references/guide-writer.md`.
- Produce the Review Guide Markdown (business context, decisions, where to
  focus, incidental changes). 400 words max.
- **Persist**: write the guide to `$work_dir/wave2-guide.md`.

Resolve placeholders in each reference file against Wave 1 paths and values.

### Tiny-PR fast-path body

When `tiny_pr=true`, replace the per-specialist loop with:

- Read `common-preamble.md` and all 8 specialist files once — combined prompt fits at <100 added lines.
- Invoke the union of `common-preamble.md`'s per-rubric standards table, plus any `CLAUDE.md` above a changed file.

  - Startup skips those because only Wave 2 needs them, and on this path you *are* Wave 2.
  - You carry all eight rubrics at once here, so no single row of that table covers you.

- Walk the diff once. Flag any issue matching a specialist's rubric; tag `scope_tag` with that specialist.
- Skip the guide writer; emit a 2-sentence change summary instead.
- **Persist**: write the summary to `$work_dir/wave2-guide.md` — same filename the full guide uses, so Wave 5 needs no tiny-PR-specific branching.

- **Persist the flat findings list to `$work_dir/wave3-findings.json`** — the filename Wave 4 reads, written here because Wave 3 never runs to write it.
  - Wave 4's script exits 1 on an input it cannot read, so a fast-path run that skips this write hard-fails there rather than reviewing.

- **Skip Wave 3 entirely.** At <100 added lines the change is in context; hallucinations are rare. Findings go straight to Wave 4.

Artifact at the end of Wave 2: **one flat findings list + one Review Guide** (or 2-sentence summary on the fast-path).

---

## Wave 3 — Batched validation pass (self-check)

Before emitting, re-read each finding against its actual file. One pass catches
hallucinations **and** tightens line anchors, so you re-load each file at most once.

**Resume check**: if `$work_dir/wave3-findings.json` already exists, load it (and `$work_dir/wave3-drop-log.txt`) and skip straight to Wave 4 — this wave already completed.

**Read `references/validator.md` once, then apply it to the flat list.**

It authors the cross-specialist dedup pre-pass, both per-finding checks — false positive, then line range — the conservative-keep threshold, and the hard rules, so nothing restates them here.

Dedup lands here rather than in Wave 2 because this is the first step holding all eight arrays at once, and it already loads every finding.

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
