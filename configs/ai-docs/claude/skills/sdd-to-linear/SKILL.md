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

Run `~/.claude/scripts/detect-modules.sh` through the `~/.claude` symlink and read its `linear=` line. Never edit the symlink target to change the result.

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

### 6. Handle failure

**A write failure partway stops the export.**

- Report which PRs got issues and which did not.

- Write the `**Linear**:` field only for the issues actually created.

- Never retry silently. Offer the retry to the user instead.

**A module failure degrades, never aborts.** This covers a disconnected MCP, a call that times out or never responds, a 5xx, and an auth or permission rejection.

- Degrade to the user's own non-Linear path: the plan file alone, which is complete without Linear.

- Report the degradation loudly, naming the failed call.

- Continue the run. Never abort and never fail closed.

Why: the plan works identically with no Linear at all, so losing the module costs a projection, never the work.

### 7. Report the tree

End by reporting every URL the run created as a nested bullet tree in the plan's own order. Put the project or initiative at the root and each PR's issue beneath it.

Flag separately each issue handed back for being In Progress, In Review or Done, and each PR that got no issue.

Why: the reader walks from plan to Linear without opening the workspace.
