#!/bin/bash

# Jira Utilities - Interactive commands for Jira API interactions
#
# Core library functions (jira-validate-env, jira-api-request, jira-check-error)
# live in jira.sh and are sourced below.
#
# Requirements:
#   export JIRA_URL='https://yourcompany.atlassian.net'
#   export JIRA_EMAIL='your.email@company.com'
#   export JIRA_API_TOKEN='your-api-token'
#   Get API token at: https://id.atlassian.com/manage-profile/security/api-tokens
#
# Functions:
#   Query:
#     query-jira                     - Search issues using JQL
#
#   Issue CRUD:
#     get-jira-issue                 - Get issue by key
#     create-jira-issue              - Create new issue
#     update-jira-issue              - Update existing issue
#     upsert-jira-issue              - Create or update (by summary match)
#     delete-jira-issue              - Delete an issue
#
#   Links:
#     get-jira-links                 - Get all links for an issue
#     link-jira-issues               - Create a link: source --[type]--> target (intuitive order)
#     delete-jira-link               - Delete a link by ID
#     bulk-link-jira-issues          - Link one source to multiple targets
#
#   Transitions:
#     get-jira-transitions           - Get available transitions for an issue
#     transition-jira-issue          - Transition an issue to a new status

# Source core library (jira-validate-env, jira-api-request, jira-check-error)
source "$HOME/.claude/skills/jira-cli/scripts/jira.sh"

# ==============================================================================
# QUERY
# ==============================================================================

# Query Jira using JQL and return JSON results
# Usage: query-jira "JQL query" [maxResults] [fields]
# Example: query-jira "assignee = currentUser() AND status = Done" 50
function query-jira() {
  local jql="$1"
  local max_results="${2:-100}"
  local fields="${3:-key,summary,issuetype,project,resolutiondate,parent,status}"

  if [[ -z "$jql" ]]; then
    echo "Usage: query-jira \"JQL query\" [maxResults] [fields]" >&2
    echo "Example: query-jira \"assignee = currentUser() AND status = Done\" 50" >&2
    return 1
  fi

  if ! jira-validate-env; then
    return 1
  fi

  local body
  body=$(jq -n \
    --arg jql "$jql" \
    --argjson maxResults "$max_results" \
    --arg fields "$fields" \
    '{
      jql: $jql,
      maxResults: $maxResults,
      fields: ($fields | split(","))
    }')

  local response
  if ! response=$(jira-api-request POST "/rest/api/3/search/jql" "$body"); then
    return 1
  fi

  echo "$response" | jira-check-error
}

# ==============================================================================
# ISSUE CRUD
# ==============================================================================

# Get a Jira issue by key
# Usage: get-jira-issue <issue-key> [fields]
# Example: get-jira-issue PROJ-123
# Example: get-jira-issue PROJ-123 "key,summary,status"
function get-jira-issue() {
  local issue_key="$1"
  local fields="${2:-key,summary,status,issuetype,project}"

  if [[ -z "$issue_key" ]]; then
    echo "Usage: get-jira-issue <issue-key> [fields]" >&2
    return 1
  fi

  local endpoint="/rest/api/3/issue/${issue_key}?fields=${fields}"
  local response
  if ! response=$(jira-api-request GET "$endpoint"); then
    return 1
  fi

  echo "$response" | jira-check-error
}

