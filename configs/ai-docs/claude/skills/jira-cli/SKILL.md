---
name: jira-cli
description: "Create, query, update, link, and transition Jira issues via the Atlassian REST API. USE for any Jira task: creating issues, linking tickets, JQL searches, status transitions, fetching context for code reviews."
user-invocable: false
---

# Jira CLI

Self-contained Jira API utilities. Scripts live in this skill's `scripts/` directory.

## Setup

Source the utilities before use:

```bash
source ~/.claude/skills/jira-cli/scripts/jira-utilities.sh
```

Required environment variables:

```bash
export JIRA_URL='https://yourcompany.atlassian.net'
export JIRA_EMAIL='your.email@company.com'
export JIRA_API_TOKEN='your-api-token'
```

## Scripts

- `scripts/jira.sh` -- core auth and request primitives (sourced automatically by the other scripts)
- `scripts/jira-utilities.sh` -- CRUD, links, transitions, queries, markdown helpers
- `scripts/fetch-jira-review-context.sh` -- fetch issue context as markdown for code reviews
- `scripts/md-to-adf.py` -- convert Markdown to Atlassian Document Format JSON (required by Jira REST API v3 for rich-text fields)

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

### Review Context

- `fetch-jira-review-context <jira-url|issue-key>` -- fetch issue summary, description, and epic as markdown

### Markdown -> ADF (Jira REST API v3 rich-text)

Jira REST API v3 expects `description` (and other rich-text fields) as ADF JSON, not markdown.

- `md-to-adf <md-file | ->` -- convert a markdown file (or stdin via `-`) to ADF JSON on stdout
- `create-jira-issue-from-md <project> <type> <summary> <md-file> [extra-fields-json]` -- like `create-jira-issue` but reads description from a markdown file
- `update-jira-issue-from-md <key> <md-file> [extra-fields-json]` -- like `update-jira-issue` but reads description from a markdown file

The `extra-fields-json` is merged into the request body, so you can set labels, parent, duedate, etc. alongside the description.

## Link Types

- `"Blocks"` -- source blocks target
- `"Parent-Child"` -- source is parent of target
- `"Relates"` -- general relation

## Examples

```bash
source ~/.claude/skills/jira-cli/scripts/jira-utilities.sh

create-jira-issue PROJ Story "My story" '{"parent":{"key":"PROJ-100"},"labels":["team-a"]}'
link-jira-issues "PROJ-100" "Blocks" "PROJ-101"
bulk-link-jira-issues "Parent-Child" PROJ-100 PROJ-101 PROJ-102 PROJ-103
get-jira-links PROJ-101

# Create from a markdown description file:
create-jira-issue-from-md PROJ Task "Foo task" task-desc.md \
  '{"parent":{"key":"PROJ-100"},"labels":["team-a"],"duedate":"2026-07-06"}'

# Update an existing issue's description:
update-jira-issue-from-md PROJ-123 task-desc-v2.md
```
