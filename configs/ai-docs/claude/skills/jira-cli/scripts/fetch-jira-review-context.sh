#!/bin/bash

# fetch-jira-review-context - Fetch Jira issue context for code review
#
# Outputs a human-readable markdown block with issue summary, description,
# and epic context. Uses jira-api-request from jira.sh for authentication.
#
# Usage:
#   fetch-jira-review-context <jira-url>
#   fetch-jira-review-context <issue-key>
#
# Examples:
#   fetch-jira-review-context https://company.atlassian.net/browse/PROJ-123
#   fetch-jira-review-context PROJ-123

# Source core Jira library if not already loaded
if ! command -v jira-api-request &>/dev/null; then
  source "$HOME/.claude/skills/jira-cli/scripts/jira.sh"
fi

function fetch-jira-review-context() {
  local input="$1"

  if [[ -z "$input" ]] || [[ "$input" == '--help' ]] || [[ "$input" == '-h' ]]; then
    echo "Usage: fetch-jira-review-context <jira-url|issue-key>"
    echo ""
    echo "Examples:"
    echo "  fetch-jira-review-context https://company.atlassian.net/browse/PROJ-123"
    echo "  fetch-jira-review-context PROJ-123"
    return 0
  fi

  # Extract issue key from URL or use as-is
  local issue_key
  if [[ "$input" == http* ]]; then
    # Strip URL prefix, then trim trailing non-key characters; subsequent validation rejects malformed inputs
    issue_key="${input##*/browse/}"
    issue_key="${issue_key%%[^A-Z0-9-]*}"
  else
    issue_key="$input"
  fi

  if [[ -z "$issue_key" ]] || ! [[ "$issue_key" =~ ^[A-Z]+-[0-9]+$ ]]; then
    echo "Error: Could not parse issue key from: $input" >&2
    echo "Expected format: PROJ-123 or https://company.atlassian.net/browse/PROJ-123" >&2
    return 1
  fi

  if ! jira-validate-env; then
    return 1
  fi

  # Fetch issue with rendered HTML fields
  local response
  response=$(jira-api-request GET "/rest/api/3/issue/${issue_key}?fields=summary,description,parent&expand=renderedFields")

  if echo "$response" | jira-check-error >/dev/null 2>&1; then
    :
  else
    echo "Error: Failed to fetch $issue_key" >&2
    return 1
  fi

  # Extract fields
  local summary epic_key epic_summary description
  summary=$(echo "$response" | jq -r '.fields.summary // ""')
  epic_key=$(echo "$response" | jq -r '.fields.parent.key // ""')
  epic_summary=$(echo "$response" | jq -r '.fields.parent.fields.summary // ""')

  # Convert rendered HTML description to plain text
  description=$(echo "$response" | jq -r '.renderedFields.description // ""' | \
    sed 's|</p>|\n\n|g' | \
    sed 's|</div>|\n|g' | \
    sed 's|<br[^>]*>|\n|g' | \
    sed 's|</li>|\n|g' | \
    sed 's|<li>|- |g' | \
    sed 's|<h3[^>]*>|### |g; s|</h3>||g' | \
    sed 's|<h2[^>]*>|## |g; s|</h2>||g' | \
    sed 's|<h1[^>]*>|# |g; s|</h1>||g' | \
    sed 's|<[^>]*>||g' | \
    sed 's|&nbsp;| |g; s|&lt;|<|g; s|&gt;|>|g; s|&amp;|\&|g; s|&quot;|"|g' | \
    sed 's/^[[:space:]]*//;s/[[:space:]]*$//' | \
    sed '/^$/N;/^\n$/D')

  # Output markdown
  echo "## Jira Card: ${issue_key} - ${summary}"
  echo ""

  if [[ -n "$epic_key" ]]; then
    echo "**Epic**: ${epic_key} - ${epic_summary}"
    echo ""
  fi

  if [[ -n "$description" ]]; then
    echo "### Description"
    echo ""
    echo "$description"
  fi
}
