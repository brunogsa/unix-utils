---
description: "Shared reviewer orchestrator for /auto-review (local) and /code-review (GitHub). Single-session pipeline (serial specialists, no internal sub-Agents): early exit → context prep (with tiny-PR fast-path) → serial specialist review + guide writer → batched self-validation → drop off-diff → emit pending review or auto-review.md → summary. The caller wraps this skill in a subagent for bias isolation; inside, everything runs serially to keep prompt cache warm."
user-invocable: false
---

# Reviewer Agent

You orchestrate a 7-wave code review pipeline (Waves 0-6). The same pipeline
serves both modes; only Waves 1 and 5 differ.

**Architecture note.** Everything inside this skill runs **serially in the same
session** — no sub-Agent spawning. The caller (`/auto-review` or `/code-review`)
wraps *this* skill in a subagent so the review is isolated from the user's
session (bias removal); inside, there are no nested subagents. Serializing
keeps the prompt cache warm, avoids N× system-prompt duplication, and lets
later specialists see what earlier ones already raised (natural dedup).

Layout you can count on:

```
~/.claude/skills/reviewer-agent/
├── SKILL.md                        (this file — the orchestrator)
├── scripts/
│   ├── extract-commentable-lines.sh
│   └── extract-skipped-files.sh
├── references/
│   ├── common-preamble.md          (shared contract for all 8 specialists)
│   ├── specialists/<name>.md       (one per topic; 8 files)
│   ├── guide-writer.md
│   ├── validator.md                (Wave 3 batched FP + line-range validator)
│   └── local-review-template.md    (Wave 5 local output template)
└── evals/evals.json                (skill-level eval scaffolding)
```

Specialist and validator prompts live in `references/`; this file is the glue.

## Before you start

**Parse the input header:**

- `Mode`: `github` or `local`
- `PR URL` (github only)
- `Jira URL` (github, optional)
- `Base branch` (local only; default `main`)
- `Language`: `Portuguese (Brazil)` (github) or `English` (local)

**Load these once and keep in working context.** They ground every specialist and validation decision:

1. `~/.claude/skills/review-standards/SKILL.md`
2. `~/.claude/skills/review-standards/checklists.md`
3. `~/.claude/skills/code-standards/SKILL.md`
4. `~/.claude/skills/test-standards/SKILL.md`
5. `~/.claude/skills/doc-standards/SKILL.md`
6. Any `CLAUDE.md` files at the repo root or in parent directories of changed files.

**Architectural principle: specialists never hit GitHub or any external system.** They process only the pre-built context from Wave 1. Keeps the review reproducible and idempotent.

---

## Wave 0 — Early-exit guard

Deterministic check; no subagent needed. Only aborts on hard no-ops.

- **github**: `state=$(gh pr view "$pr_number" --repo "$repo" --json state --jq .state)`. If `state` is `CLOSED` or `MERGED`, print `abort: PR <state>` and stop.
- **local**: always proceed. Empty diffs surface naturally — Wave 2 produces an empty findings list and Wave 5 writes an "auto-review: no findings" file.

---

## Wave 1 — Context prep

Purpose: assemble everything every specialist will need on disk, so specialists run from pre-built context (no network calls).

**Work dir**:
- github: `/tmp/pr-review-<n>/`; create fresh (`rm -rf && mkdir -p`).
- local: `$(mktemp -d /tmp/auto-review.XXXXXX)` for scratch; the skill writes output to `./auto-review.md` in CWD.

**Specialists receive the context listed in `references/common-preamble.md#Context you have`** — ensure Wave 1 produces all of it on disk. Commit messages are fetched in both modes; only `{pr_context}` differs:

- github: PR title + body + optional Jira snippet.
- local: `spec.md` + `plan.md` (if present).

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
source ~/.claude/skills/jira-tools/scripts/fetch-jira-review-context.sh 2>/dev/null \
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
out_file="./auto-review_$(date +%Y-%m-%d_%H-%M).md"
git fetch origin "$base_branch"
git diff -U20 "origin/$base_branch...HEAD"             > "$work_dir/diff"
git diff      "origin/$base_branch...HEAD" --name-only > "$work_dir/changed-files.txt"
git log  "origin/$base_branch..HEAD" --format='%B%n---%n' > "$work_dir/commit-messages.txt"

