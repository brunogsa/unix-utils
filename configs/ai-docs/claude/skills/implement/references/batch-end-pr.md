# Batch-end — branch record & the PR itself

Read this only when the batch is a PR-label run, or when the interview opted into a PR.

**Dispatched from inside Finalize (§8.3), right after its always-run push** (`batch-end-review.md`'s "Finalize" step 2).
The PR body then describes the batch's final diff — quality-gate and repo-green fixes included — in one pass.

## Branch record & PR-level status marker (PR-label runs only)

Skip this section on a plain `<task-ids>` run (no `PR-N` label, `pr_label` is `""`).

Both edits below land on this PR's own line in the plan's PR Breakdown, in one pass:

- **`Branch:` clause** — record this PR's branch (`git branch --show-current` right now), once, regardless of whether step 2 succeeds.
  See `references/pr-awareness.md`'s "Branch recording" for why this write belongs here, not at branch creation.

- **PR-level status marker** — set this PR's own line to **`[Done]`**, mirroring §6's task-level marker convention one level up:
  ```
  N. **[Done] PR-N** — <theme>. Tasks: <N, N>. Depends on: <none | PR-N>. Branch: `<branch-name>`.
  ```
  Write both inline, in a task-level marker's edit style — never scripted.
  Reaching here means every task is `[Done]` — a unit that couldn't finish halted at §5.5.
  The marker reflects the *code* being done: a PR that fails to open still halts the run (§5.5), but its work is finished.

## Open the PR (opt-in)

Only when the interview opted into a PR (§1.2, `pr.wanted: true`). Skip this section otherwise.

**One dispatch owns the PR: `agent(subAgent=pr-creator, title=Open the batch PR)`.**
It composes the body and creates (or updates) the PR — the orchestrator never writes a body.

**The branch is already on the remote — Finalize's step 1 pushed it before this section is reached.**
Push and create are split owners: pushing no longer depends on a PR being wanted, so a pushed branch with no PR is a normal outcome, not an inconsistent state needing cleanup.

- **CRITICAL: re-read this whole section fresh immediately before dispatching — never execute it from a compacted-summary recollection.**
  A paraphrase like "generate the body via a subagent, following create-pr conventions" silently drops every enumerated specific below.
  Re-reading costs one file read; skipping it costs a PR pushed with mandatory sections or safety rules missing.

- Never dispatch `deep-reviewer` for this: its write-guard hook allows only `verdict_*.md` and `/tmp` writes, denying the `pr_*.final.md` write in CWD.

- **The dispatch prompt must spell out every requirement below explicitly — never just "follow create-pr's conventions" by bare reference.**
  The agent loads its own skill's conventions but can't see this batch's specifics (output path, PR-label, base branch) unless the prompt states them:

  - Check `.github/PULL_REQUEST_TEMPLATE.md` / `.github/pull_request_template.md` first; if present it's the base structure — keep every section/checkbox, fill with rich content, never replace it.
  - The 8-section required order (drop any genuinely N/A, never silently):
    1. Jira link
    2. Context (business problem, layered)
    3. Testable Acceptance Criteria (verbatim from spec, `AC-N:` prefix dropped, each ending in a `> Covered by ...` pointer)
       - Plan-only run (§1.1 resolved no spec) → take them verbatim from each covered task's **Testable Acceptance criteria** list in the plan, same formatting.
         The plan always carries them, so this section is never N/A merely for want of a spec.

    4. Architecture (diagrams + a Decisions subsection)
    5. Changes (Planned + Discovered)
    6. Checklist (preserve the team's template checklist verbatim)
    7. Evidences (value-add only, one line per claim)
    8. References (last)

  - `WARNING:`-prefixed items for any manual deploy prerequisite (new secrets, new Parameter-Store values) or other operationally-risky item needing human coordination.
  - Zero references to untracked session docs (`spec_<slug>.md`, `plan_<slug>.md`, `verdict_*.md`, internal task/AC numbers, commit SHAs in prose).
    Verify each candidate with `git ls-files <name>` first; substitute the value or drop the reference.
  - **Create the draft PR only — never push, never force-push**: `gh pr create --draft --body-file <file> --base <base-branch>`. Never auto-merge.

    - State this in the dispatch prompt explicitly: left unsaid, the agent pushes by default, since its own skill covers the whole flow.

    - **`<base-branch>` is the parent PR's branch for a dependent PR; §1.2's confirmed base for a zero-parent PR or a plain `<task-ids>` run.**
      Read the parent's branch from its PR Breakdown line's `Branch:` clause — the fail-fast stop predicate guarantees the parent's batch-end push already wrote it.
      Targeting the confirmed base instead shows the parent's commits inside this PR's diff until the parent merges — the reviewer burden a multi-PR split exists to remove.

    - A diamond PR (2+ parents) targets its **first-listed** parent's branch.
      GitHub renders one base per PR, so the other parents' commits stay in this PR's diff until they merge — note it in the PR body as a platform limit.

    - Once a parent PR merges and its branch is deleted, GitHub retargets this PR automatically; verification and post-merge sync live in `gh-cli-usage`'s `references/stacked-prs.md`.

    - Every PR-label run needs this `--base`, dependent or not.
      Without it, `gh pr create` falls back to `branch.<name>.gh-merge-base` or the repo's default branch — never to a parent's branch by any ancestry heuristic.
      That fallback is implicit, not the plan's resolved choice.
    - **Branch already has an open PR** (`gh pr create` errors that one exists) → not a failure.
      Fall back to the REST-API body-update path below, targeting that PR number, so a rerun of `/implement` updates its own open PR instead of erroring.
    - **Updating an existing PR's body: use the REST API, never `gh pr edit --body-file`** — `gh api --method PATCH repos/<owner>/<repo>/pulls/<n> -F body=@<file>`.
      - `gh pr edit` queries Projects-classic `projectCards`; where classic Projects is sunset it errors on that query and the write silently doesn't land — the REST endpoint touches no Projects data.

      - Read the body back afterward to confirm it landed.

  - Put completed Scout / repo-green fix-loop (§8.2) commits under an **"Unexpected extras"** section in the PR body.
  - Pass the resolved `<this-PR-label>` explicitly in the dispatch prompt, so the subagent opens one PR and never asks which it covers.
    The CWD may hold several spec/plan pairs, so an unstated label binds to the wrong one.
  - Assign its body-file output path explicitly:
    - When `pr_label` is non-empty: `./pr_<slug>_<this-PR-label-lowercase>.final.md` (e.g. `pr_multi-pr-implement_pr2.final.md`).
    - On a plain `<task-ids>` run (`pr_label` is `""`): drop the label — `./pr_<slug>.final.md` — matching create-pr's single-PR-plan convention.
    - `.final.md` is the file GitHub receives; create-pr's `.ideal.md` is an intermediate this flow never pushes.

**Any failure the agent reports — no `gh`, or a create/update that errored — is a run halt, not a partial package.**
A push failure can't surface here: Finalize's step 1 owns the push and already halted if it failed.
Go to §5.5: name the failure in one short message, keep the state file, print nothing further — there is nothing to present when the PR was never published.
