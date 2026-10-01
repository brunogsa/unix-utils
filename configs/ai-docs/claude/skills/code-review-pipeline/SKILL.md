---
name: code-review-pipeline
description: "Shared 7-wave reviewer pipeline behind /auto-review (local) and /pr-review (GitHub). Each caller spawns one code-reviewer orchestrator to run it; Wave 2 fans out per lens only past the size gate. USE only via those callers — not directly."
user-invocable: false
---

# Reviewer Agent

You orchestrate a 7-wave code review pipeline (Waves 0-6) shared by both
modes — only Waves 1 and 5 differ fully.

**Architecture.** Every caller spawns one `code-reviewer` orchestrator (per "How callers dispatch" below), and every wave runs inside that one agent.

Wave 2 reviews inline by default and fans out into eight `code-reviewer` lens agents, one rubric each, only when Wave 1's `large_pr` flag is set or an earlier attempt already failed to finish — see Wave 2's path selection.

Measured on a 155 KB diff: the orchestrator's post-compaction base is ~100k tokens, the diff another ~45k, the rubrics and standards ~23k, so one inline pass sat at the ~184k compaction trigger and looped four times without writing a single lens file.

The 60 KB gate is the largest diff that leaves ~30k tokens for reasoning under that base; below it, one inline pass stays cheaper than eight separate base contexts.

