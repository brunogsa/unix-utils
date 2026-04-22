---
description: "Shared reviewer orchestrator for /auto-review (local) and /code-review (GitHub). Wave-based pipeline: early exit → context prep → 8 parallel specialists + guide writer → dedup → false-positive filter → line-range validation → drop off-diff findings → emit pending review or auto-review.md → summary."
user-invocable: false
---

# Reviewer Agent

You orchestrate a 9-wave code review pipeline (Waves 0-8). The same pipeline serves both modes; only Waves 1 and 7 differ.

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
│   ├── false-positive-validator.md (Wave 4 prompt)
│   ├── line-range-validator.md     (Wave 5 prompt)
│   └── local-review-template.md    (Wave 7 local output template)
├── tests/                          (script regression tests)
└── evals/evals.json                (skill-level eval scaffolding)
```

Subagents read their prompt file from `references/`. This file is the glue.

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

**Architectural principle: specialists never hit GitHub or any external system.** They process only the pre-built context from Wave 1. This keeps them reproducible, parallel-safe, and idempotent.

---

## Wave 0 — Early-exit guard

Deterministic check; no subagent needed. Only aborts on hard no-ops.

- **github**: `state=$(gh pr view "$pr_number" --repo "$repo" --json state --jq .state)`. If `state` is `CLOSED` or `MERGED`, print `abort: PR <state>` and stop.
- **local**: always proceed. Empty diffs surface naturally — Wave 2 specialists return empty arrays and Wave 7 writes an "auto-review: no findings" file.

---

## Wave 1 — Context prep

Purpose: assemble everything every specialist will need on disk, so specialists run from pre-built context (no network calls).

**Work dir**:
- github: `/tmp/pr-review-<n>/`; create fresh (`rm -rf && mkdir -p`).
- local: `$(mktemp -d "${TMPDIR:-/tmp}/auto-review.XXXXXX")` for scratch; the skill writes output to `./auto-review.md` in CWD.

**Specialists receive the context listed in `references/common-preamble.md#Context you have`** — ensure Wave 1 produces all of it on disk. Commit messages are fetched in both modes; only `{pr_context}` differs:

- github: PR title + body + optional Jira snippet.
- local: `spec.md` + `plan.md` (if present).

### github mode

Always clone into the work dir in `/tmp` — never touches the user's CWD.

```bash
pr_number=...
repo="owner/name"
work_dir="/tmp/pr-review-${pr_number}"

gh pr diff  "$pr_number" --repo "$repo"             > "$work_dir/pr.diff"
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
work_dir=$(mktemp -d "${TMPDIR:-/tmp}/auto-review.XXXXXX")
git fetch origin "$base_branch"
git diff "origin/$base_branch...HEAD"             > "$work_dir/diff"
git diff "origin/$base_branch...HEAD" --name-only > "$work_dir/changed-files.txt"
git log  "origin/$base_branch..HEAD" --format='%B%n---%n' > "$work_dir/commit-messages.txt"

bash ~/.claude/skills/reviewer-agent/scripts/extract-commentable-lines.sh \
  "$work_dir/diff" > "$work_dir/commentable-lines.txt"

bash ~/.claude/skills/reviewer-agent/scripts/extract-skipped-files.sh \
  "$work_dir/diff" "$work_dir"
```

---

## Wave 2 — Parallel specialists + guide writer

Spawn **9 Opus Agents in a single message** to run them in parallel. The wave completes when the slowest returns.

**The 9 agents:**

- **8 specialists** (in order of relevance): `correctness`, `corner-cases-and-side-effects`, `testing-and-type-design`, `security`, `code-design-clarity`, `ai-slop`, `docs-comments-logging`, `performance`. Each reads `references/common-preamble.md` + `references/specialists/<name>.md`.
- **1 guide writer**: reads `references/guide-writer.md` and produces the human-readable change summary shown at the top of the emitted review.

Each agent's reference file documents its placeholders; resolve them with Wave 1 paths and values.

Specialists return a JSON array of findings. Guide writer returns Markdown. Collect all 9 outputs before advancing.

---

## Wave 3 — Dedup specialists' findings

Parse every specialist's JSON array. Merge into one flat list.

**Threshold: LOW (conservative).** Only collapse findings we are very confident are the same issue. When in doubt, keep both — users can ignore noise, but silently dropping distinct findings erodes trust.

Near-duplicate rule — drop only if ALL of:
- same `path` AND
- `|f1.line − f2.line| ≤ 1` AND
- their bodies' first sentences match under a strict token-overlap (>= 0.7 Jaccard on a 40-char prefix).

