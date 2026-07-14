# Wave 1 — Context Prep

Purpose: assemble everything every specialist will need on disk, so specialists run from pre-built context (no network calls).

**Work dir**:
- github: `/tmp/pr-review-<n>/`; create fresh (`rm -rf && mkdir -p`).
- local: `$(mktemp -d /tmp/auto-review.XXXXXX)` for scratch; the review lands in a timestamped `./report_auto-review_<timestamp>` file in CWD (`out_base` set below; extension decided in Wave 5).

**Specialists receive the context listed in `references/common-preamble.md#Context you have`** — ensure Wave 1 produces all of it on disk. Commit messages are fetched in both modes; only `{pr_context}` differs:

- github: PR title + body + optional Jira snippet.
- local: the resolved `spec_<slug>.md` + `plan_<slug>.md` (if present).

## github mode

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

```bash
work_dir=$(mktemp -d /tmp/auto-review.XXXXXX)
out_base="./report_auto-review_$(date +%Y-%m-%d_%H:%M)"
git fetch origin "$base_branch"
git diff -U20 "origin/$base_branch...HEAD"             > "$work_dir/diff"
git diff      "origin/$base_branch...HEAD" --name-only > "$work_dir/changed-files.txt"
git log  "origin/$base_branch..HEAD" --format='%B%n---%n' > "$work_dir/commit-messages.txt"

bash ~/.claude/skills/code-review-pipeline/scripts/extract-commentable-lines.sh \
  "$work_dir/diff" > "$work_dir/commentable-lines.txt"

bash ~/.claude/skills/code-review-pipeline/scripts/extract-skipped-files.sh \
  "$work_dir/diff" "$work_dir"
```

### Repo-wide static checks + tests + coverage (local mode)

After the diff files are on disk, gather repo-wide signal (lint, typecheck, dead-code, circular, all test tiers, coverage) into `$work_dir/` for Wave 2 specialists to read alongside the diff.

Full discovery + outputs table + consumption rules live in [`references/wave1-repo-wide-checks.md`](references/wave1-repo-wide-checks.md). Load on demand. Local mode only today.

## Tiny-PR fast-path

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
