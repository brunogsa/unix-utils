---
name: code-review-pipeline
description: "Shared reviewer orchestrator for /auto-review (local) and /pr-review (GitHub). Runs in caller's session by default; opt into subagent wrapping for bias isolation (--isolate). USE only via those callers — not directly."
user-invocable: false
---

# Reviewer Agent

You orchestrate a 7-wave code review pipeline (Waves 0-6) shared by both
modes — only Waves 1 and 5 differ fully, plus one guide-writer skip in Wave 2 for local mode.

**Architecture.** The pipeline runs **serially in one session** — no nested sub-Agents. Specialists run linearly so the prompt cache stays warm and later passes dedup what earlier ones raised.

Whether that session is the caller's own or an isolated subagent, see "How callers dispatch" below.

**Compaction resilience.** Waves 2–4 persist their output to `$work_dir` as they complete (see each wave's "Resume check" / "Persist" notes below).
If context gets compacted mid-pipeline, re-read this SKILL.md, then check `$work_dir` for the furthest-along wave/step output before redoing any work — load it instead.

Specialist prompts and validator rubric live in `references/`; bash glue in `scripts/`.

## How callers dispatch

`/auto-review` (local) and `/pr-review` (github) each resolve their own input header, then hand execution to this pipeline.

**Dispatch rule — auto-decided, no question asked.** The mode already determines whether the calling session is biased, so never ask the user:

- `Mode: local` (`/auto-review`) → **always dispatch isolated** (subagent path below). `/auto-review` runs in the session that produced the diff, so CLAUDE.md's fresh-context-subagent rule always applies.

- `Mode: github` (`/pr-review`) → **always run inline** — review happens after the code already landed, so the calling session did not write the diff.
  - `--isolate` still forces the isolated path when explicitly passed.

**Order:** mode first, then isolate-or-inline, then the chosen run parses the full input header below.

**Inline — `Mode: github` without `--isolate`:** Read this SKILL.md and walk every wave (0 → 6) yourself, treating the resolved inputs as the "Parse the input header" step below.

The one exception to the no-Agents rule: Wave 5's density fix, delegated to the `markdown-standards-fixer` agent (see either `wave5-emit-*.md`) as post-review cleanup.

**Isolated — `Mode: local`, or `--isolate` passed:** Spawn one `agent(subAgent=general-purpose, title=Run code-review pipeline, model=sonnet)`.

Put the resolved inputs in its prompt body, and tell it to read this SKILL.md and orchestrate from there.

It runs the pipeline itself; the user sees only the final summary.

The sonnet pin trades review depth for lower cost — an accepted limit here.

## Before you start

**Parse the input header:**

- `Mode`: `github` or `local`
- `PR URL` (github only)
- `Jira URL` (github, optional)
- `Base branch` (local only; default `main`)
- `Language`: `Portuguese (Brazil)` (github) or `English` (local)

**Load lazily, by wave; keep loaded after.** They ground every specialist and validation decision:

1. Read `~/.claude/skills/code-review-pipeline/references/review-principles.md` + `review-checklists.md` (Wave 0+)
2. Invoke `code-standards` via the Skill tool (Wave 2)
3. Invoke `test-standards` via the Skill tool (Wave 2)
4. Invoke `doc-standards` via the Skill tool (Wave 2; also Wave 5's density check)

5. Read `CLAUDE.md` files at repo root / parents of changed files (Wave 2)

Invoke the three standards, never Read their `SKILL.md` — CLAUDE.md's "Skill tool over Read" rule reserves Read for meta-work like auditing a skill.

Specialists never hit GitHub or any external system; they process only Wave 1's pre-built context, keeping the review reproducible and idempotent.

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

- **local**: always proceed — Wave 0 is a no-op here (both guards above are github-only). Empty diffs surface naturally — Wave 5 writes "auto-review: no findings".

---

## Wave 1 — Context prep

Assemble everything every specialist needs on disk from GitHub PR or local repo.
Implementation: github & local modes, tiny-PR fast-path — see [`references/wave1-context-prep.md`](./references/wave1-context-prep.md).

This is where the `tiny_pr` flag (`added_lines < 100`) gets set.

---

## Wave 2 — Specialist review + guide writer (serial, in this session)

**If `tiny_pr=true`, use the fast-path at the end of this section instead
of the full per-specialist loop below.**


You run the specialist review yourself, in this same session — no sub-Agents (rationale at top).

**Loaded once, reused across all passes:**

- `references/common-preamble.md` — the shared reviewer contract.
- Wave 1 outputs: diff, changed-files list, commentable-lines, commit messages,
  `{pr_context}`.
- The standards files (per the mapping in "Before you start").

**Specialist order (do them one at a time):**

1. `correctness`
2. `corner-cases-and-side-effects`
3. `testing-and-type-design`
4. `security`
5. `code-design-clarity`
6. `ai-slop`
7. `docs-comments-logging`
8. `performance`

Per-specialist loop:

- **Resume check** (before the first iteration only): if `$work_dir/wave2-progress.txt` exists, read it.
  - One completed specialist name per line; load `$work_dir/wave2-findings.json` for their findings so far.
  - Start the loop at the first specialist NOT listed there instead of at `correctness`.

- Read `references/specialists/<name>.md`. Combine with `common-preamble.md`.
- Walk the diff through that specialist's rubric. Pull full files from
  `{repo_root}` only when the `-U20` diff context isn't enough to decide.

- Emit that specialist's findings as a JSON array; `scope_tag` matches the
  file name (e.g., `"security"`).
- **Skip issues already raised** by a previous specialist in this session —
  the scope_tag + the Problem sentence tell you. Distinct issues that share
  a line stay in.

- Maintain a running findings list in working memory; append each pass.

- **Persist**: overwrite `$work_dir/wave2-findings.json` with the full cumulative findings array, and append this specialist's name to `$work_dir/wave2-progress.txt` — both before moving to the next specialist.

**Guide writer (after all 8 specialists):**

- **Skip entirely when `Mode: local`** — go straight to Wave 3.
  - The guide only exists to post as a standalone PR comment (Wave 5, github mode); local reports drop it (see `references/local-review-template.md`).

- **Resume check** (github mode only): if `$work_dir/wave2-guide.md` already exists, load it and skip straight to Wave 3.
- Read `references/guide-writer.md`.
- Produce the Review Guide Markdown (business context, decisions, where to
  focus, incidental changes). 400 words max.
- **Persist**: write the guide to `$work_dir/wave2-guide.md`.

Resolve placeholders in each reference file against Wave 1 paths and values as you read them.

### Tiny-PR fast-path body

When `tiny_pr=true`, replace the per-specialist loop with:

- Read `common-preamble.md` and all 8 specialist files once — combined prompt still fits at <100 added lines.
- Walk the diff once. Flag any issue matching a specialist's rubric; tag `scope_tag` with that specialist.
- Skip the guide writer; emit a 2-sentence change summary instead.
- **Persist**: write the summary to `$work_dir/wave2-guide.md` — same filename the full guide uses, so Wave 5's density check and guide-posting steps don't need tiny-PR-specific branching.

- **Skip Wave 3 entirely.** At <100 added lines the change is in context; hallucinations are rare. Findings go straight to Wave 4.

Artifact at the end of Wave 2: **one flat findings list + one Review Guide** (or 2-sentence summary on the fast-path).

---

## Wave 3 — Batched validation pass (self-check)

Before emitting, re-read each finding against its actual file. This single pass
catches hallucinations (specialist mis-remembered the code) **and** tightens
line anchors, so you re-load each file at most once.

**Resume check**: if `$work_dir/wave3-findings.json` already exists, load it (and `$work_dir/wave3-drop-log.txt`) and skip straight to Wave 4 — this wave already completed.

**Read this once:** `references/validator.md` — the exact per-finding rubric.

**For each finding in the flat list:**

1. Load the file at `{finding.path}` under `{repo_root}` (reuse a prior Read
   when the same file appears in consecutive findings). Focus on
   `start_line..line ± 10`.
2. **False-positive check.** Is the claim visibly present in the code?
   - **Drop** only on clear, specific evidence the claim doesn't hold:
     the cited code doesn't exist; the code already does what was asked;
     the issue depends on a behavior the file explicitly prevents.
   - **Keep** otherwise — including when uncertain.

3. **Line-range check (kept findings only).** Is `start_line..line` the
   tightest range that captures the problem? If off by a few lines or too
   wide, update `start_line` and `line`. Don't widen/tighten just for
   style — only when the current anchor actually misleads.

**Threshold: LOW (conservative).** Dropping a real finding erodes trust
more than keeping noise. Record every drop with a one-sentence reason for
Wave 6's summary.

**Don't touch** severity, body, or scope_tag. The specialist owns those.

Artifact: a reduced, range-tightened findings list + a drop log. **Persist**: write both to `$work_dir/wave3-findings.json` and `$work_dir/wave3-drop-log.txt` before moving to Wave 4.

---

## Wave 4 — Drop off-diff findings

**Resume check**: if `$work_dir/wave4-findings.json` already exists, load it and skip straight to Wave 5 — this wave already completed.

For each surviving finding, drop it if `start_line..line` is not entirely within `commentable-lines.txt`.

We don't comment on code outside the diff — that's noise the author didn't ask for and can't act on in this PR.

**Persist**: write the surviving findings to `$work_dir/wave4-findings.json` before moving to Wave 5.

Zero surviving findings is a normal outcome — see Error handling for what Wave 5 emits.

---

## Wave 5 — Emit

Post the review to GitHub (pending) or write local review artifact.
Implementation details — read only the file matching this run's mode: [`wave5-emit-github.md`](./references/wave5-emit-github.md) or [`wave5-emit-local.md`](./references/wave5-emit-local.md).

---

## Wave 6 — Summary

Print a terminal summary using the template at `references/wave6-summary-template.md`. Both modes share the structure; only the output path / review URL differ.

---

## Error handling

- **gh api POST 422 (Wave 5 emit)**: retry once, same single-batch-POST call, after verifying line numbers against `commentable-lines.txt` and dropping findings whose anchors don't resolve.
  - If it still fails, stop and report the error.
  - Never fall back to general comments or the single-comment endpoint, never split the batch into several POSTs — a finding that can't go through drops from this run instead.

- **Post-emit verification fails (Wave 5's pending-state verification step)**: if the re-fetched review isn't `PENDING`, or its comment count/lines don't match `review-payload.json`, stop.
  - Don't proceed to Wave 6's success summary.
  - Report the mismatch (actual state, actual vs. expected comment list) to the user verbatim so they can decide whether to clean up live GitHub artifacts themselves.

  - Don't delete or edit anything on GitHub without their explicit go-ahead, since submitted reviews and comments are visible to every collaborator.

- **Clone fails (Wave 1, github-only — `gh repo clone` never runs in local mode)**: abort with a clear error and `work_dir`'s path. Review cannot proceed without the code on disk.

- **No findings at all**:
  - GH: skip the pending review entirely — don't post an empty review just to carry the guide.
    - Still post the Review Guide as a standalone PR comment (Wave 5's guide-posting step) so the human gets the context.

  - LOCAL: write `${out_file}` (the timestamped `./verdict_auto-review_<timestamp>` file) with "no findings" under Findings.

---

## What NOT to do

- Don't `gh pr checkout` into the user's working tree — isolation matters; always clone into `/tmp`.

- Don't post inline comments via the single-comment endpoint (`POST .../pulls/{pull_number}/comments`) — always use the batch review endpoint, in one call, so the review stays atomic and pending.

- Don't submit the review, ever, by any path: no `event` field on the create call, no `.../reviews/{id}/events` call, no `gh pr review --comment/--approve/--request-changes`.
  - Submitting is the human's decision; Wave 5's pending-state verification step confirms the review stayed pending.

- Don't include a changelog. The Review Guide replaces it.

- Don't spawn sub-Agents for specialists or the validator — see Architecture at top.

- Don't invent flags. The CLI surface is deliberately minimal.

## Flowchart (human-facing)

[`assets/flowchart.md`](assets/flowchart.md) diagrams this skill's flow for the human. Don't load it — non-authoritative, the waves above win; regenerate it whenever the flow changes.
