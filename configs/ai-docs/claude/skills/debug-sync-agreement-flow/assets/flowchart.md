# debug-sync-agreement-flow — flow overview

Human-facing overview for auditing the flow at a glance. Non-authoritative — the numbered steps in [`../SKILL.md`](../SKILL.md) win on any conflict. Regenerate this file whenever the skill's flow changes.

```mermaid
flowchart TD
  n1(["1. /debug-sync-agreement-flow contractId, from the integrator repo root"]):::start
  n2["2. Step 1 · Resolve inputs: ask which AWS profile, never assume one.<br/>Confirm sts get-caller-identity, run aws sso login if it fails.<br/>Default the window to 7 days and say so. Ask for contractId if missing"]:::gate
  n3["3. Step 2 · Fetch one CSV per log group, querying wide on contractId:<br/>core, and middleware for the inbound webhook payload.<br/>Write both CSVs outside the repo"]
  n4["4. Step 3 · List transaction ids with extract-payloads.py.<br/>Carry every transaction that bears on the conclusion,<br/>cross-checking each hit against a specific field"]
  n5["5. Step 4 · Extract each transaction's payloads.<br/>Paste each body unedited into a json fence.<br/>No trim-field by default; a missing section warning is signal"]
  n6["6. Step 5 · Read the ERP target's code for the why:<br/>mapper, use-case, error classes, git log on the mapper"]
  n7["7. Step 6 · Write the notes file to the repo root:<br/>contractId-sync-notes.md, or ticket-log-evidence.md"]
  n8["8. Step 7 · Re-verify every load-bearing field against the raw CSV<br/>and report the list and its outcome"]
  n9{"9. Step 8 · Ask once: post the notes as a Jira comment, and to which ticket?"}:::gate
  n9a(["9a. STOP — default is no post. The file alone is a complete outcome.<br/>No post without an explicit yes, and a yes covers one ticket only"]):::done
  n10["10. Check JIRA_URL, JIRA_EMAIL, JIRA_API_TOKEN are exported.<br/>Run post-jira-comment.sh with --dry-run"]
  n11{"11. Dry run warns of lost formatting?"}
  n11a["11a. Fix the notes file to the supported markdown set, then dry-run again"]
  n12["12. Step 9 · Post the comment with post-jira-comment.sh"]:::dispatch
  n13{"13. Post succeeded?"}
  n13a(["13a. Report the HTTP status and body verbatim. Never retry silently"]):::done
  n14(["14. Report the comment id and URL it printed"]):::done

  n1 --> n2 --> n3 --> n4 --> n5 --> n6 --> n7 --> n8 --> n9
  n9 -->|"no"| n9a
  n9 -->|"yes"| n10 --> n11
  n11 -->|"yes"| n11a --> n10
  n11 -->|"no"| n12 --> n13
  n13 -->|"no"| n13a
  n13 -->|"yes"| n14

  classDef start fill:#d4edda,stroke:#28a745
  classDef gate fill:#fff3cd,stroke:#d39e00
  classDef dispatch fill:#d6e9f8,stroke:#2f7fc1
  classDef done fill:#d4edda,stroke:#28a745
```
