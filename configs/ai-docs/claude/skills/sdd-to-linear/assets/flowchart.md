---
# performance-check budget override, not part of the diagram itself.
# One diagram carries every step, branch and stop condition of the skill,
# and trimming to the bundled default would drop steps from the flow audit.
# Parked in assets/ and never loaded by the model, so its words cost no context.
words-budget: 1024
---

# sdd-to-linear — flow overview

Human-facing overview for auditing the flow at a glance. Non-authoritative — the numbered steps in [`../SKILL.md`](../SKILL.md) win on any conflict. Regenerate this file whenever the skill's flow changes.

```mermaid
flowchart TD
  n1(["1. /sdd-to-linear [path]<br/>no path: the plan to-plan just wrote, else ask"]):::start
  n2["2. Step 1 · Run get-enabled-modules.py<br/>and read the linear= line"]
  n3{"3. linear=true?"}
  n3a(["3a. STOP — say the Linear module is absent.<br/>Zero Linear calls"])
  n3b{"3b. AskUserQuestion, recommended first:<br/>export the plan to Linear?"}
  n3c(["3c. STOP — declined means no Linear call anywhere"])
  n4["4. Step 2 · Parse the plan's PR-N headings with their<br/>Tasks, Branch and Linear fields"]
  n5{"5. Any PRs in the PR Breakdown?"}
  n5a(["5a. STOP — zero PRs, zero Linear writes.<br/>Never invent a catch-all issue"])
  n6["6. Step 3 · Read-only taxonomy calls: list_teams, list_initiatives,<br/>list_projects, list_issue_labels, list_milestones.<br/>Never hardcode a label value"]
  n7["7. ONE AskUserQuestion for initiative, project and team,<br/>unless the plan's document-level Linear line names them"]:::gate
  n8["8. Step 4 · Per PR: derive the single Application<br/>and Issue Type labels. Never set Issue Origin.<br/>Milestone only where the PR is a feature"]
  n9{"9. PR tasks span two or more Application values,<br/>or no Issue Type clearly applies?"}
  n9a["9a. Ask which single value, recommended first.<br/>Write that PR only once answered;<br/>keep going with the other PRs meanwhile"]:::gate
  n10["10. Step 5 · Read references/issue-write-rules.md,<br/>then create exactly one issue per PR in plan order,<br/>PT-BR body carrying the plan's task content"]
  n11["11. After each create, write the issue URL into that PR's<br/>Linear field, in backticks. After the first issue,<br/>write the document-level Linear line the same way"]
  n12{"12. A write failed partway?"}
  n12a["12a. Step 6 · STOP the export. Report which PRs got issues<br/>and which did not, write the Linear field only for created ones,<br/>never retry silently, offer the retry"]:::gate
  n13["13. All issues exist: write each PR's Depends on as a blockedBy<br/>relation, only for a graph the three DAG gates accepted.<br/>Verify with get_issue includeRelations"]
  n13a["13a. Relation with no blocking issue: name it,<br/>finish the rest, never report clean"]:::gate
  n14["14. One decisions comment per PR via save_comment, PT-BR.<br/>A PR with no recorded decision gets none"]
  n15{"15. spec_slug.md beside the plan?"}
  n15a["15a. Leave the project description as the user set it"]
  n15b{"15b. Current description non-empty and not<br/>written by a previous run?"}
  n15c["15c. Hand it back with the project URL, write nothing"]:::gate
  n15d["15d. Write Background and Functional Decisions<br/>from the spec, PT-BR"]
  n16{"16. Module disconnected, timed out, 5xx or auth rejected<br/>before any write was possible?"}
  n16a["16a. Degrade to the plan file alone, report loudly<br/>naming the failed call, continue. Never abort"]:::gate
  n17(["17. Step 7 · Report the URL tree in plan order.<br/>Flag handed-back issues, PRs with no issue,<br/>unwritten relations, rejected comments and description"]):::done

  n1 --> n2 --> n3
  n3 -->|"no"| n3a
  n3 -->|"yes"| n3b
  n3b -->|"no"| n3c
  n3b -->|"yes"| n4 --> n5
  n5 -->|"zero"| n5a
  n5 -->|"some"| n6 --> n7 --> n8 --> n9
  n9 -->|"yes"| n9a --> n10
  n9 -->|"no"| n10
  n10 --> n11 --> n12
  n12 -->|"yes"| n12a --> n17
  n12 -->|"no"| n13 --> n13a --> n14
  n13 --> n14
  n14 --> n15
  n15 -->|"no"| n15a --> n16
  n15 -->|"yes"| n15b
  n15b -->|"yes"| n15c --> n16
  n15b -->|"no"| n15d --> n16
  n16 -->|"yes"| n16a --> n17
  n16 -->|"no"| n17

  classDef start fill:#d4edda,stroke:#28a745
  classDef gate fill:#fff3cd,stroke:#d39e00
  classDef done fill:#d4edda,stroke:#28a745
```