When duplicates are found, keep the highest-severity one (MANDATORY > RECOMMENDED > NITPICK > OPTIONAL > COMPLIMENT > QUESTION). Note the dropped ones in a dedup log for Wave 8's summary.

You can do this inline with a short script or inline logic. It's cheap; no subagent needed.

---

## Wave 4 — False-positive filter

Purpose: drop findings where the claim clearly doesn't hold against the actual file. Separated from line-range validation so each agent has a single, focused question.

**Threshold: LOW (conservative).** Drop only when you have clear, specific evidence the finding is wrong. The validator prompt itself emphasizes "err toward kept" — when uncertain, the finding stays. We can tighten later.

For each surviving finding, spawn a validator Agent (Opus) with the prompt at `references/false-positive-validator.md`. **All validator calls in parallel in one message** (they're independent and short).

Each validator gets:
- `{finding_json}` — stringified single finding object.
- `{file_path}` — the `path` from the finding.
- `{repo_root}` — the work-dir repo (GH) or CWD (LOCAL).

Apply results:
- `kept` → carry the finding forward to Wave 5.
- `dropped` → drop the finding. Record the reason in the Wave 8 summary.

---

## Wave 5 — Line-range validation

Purpose: tighten the anchor of each surviving finding. Specialists often mis-anchor issues by a few lines; this wave corrects that. Never drops findings — false-positive filtering already happened in Wave 4.

For each surviving finding, spawn a validator Agent (Opus) with the prompt at `references/line-range-validator.md`. **All validator calls in parallel in one message.**

Each validator gets:
- `{finding_json}` — stringified single finding object.
- `{file_path}` — the `path` from the finding.
- `{repo_root}` — the work-dir repo (GH) or CWD (LOCAL).
- `{commentable_lines_path}` — Wave 1 output.

Apply results:
- `confirmed` → keep the finding as-is.
- `revised-range` → update `start_line` + `line` in the finding.

---

## Wave 6 — Drop off-diff findings

For each surviving finding, drop it if `start_line..line` is not entirely within `commentable-lines.txt`. We don't comment on code outside the diff — that's noise the author didn't ask for and can't act on in this PR.

---

## Wave 7 — Emit

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

Write `./auto-review.md` to the current CWD following the template at `references/local-review-template.md` — read that file and expand its placeholders. Keep the template file as the single source of truth for the output shape; do not inline the template here.

---

## Wave 8 — Summary

Print a terminal summary. Token accounting is covered by Claude Code's UI (per-subagent token usage is already visible); this wave just reports the review-level counts.

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
  [Wave 3 dup]  path:line — <first 80 chars of body> — dropped because <reason>
  [Wave 4 FP ]  path:line — <first 80 chars of body> — dropped because <reason>
  [Wave 6 off]  path:line — <first 80 chars of body>

Totals: <x> duplicates, <y> false positives, <z> off-diff dropped.

Skipped files (not reviewed):
  binary: <list from work_dir/skipped-binary.txt>
  deleted: <list from work_dir/skipped-deleted.txt>

Open <pr-url>/files to filter and submit.
```

The per-finding list exists so you can sanity-check the filters while thresholds are tuned LOW. If you see real findings disappearing, tighten the thresholds in Waves 3/4. If you see noise surviving, loosen.

### local mode summary

Same structure, but with `./auto-review.md` as the output path and no review URL.

---

## Error handling

- **gh api POST 422 (Wave 7 emit)**: retry once after verifying line numbers against `commentable-lines.txt` and dropping findings whose anchors don't resolve. Never fall back to general comments.
- **Clone fails (Wave 1)**: abort with a clear error and the target `work_dir` path. The review cannot proceed without the code on disk.
- **Parallel Agent wave exceeds rate limit (429)**: retry failed specialists sequentially; surface which ones ran vs. not in the summary.
- **No findings at all**: emit the pending review anyway (body-only Review Guide) for GH; for LOCAL, write `auto-review.md` with "no findings" under Findings.

---

## What NOT to do

- Don't `gh pr checkout` into the user's working tree — isolation matters; always clone into `/tmp`.
- Don't post inline comments via the single-comment endpoint — always use the batch review endpoint so the review stays atomic and pending.
- Don't include a changelog. The Review Guide replaces it.
- Don't fan out specialists sequentially — parallelism is the point.
- Don't invent flags. The CLI surface is deliberately minimal.
