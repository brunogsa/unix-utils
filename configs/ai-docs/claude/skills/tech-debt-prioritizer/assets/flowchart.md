# tech-debt-prioritizer - flow overview

Human-facing overview for auditing the flow at a glance. Non-authoritative - the numbered steps in [`../SKILL.md`](../SKILL.md) win on any conflict. Regenerate this file whenever the skill's flow changes.

Two renderings of the same flow, kept cross-checkable on purpose. The `# N` comments in the pseudo-code are the diagram's node ids, so an id with no matching comment is drift.

## Pseudo-code

Python-shaped for readability only; nothing here runs, and the function names stand for steps this skill performs, not real APIs.

```python
# 1 · Entry: "prioriza", "triar", "refina esses débitos", "set the priority on these",
#     "review the priorities of this project", pasted Jira keys or Linear ids/URLs.
def tech_debt_prioritizer(issues_or_project):
    # 2 · Choosing the platform - evidence only, never key shape
    #     (ITGD-3160 and CDPI-399 look the same).
    platform = platform_from_evidence(issues_or_project)
    if platform is None:                                       # 2
        platform = ask_user("Jira or Linear?")                 # 2a · gate

    # 3 · read ONLY the matching file; the other one is never opened
    ref = read(f"references/{platform}.md")

    # 4 · batch over a project, or several issues (Linear: open issues only by default)
    issues = list_issues(issues_or_project, ref)
    batch = len(issues) > 1

    proposals = []
    for issue in issues:                                       # 5 · per-issue loop
        read_issue_and_comments(issue, ref)                    # 5a · Step 1
        level = classify_naming_adjacent_levels(issue)         # 5b · Step 2
        confirm_priority_values(platform, ref)                 # 5c · Step 3
        if batch:                                              # 5d · gate on batch mode
            proposals.append((issue, level))                   # 5e · table: key, current, proposed, reason
        else:
            write_issue(issue, level, ref)                     # 5f · write now, Steps 4-6

    if batch:                                                  # 6 · gate on batch mode
        approved = ask_user_approval(proposals)                # 6a · changes first, unchanged compact
        for issue, level in approved:                          # 6b · write only what the user approved
            write_issue(issue, level, ref)                     # Steps 4-6, same helper as 5f

    # 7 · Step 7 - verify priority + triaged marker landed, report each final state
    verify_and_report(ref)
    return  # 8 · Done


def write_issue(issue, level, ref):
    set_priority(issue, level, ref)                            # 5f1 · Step 4
    post_ptbr_comment(issue, level, ref)                       # 5f2 · Step 5
    mark_triaged(issue, ref)                                   # 5f3 · Step 6, last
```

## Flowchart

```mermaid
flowchart TD
  n1(["1. 'prioriza' / 'triar' / 'set the priority on these' /<br/>pasted Jira keys or Linear ids/URLs"]):::start
  n2{"2. Platform known from evidence?<br/>(linear.app or atlassian.net URL, user naming it,<br/>team prefix resolved earlier - never key shape)"}
  n2a["2a. Ask the user: Jira or Linear?"]:::gate
  n3["3. Read only the matching reference file:<br/>references/jira.md or references/linear.md"]
  n4["4. Collect issues (pasted ids, or list_issues for a project -<br/>open issues by default)"]
  n5{"5. Issues remaining?"}
  n5a["5a. Step 1 · Read issue + comments"]
  n5b["5b. Step 2 · Classify, naming adjacent levels ruled out"]
  n5c["5c. Step 3 · Confirm priority values on the platform"]
  n5d{"5d. Batch mode?"}
  n5e["5e. Add to proposal table: key, current, proposed, one-line reason"]
  n5f["5f. Write issue now"]
  n5f1["5f1. Step 4 · Set priority"]
  n5f2["5f2. Step 5 · Post PT-BR rationale comment"]
  n5f3["5f3. Step 6 · Mark triaged (label, last)"]
  n6{"6. Batch mode?"}
  n6a["6a. Present proposals: changes first, unchanged listed compactly;<br/>user approves"]:::gate
  n6b["6b. Write only approved issues (steps 4-6 each)"]
  n7["7. Step 7 · Verify priority + marker landed;<br/>report each final state"]
  n8(["8. Done"])

  n1 --> n2
  n2 -->|"no"| n2a
  n2 -->|"yes"| n3
  n2a --> n3
  n3 --> n4
  n4 --> n5
  n5 -->|"yes"| n5a
  n5a --> n5b
  n5b --> n5c
  n5c --> n5d
  n5d -->|"yes"| n5e
  n5d -->|"no"| n5f
  n5e --> n5
  n5f --> n5f1
  n5f1 --> n5f2
  n5f2 --> n5f3
  n5f3 --> n5
  n5 -->|"no, all read"| n6
  n6 -->|"yes"| n6a
  n6 -->|"no"| n7
  n6a --> n6b
  n6b --> n7
  n7 --> n8

  classDef start fill:#fef3c7,stroke:#d97706,stroke-width:2px
  classDef gate fill:#fee2e2,stroke:#dc2626,stroke-width:2px
  classDef dispatch fill:#dbeafe,stroke:#2563eb,stroke-width:2px
  classDef state fill:#dcfce7,stroke:#16a34a,stroke-width:2px
  classDef skill fill:#f3e8ff,stroke:#9333ea,stroke-width:2px
  classDef hook fill:#e5e7eb,stroke:#4b5563,stroke-width:2px
```
