# Wave 1 — Context Prep

Purpose: assemble everything every specialist will need on disk, so specialists run from pre-built context (no network calls).

**Work dir**:
- github: `/tmp/pr-review-<n>/`; create fresh (`rm -rf && mkdir -p`).
- local: `$(mktemp -d /tmp/auto-review.XXXXXX)` for scratch; the review lands in a timestamped `./verdict_auto-review_<timestamp>` file in CWD (`out_base` set below; always `.md`, per the html-artifacts Gate 1 note in `auto-review/SKILL.md`).

**Specialists receive the context listed in `references/common-preamble.md#Context you have`** — ensure Wave 1 produces all of it on disk. Commit messages are fetched in both modes; only `{pr_context}` differs:

- github: PR title + body + optional Jira snippet.
- local: the resolved spec and plan (if present).

## github mode

Always clone into the work dir in `/tmp` — never touches the user's CWD.

```bash
pr_number=...
repo="owner/name"
work_dir="/tmp/pr-review-${pr_number}"

# gh pr diff has no context-width flag, so github mode gets 3-line hunks (vs
# local's -U20); specialists read the on-disk clone below for deeper context.
gh pr diff "$pr_number" --repo "$repo" > "$work_dir/pr.diff"
gh pr diff  "$pr_number" --repo "$repo" --name-only > "$work_dir/changed-files.txt"
gh pr view  "$pr_number" --repo "$repo" --json title,body,headRefOid,baseRefName,headRefName > "$work_dir/pr.json"

# Commit messages (all commits on the PR branch)
gh api "repos/$repo/pulls/$pr_number/commits" --jq '.[].commit.message' \
  > "$work_dir/commit-messages.txt"

bash ~/.claude/skills/code-review-pipeline/scripts/extract-commentable-lines.sh \
  "$work_dir/pr.diff" > "$work_dir/commentable-lines.txt"

bash ~/.claude/skills/code-review-pipeline/scripts/extract-skipped-files.sh \
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

## local mode

Repo root for specialists is the user's CWD; the work dir is scratch for diff/context files.

`base_ref` is supplied by the caller — `auto-review`'s resolved `<BASE_REF>`, or `/implement`'s `BATCH_BASE_SHA` — and may be a branch name, a commit SHA, or `HEAD~N`.

`base_ref` resolution: a branch on origin diffs against the freshly fetched remote copy, so a stale local branch never silently narrows the diff. Anything else must already resolve locally (SHA, `HEAD~N`, tag).

See the script's own `if`/`else` for the exact fallback and its failure message.

```bash
work_dir=$(mktemp -d /tmp/auto-review.XXXXXX)
out_base="./verdict_auto-review_$(date +%Y-%m-%d_%H:%M)"

bash ~/.claude/skills/code-review-pipeline/scripts/prep-local-context.sh \
  "$base_ref" "$work_dir"
```

### Repo-wide static checks + tests + coverage (local mode)

After the diff files are on disk, gather repo-wide signal (lint, typecheck, dead-code, circular, all test tiers, coverage) into `$work_dir/` for Wave 2 specialists to read alongside the diff.

Full discovery + outputs table + consumption rules live in [`wave1-repo-wide-checks.md`](wave1-repo-wide-checks.md). Load on demand. Local mode only today.

## Tiny-PR fast-path

Both modes count added lines once the diff is on disk. Local mode's `prep-local-context.sh` already did this and wrote the result to `$work_dir/tiny-pr.txt` (see above).

Github mode still counts inline, since it has no equivalent script:

```bash
added_lines=$(grep -c '^+[^+]' "$work_dir/pr.diff" || true)
tiny_pr=false; [ "$added_lines" -lt 100 ] && tiny_pr=true
echo "$tiny_pr" > "$work_dir/tiny-pr.txt"
```

If `added_lines < 100`, `tiny_pr=true`. Waves 2 and 3 collapse into a single combined pass (see Wave 2 below).

At this scale the whole diff fits comfortably in context, serial expansion buys little, and the per-finding validator adds more cost than it saves.

Otherwise leave `tiny_pr=false` and run the full pipeline.

**Persist it to `$work_dir/tiny-pr.txt`** so Wave 2 can recover the flag from disk instead of trusting working memory after a mid-pipeline compaction.

Without it, a resumed tiny PR reruns through the full 8-specialist loop the fast-path exists to skip.
