#!/bin/bash

# Jira API Core Library - Authentication and request primitives
#
# Provides the foundational functions for Jira API interactions.
# Sourced by commands/jira-utilities.sh and other scripts that need Jira access.
#
# Requirements:
#   export JIRA_URL='https://yourcompany.atlassian.net'
#   export JIRA_EMAIL='your.email@company.com'
#   export JIRA_API_TOKEN='your-api-token'
#   Get API token at: https://id.atlassian.com/manage-profile/security/api-tokens
#
# Functions:
#   jira-validate-env   - Validate required environment variables
#   jira-api-request    - Make authenticated API requests
#   jira-check-error    - Check API response for errors

# Validate that all required Jira environment variables are set
# Returns 0 if valid, 1 if missing variables
function jira-validate-env() {
  local has_error=0

  if [[ -z "$JIRA_URL" ]]; then
    echo "Error: JIRA_URL environment variable is not set." >&2
    echo "Set with: export JIRA_URL='https://yourcompany.atlassian.net'" >&2
    has_error=1
  fi

  if [[ -z "$JIRA_EMAIL" ]]; then
    echo "Error: JIRA_EMAIL environment variable is not set." >&2
    echo "Set with: export JIRA_EMAIL='your.email@company.com'" >&2
    has_error=1
  fi

  if [[ -z "$JIRA_API_TOKEN" ]]; then
    echo "Error: JIRA_API_TOKEN environment variable is not set." >&2
    echo "Set with: export JIRA_API_TOKEN='your-api-token'" >&2
    echo "Get token at: https://id.atlassian.com/manage-profile/security/api-tokens" >&2
    has_error=1
  fi

  return $has_error
}

# Make a Jira API request
# Usage: jira-api-request <method> <endpoint> [json-body]
# Example: jira-api-request GET "/rest/api/3/issue/PROJ-123"
# Example: jira-api-request POST "/rest/api/3/issue" '{"fields":...}'
function jira-api-request() {
  local method="$1"
  local endpoint="$2"
  local body="$3"

  if [[ -z "$method" ]] || [[ -z "$endpoint" ]]; then
    echo "Usage: jira-api-request <method> <endpoint> [json-body]" >&2
    return 1
  fi

  if ! jira-validate-env; then
    return 1
  fi

  local curl_args=(
    -s
    -X "$method"
    -u "${JIRA_EMAIL}:${JIRA_API_TOKEN}"
    -H "Accept: application/json"
    -H "Content-Type: application/json"
  )

  if [[ -n "$body" ]]; then
    curl_args+=(-d "$body")
  fi

  curl_args+=("${JIRA_URL}${endpoint}")

  local response
  response=$(curl "${curl_args[@]}" 2>&1)

  if [[ $? -ne 0 ]]; then
    echo "Error: Failed to make Jira API request: $response" >&2
    return 1
  fi

  echo "$response"
}

# Check if a Jira API response contains errors
# Usage: echo "$response" | jira-check-error
# Returns 0 if no error, 1 if error found
function jira-check-error() {
  local response
  response=$(cat)

  if echo "$response" | grep -q '"errorMessages"'; then
    local error_messages
    error_messages=$(echo "$response" | jq -r '.errorMessages[]? // empty' 2>/dev/null)
    local errors
    errors=$(echo "$response" | jq -r '.errors | to_entries[]? | "\(.key): \(.value)"' 2>/dev/null)

    if [[ -n "$error_messages" ]]; then
      echo "Error: Jira API returned error messages:" >&2
      echo "$error_messages" >&2
    fi

    if [[ -n "$errors" ]]; then
      echo "Error: Jira API returned field errors:" >&2
      echo "$errors" >&2
    fi

    return 1
  fi

  echo "$response"
  return 0
}