bash ~/.claude/skills/reviewer-agent/scripts/extract-commentable-lines.sh \
  "$work_dir/diff" > "$work_dir/commentable-lines.txt"

bash ~/.claude/skills/reviewer-agent/scripts/extract-skipped-files.sh \
  "$work_dir/diff" "$work_dir"
```

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


You run the specialist review yourself, in this same session. **Do not spawn
sub-Agents for specialists.** The work is linear reasoning over the diff, and
serializing it in one session has three big wins:

- Zero duplicated system-prompt overhead (vs. N separate Agent calls).
- The prompt cache stays warm — the shared preamble/standards/context is paid
  for once, not once per specialist.
- Later specialists see what earlier ones already flagged → natural dedup
  without a separate Wave.

**Loaded once, reused across all passes:**

- `references/common-preamble.md` — the shared reviewer contract.
- Wave 1 outputs: diff, changed-files list, commentable-lines, commit messages,
  `{pr_context}`.
- The standards files loaded at startup.

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

- Read `references/specialists/<name>.md`. Combine with `common-preamble.md`.
- Walk the diff through that specialist's rubric. Pull full files from
  `{repo_root}` only when the `-U20` diff context isn't enough to decide.
- Emit that specialist's findings as a JSON array; `scope_tag` matches the
  file name (e.g., `"security"`).
- **Skip issues already raised** by a previous specialist in this session —
  the scope_tag + the Problem sentence tell you. This replaces the old Wave 3
  dedup; distinct issues that just share a line stay in.
- Maintain a running findings list in working memory; append each pass.

**Guide writer (after all 8 specialists):**

- Read `references/guide-writer.md`.
- Produce the Review Guide Markdown (business context, decisions, where to
  focus, incidental changes). 400 words max.

Resolve placeholders in each reference file against Wave 1 paths and values as
you read them — there's no separate Agent to parameterize.

### Tiny-PR fast-path body

When `tiny_pr=true`, do this in place of the per-specialist loop:

- Read `common-preamble.md` once. Then read all 8 specialist files — at <100
  added lines their combined prompt is still small enough to hold in context.
- Walk the diff once. Flag any issue that matches any specialist's rubric,
  tagging each finding's `scope_tag` with the matching specialist name.
- Skip the guide writer and produce a 2-sentence change summary instead —
  at this size a full Review Guide is usually busywork.
- **Skip Wave 3 entirely.** Validators add the most value on large diffs
  where specialists reason from partial memory; at <100 added lines the
  whole change is in context already and hallucinations are rare. Findings
  go straight to Wave 4.

Artifact at the end of Wave 2: **one flat findings list + one Review Guide**
(or 2-sentence summary on the fast-path).

---

## Wave 3 — Batched validation pass (self-check)

Before emitting, re-read each finding against its actual file. This single pass
catches hallucinations (specialist mis-remembered the code) **and** tightens
line anchors — merged from two previously-separate waves so you re-load each
file at most once. Inline reasoning, no subagent.

Dedup used to be a separate wave here. It isn't needed: serial specialists in
Wave 2 already skip issues earlier specialists raised. If two distinct issues
happen to share a line, keeping both is correct.

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

Artifact: a reduced, range-tightened findings list + a drop log.

---

## Wave 4 — Drop off-diff findings

For each surviving finding, drop it if `start_line..line` is not entirely within `commentable-lines.txt`. We don't comment on code outside the diff — that's noise the author didn't ask for and can't act on in this PR.

---

## Wave 5 — Emit

### github mode

1. **Re-fetch the commit_sha** so it's fresh (avoids "stale commit_id" rejection):
   ```bash
   commit_sha=$(gh pr view "$pr_number" --repo "$repo" --json headRefOid --jq '.headRefOid')
   ```

2. Build `$work_dir/review-payload.json` with jq, combining the guide, findings, and `commit_sha`. The Review Guide goes in `body`. Every inline comment body gets the signature footer appended: two newlines + `— 🤖 claude`. Include `start_line`/`start_side` only on multi-line ranges (`line > start_line`). Target shape:

   ```json
   {
     "commit_id": "<commit_sha>",
     "body": "<guide + signature footer>",
     "comments": [
       {
         "path": "src/foo.ts",
         "line": 42,
         "side": "RIGHT",
         "start_line": 40,
         "start_side": "RIGHT",
         "body": "<finding body>\n\n— 🤖 claude"
       }
     ]
   }
   ```

3. POST as a **pending** review (no `event` field):

   ```bash
   gh api repos/"$repo"/pulls/"$pr_number"/reviews \
     --method POST \
     --input "$work_dir/review-payload.json" \
     > "$work_dir/review-response.json"

   review_id=$(jq -r '.id' "$work_dir/review-response.json")
   review_url=$(jq -r '.html_url // "(pending — open PR and filter reviews)"' "$work_dir/review-response.json")
   ```

4. If the POST fails (422), re-read line numbers from `commentable-lines.txt`, drop findings whose anchors are unresolvable, and retry once. Never fall back to general comments — integrity of the pending-review contract matters more than posting at all.

### local mode

Write `${out_file}` (set in Wave 1 to `./auto-review_YYYY-MM-DD_HH-MM.md`; timestamp preserves ordering across runs, e.g. per-task in autonomous mode) to the current CWD following the template at `references/local-review-template.md` — read that file and expand its placeholders. Keep the template file as the single source of truth for the output shape; do not inline the template here.

---

## Wave 6 — Summary

Print a terminal summary reporting the review-level counts.

### github mode summary

```
PR #<n>: <title>
<pr-url>

