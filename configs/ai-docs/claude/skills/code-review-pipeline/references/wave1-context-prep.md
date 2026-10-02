# Wave 1 — Context Prep

Purpose: assemble everything Wave 2 will need on disk, so it runs from pre-built context (no network calls).

**Work dir**:
- github: `/tmp/pr-review-<n>/`; if it already exists, move it aside to `/tmp/pr-review-<n>.prev-<timestamp>`, then `mkdir -p`.
  - `rm -rf` is blocked by the rm-guard hook, and the moved-aside dir keeps a prior run's artifacts readable.

- local: `$(mktemp -d /tmp/auto-review.XXXXXX)` for scratch; the review lands in a `./verdict_auto-review_<branch>_<timestamp>` file in CWD (`out_base` set below; always `.md`, per the html-artifacts Gate 1 note in
`auto-review/SKILL.md`). The branch segment lets several PRs run in series, each on its own branch, keep distinguishable verdict files.

**Wave 2 reads the context listed in `references/common-preamble.md#Context you have`** — ensure Wave 1 produces all of it on disk. Commit messages are fetched in both modes; only `{pr_context}` differs:

- github: PR title + body + optional issue-tracker snippet (Jira or Linear, extracted from the title and body or from the explicit Issue ref).
- local: the resolved spec and plan (if present).

## github mode

Always clone into the work dir in `/tmp` — never touches the user's CWD.

```bash
pr_number=...
repo="owner/name"
work_dir="/tmp/pr-review-${pr_number}"
[ -d "$work_dir" ] && mv "$work_dir" "$work_dir.prev-$(date +%Y%m%dT%H%M%S)"
mkdir -p "$work_dir"

# gh pr diff has no context-width flag, so github mode gets 3-line hunks (vs
# local's -U20); Wave 2 reads the on-disk clone below for deeper context.
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

# Issue-tracker context: Jira or Linear references found in the PR title
# and body. An explicit Issue ref from the input header replaces the
# extraction, since the caller is pointing at an issue the PR text lacks.
# The file is written even when empty; a miss only costs the snippet.
if [ -n "$issue_ref" ]; then
  # Bare keys match only in uppercase in free text, so a typed ref is normalized.
  printf '%s\n' "$issue_ref" | tr '[:lower:]' '[:upper:]'
else
  jq -r '.title, .body' "$work_dir/pr.json"
fi \
  | ~/.claude/skills/code-review-pipeline/scripts/extract-issue-refs.py \
  | ~/.claude/skills/code-review-pipeline/scripts/fetch-issue-context.py \
  > "$work_dir/issue-context.md" || true
```

The fetcher logs one `issue-context:` line per reference on stderr; a reference that neither tracker knows (for example a false-positive key such as `SHA-256`) is a logged miss, never an abort.

```bash
# Clone the PR head
gh repo clone "$repo" "$work_dir/repo" -- --depth=50 --filter=blob:none
git -C "$work_dir/repo" fetch origin "pull/$pr_number/head" --depth=50
git -C "$work_dir/repo" checkout FETCH_HEAD
```

Teardown: work dir stays in `/tmp` for macOS's periodic cleanup. On failure, print the path.

## local mode

Repo root for Wave 2 is the user's CWD; the work dir is scratch for diff/context files.

`base_ref` is supplied by the caller — `auto-review`'s resolved `<BASE_REF>`, or `/implement`'s `BATCH_BASE_SHA` — and may be a branch name, a commit SHA, or `HEAD~N`.

`base_ref` resolution: a branch on origin diffs against the freshly fetched remote copy, so a stale local branch never silently narrows the diff. Anything else must already resolve locally (SHA, `HEAD~N`, tag).

See the script's own `if`/`else` for the exact fallback and its failure message.

```bash
work_dir=$(mktemp -d /tmp/auto-review.XXXXXX)
branch="$(git branch --show-current | tr '/' '-')"
out_base="./verdict_auto-review_${branch}_$(date +%Y-%m-%d_%H:%M)"

bash ~/.claude/skills/code-review-pipeline/scripts/prep-local-context.sh \
  "$base_ref" "$work_dir"
```

### Repo-wide static checks + tests + coverage (local mode)

After the diff files are on disk, gather repo-wide signal (lint, typecheck, dead-code, circular, all test tiers, coverage) into `$work_dir/` for Wave 2 to read alongside the diff.

Full discovery + outputs table + consumption rules live in [`wave1-repo-wide-checks.md`](wave1-repo-wide-checks.md). Load on demand. Local mode only today.

## Tiny-PR and large-PR flags

Both modes size the diff once it is on disk. Local mode's `prep-local-context.sh` already did this and wrote the results to `$work_dir/tiny-pr.txt` and `$work_dir/large-pr.txt` (see above).

Github mode still computes both inline, since it has no equivalent script:

```bash
added_lines=$(grep -c '^+[^+]' "$work_dir/pr.diff" || true)
tiny_pr=false; [ "$added_lines" -lt 100 ] && tiny_pr=true
echo "$tiny_pr" > "$work_dir/tiny-pr.txt"

diff_bytes=$(wc -c < "$work_dir/pr.diff" | tr -d ' ')
large_pr=false; [ "$diff_bytes" -gt 60000 ] && large_pr=true
echo "$large_pr" > "$work_dir/large-pr.txt"
```

If `added_lines < 100`, `tiny_pr=true`: Wave 2's guide step emits a 2-sentence summary instead of the full Review Guide, and Wave 3 is skipped entirely (see Wave 2 and Wave 3 below).

At this scale the whole diff fits comfortably in context, the full guide narrates little a 2-sentence summary doesn't already say, and the per-finding validator adds more cost than it saves.

Otherwise leave `tiny_pr=false` and run the full pipeline.

**Persist it to `$work_dir/tiny-pr.txt`** so Wave 2 can recover the flag from disk instead of trusting working memory after a mid-pipeline compaction.

Without it, a resumed tiny PR reruns Wave 3's full validator pass and writes the long-form guide the flag exists to skip.

If `diff_bytes > 60000`, `large_pr=true`: Wave 2 fans its eight lenses out to one subagent each instead of reviewing inline (see Wave 2).

The byte count is what Wave 2 reads, and 60 KB (~15k tokens) is the most the inline pass can hold beside its measured ~100k-token post-compaction base plus ~25k of rubric and standards text, leaving ~30k for reasoning.

Local diffs carry `-U20` context while github's carry `-U3`, so the same byte gate fans out on a smaller local change on purpose — the context lines get read too.

**Persist it to `$work_dir/large-pr.txt`** for the same reason as `tiny-pr.txt`: a resumed run must take the Wave 2 path it started on, or an inline retry reproduces the compaction loop the flag exists to prevent.
