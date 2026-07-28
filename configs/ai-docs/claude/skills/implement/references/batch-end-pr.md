# Batch-end — branch record & the PR itself

Read this only when the batch is a PR-label run, or when the interview opted into a PR.

**Dispatched from inside Finalize (§8.3), right after its always-run push** (`batch-end-review.md`'s "Finalize" step 2).
The PR body describes the batch's final diff, including whatever the quality gate applied and the repo-green gate then verified, in one pass.

## Branch record & PR-level status marker (PR-label runs only)

Skip this whole section on a plain `<task-ids>` run (no `PR-N` label, `pr_label` is `""`).

Both edits below land on this PR's own line in the plan's PR Breakdown, in one pass:

- **`Branch:` clause** — record this PR's own branch, once, regardless of whether step 2 (opening the PR) later succeeds.
  `<this-PR-branch>` is `git branch --show-current` right now.
  See `references/pr-awareness.md`'s "Branch recording" for why this write belongs here and not at branch creation.
- **PR-level status marker** — set this PR's own line to **`[Done]`**.
  This step is reached only when every task is already `[Done]`.
  A unit that couldn't finish halted at §5.5 long before it got here.
  This mirrors §6's task-level marker convention one level up:
  ```
  N. **[Done] PR-N** — <theme>. Tasks: <N, N>. Depends on: <none | PR-N>. Branch: `<branch-name>`.
  ```
  Write both inline, in the same edit style as a task-level marker — never scripted.
  The marker reflects the *code* being done, independent of whether step 2 opens the PR.
  A PR that fails to open still halts the run (§5.5), but the work behind it is finished.

## Open the PR (opt-in)

Only when the interview opted into a PR (§1.2, `pr.wanted: true`). Skip this section entirely otherwise.

**One dispatch owns the PR: `agent(subAgent=pr-creator, title=Open the batch PR)`.**
It composes the body and creates (or updates) the PR — the orchestrator never writes a body.

**The branch is already on the remote — Finalize's step 1 pushed it, on every batch end, before this section is reached.**
Push and create are deliberately split owners now: pushing no longer depends on a PR being wanted.
A pushed branch with no PR is the default outcome rather than an inconsistent state needing cleanup.

- **CRITICAL: re-read this whole section fresh immediately before dispatching — never execute it from a compacted-summary recollection.**
  A post-compaction paraphrase like "generate the body via a subagent, following create-pr conventions" is lossy.
  It silently drops the enumerated specifics below (template check, TAC-verbatim, `WARNING:`-prefixed items, exact output path, the push/create requirements, REST-API-PATCH-only).
  Re-reading costs one file read; skipping it costs a PR pushed to GitHub with mandatory sections or safety rules missing.
- Never dispatch `deep-reviewer` for this: its write-guard hook allows only `verdict_*.md` and `/tmp` writes, and denies a `pr_*.final.md` write in CWD outright.
- **The dispatch prompt must spell out every one of these requirements explicitly — never just "follow create-pr's conventions" by bare reference.**
  The agent loads its own skill's conventions, but has no visibility into this batch's own specifics (output path, PR-label, base branch) unless the prompt states them.
  Every requirement below belongs **in the dispatch prompt**, not left for the agent to infer:
  - Check `.github/PULL_REQUEST_TEMPLATE.md` / `.github/pull_request_template.md` first; if present it's the base structure — keep every section/checkbox, fill with rich content, never replace it.
  - The 8-section required order (drop any that are genuinely N/A, never silently):
    1. Jira link
    2. Context (business problem, layered)
    3. Testable Acceptance Criteria (verbatim from spec, `AC-N:` prefix dropped, each ending in a `> Covered by ...` pointer)
       - Plan-only run (§1.1 resolved no spec) → take them verbatim from each covered task's **Testable Acceptance criteria** list in the plan instead, same formatting.
       - The plan always carries them per task, so this section is never dropped as N/A merely for want of a spec.

    4. Architecture (diagrams + a Decisions subsection)
    5. Changes (Planned + Discovered)
    6. Checklist (preserve the team's template checklist verbatim)
    7. Evidences (value-add only, one line per claim)
    8. References (last)

  - `WARNING:`-prefixed items for any manual deploy prerequisite (new secrets, new Parameter-Store values) or other operationally-risky item needing human coordination.
  - Zero references to untracked session docs (`spec_<slug>.md`, `plan_<slug>.md`, `verdict_*.md`, internal task/AC numbers, commit SHAs in prose).
    Verify each candidate reference with `git ls-files <name>` first; substitute the value or drop the reference.
  - **Create the draft PR only — never push, never force-push**: `gh pr create --draft --body-file <file> --base <base-branch>`, where `<base-branch>` is §1.2's confirmed base branch. Never auto-merge.

    - State this in the dispatch prompt explicitly. Left unsaid, the agent pushes by default, since its own skill covers the case where it owns the whole flow.

    - Every PR-label run needs this `--base`, dependent or not.
      Without it, `gh pr create` falls back to `branch.<name>.gh-merge-base` or the repo's default branch — never to a parent's branch by any ancestry heuristic.
      That fallback is implicit, not the plan's explicitly confirmed choice.
    - **This branch already has an open PR** (`gh pr create` errors that a PR already exists) → not a failure.
      Fall back to the REST-API body-update path below, targeting that existing PR number — a rerun of `/implement` on the same branch updates its own already-open PR instead of erroring.
    - **Updating an existing PR's body: use the REST API, never `gh pr edit --body-file`** — `gh api --method PATCH repos/<owner>/<repo>/pulls/<n> -F body=@<file>`.
      - `gh pr edit` eagerly queries Projects-classic `projectCards`; on repos where classic Projects is sunset it errors on that query and the write silently doesn't land.

      - The REST endpoint touches no Projects data.
      - Read the body back afterward to confirm it landed.

  - Put completed Scout / repo-green fix-loop (§8.2) commits under an **"Unexpected extras"** section in the PR body.
  - Pass the resolved `<this-PR-label>` explicitly in the dispatch prompt, so the subagent writes and opens one PR, never asks which PR it covers.
    The CWD may hold several spec/plan pairs and a run may cover several PRs, so an unstated label binds to the wrong one.
  - Assign its body-file output path explicitly:
    - When `pr_label` is non-empty: `./pr_<slug>_<this-PR-label-lowercase>.final.md` (e.g. `pr_multi-pr-implement_pr2.final.md`).
    - On a plain `<task-ids>` run (`pr_label` is `""`): drop the label entirely — `./pr_<slug>.final.md` — matching create-pr's own single-PR-plan convention.
    - `.final.md` is the file GitHub receives; create-pr's `.ideal.md` is an intermediate this flow never pushes.

**Any failure the agent reports — no `gh`, or a create/update that errored — is a run halt, not a partial package.**
A push failure can't surface here: Finalize's step 1 owns the push and already halted the run if it failed.
Go to §5.5: name the failure in one short message, keep the state file, print nothing further. There is nothing to present when the PR the package would describe was never published.

