---
name: sdd-to-linear
description: "Export an approved plan_<slug>.md to Linear, one issue per plan PR, writing the Linear MCP directly. USE when the user says 'export to Linear' or 'sdd-to-linear', or to-plan offers it. One direction only; never reads Linear back into the plan."
---

# SDD To Linear

Export `plan_<slug>.md` to Linear as one issue per plan PR, filled with the user's own taxonomy and content.

The direction is plan to Linear only. Nothing re-derives the plan from Linear, because the plan stays the source of truth for what Linear cannot carry: decision log, dependency graph, planned tests.

Write the Linear MCP tools directly. Never delegate to `core:to-issue` and never to `sdd:export-linear`.

Why: both were refused because they suggest a verbose body and their own structure, where the user wants the plan's task content carried across unchanged.

## Usage

`/sdd-to-linear [path]` — the path to `plan_<slug>.md`. With none given, use the plan `to-plan` just wrote, else ask for the path.

## Process

### 1. Pre-flight: detect the optional module

Run `~/.claude/scripts/get-enabled-modules.py` through the `~/.claude` symlink and read its `linear=` line. Never edit the symlink target to change the result.

- `linear=false`: never show the opt-in question at all. Say the Linear module is absent and stop, with zero Linear calls.

- `linear=true`: ask once via `AskUserQuestion`, recommended answer first, whether to export the plan to Linear. Keep a free-text "something else" option open.

Why ask only when present: a question about a module the machine lacks offers a choice that cannot be taken.

A declined answer means no Linear call anywhere in the run.

### 2. Read the plan and count its PRs

Parse the plan's `### PR-N.` headings under the PR Breakdown, each with its `**Tasks**:`, `**Branch**:` and `**Linear**:` fields.

A PR Breakdown holding zero PRs produces zero Linear writes. Say so and stop, never inventing a catch-all issue.

Why: an invented issue maps to no PR, so the one-issue-per-PR link the reader relies on breaks.

### 3. Read the live taxonomy

Read the workspace with read-only calls before any write: `list_teams`, `list_initiatives`, `list_projects`, `list_issue_labels`, and `list_milestones` for the chosen project.

Never hardcode a label value. Derive the candidate values from what `list_issue_labels` returns.

Why: label values change in the workspace, and a value this file named would go stale silently.

Ask the user once, in one `AskUserQuestion` call with a recommended answer first, for the initiative, project and team, unless the plan's document-level `Linear:` line already names them.

### 4. Resolve each PR's labels

Two label groups are single-select, so exactly one value of each lands per issue:

- `Application`.

- `Issue Type`.

Derive each PR's value from the tasks that roll into it.

Never set `Issue Origin`. Arco's own plugins and skills own that field.

Milestone: set one only where the PR is a feature. Leave it empty for a non-feature PR.

**Ask per ambiguous PR.** Ask when the PR's tasks span two or more `Application` values, or no `Issue Type` value clearly applies.

- List the candidates you derived, recommended one first, and ask which single value to use.

- Write that PR's issue only once answered.

- Keep going with the other PRs meanwhile, so the unambiguous ones still land in the same run.

- Never question a PR whose labels resolve unambiguously.

Why: writing both values would violate the single-select group, and aborting the run would block PRs that had no ambiguity.

### 5. Write one issue per PR

Read [`references/issue-write-rules.md`](references/issue-write-rules.md) before the first write. It holds the body shape, the idempotent re-run match, and the status check.

Create exactly one issue per PR, in the plan's order. Never collapse several PRs into one issue and never add an extra one.

Set initiative, project, the `Application` label, the `Issue Type` label, and the milestone where the PR is a feature.

The body carries the tasks that roll into that PR, in the user's own content shape, never Arco's suggested body.

Write every Linear issue in PT-BR, matching the user's flat rule for PR and Linear text.

After each successful create, write that issue's URL into the plan's `**Linear**:` field for that PR, wrapped in backticks.

