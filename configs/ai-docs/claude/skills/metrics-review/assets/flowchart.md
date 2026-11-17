---
# performance-check budget override, not part of the diagram itself.
# This file renders one flow twice - once as pseudo-code, once as a diagram.
# Parked in assets/ and never loaded by the model, so its words cost no context.
words-budget: 2048
---

# metrics-review - flow overview

Human-facing overview for auditing the flow at a glance. Non-authoritative - the steps in [`../SKILL.md`](../SKILL.md) win on any conflict. Regenerate this file whenever the skill's flow changes.

Two renderings of the same flow, kept cross-checkable on purpose. The `# N` comments in the pseudo-code are the diagram's node ids, so an id with no matching comment is drift.

## Pseudo-code

Python-shaped for readability only; nothing here runs, and the function names stand for steps this skill performs, not real APIs.

```python
def metrics_review(base_ref_arg=None, pushed=None):          # 1 · /metrics-review, or /quality-gate section 3
    if pushed:                                               # 2
        run_dir, base_ref, session_id = pushed               # 2a · a caller pushed them in; resolve nothing twice
    else:
        run_dir = mktemp_dir("<scratchpad>/metrics-review.XXXXXX")   # 2b
        base_ref = base_ref_arg or run("resolve-base-ref.sh")   # 2b · asks which branch when detection fails
        session_id = scratchpad_segment_above("scratchpad")  # 2b

    if tool_map_has_no_entry(repo, base_ref, session_id):    # 3
        report = dispatch("Explore", "metrics-tool-inspector")   # 3a · read-only; main double-checks it
        # 3a1 · a tool no detector matches becomes a detector edit main commits

    lens = dispatch("code-reviewer", title="Metrics-lens review",
                    follow="metrics-lens.md",
                    inputs=(run_dir, base_ref, "HEAD", session_id))   # 4 · background; /tmp told writable

    # 4a · hook: check-reviewer-writes guards the lens's writes at the tool layer.
    while lens.returns_tooling_ask():                        # 5
        if nobody_can_ask():                                 # 5a · a flag or a non-cli CLAUDE_CODE_ENTRYPOINT
            answer = "defer"                                 # 5a1 · pessimistic / not measured, scored failing
        else:
            answer = ask_user("fix now or defer", recommend="defer only if the fix is not understood")   # 5b
        lens = resume_or_redispatch(lens, answer)            # 5c

    if not outputs_present_and_non_empty(run_dir):           # 6
        redispatch_once(lens)                                # 6a
        if still_missing(run_dir):                           # 6b
            return "metrics: FAIL - leg failed"              # 6b1 · never read as clean

    # 6c · main runs check-metrics-judge-coverage.py itself: every rendered
    #      Record key ruled exactly once, by a finding or a dismissal
    if run("check-metrics-judge-coverage.py", run_dir).exit != 0:
        redispatch_once(lens)                                # 6c1
        if run("check-metrics-judge-coverage.py", run_dir).exit != 0:
            return "metrics: FAIL - leg failed"              # 6c2 · same failure as 6b1

    # 7 · print both verdict paths, counts, deferred asks and detector edits;
    #     applying is /address-verdicts' job
    return run_dir
```

## Flowchart

```mermaid
flowchart TD
  n1(["1. /metrics-review [--base-ref ref], or /quality-gate section 3<br/>pushing in RUN_DIR, BASE_REF, HEAD, SESSION_ID"]):::start
  n2{"2. Did a caller push the inputs in?"}
  n2a["2a. Use the pushed RUN_DIR, BASE_REF and SESSION_ID"]
  n2b["2b. Mint RUN_DIR (mktemp -d scratchpad/metrics-review.XXXXXX),<br/>resolve BASE_REF (argument, else resolve-base-ref.sh,<br/>else ask which branch), take SESSION_ID from the scratchpad path"]:::state
  n3{"3. Per-session tool map has no entry<br/>for this repo and base ref?"}
  n3a["3a. Main dispatches the read-only metrics-tool-inspector<br/>(Explore · serial) and double-checks its report"]:::dispatch
  n3a1["3a1. Commit each detector edit it justifies<br/>in the global config repo"]:::state
  n4["4. Dispatch code-reviewer, title Metrics-lens review<br/>(agent-pinned · background) following metrics-lens.md<br/>with RUN_DIR, BASE_REF, HEAD, SESSION_ID; told /tmp is writable"]:::dispatch
  n4a["4a. Hook: check-reviewer-writes"]:::hook
  n5{"5. Did the lens return a tooling ask?"}
  n5a{"5a. Can anyone be asked?<br/>(no flag, and CLAUDE_CODE_ENTRYPOINT is cli)"}
  n5a1["5a1. Defer without asking: coverage reads pessimistic,<br/>a file with no language entry reads not measured -<br/>both score as failing"]:::gate
  n5b["5b. AskUserQuestion: fix now or defer,<br/>quoting the tool and the reason"]:::gate
  n5c["5c. Continue or re-dispatch the lens with the answer"]
  n6{"6. Verdict and judge files<br/>present and non-empty?"}
  n6a["6a. Re-dispatch the lens once"]:::dispatch
  n6b{"6b. Still missing?"}
  n6b1(["6b1. Report: metrics: FAIL - leg failed (reason)"])
  n6c{"6c. Main runs check-metrics-judge-coverage.py:<br/>every Record key ruled once - exit 0?"}
  n6c1["6c1. Re-dispatch the lens once with the checker output"]:::dispatch
  n6c2{"6c2. Checker still non-zero?"}
  n7(["7. Print both verdict paths, counts, deferred asks and<br/>detector edits. Stop: applying is /address-verdicts' job"])

  n1 --> n2
  n2 -->|"yes"| n2a --> n3
  n2 -->|"no"| n2b --> n3
  n3 -->|"yes"| n3a --> n3a1 --> n4
  n3 -->|"no"| n4
  n4 -.->|"guards"| n4a
  n4 --> n5
  n5 -->|"yes"| n5a
  n5a -->|"no"| n5a1 --> n5c
  n5a -->|"yes"| n5b --> n5c
  n5c --> n5
  n5 -->|"no"| n6
  n6 -->|"no"| n6a --> n6b
  n6b -->|"yes"| n6b1
  n6b -->|"no"| n6
  n6 -->|"yes"| n6c
  n6c -->|"yes"| n7
  n6c -->|"no"| n6c1 --> n6c2
  n6c2 -->|"yes"| n6b1
  n6c2 -->|"no"| n7

  classDef start fill:#fef3c7,stroke:#d97706,stroke-width:2px
  classDef gate fill:#fee2e2,stroke:#dc2626,stroke-width:2px
  classDef dispatch fill:#dbeafe,stroke:#2563eb,stroke-width:2px
  classDef state fill:#dcfce7,stroke:#16a34a,stroke-width:2px
  classDef skill fill:#f3e8ff,stroke:#9333ea,stroke-width:2px
  classDef hook fill:#e5e7eb,stroke:#4b5563,stroke-width:2px
```
