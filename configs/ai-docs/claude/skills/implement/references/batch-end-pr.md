# Batch-end — open the PR

Read this only when the interview opted into a PR.
On a PR-label run, the branch-record and PR-level status-marker edits live in [`batch-end-pr-branch-record.md`](batch-end-pr-branch-record.md) instead, reached from that same §8.1 step whether or not a PR is also opened.

**Dispatched from inside §8.1, right after its always-run push** (`batch-end-review.md`'s §8.1 step 2), before either gate runs.
The body describes the pre-gate diff; §8.4 refreshes it once the quality-gate and repo-green fixes land — why the PR opens as a draft.

## Open the PR (opt-in)

Only when `pr.wanted: true` (§1.2). Skip this section otherwise.

**When `stack.wanted` is true, this unit opens one PR per task, not one total** — [`stacked-by-task-batch-end.md`](stacked-by-task-batch-end.md) owns that loop. Every requirement below still binds each PR it opens.

**One dispatch owns the PR: `agent(subAgent=pr-creator, title=Open the batch PR)`.**
It composes the body and creates (or updates) the PR — the orchestrator never writes a body.

- **CRITICAL: `pr-creator`, never `core:pr-creator`** — the agent list carries both; `core:pr-creator` is a different, unrelated agent (a generic GitHub PR opener with no create-pr-skill awareness).

  It ignores every requirement this section enumerates (template preservation, `.final.md` output path, untracked-doc-reference stripping, the REST-API update path) — picking it silently drops this whole section's contract.

**The branch is already on the remote — §8.1's step 1 pushed it before this section is reached.**
Push and create are split owners: pushing doesn't depend on a PR being wanted, so a pushed branch with no PR is normal, not an inconsistent state needing cleanup.

- **CRITICAL: re-read this whole section immediately before dispatching — never execute it from a compacted-summary recollection.**
  A paraphrase like "generate the body via a subagent, following create-pr conventions" silently drops every enumerated specific below.
  Re-reading costs one file read; skipping it costs a PR pushed with mandatory sections or safety rules missing.

- Never dispatch a reviewer agent (`code-reviewer`, `spec-reviewer`, `plan-reviewer`, or `test-reviewer`) for this: their shared write-guard hook allows only `verdict_*.md` and `/tmp` writes, denying the `pr_*.final.md` write in CWD.

## Dispatch prompt requirements

- **The dispatch prompt must spell out every requirement below explicitly — never just "follow create-pr's conventions".**
  The agent loads its own skill's conventions but can't see this batch's specifics (output path, PR-label, base branch) unless the prompt states them:

  - Check `.github/PULL_REQUEST_TEMPLATE.md` / `.github/pull_request_template.md` first; if present it's the base structure — keep every section/checkbox, fill with rich content, never replace it.
  - The body's section list and order are `create-pr`'s, owned by [`pr-template.md`](../../create-pr/references/pr-template.md).
    This is the one item the prompt does NOT re-enumerate: the agent loads that file with its own skill.
    A copy here would drift, then silently outrank the original.
    - Drop a section only when it is genuinely N/A for this batch, never silently.

    - Plan-only run (§1.1 resolved no spec) → the acceptance criteria the template puts in the appendix come verbatim from each covered task's `## Task Details` entry, same formatting.
      The plan always carries them, never N/A for want of a spec.

  - `WARNING:`-prefixed items for any manual deploy prerequisite (new secrets, new Parameter-Store values) or other operationally-risky item needing human coordination.
  - Zero references to untracked session docs (`spec_<slug>.md`, `plan_<slug>.md`, `verdict_*.md`, internal task/AC numbers, commit SHAs).
    Verify each with `git ls-files <name>`; substitute the value or drop it.
  - **Create the draft PR only — never push, never force-push**: `gh pr create --draft --title "<title>" --body-file <file> --base <base-branch>`. Never auto-merge.

    - State this in the dispatch prompt explicitly: left unsaid, the agent pushes by default, since its own skill covers the whole flow.

    - **`<base-branch>` is the parent PR's branch for a dependent PR; §1.2's confirmed base for a zero-parent PR or a plain `<task-ids>` run.**
      Read the parent's branch from its PR Breakdown entry's `Branch:` field — the fail-fast stop predicate guarantees the parent's batch-end push already wrote it.
      Targeting the confirmed base instead shows the parent's commits inside this PR's diff until the parent merges — the reviewer burden a multi-PR split exists to remove.

    - A diamond PR (2+ parents) targets its **first-listed** parent's branch.
      GitHub renders one base per PR, so other parents' commits stay in this PR's diff until merged — note it in the PR body.

    - Once a parent PR merges and its branch deletes, GitHub retargets this PR automatically; verification and sync live in [`stacked-prs.md`](stacked-prs.md).

    - Every PR-label run needs this `--base`, dependent or not.
      Without it, `gh pr create` falls back to `branch.<name>.gh-merge-base` or the repo's default branch — never to a parent's branch by any ancestry heuristic.
    - **Branch already has an open PR** (`gh pr create` errors that one exists) → not a failure.
      Fall back to the REST-API body-update path below, targeting that PR number, so a rerun updates its own open PR instead of erroring.
    - **Updating an existing PR's body: use the REST API, never `gh pr edit --body-file`** — the command and its mandatory read-back live in the `gh-cli-usage` skill.
      - Name the skill in the dispatch prompt rather than pasting the command: a third copy drifts the next time GitHub changes the endpoint.

  - Put completed Scout / repo-green fix-loop (§8.3) commits under an **"Unexpected extras"** section in the PR body.
  - Pass §1.2's ticket ID or "none" ([`ticket-id.md`](../../create-pr/references/ticket-id.md)); the subagent cannot ask.

  - Pass the resolved `<this-PR-label>` explicitly in the dispatch prompt, so the subagent opens one PR without asking which it covers — CWD may hold several spec/plan pairs.
  - Assign its body-file output path explicitly:
    - When `pr_label` is non-empty: `./pr_<slug>_<this-PR-label-lowercase>.final.md` (e.g. `pr_multi-pr-implement_pr2.final.md`).
    - On a plain `<task-ids>` run (`pr_label` is `""`): drop the label — `./pr_<slug>.final.md` — matching create-pr's single-PR-plan convention.
    - `.final.md` is the file GitHub receives; create-pr's `.ideal.md` is an intermediate this flow never pushes.

## On failure

**Any failure the agent reports — no `gh`, or a create/update that errored — is a run halt, not a partial package.**
Go to §5.5: name the failure in one short message, keep the state file, print nothing further.

Once this run's last PR has just been created under `Mode: native`, continue to [`batch-end-pr-native-link.md`](batch-end-pr-native-link.md) to register the stack. Skip otherwise.