# Create a new Jira issue
# Usage: create-jira-issue <project> <issue-type> <summary> [json-fields]
# Example: create-jira-issue PROJ Story "My new story"
# Example: create-jira-issue PROJ Task "My task" '{"labels":["team-a"],"parent":{"key":"PROJ-100"}}'
function create-jira-issue() {
  local project="$1"
  local issue_type="$2"
  local summary="$3"
  # Avoid ${4:-{}} — zsh misparses the closing brace in the default word,
  # appending a stray '}' to the value when $4 is set. Use explicit conditional.
  local extra_fields
  extra_fields="${4}"
  [[ -z "$extra_fields" ]] && extra_fields="{}"

  if [[ -z "$project" ]] || [[ -z "$issue_type" ]] || [[ -z "$summary" ]]; then
    echo "Usage: create-jira-issue <project> <issue-type> <summary> [json-fields]" >&2
    echo "Example: create-jira-issue PROJ Story \"My new story\"" >&2
    echo "Example: create-jira-issue PROJ Task \"My task\" '{\"labels\":[\"team-a\"]}'" >&2
    return 1
  fi

  # Write extra_fields to a temp file to avoid shell-escaping issues with --argjson
  local tmp_extra
  tmp_extra=$(mktemp)
  printf '%s' "$extra_fields" > "$tmp_extra"

  # Build the fields JSON, merging extra_fields
  local fields_json
  fields_json=$(jq -n \
    --arg project "$project" \
    --arg issuetype "$issue_type" \
    --arg summary "$summary" \
    --slurpfile extra "$tmp_extra" \
    '{
      project: {key: $project},
      issuetype: {name: $issuetype},
      summary: $summary
    } + $extra[0]')
  rm -f "$tmp_extra"

  local body
  body=$(jq -n --argjson fields "$fields_json" '{fields: $fields}')

  local response
  if ! response=$(jira-api-request POST "/rest/api/3/issue" "$body"); then
    return 1
  fi

  echo "$response" | jira-check-error
}

# Update an existing Jira issue
# Usage: update-jira-issue <issue-key> <json-fields>
# Example: update-jira-issue PROJ-123 '{"summary":"Updated summary"}'
# Example: update-jira-issue PROJ-123 '{"labels":["new-label"]}'
function update-jira-issue() {
  local issue_key="$1"
  local fields_json="$2"

  if [[ -z "$issue_key" ]] || [[ -z "$fields_json" ]]; then
    echo "Usage: update-jira-issue <issue-key> <json-fields>" >&2
    echo "Example: update-jira-issue PROJ-123 '{\"summary\":\"Updated summary\"}'" >&2
    return 1
  fi

  local body
  body=$(jq -n --argjson fields "$fields_json" '{fields: $fields}')

  local response
  if ! response=$(jira-api-request PUT "/rest/api/3/issue/${issue_key}" "$body"); then
    return 1
  fi

  # PUT returns empty on success
  if [[ -n "$response" ]]; then
    if ! echo "$response" | jira-check-error > /dev/null; then
      return 1
    fi
  fi

  echo "Issue ${issue_key} updated successfully"
}

# Create or update a Jira issue
# Searches for existing issue by project and exact summary match
# Usage: upsert-jira-issue <project> <issue-type> <summary> [json-fields]
# Example: upsert-jira-issue PROJ Story "My story" '{"labels":["team-a"]}'
function upsert-jira-issue() {
  local project="$1"
  local issue_type="$2"
  local summary="$3"
  local extra_fields="${4:-{}}"

  if [[ -z "$project" ]] || [[ -z "$issue_type" ]] || [[ -z "$summary" ]]; then
    echo "Usage: upsert-jira-issue <project> <issue-type> <summary> [json-fields]" >&2
    return 1
  fi

  # Search for existing issue with exact summary match
  local escaped_summary
  escaped_summary="${summary//\"/\\\"}"
  local jql="project = ${project} AND summary ~ \"\\\"${escaped_summary}\\\"\" AND issuetype = \"${issue_type}\""

  local search_body
  search_body=$(jq -n \
    --arg jql "$jql" \
    '{jql: $jql, maxResults: 1, fields: ["key", "summary"]}')

  local search_response
  if ! search_response=$(jira-api-request POST "/rest/api/3/search/jql" "$search_body"); then
    return 1
  fi

  local existing_key
  existing_key=$(echo "$search_response" | jq -r '.issues[0].key // empty')

  if [[ -n "$existing_key" ]]; then
    # Issue exists, update it
    echo "Found existing issue: ${existing_key}, updating..." >&2
    update-jira-issue "$existing_key" "$extra_fields"
    echo "$existing_key"
  else
    # Issue doesn't exist, create it
    echo "No existing issue found, creating new..." >&2
    local create_response
    if ! create_response=$(create-jira-issue "$project" "$issue_type" "$summary" "$extra_fields"); then
      return 1
    fi

    local new_key
    new_key=$(echo "$create_response" | jq -r '.key')
    echo "Created: ${new_key}" >&2
    echo "$new_key"
  fi
}