PENDING review created: <review_url>
Review ID: <review_id>

Findings posted: <N>
  MANDATORY: <m>
  RECOMMENDED: <p>
  NITPICK: <q>
  OPTIONAL: <o>
  COMPLIMENT: <r>
  QUESTION: <s>

Dropped findings (one line each, for validation):
  [Wave 3 FP ]  path:line — <first 80 chars of body> — dropped because <reason>
  [Wave 4 off]  path:line — <first 80 chars of body>

Totals: <y> false positives, <z> off-diff dropped.

Skipped files (not reviewed):
  binary: <list from work_dir/skipped-binary.txt>
  deleted: <list from work_dir/skipped-deleted.txt>

Open <pr-url>/files to filter and submit.
```

The per-finding drop list exists so you can sanity-check the filter while the threshold is tuned LOW. If real findings are disappearing, tighten Wave 3. If noise is surviving, loosen.

### local mode summary

Same structure, but with `${out_file}` (the timestamped path) as the output path and no review URL.

---

## Error handling

- **gh api POST 422 (Wave 5 emit)**: retry once after verifying line numbers against `commentable-lines.txt` and dropping findings whose anchors don't resolve. Never fall back to general comments.
- **Clone fails (Wave 1)**: abort with a clear error and the target `work_dir` path. The review cannot proceed without the code on disk.
- **No findings at all**: emit the pending review anyway (body-only Review Guide) for GH; for LOCAL, write `auto-review.md` with "no findings" under Findings.

---

## What NOT to do

- Don't `gh pr checkout` into the user's working tree — isolation matters; always clone into `/tmp`.
- Don't post inline comments via the single-comment endpoint — always use the batch review endpoint so the review stays atomic and pending.
- Don't include a changelog. The Review Guide replaces it.
- Don't spawn sub-Agents for specialists or the validator — the pipeline is intentionally single-session to keep the prompt cache warm and avoid duplicated system-prompt overhead. The caller already wraps this skill in a subagent for bias isolation.
- Don't invent flags. The CLI surface is deliberately minimal.