**Compaction resilience.** Waves 2–4 persist their output to `$work_dir` as they complete (see each wave's "Resume check" / "Persist" notes).
After a mid-pipeline compaction, re-read this SKILL.md, then load `$work_dir`'s furthest-along wave/step output instead of redoing that work.

Never Read a `tool-results/*.txt` file the post-compaction reminder names as too large to include — it is the output that overflowed, and everything a wave needs is re-derivable from `$work_dir`.

Rubric prompts and validator rubric live in `references/`; bash glue in `scripts/`.

## How callers dispatch

`/auto-review` (local) and `/pr-review` (github) each resolve their own input header, then spawn one `agent(subAgent=code-reviewer, title=Run code-review pipeline)` in the background, with the header in its prompt body.

Tell it to read this SKILL.md and orchestrate every wave (0 → 6) from there, then wait for its completion notification; the caller prints only what the orchestrator reports back.

One path for both modes, on purpose: `/auto-review` runs in the session that produced the diff, so CLAUDE.md's fresh-context-subagent rule requires the isolation.

Both callers also need the pipeline's reads — diff, rubrics, standards — kept out of their own window, which is where the compaction loop on a large PR started.

`code-reviewer` pins `model: opus` / `effort: high` in its frontmatter, so no dispatch names a model — review judgment is the product here.

## Before you start

**Parse the input header:**

- `Mode`: `github` or `local`
- `PR URL` (github only)
- `Jira URL` (github, optional)
- `Base ref` (local only; a branch name, commit SHA, or `HEAD~N` — defaults to the repo's detected default branch)
- `Language`: `Portuguese (Brazil)` (github) or `English` (local)

**Load lazily, by wave; keep loaded after.** They ground your own validation and emit decisions:

1. Read `~/.claude/skills/code-review-pipeline/references/review-principles.md` + `review-checklists.md` (Wave 0+)

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

This is where the `tiny_pr` flag (`added_lines < 100`) and the `large_pr` flag (`diff_bytes > 60000`) get set; Wave 2 reads both from disk.

---

## Wave 2 — Review + guide writer

- **Resume check** (before anything else):

  - Read `$work_dir/tiny-pr.txt` and `$work_dir/large-pr.txt` and use them as `tiny_pr` / `large_pr` instead of any in-memory value;
    - a missing file reads as `false`, so a work dir from before the flag existed still resumes.

  - Wave 1 persists them so a mid-pipeline compaction can't lose which path (guide length, whether Wave 3 runs, inline or fan-out) a resumed run takes.

  - Bump the attempt counter: `f="$work_dir/wave2-attempts.txt"; n=$(cat "$f" 2>/dev/null); echo $(( ${n:-0} + 1 )) > "$f"`.
    - Every entry into Wave 2, first run or post-compaction resume, counts as one attempt.

  - List `$work_dir/wave2-lens-*.json`; the lenses with no file there are the remaining ones.
  - A finished lens's array is already on disk. Reviewing it again spends tokens to reproduce a file you can just read.

**Path selection** — decide once per entry, from those three values:

- `large_pr=true` → fan-out path.
- attempts ≥ 2 and fewer than 8 lens files → fan-out path, whatever the size.
  - A second entry means the first inline pass could not finish inside one window, and retrying the same pass reproduces the compaction loop instead of finishing.

- otherwise → inline path.

**The eight rubric lenses** — apply in this order, `review-principles.md`'s priority order, most critical first:

1. `correctness`
2. `corner-cases-and-side-effects`
3. `testing-and-type-design`
4. `security`
5. `code-design-clarity`
6. `ai-slop`
7. `docs-comments-logging`
8. `performance`

### Inline path

One pass, strictly one lens at a time:

1. **Setup**, once: read `references/common-preamble.md`, invoke `code-standards` (every lens cites it), and read any `CLAUDE.md` above a changed file.
   - `common-preamble.md`'s two lazy triggers govern `test-standards` and `doc-standards`; on a resume, re-invoke one only when a remaining lens's trigger fires.

2. For each remaining lens, in order: read that lens's rubric file only, walk the diff through that lens only, and apply the preamble's confidence gate and don't-flag list.
   - Tag every finding `scope_tag: <lens name>` and **write `$work_dir/wave2-lens-<name>.json` before reading the next rubric**.

The per-lens file is the only thing a compaction cannot erase, so writing it before moving on is what makes the resume check worth anything.

Reading all eight rubrics up front and reviewing in one turn is how a 155 KB diff produced zero lens files across four attempts. Never re-read a rubric whose lens file exists.

### Fan-out path

Read [`references/wave2-fan-out.md`](./references/wave2-fan-out.md) and follow it: it dispatches one `code-reviewer` per remaining lens in one background message, verifies each `$work_dir/wave2-lens-<name>.json` parses, and merges them.

Never merge with fewer than eight lens files, and never read the diff in this window on this path.

Dedup is **not** done at the merge — Wave 3 resolves overlaps with the full merged list in hand.

**Guide writer:**

- **Skip entirely when `Mode: local`** — go straight to Wave 3; local reports drop the guide (rationale in `references/local-review-template.md`).

- **Resume check** (github mode only): if `$work_dir/wave2-guide.md` already exists, load it and skip straight to Wave 3.
- **If `tiny_pr=true`**: skip `references/guide-writer.md`; emit a 2-sentence change summary instead. At <100 added lines the change speaks for itself.
- **Else, on the inline path**: read `references/guide-writer.md` after the merge. Produce the Review Guide Markdown (business context, decisions, where to
  focus, incidental changes). 400 words max.
- **Else, on the fan-out path**: never write the guide inline, since `guide-writer.md` re-reads the whole diff; dispatch the guide agent per "Guide writer on the fan-out path" in `references/wave2-fan-out.md`.

- **Persist**: write the guide (or 2-sentence summary) to `$work_dir/wave2-guide.md`.

Resolve placeholders in each reference file against Wave 1 paths and values.

Artifact at the end of Wave 2: **one flat findings list + one Review Guide** (or 2-sentence summary when `tiny_pr=true`).

---

## Wave 3 — Batched validation pass (self-check)

Before emitting, re-read each finding against its actual file. One pass catches
hallucinations **and** tightens line anchors, so you re-load each file at most once.

**Resume check**: if `$work_dir/wave3-findings.json` already exists, load it (and `$work_dir/wave3-drop-log.txt`) and skip straight to Wave 4 — this wave already completed.

**If `tiny_pr=true`**: copy `$work_dir/wave2-findings.json` to `$work_dir/wave3-findings.json` verbatim, write an empty `$work_dir/wave3-drop-log.txt`, and go to Wave 4 — skip everything below. At <100 added lines the change is in
context; hallucinations are rare, and the per-finding validator adds more cost than it saves.

**Read `references/validator.md` once, then apply it to the flat list.**

On the fan-out path, check each finding by reading only its anchored range (`sed -n '<start>,<end>p'` with a few lines around it), never the whole diff or the whole file — that path exists to keep the diff out of this window.

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

  - LOCAL: write `${out_file}` (the `./verdict_auto-review_<branch>_<timestamp>` file) with "no findings" under Findings.

---

## What NOT to do

- Don't `gh pr checkout` into the user's working tree — clone into `/tmp` (Wave 1).

- Don't post inline comments via the single-comment endpoint — always the batch review endpoint, in one call (see `wave5-emit-github.md`).

- Don't submit the review, by any path (exact call list in `wave5-emit-github.md`) — submitting is the human's decision alone.

- Don't include a changelog. The Review Guide replaces it.

- Don't invent flags. The CLI surface is deliberately minimal.

## Flowchart (human-facing)

[`assets/flowchart.md`](assets/flowchart.md) diagrams this skill's flow for the human. Don't load it — non-authoritative, the waves above win; regenerate it whenever the flow changes.
