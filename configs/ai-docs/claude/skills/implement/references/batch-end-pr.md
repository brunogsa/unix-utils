# Batch-end — PR manifest & draft PR

Read this only when the batch is a PR-label run, or when the interview opted into a draft PR.

When neither applies, go straight from "Run metrics" to "Finalize" in [`batch-end-package.md`](batch-end-package.md) — this whole file is skipped.

## PR manifest entry & PR-level status marker (PR-label runs only)

Skip this whole section on a plain `<task-ids>` run (no `PR-N` label, `pr_label` is `""`).

- **Manifest entry** — record this PR's own branch, once, regardless of terminal outcome:
  ```bash
  ~/.claude/skills/implement/scripts/append-branch-pr-entry.sh <worktree-path>/branches_<slug>.md <slug> <this-PR-label> <this-PR-branch>
  ```
  `<this-PR-branch>` is `git branch --show-current` right now. See `references/pr-awareness.md`'s "Manifest writes" for why this write belongs here and not at branch creation.
- **PR-level status marker** — on a fully **`[Done]`** batch only (every task `[Done]`, repo-green gate passed), update this PR's own line in the plan's PR Breakdown.
  This mirrors §6's task-level marker convention one level up:
  ```
  N. **[Done] PR-N** — <theme>. Tasks: <N, N>. Depends on: <none | PR-N>.
  ```
  Write it inline, in the same edit style as a task-level marker — never scripted.
  A halted batch (any task `blocked`/`stuck`, or the gate failed) leaves the PR Breakdown line **unmarked**.
  Resuming re-evaluates it, so a partial PR must never read as `[Done]`.

## Draft PR (opt-in)

Only when the interview opted into a draft PR (§1.2). Skip this section entirely otherwise.

- **CRITICAL: re-read this whole section fresh immediately before dispatching — never execute it from a compacted-summary recollection.**
  A post-compaction paraphrase like "generate the body via a subagent, following create-pr conventions" is lossy.
  It silently drops the enumerated specifics below (template check, TAC-verbatim, `WARNING:`-prefixed items, exact output path, REST-API-PATCH-only).
  The cost of re-reading is one file read; the cost of skipping it is a PR body already pushed to GitHub with mandatory sections missing.
- **Guard first** — if `gh` is absent or the repo has no remote, skip the PR with an explicit notice in the package; everything else in the package is unaffected.
- Otherwise **push the branch** and create a **draft** PR with `gh pr create --draft --body-file <file> --base <base-branch>`, where `<base-branch>` is §1.2's confirmed base branch. Never auto-merge, never force-push.
  - Every PR-label run needs this `--base`, dependent or not.
    Without it, `gh pr create` falls back to `branch.<name>.gh-merge-base` or the repo's default branch — never to a parent's branch by any ancestry heuristic.
    That fallback is implicit, not the plan's explicitly confirmed choice.
  - **This branch already has an open PR** (`gh pr create` errors that a PR already exists) → not a failure.
    Fall back to the same REST-API body-update path below, targeting that existing PR number.
    A resumed batch updates its own already-open PR instead of erroring.
  - **Updating an existing PR's body: use the REST API, never `gh pr edit --body-file`** — `gh api --method PATCH repos/<owner>/<repo>/pulls/<n> -F body=@<file>`.
    - `gh pr edit` eagerly queries Projects-classic `projectCards`; on repos where classic Projects is sunset it errors on that query and the write silently doesn't land.
    - The REST endpoint touches no Projects data.
    - Read the body back afterward to confirm it landed.
- Generate the description with the **`create-pr` agent** (Agent tool, `subagent_type=create-pr` — its frontmatter pins model/effort, no override needed) from the spec/plan and commit bodies.
  - Never dispatch `deep-reviewer` for this: its write-guard hook allows only `verdict_*.md` and `/tmp` writes, and denies a `pr-descr_*.md` write in CWD outright.
  - Scope this dispatch to drafting only — the agent's own skill would otherwise push and create the PR itself, which the orchestrator owns instead (see "must not push" below).
  - **The dispatch prompt must spell out every one of these requirements explicitly — never just "follow create-pr's conventions" by bare reference.**
    The agent loads its own skill's conventions, but has no visibility into this batch's own specifics (output path, PR-label, draft-only scope) unless the prompt states them.
    A vague pointer produces the same silently-incomplete body this note exists to prevent:
    - Check `.github/PULL_REQUEST_TEMPLATE.md` / `.github/pull_request_template.md` first; if present it's the base structure — keep every section/checkbox, fill with rich content, never replace it.
    - The 8-section required order (drop any that are genuinely N/A, never silently):
      1. Jira link
      2. Context (business problem, layered)
      3. Testable Acceptance Criteria (verbatim from spec, `AC-N:` prefix dropped, each ending in a `> Covered by ...` pointer)
      4. Architecture (diagrams + a Decisions subsection)
      5. Changes (Planned + Discovered)
      6. Checklist (preserve the team's template checklist verbatim)
      7. Evidences (value-add only, one line per claim)
      8. References (last)
    - `WARNING:`-prefixed items for any manual deploy prerequisite (new secrets, new Parameter-Store values) or other operationally-risky item needing human coordination.
    - Zero references to untracked session docs (`spec_<slug>.md`, `plan_<slug>.md`, `verdict_*.md`, internal task/AC numbers, commit SHAs in prose).
      Verify each candidate reference with `git ls-files <name>` first; substitute the value or drop the reference.
  - Pass the resolved `<this-PR-label>` explicitly in the dispatch prompt, so the subagent writes one PR's description, never asks which PR it covers.
    The CWD may hold several spec/plan pairs, and a PR-label run may cover several PRs, so an unstated label binds to the wrong one.
  - Assign its output path explicitly:
    - When `pr_label` is non-empty: `./pr-descr_<slug>_<this-PR-label-lowercase>.md` (e.g. `pr-descr_multi-pr-implement_pr2.md`).
    - On a plain `<task-ids>` run (`pr_label` is `""`): drop the suffix entirely — `./pr-descr_<slug>.md` — matching create-pr's own single-PR-plan convention.
    - The subagent writes that file directly; the orchestrator then reads it for `--body-file`.
  - It must not push or commit — the orchestrator owns the push.
  - Its tokens are **not tracked**: metrics print before this step, and a presented run's state file is deleted right after — so don't add a `tokens` field for it.
- Put completed Scout / repo-green fixes under an **"Unexpected extras"** section in the PR body.

