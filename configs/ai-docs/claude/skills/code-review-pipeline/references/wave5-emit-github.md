# Wave 5 — Emit (github mode)

Read this only in **github mode**; local mode uses [`wave5-emit-local.md`](wave5-emit-local.md).

## Prepare the payload inputs

1. **Re-fetch the commit_sha** so it's fresh (avoids "stale commit_id" rejection):
   ```bash
   commit_sha=$(gh pr view "$pr_number" --repo "$repo" --json headRefOid --jq '.headRefOid')
   ```

2. **doc-standards check.** Every comment body is measured against doc-standards' line rules before it reaches the payload — the density cap and the bullet blank-line rule.
   - GitHub's review UI renders a dense paragraph as one hard-to-scan block, with no line breaks to anchor a skim-read.
   - Write each Wave-4 finding's `body` to its own file, `$work_dir/wave5-comment-<n>.md` (one per finding, in finding order).

   - Copy the guide's raw content from `$work_dir/wave2-guide.md` alongside them — it isn't wrapped in `<details>` yet, so it's still plain markdown the script can check.

   - Run `~/.claude/skills/doc-standards/scripts/check-density.sh "$work_dir"/wave5-comment-*.md "$work_dir/wave2-guide.md"` in one call.

   - Run `~/.claude/skills/doc-standards/scripts/check-bullet-gap.py "$work_dir"/wave5-comment-*.md "$work_dir/wave2-guide.md"` in one call too.

   - Report what they flag; never repair it, and never dispatch `markdown-standards-fixer`.
     - Reflowing prose is a judgment call that has already split sentences mid-phrase across bullet boundaries and damaged a document, and this step has no channel to ask the user.

   - The report is ONE `[Scout]` TaskList entry per offending file, naming the file and what is off standard.
   - Where that entry lands depends on whether this Wave 5 was spawned as a subagent:
     - **Calling session (you were NOT spawned as a subagent):** file those `[Scout]` entries yourself.
     - **Isolated (you WERE spawned as a subagent):** carry them into your Wave 6 summary instead, for the calling session to file.
       - A subagent's TaskList write never reaches the user who triages it.

   - Either way, build the payload from the bodies exactly as written. An over-cap comment still posts, because the user alone decides if and when that Scout runs.

## Build and POST the pending review

3. Build `$work_dir/review-payload.json` with jq for the inline comments only, sourcing each `body` verbatim from its `$work_dir/wave5-comment-<n>.md`.
   - **Leave the top-level `body` empty** — the Review Guide is delivered as a separate standalone PR comment in the guide-posting step below.
     - Rationale: a guide in the body gets buried behind GitHub's review filter.

   - Every inline comment body gets the signature footer appended: two newlines + `— gerado por IA, revisado pelo usuário`.
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
         "body": "<finding body>\n\n— gerado por IA, revisado pelo usuário"
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
   - Never fall back to the single-comment endpoint (`POST .../pulls/{pull_number}/comments`) or to `gh pr review`, even for findings the retry couldn't place.
     - Both submit immediately with no way to stay pending, worse than not posting those findings at all.

   - If the retry also fails, stop and report the 422 body to the user instead of degrading the contract further.

## Confirm nothing submitted the review

6. **Verify the review actually stayed pending** — a POST response of `"state": "PENDING"` is not proof by itself.
   - Re-fetch the same review a moment later and check again.
   - Something between POST and report-out (a stray follow-up call, a retry, a second Wave-5 run in the same session) can submit it without your noticing:

   ```bash
   gh api repos/"$repo"/pulls/"$pr_number"/reviews/"$review_id" --jq '{state, submitted_at}'
   ```

   - Expect `{"state": "PENDING", "submitted_at": null}`.
   - Anything else — `COMMENTED`, `APPROVED`, `CHANGES_REQUESTED`, or a non-null `submitted_at` — means the review already went live.

   - A submitted review can't be put back to pending via the API (only its individual comments can be deleted, one by one, via `DELETE /repos/{owner}/{repo}/pulls/comments/{comment_id}`).

   - Also re-fetch `.../reviews/"$review_id"/comments` and confirm the comment count and line numbers match `review-payload.json` exactly — an unexpected extra comment or mismatched count is the same signal as an unexpected state.

   - **If either check comes back wrong, stop: don't declare success** — report the actual state (or the mismatch) to the user.
     - Never call anything that submits a review (no `event` field on the POST, no follow-up call to `.../reviews/{id}/events`, no `gh pr review --comment/--approve/--request-changes`).
     - Submitting is the human's action alone.

## Post the Review Guide as its own PR comment

7. **Post the Review Guide as a standalone PR comment**, wrapped in a collapsed `<details>` block so it doesn't dominate the conversation feed but stays one click away.
   - Its content is `$work_dir/wave2-guide.md`, already measured by the density-check step above — don't re-check it here.
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

   — gerado por IA, revisado pelo usuário
   ```

   Print both `review_url` (pending review) and `guide_url` (standalone comment) in Wave 6.
