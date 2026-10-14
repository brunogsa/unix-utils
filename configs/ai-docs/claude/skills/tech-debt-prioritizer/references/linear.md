# Linear commands for the tech-debt-prioritizer workflow

Exact calls for each workflow step in `../SKILL.md`, using the Linear MCP plugin (`mcp__plugin_linear_linear__*`).

## Read the issue (step 1)

- `get_issue` with the issue id (like `CDPI-399`).
- `list_comments` for the same issue, so the rationale accounts for what was already discussed.

## Priority mapping (steps 3-4)

`save_issue` takes `priority` as a number: `0=None, 1=Urgent, 2=High, 3=Medium, 4=Low`.

| Rubric level | `priority` |
|---|---|
| Highest | 1 (Urgent) |
| High | 2 |
| Medium | 3 |
| Low | 4 |
| Lowest | 4 (Low) |

- Linear has no Lowest, so Lowest maps to 4 Low; the comment heading carries `Lowest (Linear: Low)`.
- Never use 0 "No priority" for Lowest - it reads as untriaged.

## Post the comment (step 5)

`save_comment` with `issueId` and `body`. The body is plain Markdown (no ADF); use literal newlines, not `\n` escapes.

## Mark as triaged (step 6)

- Check `list_issue_labels` for `pre-refined-ai` in the issue's team.
- If it exists, add it with `save_issue` `addLabels`.
- If it does not exist, skip it, because the comment footer already marks the issue as triaged.
- Never create the label without asking the user.
- Never pass `labels` here: `labels` REPLACES the whole set, while `addLabels` appends and `removeLabels` removes. This is the opposite trap from Jira.

## Verify (step 7)

`get_issue` shows the new priority; `list_comments` shows the comment.

## Batch over a project

- `list_issues` with `project` and `includeArchived: true`.
- Default scope is open issues (statusType not completed, canceled, or duplicate), because a comment on a closed issue notifies subscribers without changing any decision.
