#!/usr/bin/env bash
#
# Post a markdown file as a comment on a Jira issue.
#
# Self-contained on purpose: it talks to the Jira Cloud REST API v3 directly so this skill works
# from a fresh clone of the repo, with no dependency on any personally-installed Jira tooling.
#
# The v3 API requires rich-text fields as ADF documents, so the markdown is converted by the
# sibling build-adf-payload.py before being wrapped as {"body": <adf>}.
#
# Usage:
#   post-jira-comment.sh <issue-key> <markdown-file>
#   post-jira-comment.sh <issue-key> <markdown-file> --dry-run
#
# --dry-run converts and validates without posting, printing the ADF to stdout. Use it while
# drafting: a comment is public the moment it posts, and there is no edit-before-anyone-sees-it.
#
# Required environment:
#   JIRA_URL        e.g. https://yourcompany.atlassian.net
#   JIRA_EMAIL      the account's email
#   JIRA_API_TOKEN  an API token from https://id.atlassian.com/manage-profile/security/api-tokens

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
  echo "usage: $(basename "$0") <issue-key> <markdown-file> [--dry-run]" >&2
  exit 1
}

[[ $# -lt 2 || $# -gt 3 ]] && usage

ISSUE_KEY="$1"
MD_FILE="$2"
DRY_RUN=false
if [[ $# -eq 3 ]]; then
  [[ "$3" == "--dry-run" ]] || usage
  DRY_RUN=true
fi

for cmd in curl jq python3; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Error: required command '$cmd' not found." >&2
    exit 1
  fi
done

if [[ ! -f "$MD_FILE" ]]; then
  echo "Error: markdown file not found: $MD_FILE" >&2
  exit 1
fi

# Convert first, so a conversion failure never reaches the network.
if ! ADF=$(python3 "$SCRIPT_DIR/build-adf-payload.py" "$MD_FILE"); then
  echo "Error: markdown to ADF conversion failed." >&2
  exit 1
fi

BODY=$(jq -n --argjson adf "$ADF" '{body: $adf}')

if [[ "$DRY_RUN" == true ]]; then
  echo "$BODY" | jq .
  echo "Dry run: nothing posted to $ISSUE_KEY." >&2
  exit 0
fi

for var in JIRA_URL JIRA_EMAIL JIRA_API_TOKEN; do
  if [[ -z "${!var:-}" ]]; then
    echo "Error: $var is not set." >&2
    exit 1
  fi
done

# A trailing slash would produce a double slash in the path and a 404.
BASE_URL="${JIRA_URL%/}"

RESPONSE=$(
  curl -sS -w $'\n%{http_code}' \
    -u "$JIRA_EMAIL:$JIRA_API_TOKEN" \
    -X POST \
    -H "Content-Type: application/json" \
    -H "Accept: application/json" \
    --data-binary "$BODY" \
    "$BASE_URL/rest/api/3/issue/$ISSUE_KEY/comment"
) || {
  echo "Error: request to Jira failed (network or TLS)." >&2
  exit 1
}

HTTP_CODE=$(printf '%s' "$RESPONSE" | tail -n 1)
PAYLOAD=$(printf '%s' "$RESPONSE" | sed '$d')

if [[ "$HTTP_CODE" != "201" ]]; then
  echo "Error: Jira returned HTTP $HTTP_CODE" >&2
  printf '%s\n' "$PAYLOAD" >&2
  exit 1
fi

COMMENT_ID=$(printf '%s' "$PAYLOAD" | jq -r '.id // "unknown"')
CREATED=$(printf '%s' "$PAYLOAD" | jq -r '.created // "unknown"')
echo "Posted comment $COMMENT_ID on $ISSUE_KEY at $CREATED"
echo "$BASE_URL/browse/$ISSUE_KEY?focusedCommentId=$COMMENT_ID"
