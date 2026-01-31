---
description: "Jira API shell utilities for issue CRUD, linking, querying, and status transitions"
user-invocable: false
---

# Jira Tools

Shell functions at `~/oh-my-zsh/func-utilities/jira-utilities.sh`.

## Environment Variables (required)

```bash
export JIRA_URL='https://yourcompany.atlassian.net'
export JIRA_EMAIL='your.email@company.com'
export JIRA_API_TOKEN='your-api-token'
```

## Functions

### Authentication & Common

- `jira-validate-env` -- validate required env vars
- `jira-api-request <method> <endpoint> [json-body]` -- authenticated API caller
- `jira-check-error` -- pipe response through this to check for errors

### Query

- `query-jira "<JQL>" [maxResults] [fields]` -- search issues via JQL

### Issue CRUD

- `get-jira-issue <key> [fields]` -- get issue by key
- `create-jira-issue <project> <type> <summary> [json-fields]` -- create issue
- `update-jira-issue <key> <json-fields>` -- update issue
- `upsert-jira-issue <project> <type> <summary> [json-fields]` -- create or update by summary match
- `delete-jira-issue <key> [--delete-subtasks]` -- delete issue

### Links

- `get-jira-links <key> [--raw]` -- get all links for an issue
- `link-jira-issues <source> <link-type> <target>` -- create link (intuitive order: SOURCE --[type]--> TARGET)
- `delete-jira-link <link-id>` -- delete a link by ID
- `bulk-link-jira-issues <link-type> <source> <target1> [target2] ...` -- link one source to many targets

### Transitions

- `get-jira-transitions <key>` -- list available transitions
- `transition-jira-issue <key> <transition-id>` -- move issue to new status

## Link Types

- `"Blocks"` -- source blocks target
- `"Parent-Child"` -- source is parent of target
- `"Relates"` -- general relation

## Examples

```bash
source ~/oh-my-zsh/func-utilities/jira-utilities.sh

create-jira-issue PROJ Story "My story" '{"parent":{"key":"PROJ-100"},"labels":["team-a"]}'
link-jira-issues "PROJ-100" "Blocks" "PROJ-101"
bulk-link-jira-issues "Parent-Child" PROJ-100 PROJ-101 PROJ-102 PROJ-103
get-jira-links PROJ-101
```
