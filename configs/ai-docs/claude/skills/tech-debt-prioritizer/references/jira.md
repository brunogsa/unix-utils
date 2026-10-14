# Jira commands for the tech-debt-prioritizer workflow

Exact calls for each workflow step in `../SKILL.md`, using the jira-cli skill (Jira REST API v3 helpers and its env vars). Rubric levels map 1:1 to Jira priority names: Highest, High, Medium, Low, Lowest.

## Read the issue (step 1)

Pull summary + description so the rationale is grounded in what the card says:

```bash
source ~/.claude/skills/jira-cli/scripts/jira-utilities.sh
get-jira-issue ITGD-3160 "summary,description,priority,labels"
```

## Confirm priority values (step 3)

Priority names and the label spelling can differ per instance:

```bash
jira-api-request GET "/rest/api/3/priority"   # confirm Highest/High/Medium/Low/Lowest exist
```

## Set the priority (step 4)

```bash
update-jira-issue ITGD-3160 '{"priority":{"name":"Medium"}}'
```

## Post the comment (step 5)

Write the comment to a markdown file, convert to ADF (Jira v3 needs ADF, not markdown), and POST it:

```bash
adf=$(md-to-adf /tmp/comment.md)
body=$(python3 -c "import sys,json; print(json.dumps({'body': json.load(open(sys.argv[1]))}))" <(printf '%s' "$adf"))
jira-api-request POST "/rest/api/3/issue/ITGD-3160/comment" "$body"
```

## Mark as triaged (step 6)

Add the label `pre-refined-ai` last, after the rationale is recorded, so the label means "triaged with justification". Preserve existing labels - read them in step 1 and re-send the full list, since `update` replaces the array:

```bash
update-jira-issue ITGD-3160 '{"labels":["kit1:1","pre-refined-ai"]}'
```

## Verify (step 7)

Re-run `get-jira-issue` from step 1 and check that priority and labels landed.

## Notes

- **Labels are literal.** This Jira accepts colons (`kit1:1`); other instances may reject colons or spaces.

  - If `update` errors on the label, report it and fall back to a hyphenated form rather than silently dropping it.

- **Spikes need a due date** in this project (Tech Spike / Functional Spike). Tech Debt does not.

  - If you set priority on a Spike here and creation/edit fails on `duedate`, that's why.
