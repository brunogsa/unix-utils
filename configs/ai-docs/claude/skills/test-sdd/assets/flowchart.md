# test-sdd — flow overview

Human-facing overview for auditing the flow at a glance. Non-authoritative — the numbered steps in [`../SKILL.md`](../SKILL.md) win on any conflict. Regenerate this file whenever the skill's flow changes.

Two renderings of the same flow, kept cross-checkable on purpose. The `# N` comments in the pseudo-code are the diagram's node ids, so an id with no matching comment is drift.

## Pseudo-code

Python-shaped for readability only; nothing here runs, and the function names stand for steps this skill performs, not real APIs.

```python
# 1 · Entry: /test-sdd <plan-file> <task-ids>
#     or natural language ("are the planned tests there?").
def test_sdd(arg):
    plans = [read(arg.plan_file)] if readable(arg.plan_file) else glob("plan_*.md")  # 2 · Step 1
    if len(plans) == 0:                                    # 3
        return stop("no plan to check against")            # 3a
    plan = plans[0] if len(plans) == 1 else ask_user_to_pick(numbered(plans))   # 3b

    # 4 · Step 2 — every "### N." heading by default, else exact-match the arg's ids.
    tasks = resolve_task_ids(plan, arg.task_ids)
    for t in tasks:
        t.status_marker = plan.status_of(t)
    if not each_id_matched_exactly_one(tasks):             # 5
        return stop(the_id_that_missed_or_the_collision)   # 5a · a collision = malformed plan

    # 6 · Step 3 — minted in CWD, one per run, never reused.
    verdict_path = f"verdict_test-sdd_{now('%Y-%m-%d_%H:%M')}.md"

    # 7 · Step 4 — ONE test-reviewer, agent-pinned, background, fresh context.
    dispatch("test-reviewer", plan, tasks, verdict_path)
    # 7a · hook: check-reviewer-writes (only verdict_*.md writes are approved)

    # ---- 8–13 · Step 5 · inside the reviewer, once per resolved task-id ----
    for task in tasks:
        if task.carries_decision_skip:                     # 8
            report_opted_out(task, quoting=task.stated_reason)   # 8a
            continue

        titles, exit_code = extract_planned_tests_for_task(plan, task.id)   # 9
        if exit_code in (1, 2):                            # 10
            record_parse_failure(task)   # 10a · marks the WHOLE run inconclusive
            continue
        if not titles:                                     # exit 0, empty
            report_na(task)              # 10b · task declared N/A, never a finding
            continue

        for title in titles:             # 11 · exit 0 with titles
            hit = git_grep("-nF", "--untracked", title)     # over the working tree
            if not hit:                                    # 12
                # 12a · AI semantic pass — reworded, wrapped or templated titles
                #       count as present ONLY with a path:line citation.
                hit = semantic_pass(title, require="path:line")
            classify(title, found_at=hit)                  # 13 · found (path:line) or missing

    # 14 · Step 6 — the reviewer writes the COMPLETE report to VERDICT_PATH:
    #      summary table, N/A list, opt-out list, one "### N. [HIGH]" per missing title.
    reviewer.write(verdict_path)

    while not present_and_non_empty(verdict_path):         # 15 · Step 7
        redispatch_once("test-reviewer")   # 15a · never report from the truncated return

    read_end_to_end(verdict_path)                          # 16 · Step 7
    print(plan, checked_ids, found_and_missing_counts, one_line_per_finding)

    return  # 17 · Stop — report only. Writing the missing tests is
            #      /quality-gate, or a direct ask.
```

## Flowchart

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
  n7["7. Step 4 · Dispatch ONE test-reviewer<br/>(agent-pinned, background, fresh context)"]:::dispatch
  n7a["7a. Hook: check-reviewer-writes<br/>(only verdict_*.md writes are approved)"]:::hook

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
  n17(["17. Stop — report only.<br/>Writing the missing tests is<br/>/quality-gate, or a direct ask"])

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