# Delete a Jira issue
# Usage: delete-jira-issue <issue-key> [--delete-subtasks]
# Example: delete-jira-issue PROJ-123
# Example: delete-jira-issue PROJ-123 --delete-subtasks
function delete-jira-issue() {
  local issue_key="$1"
  local delete_subtasks="$2"

  if [[ -z "$issue_key" ]]; then
    echo "Usage: delete-jira-issue <issue-key> [--delete-subtasks]" >&2
    echo "Example: delete-jira-issue PROJ-123" >&2
    return 1
  fi

  local endpoint="/rest/api/3/issue/${issue_key}"
  if [[ "$delete_subtasks" == "--delete-subtasks" ]]; then
    endpoint="${endpoint}?deleteSubtasks=true"
  fi

  local response
  if ! response=$(jira-api-request DELETE "$endpoint"); then
    return 1
  fi

  # DELETE returns empty on success
  if [[ -n "$response" ]]; then
    if ! echo "$response" | jira-check-error > /dev/null; then
      return 1
    fi
  fi

  echo "Issue ${issue_key} deleted successfully"
}

# ==============================================================================
# LINKS
# ==============================================================================

# Get all links for a Jira issue
# Usage: get-jira-links <issue-key> [--raw]
# Example: get-jira-links PROJ-123
# Example: get-jira-links PROJ-123 --raw  # Returns full JSON response
function get-jira-links() {
  local issue_key="$1"
  local raw_mode="$2"

  if [[ -z "$issue_key" ]]; then
    echo "Usage: get-jira-links <issue-key> [--raw]" >&2
    return 1
  fi

  local response
  if ! response=$(jira-api-request GET "/rest/api/3/issue/${issue_key}?fields=issuelinks"); then
    return 1
  fi

  if ! echo "$response" | jira-check-error > /dev/null; then
    return 1
  fi

  # Return raw response if requested
  if [[ "$raw_mode" == "--raw" ]]; then
    echo "$response"
    return 0
  fi

  # Extract and format links
  local links
  links=$(echo "$response" | jq '.fields.issuelinks // []')

  if [[ "$links" == "[]" ]]; then
    echo "No links found for ${issue_key}"
    return 0
  fi

  echo "$links" | jq -c '.[] | {
    id: .id,
    type: .type.name,
    inward: .type.inward,
    outward: .type.outward,
    inwardIssue: .inwardIssue.key,
    outwardIssue: .outwardIssue.key
  }'
}

# Link two Jira issues
# Usage: link-jira-issues <source-key> <link-type> <target-key>
#
# The link reads naturally: SOURCE --[link-type]--> TARGET
#   - "PROJ-100 blocks PROJ-101"      => link-jira-issues PROJ-100 "Blocks" PROJ-101
#   - "PROJ-100 is parent of PROJ-101" => link-jira-issues PROJ-100 "Parent-Child" PROJ-101
#
# Common link types:
#   - "Blocks"       (source blocks target / target is blocked by source)
#   - "Parent-Child" (source is parent of target / target is child of source)
#   - "Relates"      (source relates to target)
#
function link-jira-issues() {
  local source_key="$1"
  local link_type="$2"
  local target_key="$3"

  if [[ -z "$source_key" ]] || [[ -z "$link_type" ]] || [[ -z "$target_key" ]]; then
    echo "Usage: link-jira-issues <source-key> <link-type> <target-key>" >&2
    echo "Example: link-jira-issues PROJ-100 \"Blocks\" PROJ-101  # 100 blocks 101" >&2
    echo "Example: link-jira-issues PROJ-100 \"Parent-Child\" PROJ-101  # 100 is parent of 101" >&2
    return 1
  fi

  # NOTE: Jira API is counter-intuitive. To make "A blocks B" appear in UI:
  #   - inwardIssue = A (the source/blocker/parent)
  #   - outwardIssue = B (the target/blocked/child)
  local body
  body=$(jq -n \
    --arg linkType "$link_type" \
    --arg source "$source_key" \
    --arg target "$target_key" \
    '{
      type: {name: $linkType},
      inwardIssue: {key: $source},
      outwardIssue: {key: $target}
    }')

  local response
  if ! response=$(jira-api-request POST "/rest/api/3/issueLink" "$body"); then
    return 1
  fi

  # POST returns empty on success
  if [[ -n "$response" ]]; then
    if ! echo "$response" | jira-check-error > /dev/null; then
      return 1
    fi
  fi

  echo "Linked ${source_key} --[${link_type}]--> ${target_key}"
}

