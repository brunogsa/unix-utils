---
description: "Shared debug patterns for Integrator: interaction model, self-improvement, cross-command delegation"
user-invocable: false
---

# Integrator Debug Patterns

Shared patterns across all Integrator debug commands. Auto-loaded as context.

See also: @integrator-architecture, @arco-architecture

---

## Interaction Model

**CRITICAL -- All debug commands follow this collaborative model:**

- **Work in series, not in parallel** -- tackle one step at a time, like a human debugging alongside the user.
- **Explain as you go** -- before each action, explain what you're about to do and why. After each result, share your interpretation and hypotheses.
- **Keep the user in the loop at all times** -- never run multiple investigative steps silently. Present findings, state your current hypothesis, and confirm direction before moving on.
- **Show evidence** -- CRITICAL: after every log fetch, DLQ peek, or API call, quote the relevant snippets (log lines, payloads, status codes, error messages, timestamps) directly in your response. Never summarize without showing the raw data that supports the conclusion. The user must see the evidence, not just the interpretation.
- **Ask before branching** -- if the investigation could go in multiple directions, present the options and let the user decide.

---

## Self-Improvement Protocol

During debug sessions, new insights about architecture, log patterns, or debugging strategy will emerge.

**When a new insight is discovered:**

1. Briefly state: "I learned X. Should I update the skill/command now or later?"
2. If approved, edit the relevant skill or command file immediately
3. **Never update silently** -- always ask first

**What counts as a new insight:**
- New API key name -> caller mapping
- New DLQ name -> flow mapping
- New log group or log pattern
- Architectural detail not yet documented (routing, auth, retries)
- New debugging strategy or shortcut
- Correction to existing documentation

---

## Cross-Command Delegation

Debug commands can suggest running another command for deeper investigation:

| From | To | When |
|------|----|------|
| `/debug-integrator-alarm` | `/debug-integrator-tid` | After identifying a transactionId from alarm logs |
| `/debug-integrator-dlq` | `/debug-integrator-tid` | After extracting transactionId from DLQ message |
| `/debug-integrator-orders` | `/debug-integrator-tid` | After finding transactionId for a specific order |
| `/debug-integrator-alarm` | `/debug-integrator-dlq` | When alarm is DLQ-related |

Always suggest the delegation explicitly and let the user decide.

---

## Common Tools

| Tool | Purpose |
|------|---------|
| `aws-get-cloudwatch-logs` | Fetch and paginate CloudWatch logs; omit `--start-date` for progressive mode (see @aws-tools) |
| `aws-get-status-distribution-api-gw` | Bird's-eye view of API GW status distribution (see @aws-tools) |
| `aws-get-api-keys` | List/filter API keys by suffix to identify callers (see @aws-tools) |
| `aws-get-dlq-summary` | DLQ attributes + peek at messages with identifier extraction (see @aws-tools) |
| `gh api` | Check recent deployments, PRs, and commits on GitHub |
| `aws cloudwatch describe-alarms` | List active CloudWatch alarms |

---

## Codebase Investigation

After gathering log evidence, leverage the Integrator codebase to deepen the investigation:

- Check OpenAPI spec in `docs/integrator/` for endpoint routing (HTTP_PROXY vs HTTP)
- Search for endpoint handler, auth logic, and downstream client
- Trace the request flow through code to understand what could produce the observed error
- Cross-reference error messages from logs with error strings in code
- Identify configuration, env vars, or external dependencies involved

**Smoke tests** at `scripts/smoke-tests/` can reproduce issues by calling endpoints via the API GW URL with an API key.

---

## Deployment Check

Use `gh` to check if any deploy happened close to the first error timestamp:

```bash
gh api repos/arco-cv/arco2-integrator/deployments --paginate \
  -q '.[] | select(.created_at >= "<date>") | {created_at, environment, sha: .sha[0:7], description}'
```

- If deploy happened shortly before errors started: inspect the commit
- If the gap is large (hours): likely unrelated -- focus on external causes

---

## Findings Summary Template

After investigation, summarize:

- **Key evidence** (quoted log lines, payloads, status codes that support the conclusion)
- **Root cause** (if identifiable from logs + code)
- **Timeline of events** (with timestamps from actual logs)
- **Affected transactions/documents**
- **Relevant code paths and configuration**
- **Current hypothesis and confidence level**
- **Suggested next steps**
