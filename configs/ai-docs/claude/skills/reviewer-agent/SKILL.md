---
name: reviewer-agent
description: "Shared reviewer orchestrator for /auto-review (local) and /code-review (GitHub). Runs in caller's session by default; opt into subagent wrapping for bias isolation (--isolate). USE only via those callers — not directly."
user-invocable: false
---

# Reviewer Agent

You orchestrate a 7-wave code review pipeline (Waves 0-6). The same pipeline
serves both modes; only Waves 1 and 5 differ.

**Architecture.** The pipeline runs **serially in one session** — no nested sub-Agents. Specialists run linearly so the prompt cache stays warm and later passes dedup what earlier ones raised.

Whether that session is the caller's own or an isolated subagent is the caller's choice — see "How callers dispatch" below.

**Compaction resilience.** Waves 2–4 persist their output to `$work_dir` as they complete (see each wave's "Resume check" / "Persist" notes below).
If context gets compacted mid-pipeline, re-read this SKILL.md, then check `$work_dir` for the furthest-along wave/step output before redoing any work — load it instead of recomputing.

Specialist prompts and validator rubric live in `references/`; bash glue in `scripts/`. This file is the orchestrator.

## How callers dispatch

`/auto-review` (local) and `/code-review` (github) each resolve their own input header, then hand execution to this pipeline.

The dispatch mechanics live here so both callers stay identical; each caller keeps only its own inputs.

**Thinking depth.** For maximum depth on the wave pipeline, the user may run `/effort max` before invoking the caller.

**Fresh-session check — ask before dispatching.** Confirm with the user whether this is a fresh session that did NOT write the code under review.

- Fresh session → run in the calling session (default below). No prior conversation biases the review, and specialists stream live.
- Same session that wrote the diff → dispatch isolated, as if `--isolate`. That session holds opinions the review must not inherit — CLAUDE.md's fresh-context-subagent rule.

**Default — calling session (no `--isolate`):** Read this SKILL.md and walk every wave (0 → 6) yourself, treating the resolved inputs as the "Parse the input header" step below.

Do not spawn any Agent — every specialist pass and the Wave 5 density check streams into the conversation for live visibility.

**Isolated — `--isolate`, or a non-fresh session:** Spawn one Agent, put the resolved inputs in its prompt body, and tell it to read this SKILL.md and orchestrate from there.

The subagent runs the whole pipeline itself — no further Agents. The user sees only the final summary; the trade-off buys bias isolation from the calling session's history.

## Before you start

**Parse the input header:**

- `Mode`: `github` or `local`
- `PR URL` (github only)
- `Jira URL` (github, optional)
- `Base branch` (local only; default `main`)
- `Language`: `Portuguese (Brazil)` (github) or `English` (local)

**Load lazily, by wave; keep loaded after.** They ground every specialist and validation decision:

1. `~/.claude/skills/reviewer-agent/references/review-principles.md` + `review-checklists.md` (Wave 0+)
2. `~/.claude/skills/code-standards/SKILL.md` (Wave 2)
3. `~/.claude/skills/test-standards/SKILL.md` (Wave 2)
4. `~/.claude/skills/doc-standards/SKILL.md` (Wave 2; Wave 5 density check, local)
5. `CLAUDE.md` files at repo root / parents of changed files (Wave 2)

**Architectural principle: specialists never hit GitHub or any external system.** They process only the pre-built context from Wave 1. Keeps the review reproducible and idempotent.

---

## Wave 0 — Early-exit guard

Deterministic check; no subagent needed. Only aborts on hard no-ops.

- **github**: `state=$(gh pr view "$pr_number" --repo "$repo" --json state --jq .state)`. If `state` is `CLOSED` or `MERGED`, print `abort: PR <state>` and stop.
- **github — prior-review guard**: check whether this PR already carries a review from this pipeline, pending or submitted, before spending tokens on a duplicate:
  ```bash
  prior_count=$(gh api repos/"$repo"/pulls/"$pr_number"/comments \
    --jq '[.[] | select(.body | contains("comentário gerado automaticamente por IA"))] | length')
  ```
  If `prior_count > 0`, print `abort: prior review detected` and stop.
  - Every inline comment this pipeline posts carries that signature (Wave 5), so any match means a run already reviewed this exact PR.
- **local**: always proceed. Empty diffs surface naturally — Wave 5 writes "auto-review: no findings".

---

## Wave 1 — Context prep

Purpose: assemble everything every specialist will need on disk, so specialists run from pre-built context (no network calls).

**Work dir**:
- github: `/tmp/pr-review-<n>/`; create fresh (`rm -rf && mkdir -p`).
- local: `$(mktemp -d /tmp/auto-review.XXXXXX)` for scratch; the review lands in a timestamped `./auto-review_<timestamp>` file in CWD (`out_base` set below; extension decided in Wave 5).

**Specialists receive the context listed in `references/common-preamble.md#Context you have`** — ensure Wave 1 produces all of it on disk. Commit messages are fetched in both modes; only `{pr_context}` differs:

- github: PR title + body + optional Jira snippet.
- local: the resolved `spec_<slug>.md` + `plan_<slug>.md` (if present).

### github mode

Always clone into the work dir in `/tmp` — never touches the user's CWD.

```bash
pr_number=...
repo="owner/name"
work_dir="/tmp/pr-review-${pr_number}"

gh pr diff  "$pr_number" --repo "$repo" -- -U20     > "$work_dir/pr.diff"
gh pr diff  "$pr_number" --repo "$repo" --name-only > "$work_dir/changed-files.txt"
gh pr view  "$pr_number" --repo "$repo" --json title,body,headRefOid,baseRefName,headRefName > "$work_dir/pr.json"

# Commit messages (all commits on the PR branch)
gh api "repos/$repo/pulls/$pr_number/commits" --jq '.[].commit.message' \
  > "$work_dir/commit-messages.txt"

bash ~/.claude/skills/reviewer-agent/scripts/extract-commentable-lines.sh \
  "$work_dir/pr.diff" > "$work_dir/commentable-lines.txt"

bash ~/.claude/skills/reviewer-agent/scripts/extract-skipped-files.sh \
  "$work_dir/pr.diff" "$work_dir"

# Jira context (optional)
source ~/.claude/skills/jira-cli/scripts/fetch-jira-review-context.sh 2>/dev/null \
  && fetch-jira-review-context "$jira_url" > "$work_dir/jira-context.md" 2>/dev/null || true

# Clone the PR head
gh repo clone "$repo" "$work_dir/repo" -- --depth=50 --filter=blob:none
git -C "$work_dir/repo" fetch origin "pull/$pr_number/head" --depth=50
git -C "$work_dir/repo" checkout FETCH_HEAD
```

Teardown: work dir stays in `/tmp` for macOS's periodic cleanup. On failure, print the path.

### local mode

Repo root for specialists is the user's CWD; the work dir is scratch for diff/context files.

```bash
work_dir=$(mktemp -d /tmp/auto-review.XXXXXX)
out_base="./auto-review_$(date +%Y-%m-%d_%H:%M)"
git fetch origin "$base_branch"
git diff -U20 "origin/$base_branch...HEAD"             > "$work_dir/diff"
git diff      "origin/$base_branch...HEAD" --name-only > "$work_dir/changed-files.txt"
git log  "origin/$base_branch..HEAD" --format='%B%n---%n' > "$work_dir/commit-messages.txt"

bash ~/.claude/skills/reviewer-agent/scripts/extract-commentable-lines.sh \
  "$work_dir/diff" > "$work_dir/commentable-lines.txt"

bash ~/.claude/skills/reviewer-agent/scripts/extract-skipped-files.sh \
  "$work_dir/diff" "$work_dir"
```

#### Repo-wide static checks + tests + coverage (local mode)

After the diff files are on disk, gather repo-wide signal (lint, typecheck, dead-code, circular, all test tiers, coverage) into `$work_dir/` for Wave 2 specialists to read alongside the diff.

Full discovery + outputs table + consumption rules live in [`references/wave1-repo-wide-checks.md`](references/wave1-repo-wide-checks.md). Load on demand. Local mode only today.

### Tiny-PR fast-path

After the diff is on disk (both modes), count added lines:

```bash
diff_file="$work_dir/pr.diff"; [ -f "$diff_file" ] || diff_file="$work_dir/diff"
added_lines=$(grep -c '^+[^+]' "$diff_file" || echo 0)
```

If `added_lines < 100`, set the `tiny_pr=true` flag. Waves 2 and 3 collapse
into a single combined pass (see Wave 2 below). At this scale the whole diff
fits comfortably in context, serial expansion buys little, and the
per-finding validator adds more cost than it saves. Otherwise leave
`tiny_pr=false` and run the full pipeline.

---

## Wave 2 — Specialist review + guide writer (serial, in this session)

**If `tiny_pr=true`, use the fast-path at the end of this section instead
of the full per-specialist loop below.**


You run the specialist review yourself, in this same session. **Do not spawn sub-Agents for specialists** (rationale at top: serial = warm cache + natural dedup).

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

- **Resume check**: if `$work_dir/wave2-guide.md` already exists, load it and skip straight to Wave 3.
- Read `references/guide-writer.md`.
- Produce the Review Guide Markdown (business context, decisions, where to
  focus, incidental changes). 400 words max.
- **Persist**: write the guide to `$work_dir/wave2-guide.md`.

Resolve placeholders in each reference file against Wave 1 paths and values as
you read them — there's no separate Agent to parameterize.

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
line anchors — merged from two previously-separate waves so you re-load each
file at most once. Inline reasoning, no subagent.

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
   - **Keep** otherwise — including when uncertain. Err toward kept.
3. **Line-range check (kept findings only).** Is `start_line..line` the
   tightest range that captures the problem? If off by a few lines or too
   wide, update `start_line` and `line`. Don't widen/tighten just for
   style — only when the current anchor actually misleads.

**Threshold: LOW (conservative).** Dropping a real finding erodes trust
more than keeping noise. When in doubt, keep. Record every drop with a
one-sentence reason for Wave 6's summary.

**Don't touch** severity, body, or scope_tag. The specialist owns those.

Artifact: a reduced, range-tightened findings list + a drop log. **Persist**: write both to `$work_dir/wave3-findings.json` and `$work_dir/wave3-drop-log.txt` before moving to Wave 4.

---

## Wave 4 — Drop off-diff findings

**Resume check**: if `$work_dir/wave4-findings.json` already exists, load it and skip straight to Wave 5 — this wave already completed.

For each surviving finding, drop it if `start_line..line` is not entirely within `commentable-lines.txt`.

We don't comment on code outside the diff — that's noise the author didn't ask for and can't act on in this PR.

**Persist**: write the surviving findings to `$work_dir/wave4-findings.json` before moving to Wave 5.

---

## Wave 5 — Emit

### github mode

1. **Re-fetch the commit_sha** so it's fresh (avoids "stale commit_id" rejection):
   ```bash
   commit_sha=$(gh pr view "$pr_number" --repo "$repo" --json headRefOid --jq '.headRefOid')
   ```

2. **Density check.** Every comment body about to be posted must obey doc-standards' cap (≤256 chars / ≤32 words per line) before it goes anywhere near the payload.
   - GitHub's review UI renders a dense paragraph as one hard-to-scan block, with no line breaks to anchor a skim-read.
   - Write each Wave-4 finding's `body` to its own file, `$work_dir/wave5-comment-<n>.md` (one per finding, in finding order).
   - Copy the guide's raw content from `$work_dir/wave2-guide.md` alongside them — it isn't wrapped in `<details>` yet, so it's still plain markdown the script can check.
   - Run `~/.claude/skills/doc-standards/scripts/check-density.sh "$work_dir"/wave5-comment-*.md "$work_dir/wave2-guide.md"` in one call.
   - For any flagged line, rewrite it in place per `~/.claude/skills/doc-standards/references/density-rules.md` — split into bullets/sub-bullets or shorter sentences, never drop information.
   - Re-run the script until it exits 0 for every file. The payload-build step below reads finding bodies from these now-clean files; the guide-posting step below reads the guide from `wave2-guide.md`.

3. Build `$work_dir/review-payload.json` with jq for the inline comments only, sourcing each `body` from its density-clean `$work_dir/wave5-comment-<n>.md`.
   - **Leave the top-level `body` empty** — the Review Guide is delivered as a separate standalone PR comment in the guide-posting step below.
     - Rationale: the pending-review body is not a good carrier for the guide; it gets buried behind the GitHub review filter and is hard for the human reviewer to find.
   - Every inline comment body gets the signature footer appended: two newlines + `— comentário gerado automaticamente por IA`.
     - Rationale: the review posts under the human operator's own GitHub account (`gh api` authenticates as them).
     - Without an explicit AI disclaimer, the comments read as if that person wrote them by hand.
   - Include `start_line`/`start_side` only on multi-line ranges (`line > start_line`).
   - Target shape:

   ```json
   {
     "commit_id": "<commit_sha>",
     "body": "",
     "comments": [
       {
         "path": "src/foo.ts",
         "line": 42,
         "side": "RIGHT",
         "start_line": 40,
         "start_side": "RIGHT",
         "body": "<finding body>\n\n— comentário gerado automaticamente por IA"
       }
     ]
   }
   ```

4. POST as a **pending** review (no `event` field), in exactly one call — the whole `comments[]` array goes in this single request, never one comment at a time:

   ```bash
   gh api repos/"$repo"/pulls/"$pr_number"/reviews \
     --method POST \
     --input "$work_dir/review-payload.json" \
     > "$work_dir/review-response.json"

   review_id=$(jq -r '.id' "$work_dir/review-response.json")
   review_url=$(jq -r '.html_url // "(pending — open PR and filter reviews)"' "$work_dir/review-response.json")
   ```

5. If the POST fails (422), re-read line numbers from `commentable-lines.txt` and drop findings whose anchors are unresolvable, then retry once **with the same single-batch-POST shape**.
   - Same endpoint, same one call, just a smaller `comments[]`.
   - Never fall back to the single-comment endpoint (`POST .../pulls/{pull_number}/comments`) or to `gh pr review`, not even for the findings the retry couldn't place.
   - Both endpoints submit immediately on creation — there is no way to keep their output pending.
   - Posting some findings as always-visible, unreviewable comments while the rest wait in a pending review is worse than not posting those findings at all.
   - If the retry also fails, stop and report the 422 body to the user instead of degrading the contract further.

6. **Verify the review actually stayed pending** — a POST response of `"state": "PENDING"` is not proof by itself.
   - Re-fetch the same review a moment later and check again.
   - Something between POST and report-out (a stray follow-up call, a retry, a second Wave-5 run in the same session) can submit it without your noticing:

   ```bash
   gh api repos/"$repo"/pulls/"$pr_number"/reviews/"$review_id" --jq '{state, submitted_at}'
   ```

   - Expect `{"state": "PENDING", "submitted_at": null}`.
   - Anything else — `COMMENTED`, `APPROVED`, `CHANGES_REQUESTED`, or a non-null `submitted_at` — means the review already went live.
   - Do not report success; report the actual state to the user and stop.
   - A submitted review can't be put back to pending via the API (only its individual comments can be deleted, one by one, via `DELETE /repos/{owner}/{repo}/pulls/comments/{comment_id}`).
   - Also re-fetch `.../reviews/"$review_id"/comments` and confirm the comment count and line numbers match `review-payload.json` exactly.
   - An unexpected extra comment or a mismatched count is the same signal as an unexpected state: stop and report, don't declare success.
   - **Never call anything that submits a review** — no `event` field on the POST, no follow-up call to `.../reviews/{id}/events`, no `gh pr review --comment/--approve/--request-changes`.
   - Submitting is the human's action alone; the pipeline's job ends at a verified-pending review.

7. **Post the Review Guide as a standalone PR comment**, wrapped in a collapsed `<details>` block so it doesn't dominate the conversation feed but stays one click away.
   - Its content is `$work_dir/wave2-guide.md`, already made density-clean by the density-check step above — don't re-check it here.
   - Use the issue-comments endpoint (PR conversation comments share the issue API):

   ```bash
   jq -n --arg body "$guide_body" '{body: $body}' > "$work_dir/guide-payload.json"
   gh api repos/"$repo"/issues/"$pr_number"/comments \
     --method POST \
     --input "$work_dir/guide-payload.json" \
     > "$work_dir/guide-response.json"
   guide_url=$(jq -r '.html_url' "$work_dir/guide-response.json")
   ```

   The `$guide_body` must follow this shape (PT-BR for github mode):

   ```markdown
   <details>
   <summary><strong>Code review — guia de leitura</strong> (clique para expandir)</summary>

   Este comentário acompanha a [revisão automática neste PR](<pr-files-url>). Use ele pra localizar os hunks que valem mais atenção antes de mergulhar no diff inteiro.

   <guide content from references/guide-writer.md — sections "Onde focar" + "Mudanças incidentais" only; on tiny_pr=true this is just the 2-sentence summary from Wave 2's fast-path>

   </details>

   — comentário gerado automaticamente por IA
   ```

   Print both `review_url` (pending review) and `guide_url` (standalone comment) in Wave 6.

### local mode

Consult the `html-artifacts` skill's decision tree, then write `${out_file}` — `${out_base}.md` or `${out_base}.html` per its verdict — to the current CWD.

- The routing table's fixed verdict for this artifact type counts as standing approval — skip html-artifacts' propose-first gate here.
  - Why: the pipeline may run unattended (isolated subagent, `/implement`'s batch-end tail), where no per-instance OK is possible; pausing to propose would stall the async run.
- `${out_base}` is set in Wave 1 to `./auto-review_YYYY-MM-DD_HH:MM`; the timestamp preserves ordering when the user runs several reviews in one CWD. Only the extension is the router's call.
- Either format follows the template at `references/local-review-template.md` — read it and expand its placeholders; an `.html` output renders those same sections under html-artifacts' non-negotiables.
- Keep the template file as the single source of truth for the output shape; do not inline the template here.

**Density check (after writing, `.md` output only).** Run `~/.claude/skills/doc-standards/scripts/check-density.sh "$out_file"`. Rewrite each violation per `doc-standards/references/density-rules.md`; re-run until exit 0.

---

## Wave 6 — Summary

Print a terminal summary using the template at `references/wave6-summary-template.md`. Both modes share the structure; only the output path / review URL differ.

---

## Error handling

- **gh api POST 422 (Wave 5 emit)**: retry once, same single-batch-POST call, after verifying line numbers against `commentable-lines.txt` and dropping findings whose anchors don't resolve.
  - If it still fails, stop and report the error.
  - Never fall back to general comments or to the single-comment endpoint, and never split the batch into several POSTs.
  - A finding that can't go through the batch endpoint gets dropped from this run, not posted a different way.
- **Post-emit verification fails (Wave 5's pending-state verification step)**: if the re-fetched review isn't `PENDING`, or its comment count/lines don't match `review-payload.json`, stop.
  - Don't proceed to Wave 6's success summary.
  - Report the mismatch (actual state, actual vs. expected comment list) to the user verbatim so they can decide whether to clean up live GitHub artifacts themselves.
  - Don't delete or edit anything on GitHub without their explicit go-ahead, since submitted reviews and comments are visible to every collaborator.
- **Clone fails (Wave 1)**: abort with a clear error and the target `work_dir` path. The review cannot proceed without the code on disk.
- **No findings at all**:
  - GH: skip the pending review entirely — don't post an empty review just to carry the guide.
    - Still post the Review Guide as a standalone PR comment (Wave 5's guide-posting step) so the human gets the context.
  - LOCAL: write `${out_file}` (the timestamped `./auto-review_<timestamp>` file) with "no findings" under Findings.

---

## What NOT to do

- Don't `gh pr checkout` into the user's working tree — isolation matters; always clone into `/tmp`.
- Don't post inline comments via the single-comment endpoint (`POST .../pulls/{pull_number}/comments`) — always use the batch review endpoint, in one call, so the review stays atomic and pending.
  - This holds on retries too: a 422 on the batch call is never a reason to fall back to single comments.
- Don't submit the review, ever, by any path: no `event` field on the create call, no `.../reviews/{id}/events` call, no `gh pr review --comment/--approve/--request-changes`.
  - Submitting is the human's decision — verify `state == "PENDING"` after posting (Wave 5's pending-state verification step) instead of trusting the create response alone.
- Don't include a changelog. The Review Guide replaces it.
- Don't spawn sub-Agents for specialists or the validator — see Architecture at top.
- Don't invent flags. The CLI surface is deliberately minimal.