# Delete a Jira issue link
# Usage: delete-jira-link <link-id>
# Example: delete-jira-link 12345
# Get link IDs using: get-jira-links <issue-key>
function delete-jira-link() {
  local link_id="$1"

  if [[ -z "$link_id" ]]; then
    echo "Usage: delete-jira-link <link-id>" >&2
    echo "Get link IDs using: get-jira-links <issue-key>" >&2
    return 1
  fi

  local response
  if ! response=$(jira-api-request DELETE "/rest/api/3/issueLink/${link_id}"); then
    return 1
  fi

  # DELETE returns empty on success
  if [[ -n "$response" ]]; then
    if ! echo "$response" | jira-check-error > /dev/null; then
      return 1
    fi
  fi

  echo "Link ${link_id} deleted successfully"
}

# Bulk link issues (helper for linking one source to multiple targets)
# Usage: bulk-link-jira-issues <link-type> <source-key> <target-key1> [target-key2] ...
# Example: bulk-link-jira-issues "Parent-Child" PROJ-100 PROJ-101 PROJ-102 PROJ-103
#          (makes PROJ-100 parent of 101, 102, 103)
# Example: bulk-link-jira-issues "Blocks" PROJ-100 PROJ-101 PROJ-102
#          (makes PROJ-100 block 101 and 102)
function bulk-link-jira-issues() {
  local link_type="$1"
  local source_key="$2"
  shift 2

  if [[ -z "$link_type" ]] || [[ -z "$source_key" ]] || [[ $# -eq 0 ]]; then
    echo "Usage: bulk-link-jira-issues <link-type> <source-key> <target-key1> [target-key2] ..." >&2
    echo "Example: bulk-link-jira-issues \"Parent-Child\" PROJ-100 PROJ-101 PROJ-102" >&2
    return 1
  fi

  local success_count=0
  local fail_count=0

  for target_key in "$@"; do
    if link-jira-issues "$source_key" "$link_type" "$target_key"; then
      ((success_count++))
    else
      ((fail_count++))
    fi
  done

  echo "Bulk link complete: ${success_count} succeeded, ${fail_count} failed"
}

# ==============================================================================
# TRANSITIONS (Status changes)
# ==============================================================================

# Get available transitions for an issue
# Usage: get-jira-transitions <issue-key>
# Example: get-jira-transitions PROJ-123
function get-jira-transitions() {
  local issue_key="$1"

  if [[ -z "$issue_key" ]]; then
    echo "Usage: get-jira-transitions <issue-key>" >&2
    return 1
  fi

  local response
  if ! response=$(jira-api-request GET "/rest/api/3/issue/${issue_key}/transitions"); then
    return 1
  fi

  if ! echo "$response" | jira-check-error > /dev/null; then
    return 1
  fi

  echo "$response" | jq -r '.transitions[] | "\(.id): \(.name)"'
}

# Transition an issue to a new status
# Usage: transition-jira-issue <issue-key> <transition-id>
# Example: transition-jira-issue PROJ-123 31
# Get transition IDs using: get-jira-transitions <issue-key>
function transition-jira-issue() {
  local issue_key="$1"
  local transition_id="$2"

  if [[ -z "$issue_key" ]] || [[ -z "$transition_id" ]]; then
    echo "Usage: transition-jira-issue <issue-key> <transition-id>" >&2
    echo "Get transition IDs using: get-jira-transitions <issue-key>" >&2
    return 1
  fi

  local body
  body=$(jq -n --arg id "$transition_id" '{transition: {id: $id}}')

  local response
  if ! response=$(jira-api-request POST "/rest/api/3/issue/${issue_key}/transitions" "$body"); then
    return 1
  fi

  # POST returns empty on success
  if [[ -n "$response" ]]; then
    if ! echo "$response" | jira-check-error > /dev/null; then
      return 1
    fi
  fi

  echo "Issue ${issue_key} transitioned successfully"
}
