# Wave 5 — Emit

## github mode

1. **Re-fetch the commit_sha** so it's fresh (avoids "stale commit_id" rejection):
   ```bash
   commit_sha=$(gh pr view "$pr_number" --repo "$repo" --json headRefOid --jq '.headRefOid')
   ```

2. **Density check.** Every comment body about to be posted must obey doc-standards' cap (≤256 chars / ≤32 words per line) before it goes anywhere near the payload.
   - GitHub's review UI renders a dense paragraph as one hard-to-scan block, with no line breaks to anchor a skim-read.
   - Write each Wave-4 finding's `body` to its own file, `$work_dir/wave5-comment-<n>.md` (one per finding, in finding order).
   - Copy the guide's raw content from `$work_dir/wave2-guide.md` alongside them — it isn't wrapped in `<details>` yet, so it's still plain markdown the script can check.
   - Run `~/.claude/skills/doc-standards/scripts/check-density.sh "$work_dir"/wave5-comment-*.md "$work_dir/wave2-guide.md"` in one call.
   - Fix every flagged line so all files exit 0. Which path you take depends on whether this Wave 5 runs in the top-level session or inside a spawned subagent:
     - **Calling session (you were NOT spawned as a subagent):** delegate to the `density-fixer` agent and wait for it to report every file at exit 0.
       - Pass it the file list: `$work_dir`/wave5-comment-*.md plus `$work_dir/wave2-guide.md`.
       - It splits over-cap lines and re-runs the script itself, and is contractually barred from rewording or dropping content.
       - So each finding's wording stays verbatim — unlike an inline rewrite, which can drift the meaning while fixing density.
     - **Isolated (`--isolate`, or the non-fresh-session dispatch that spawned you):** you are already a subagent, so do NOT spawn another.
       - Rewrite each flagged line in place per `~/.claude/skills/doc-standards/references/density-rules.md` — split into bullets/sub-bullets or shorter sentences, never drop information.
       - Re-run the script until it exits 0 for every file.
   - Either way, the payload-build step below reads finding bodies from these now-clean files; the guide-posting step below reads the guide from `wave2-guide.md`.

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

## local mode

Consult the `html-artifacts` skill's decision tree, then write `${out_file}` — `${out_base}.md` or `${out_base}.html` per its verdict — to the current CWD.

- The routing table's fixed verdict for this artifact type counts as standing approval — skip html-artifacts' propose-first gate here.
  - Why: the pipeline may run unattended (isolated subagent, `/implement`'s batch-end tail), where no per-instance OK is possible; pausing to propose would stall the async run.
- `${out_base}` is set in Wave 1 to `./verdict_auto-review_YYYY-MM-DD_HH:MM`; the timestamp preserves ordering when the user runs several reviews in one CWD. Only the extension is the router's call.
- Either format follows the template at `references/local-review-template.md` — read it and expand its placeholders; an `.html` output renders those same sections under html-artifacts' non-negotiables.
- Keep the template file as the single source of truth for the output shape; do not inline the template here.

**Density check (after writing, `.md` output only).** Run `~/.claude/skills/doc-standards/scripts/check-density.sh "$out_file"`, then fix flagged lines by how this Wave 5 runs:

- **Calling session (you were NOT spawned as a subagent):** delegate to the `density-fixer` agent, passing it `$out_file`; wait for it to report exit 0.
  - It splits over-cap lines and re-runs the script itself, without rewording or dropping content.
- **Isolated (`--isolate`, or the non-fresh-session dispatch that spawned you):** you are already a subagent — do NOT spawn another; rewrite each violation in place per `doc-standards/references/density-rules.md` and re-run until exit 0.
