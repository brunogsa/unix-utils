# test-sdd — flow overview

Human-facing overview for auditing the flow at a glance. Non-authoritative — the numbered steps in [`../SKILL.md`](../SKILL.md) win on any conflict. Regenerate this file whenever the skill's flow changes.

```mermaid
flowchart TD
  n1(["1. /test-sdd &lt;plan-file&gt; &lt;task-ids&gt;<br/><br/>or natural language<br/>('are the planned tests there?')"]):::start
  n2["2. Step 1 · Resolve the plan: use the arg path<br/>if readable, else glob ls -1 plan_*.md in CWD"]
  n3{"3. How many plans?"}
  n3a(["3a. Stop: no plan to check against"])
  n3b["3b. Prompt with a numbered list;<br/>the user picks one plan"]:::gate
  n4["4. Step 2 · Resolve task-ids: every ### N. heading<br/>by default, else exact-match the arg's ids;<br/>record each task's status marker"]
  n5{"5. Every id matched exactly one heading?"}
  n5a(["5a. Stop: name the id that missed,<br/>or the collision (malformed plan)"])
  n6["6. Step 3 · Mint VERDICT_PATH in CWD:<br/>date +verdict_test-sdd_%Y-%m-%d_%H:%M.md<br/>(one per run, never reused)"]:::state
  n7["7. Step 4 · Dispatch ONE deep-reviewer<br/>(agent-pinned, background, fresh context)"]:::dispatch
  n7a["7a. Hook: deep-reviewer-write-guard<br/>(only verdict_*.md writes are approved)"]:::hook

  subgraph reviewer["Step 5 · Inside the reviewer, once per resolved task-id"]
    direction TB
    n8{"8. Task carries DECISION: Skip<br/>planned-test check?"}
    n8a["8a. Report the task as opted out,<br/>quoting its stated reason"]
    n9["9. Run extract-planned-tests-for-task.sh<br/>&lt;plan&gt; &lt;N&gt;"]:::hook
    n10{"10. Script exit code?"}
    n10a["10a. Exit 1 or 2 · record the parse failure;<br/>mark the whole run inconclusive"]
    n10b["10b. Exit 0, empty · task declared N/A;<br/>report it, never a finding"]
    n11["11. Exit 0, titles · per title run<br/>git grep -nF --untracked over the working tree"]:::hook
    n12{"12. Grep matched the title?"}
    n12a["12a. AI semantic pass — reworded, wrapped,<br/>or templated titles count as present<br/>ONLY with a path:line citation"]
    n13["13. Classify each title found (path:line)<br/>or missing"]
  end

  n14["14. Step 6 · Reviewer writes the COMPLETE report<br/>to VERDICT_PATH: summary table, N/A list,<br/>opt-out list, one ### N. [HIGH] finding<br/>per missing title"]:::state
  n15{"15. Step 7 · VERDICT_PATH present and non-empty?"}
  n15a["15a. Re-dispatch the reviewer once;<br/>never report from the truncated return"]:::dispatch
  n16["16. Step 7 · Read VERDICT_PATH end-to-end,<br/>then print the plan, the checked ids,<br/>found/missing counts, one line per finding"]
  n17(["17. Stop — report only.<br/>Writing the missing tests is<br/>/quality-gate --auto-solve, or a direct ask"])

  n1 --> n2 --> n3
  n3 -->|"zero"| n3a
  n3 -->|"many"| n3b --> n4
  n3 -->|"one"| n4
  n4 --> n5
  n5 -->|"no"| n5a
  n5 -->|"yes"| n6 --> n7
  n7 -.->|"guards"| n7a
  n7 --> n8
  n8 -->|"yes"| n8a
  n8 -->|"no"| n9 --> n10
  n10 -->|"1 / 2"| n10a
  n10 -->|"0, empty"| n10b
  n10 -->|"0, titles"| n11 --> n12
  n12 -->|"no"| n12a --> n13
  n12 -->|"yes"| n13
  n13 --> n14
  n8a --> n14
  n10a --> n14
  n10b --> n14
  n14 --> n15
  n15 -->|"no"| n15a --> n15
  n15 -->|"yes"| n16 --> n17

  classDef start fill:#fef3c7,stroke:#d97706,stroke-width:2px
  classDef gate fill:#fee2e2,stroke:#dc2626,stroke-width:2px
  classDef dispatch fill:#dbeafe,stroke:#2563eb,stroke-width:2px
  classDef state fill:#dcfce7,stroke:#16a34a,stroke-width:2px
  classDef skill fill:#f3e8ff,stroke:#9333ea,stroke-width:2px
  classDef hook fill:#e5e7eb,stroke:#4b5563,stroke-width:2px
```
