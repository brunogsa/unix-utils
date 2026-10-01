# auto-review — flow overview

Human-facing overview for auditing the flow at a glance. Non-authoritative — the steps in [`../SKILL.md`](../SKILL.md) win on any conflict. Regenerate this file whenever the skill's flow changes.

Two renderings of the same flow, kept cross-checkable on purpose. The `# N` comments in the pseudo-code are the diagram's node ids, so an id with no matching comment is drift.

The pipeline's own waves are collapsed into the dispatch node; they live in `../../code-review-pipeline/assets/flowchart.md`.

## Pseudo-code

Python-shaped for readability only; nothing here runs, and the function names stand for steps this skill performs, not real APIs.

```python
def auto_review(base_ref_arg=None):                            # 1
    if base_ref_arg:                                           # 2
        base_ref = base_ref_arg          # used as-is, any git ref
    else:
        base_ref = run("~/.claude/scripts/resolve-base-ref.sh")   # 2a
        if not base_ref:                                       # 2b
            # 2b1 · never guess a base -- the diff would be against the wrong branch
            base_ref = ask_user("Which branch should I diff against?")

    # 3 · top-level CWD only, never recursive
    candidates = run("ls -1 spec_*.md plan_*.md")

    # 4 · loop check: the spec and the plan resolve independently
    chosen = []
    for kind in ("spec", "plan"):
        of_kind = [c for c in candidates if c.startswith(kind)]
        match len(of_kind):                                    # 4a
            case 1:
                chosen += of_kind; print(of_kind)              # 4a1
            case 0:
                print(f"no {kind}; proceeding without it")     # 4a2
            case _:
                # 4a3 · a prompt is only worth its friction with something to choose
                reply = ask_user(numbered_list(of_kind), options="all | <numbers> | none | cancel")
                if reply == "cancel":                          # 4a3a
                    return abort("review cancelled by the user")   # 4a3a1
                chosen += resolve_selection(reply, of_kind)    # 4a3b

    # 5 · space-separated absolute paths, or the literal <none>
    spec_plan_paths = " ".join(absolute(chosen)) or "<none>"

    # 6 · fresh context is the point: this session usually wrote the diff
    agent = dispatch("code-reviewer", title="Run code-review pipeline",
                     prompt={"Mode": "local", "Base ref": base_ref,
                             "Language": "English",
                             "Spec/plan files": spec_plan_paths}
                            + "read code-review-pipeline/SKILL.md and run Waves 0-6")

    report = await_completion_notification(agent)              # 7

    # 8 · verdict path comes from the Wave 6 summary in the report
    print(report.verdict_path, report.per_severity_counts,
          report.skipped_files, report.wave6_summary)

    # 9 · runtime-sized set: one entry per file the summary's
    #     doc-standards-flags block lists; the isolated pipeline cannot
    #     reach the user's TaskList, so this session files them
    for flagged in report.doc_standards_flags:
        task_create(f"[Scout] {flagged.file}: {flagged.what_is_off_standard}")

    # 10 · report only; applying is /address-verdicts' job
    return "verdict written; nothing applied"
```

## Flowchart

```mermaid
flowchart TD
  n1(["1. Invoke /auto-review [base-ref], or a phrase like<br/>'review this branch', or another skill's flow"]):::start
  n2{"2. base-ref argument passed?"}
  n2a["2a. Run ~/.claude/scripts/resolve-base-ref.sh<br/>(origin/HEAD, then local main, then local master)"]:::hook
  n2b{"2b. Resolved?"}
  n2b1["2b1. Ask the user which branch to diff against<br/>-- never guess"]:::gate
  n3["3. Discover candidates in CWD, top-level only:<br/>ls -1 spec_*.md plan_*.md"]:::hook
  n4{"4. Kinds left to resolve<br/>(spec, plan -- each independently)?"}
  n4a{"4a. How many candidates of that kind?"}
  n4a1["4a1. Exactly one: use it, print the path"]
  n4a2["4a2. Zero: proceed without it, say so plainly"]
  n4a3["4a3. More than one: prompt a numbered list<br/>-- all | numbers | none | cancel"]:::gate
  n4a3a{"4a3a. Reply is cancel?"}
  n4a3a1(["4a3a1. Abort the review"])
  n4a3b["4a3b. Resolve the selection into absolute paths"]
  n5["5. Set SPEC_PLAN_PATHS: space-separated<br/>absolute paths, or the literal &lt;none&gt;"]
  n6["6. Dispatch code-reviewer, title Run code-review pipeline<br/>(agent-pinned · background · serial):<br/>Mode local · Base ref · Language English · spec/plan paths<br/>in the prompt body; it reads code-review-pipeline/SKILL.md<br/>and runs Waves 0-6 in fresh context"]:::dispatch
  n7["7. Wait for its completion notification<br/>(never poll)"]
  n8["8. Print from its report: verdict path<br/>./verdict_auto-review_&lt;branch&gt;_&lt;timestamp&gt;.md,<br/>per-severity counts, skipped files, Wave 6 summary"]
  n9["9. Add to TaskList one [Scout] per file in the summary's<br/>doc-standards-flags block, naming the file and what is<br/>off standard -- the isolated pipeline cannot file them"]:::state
  n10(["10. Stop: report only. Applying findings<br/>is /address-verdicts' job"])

  n1 --> n2
  n2 -->|"yes -- use as-is"| n3
  n2 -->|"no"| n2a
  n2a --> n2b
  n2b -->|"yes"| n3
  n2b -->|"no"| n2b1
  n2b1 --> n3
  n3 --> n4
  n4 -->|"yes"| n4a
  n4a -->|"one"| n4a1
  n4a -->|"zero"| n4a2
  n4a -->|"many"| n4a3
  n4a3 --> n4a3a
  n4a3a -->|"yes"| n4a3a1
  n4a3a -->|"no"| n4a3b
  n4a1 --> n4
  n4a2 --> n4
  n4a3b --> n4
  n4 -->|"no -- both resolved"| n5
  n5 --> n6
  n6 --> n7
  n7 --> n8
  n8 --> n9
  n9 --> n10

  classDef start fill:#fef3c7,stroke:#d97706,stroke-width:2px
  classDef gate fill:#fee2e2,stroke:#dc2626,stroke-width:2px
  classDef dispatch fill:#dbeafe,stroke:#2563eb,stroke-width:2px
  classDef state fill:#dcfce7,stroke:#16a34a,stroke-width:2px
  classDef skill fill:#f3e8ff,stroke:#9333ea,stroke-width:2px
  classDef hook fill:#e5e7eb,stroke:#4b5563,stroke-width:2px
```