Why backticks: the plan parser's field reader ends a value at the first period, so a bare `https://linear.app/...` truncates at `https://linear`.

After the run's first issue lands, write the plan's document-level `Linear:` line with the resolved project or initiative URL, wrapped in backticks the same way.

A run that writes zero issues writes no `Linear:` line, matching the zero-PR rule.

Once every issue this run creates exists, mirror the plan's dependency graph: write each PR's `Depends on` as a `blockedBy` relation on that PR's issue through `save_issue`.

Write relations only after all the issues exist, because a relation needs both endpoints.

Read a relation back with `get_issue(includeRelations: true)` to verify it landed.

The plan stays the source of truth and Linear is a projection of it, never the origin. Export only a graph `check-pr-dag.sh`, `check-tasks-dag.sh` and `check-pr-task-projection.py` already accepted.

Why: Linear documents no cycle detection and no depth limit on `blocks`/`blockedBy`.

So those three gates alone can reject a cyclic or cross-level graph.

Exporting only a graph they accepted keeps an uncheckable cycle out of Linear.

Once the issues exist, write each PR's decisions as one comment on that PR's issue through `save_comment`.

The comment carries the decisions recorded in the tasks that roll into that PR, and the alternatives each one discarded.

`save_comment` takes markdown, threads through `parentId`, and attributes the author automatically.

Write a mermaid block inside a decision through unchanged, because Linear renders a `mermaid` fenced block natively.

A PR whose tasks record no decision gets no comment at all, never an empty or placeholder one.

Then set the Linear project description from `spec_<slug>.md` when it sits beside the plan.

Take its `## Background / Context` and `## Functional Decisions` sections.

Read the current description first. Where it is non-empty and no previous run of this export wrote it, hand it back to the user with the project URL and write nothing, the same rule as an in-flight issue.

Where no spec exists, the export still runs and the project description stays as the user set it, never overwritten with plan-derived filler.

Why: a colleague opening any one issue reaches the reasoning behind the whole project without the plan file.

Write the comments and the project description in PT-BR, the same rule as the issues.

### 6. Handle failure

**A write failure partway stops the export.**

- Report which PRs got issues and which did not.

- Write the `**Linear**:` field only for the issues actually created.

- Never retry silently. Offer the retry to the user instead.

- Apply the same rule to a `blockedBy` relation whose blocking PR has no issue, because the export stopped early or that PR was skipped.

- Name that specific relation, finish the rest of the export, and never report a clean export over a partial one.

- Apply the same rule to a rejected comment write and a rejected project-description write.

- Name the specific comment, by its PR, or the description that did not land, and finish the rest of the export.

**A module failure degrades, never aborts.** This covers a disconnected MCP, a call that times out or never responds, a 5xx, and an auth or permission rejection.

A failure on a call that would have written, an issue create or update, is a write failure first, so the stop-and-report rule above wins. Degrade only when no write was ever possible: the module is disconnected, or it rejected the run before its first write.

- Degrade to the user's own non-Linear path: the plan file alone, which is complete without Linear.

- Report the degradation loudly, naming the failed call.

- Continue the run. Never abort and never fail closed.

Why: the plan works identically with no Linear at all, so losing the module costs a projection, never the work.

### 7. Report the tree

End by reporting every URL the run created as a nested bullet tree in the plan's own order. Put the project or initiative at the root and each PR's issue beneath it.

Flag separately each issue handed back for being In Progress, In Review or Done, and each PR that got no issue.

Also list each `blockedBy` relation left unwritten, naming both PRs, so a partial tree is never read as clean.

Name too each comment write and the project-description write that was rejected, for the same reason.

Why: the reader walks from plan to Linear without opening the workspace.

## Flowchart (human-facing)

[`assets/flowchart.md`](assets/flowchart.md) diagrams this skill's flow for the human. Don't load it — non-authoritative, the steps above win; regenerate it whenever the flow changes.
