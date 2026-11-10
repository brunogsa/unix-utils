---
words-budget: 2048
---

# tech-doc-review flowchart

Human-facing and non-authoritative: SKILL.md's numbered steps win on conflict.

The `# <id> ·` comments in the pseudo-code are load-bearing: each matches a diagram node id, so drift between the two renderings is something `grep` finds.

## Pseudo-code

The function names stand for orchestrator actions, not real APIs.

```python
def halt(reason):
    # 3a · stop: name the source and the sign, ask, write no report
    ask_engineer(reason)
    return

# 1 · engineer runs the skill with doc, context, optional reference contract, optional last report
load_read_tools_via_toolsearch()                      # 2 · read-only Drive and Slack tools, by function
sources = read(doc_with_comments, thread, reference, baseline)   # 3 ·
if not every_source_whole_and_parsed(sources):        # 4 · incl. JSON/YAML parse, xlsx tab count
    return halt("unreadable, incomplete, unparseable or ambiguous source")  # 4a ·
save_text_to_scratchpad(sources)                      # 5 · checker reads the same bytes
missing = operations_without_goal()                   # 6 ·
if missing:
    ask_engineer_in_one_batch(missing)                # 6a ·
findings = review_against_checklist()                 # 7 · clusters, tiers, tags, baseline match
if baseline:
    if source_line_differs():                         # 8 ·
        if engineer_says_different_doc():             # 8a ·
            return halt("different doc, no report")
    findings = mark_resolved_and_recurring(findings)  # 9 · re-check item at its places first
report = write_report_from_template(findings)         # 10 · never overwrite
rc = check_report(report)                             # 11 ·
while rc != 0:                                        # 12 · exit code
    if rc == 1 and non_bloqueia_left(report):
        cut_lowest_finding_of_lowest_tier(report)     # 12a · record the cut
    elif rc == 1:
        relay_word_count_in_chat()                    # 12b · only Bloqueia left, kept
        break
    elif rc == 2:
        fix_report_shape(report)                      # 12c · skill defect
    else:
        report = rerun_with_report_path()             # 12d · exit 3: wrong, missing or unreadable path
    rc = check_report(report)
verdicts = opus_check(report)                         # 13 · general-purpose, once per run
apply_verdicts_once(report, verdicts)                 # 15 · the verdicts it gave, no second check
if not covers_items_1_to_19(verdicts):                # 14 ·
    say_in_chat("check incomplete")                   # 14a · never present as checked
rc = check_report(report)                             # 16 ·
while rc == 1 and non_bloqueia_left(report):          # 17 ·
    cut_lowest_finding_of_lowest_tier(report)         # 17a · name the cut in chat
    rc = check_report(report)
chat_notes(report, cuts, not_applicable, check_result, words)   # 18 ·
```

## Flowchart

```mermaid
flowchart TD
  n1(["1. Engineer runs the skill"]):::start --> n2
  n2["2. Load Drive and Slack read tools via ToolSearch"]:::skill --> n3
  n3["3. Read doc with comments, thread, reference contract, baseline"] --> n4
  n4{"4. Every source read whole and parsed?"}:::gate
  n4 -- no --> n4a(["4a. Stop: name source and sign, ask, write no report"]):::gate
  n4 -- yes --> n5
  n5["5. Save fetched text to the scratchpad"]:::state --> n6
  n6{"6. Goal known for every operation?"}:::gate
  n6 -- no --> n6a["6a. Ask every missing goal in one batch; declined goal ranks as generic consumer"]:::gate --> n7
  n6 -- yes --> n7
  n7["7. Review against checklist: findings, clusters, tiers, tags"] --> n8
  n8{"8. Baseline source differs from new doc?"}:::gate
  n8 -- yes --> n8a{"8a. Engineer says different doc?"}:::gate
  n8a -- yes --> n4a
  n8a -- no --> n9
  n8 -- no --> n9
  n9["9. Mark resolved and recurring after re-checking each item"] --> n10
  n10["10. Write report from template, never overwriting"]:::state --> n11
  n11["11. Run bash check-report.sh"]:::hook --> n12
  n12{"12. Exit code?"}:::gate
  n12 -- "1, non-Bloqueia left" --> n12a["12a. Cut lowest finding of lowest tier, record the cut"] --> n11
  n12 -- "1, only Bloqueia left" --> n12b["12b. Relay word count in chat"] --> n13
  n12 -- "2" --> n12c["12c. Skill defect: fix the report shape"] --> n11
  n12 -- "3" --> n12d["12d. Wrong path: rerun with the report's path"] --> n11
  n12 -- 0 --> n13
  n13["13. Opus subagent checks report, cuts and N/A as decided, serial"]:::dispatch --> n15
  n15["15. Apply verdicts once"]:::state --> n14
  n14{"14. Verdicts cover items 1 to 19?"}:::gate
  n14 -- no --> n14a(["14a. Apply verdicts given, say check incomplete"]):::gate --> n16
  n14 -- yes --> n16
  n16["16. Re-run check-report.sh"]:::hook --> n17
  n17{"17. Exit 1 with non-Bloqueia left?"}:::gate
  n17 -- yes --> n17a["17a. Cut again, name the cut in chat"] --> n16
  n17 -- no --> n18
  n18(["18. Chat: path, cuts, N/A items, check result, word count"]):::start

  classDef state fill:#dcfce7,stroke:#16a34a,stroke-width:2px
  classDef start fill:#fef3c7,stroke:#d97706,stroke-width:2px
  classDef skill fill:#f3e8ff,stroke:#9333ea,stroke-width:2px
  classDef gate fill:#fee2e2,stroke:#dc2626,stroke-width:2px
  classDef dispatch fill:#dbeafe,stroke:#2563eb,stroke-width:2px
  classDef hook fill:#e5e7eb,stroke:#4b5563,stroke-width:2px
```
