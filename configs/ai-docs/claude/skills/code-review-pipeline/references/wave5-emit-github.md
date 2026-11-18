# Wave 5 - Emit (github mode)

Read this only in **github mode**; local mode uses [`wave5-emit-local.md`](wave5-emit-local.md).

## Prepare the payload inputs

1. **Re-fetch the commit_sha** so it's fresh (avoids "stale commit_id" rejection):
   ```bash
   commit_sha=$(gh pr view "$pr_number" --repo "$repo" --json headRefOid --jq '.headRefOid')
   ```

2. Run `python3 ~/.claude/skills/code-review-pipeline/scripts/check-finding-bodies.py --findings-json "$work_dir/wave4-findings.json"`.
   - On exit 1, rewrite only the flagged bodies in `wave4-findings.json` and re-run, at most twice.

   - Fix a budget violation by cutting prose, and a cited rule source by stating the principle it stands for; never drop Sugestão or Trade-off.

   - Report any violations still remaining in Wave 6 rather than looping. Exit 2 means the file is unreadable - stop and report it.

   - Why: these comments post under the human's name to a PR the whole team reads, so the body rules in `review-principles.md` must hold before posting, not only in local verdict files.

3. Write each Wave-4 finding's `body` to its own file, `$work_dir/wave5-comment-<n>.md` (one per finding, in finding order).

## Build and POST the pending review

4. Build `$work_dir/review-payload.json` with jq for the inline comments only, sourcing each `body` verbatim from its `$work_dir/wave5-comment-<n>.md`.
   - **Leave the top-level `body` empty** - the review guide is a separate PR comment, posted by `/pr-review` through the `code-review-guide` skill.
     - Rationale: a guide in the body gets buried behind GitHub's review filter.

   - Every inline comment body gets the signature footer appended: two newlines + `gerado por IA, revisado pelo usuário`.
     - Rationale: `gh api` authenticates as the human operator, so comments need an explicit AI disclaimer.

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
         "body": "<finding body>\n\ngerado por IA, revisado pelo usuário"
       }
     ]
   }
   ```

5. POST as a **pending** review (no `event` field), in exactly one call - the whole `comments[]` array goes in this single request, never one comment at a time:

   ```bash
   gh api repos/"$repo"/pulls/"$pr_number"/reviews \
     --method POST \
     --input "$work_dir/review-payload.json" \
     > "$work_dir/review-response.json"

   review_id=$(jq -r '.id' "$work_dir/review-response.json")
   review_url=$(jq -r '.html_url // "(pending - open PR and filter reviews)"' "$work_dir/review-response.json")
   ```

6. If the POST fails (422), re-read line numbers from `commentable-lines.txt` and drop findings whose anchors are unresolvable, then retry once **with the same single-batch-POST shape**.
   - Same endpoint, same one call, just a smaller `comments[]`.
   - Never fall back to the single-comment endpoint (`POST .../pulls/{pull_number}/comments`) or to `gh pr review`, even for findings the retry couldn't place.
     - Both submit immediately with no way to stay pending, worse than not posting those findings at all.

   - If the retry also fails, stop and report the 422 body to the user instead of degrading the contract further.

## Confirm nothing submitted the review

7. **Verify the review actually stayed pending** - a POST response of `"state": "PENDING"` is not proof by itself.
   - Re-fetch the same review a moment later and check again.
   - Something between POST and report-out (a stray follow-up call, a retry, a second Wave-5 run in the same session) can submit it without your noticing:

   ```bash
   gh api repos/"$repo"/pulls/"$pr_number"/reviews/"$review_id" --jq '{state, submitted_at}'
   ```

   - Expect `{"state": "PENDING", "submitted_at": null}`.
   - Anything else - `COMMENTED`, `APPROVED`, `CHANGES_REQUESTED`, or a non-null `submitted_at` - means the review already went live.

   - A submitted review can't be put back to pending via the API (only its individual comments can be deleted, one by one, via `DELETE /repos/{owner}/{repo}/pulls/comments/{comment_id}`).

   - Also re-fetch `.../reviews/"$review_id"/comments` and confirm the comment count and line numbers match `review-payload.json` exactly - an unexpected extra comment or mismatched count is the same signal as an unexpected state.

   - **If either check comes back wrong, stop: don't declare success** - report the actual state (or the mismatch) to the user.
     - Never call anything that submits a review (no `event` field on the POST, no follow-up call to `.../reviews/{id}/events`, no `gh pr review --comment/--approve/--request-changes`).
     - Submitting is the human's action alone.
