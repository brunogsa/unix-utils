# quality-gate — flow overview

Human-facing overview for auditing the flow at a glance. Non-authoritative — the numbered steps in [`../SKILL.md`](../SKILL.md) win on any conflict. Regenerate this file whenever the skill's flow changes.

```mermaid
flowchart TD
  n1(["1. /quality-gate &lt;spec&gt; &lt;plan&gt;<br/>--tasks &lt;ids&gt; --auto-solve<br/><br/>or another skill's batch-end dispatch"]):::start
  n2{"2. --auto-solve passed?"}
  n2a["2a. Step 1 · ONE question, before anything else:<br/>report only (default) or auto-solve?<br/>Asked first so no one is surprised by commits"]:::gate
  n3["3. Step 2 · Resolve spec + plan: arg paths by<br/>spec_/plan_ prefix, else glob CWD"]
  n4{"4. More than one spec, or more than one plan?"}
  n4a["4a. Prompt with a numbered list;<br/>the user picks which files feed the run"]:::gate
  n5["5. Step 2 · Resolve BASE_BRANCH from<br/>origin/HEAD, or take the caller's base ref<br/>(/implement passes BATCH_BASE_SHA)"]

  subgraph legs["6. Step 3 · Dispatch every leg in the SAME turn — independent report-only passes, no ordering between them. Each leg IS the fresh-context reviewer, so none spawns a nested one."]
    direction TB
    n6a["6a. deep-reviewer · reads refactor/SKILL.md<br/>(agent-pinned, background, ∥)<br/>→ verdict_refactor_&lt;ts&gt;.md"]:::dispatch
    n6b["6b. deep-reviewer · reads auto-review/SKILL.md<br/>(agent-pinned, background, ∥)<br/>→ verdict_auto-review_&lt;ts&gt;.md"]:::dispatch
    n6c["6c. deep-reviewer · reads test-sdd/SKILL.md,<br/>scoped by --tasks (agent-pinned, background, ∥)<br/>→ verdict_test-sdd_&lt;ts&gt;.md<br/>ONLY when a plan resolved"]:::dispatch
  end

  n6d["6d. Hook: deep-reviewer-write-guard<br/>(only verdict_*.md writes are approved)"]:::hook
  n7{"7. Step 4 · Each leg's verdict file<br/>present and non-empty?"}
  n7a["7a. Re-dispatch that leg ONCE; still missing,<br/>flag it and let the others stand.<br/>Never report from a capped return message"]:::dispatch
  n8{"8. Auto-solve chosen?"}
  n8a(["8a. Step 5 · Print the compact index — one line<br/>per finding, per leg — and STOP.<br/>Nothing is applied, however safe it looks"])
  n9["9. Step 6.1 · Read all three verdict files IN FULL;<br/>sort every finding addressable vs not;<br/>print both lists with reasons BEFORE applying"]

  subgraph seed["10. Step 6.2 · Seed the whole TaskList upfront, before applying anything — the list is this run's entire timeline"]
    direction TB
    n10a["10a. Add to TaskList one [Task] per addressable<br/>finding, in execution order, each breadcrumbed<br/>apply → commit → mark [Done]"]:::state
    n10b["10b. Add to TaskList a [Reminder] for Step 7:<br/>the closing report, so a compaction<br/>cannot drop the wrap-up"]:::state
    n10a --> n10b
  end

  subgraph apply["Step 6.3 · One finding at a time, SERIAL — two agents on overlapping scope would conflict unseen"]
    direction TB
    n11["11. TaskUpdate this finding's entry to in_progress"]:::state
    n12{"12. Which lens raised the finding?"}
    n12a["12a. Refactor lens → dispatch the refactor agent<br/>(agent-pinned) with the scope + test command.<br/>It refuses behavior changes by design"]:::dispatch
    n12b["12b. Auto-review or test-sdd lens → dispatch<br/>tdd-coder (agent-pinned): the test goes<br/>RED before it goes GREEN"]:::dispatch
    n13["13. Verify against the ARTIFACTS — the diff and the<br/>test output, never the agent's summary"]
    n14{"14. Applied clean?"}
    n14a["14a. Record the failure; leave the entry open<br/>and the finding unmarked, with what<br/>it needs to retry"]:::state
    n15["15. Commit: tdd-coder already committed, so confirm<br/>the SHA; the refactor agent leaves its change<br/>uncommitted, so commit it HERE, in session,<br/>where the permission prompt can render"]
    n16["16. Mark the finding [Done] in its verdict file<br/>IMMEDIATELY — ### N. [Done][SEVERITY] title.<br/>Batching it would leave a killed session<br/>with fixes and no ledger"]:::state
    n17["17. TaskUpdate this finding's entry to completed"]:::state
    n18{"18. Any addressable finding left?"}
  end

  n19(["19. Step 7 · Close with the report: the three verdict<br/>paths, applied findings with SHAs, findings judged<br/>not addressable with reasons, failed applies with<br/>their retry needs, and that unmarked findings<br/>are worked later by /address-verdicts"])

  n1 --> n2
  n2 -->|"no"| n2a --> n3
  n2 -->|"yes"| n3
  n3 --> n4
  n4 -->|"yes"| n4a --> n5
  n4 -->|"no"| n5
  n5 --> n6a
  n5 --> n6b
  n5 --> n6c
  n6a -.->|"guards"| n6d
  n6b -.->|"guards"| n6d
  n6c -.->|"guards"| n6d
  n6a --> n7
  n6b --> n7
  n6c --> n7
  n7 -->|"no"| n7a --> n8
  n7 -->|"yes"| n8
  n8 -->|"no"| n8a
  n8 -->|"yes"| n9 --> n10a
  n10b --> n11 --> n12
  n12 -->|"refactor"| n12a --> n13
  n12 -->|"correctness / missing test"| n12b --> n13
  n13 --> n14
  n14 -->|"no"| n14a --> n18
  n14 -->|"yes"| n15 --> n16 --> n17 --> n18
  n18 -->|"yes"| n11
  n18 -->|"no"| n19

  classDef start fill:#fef3c7,stroke:#d97706,stroke-width:2px
  classDef gate fill:#fee2e2,stroke:#dc2626,stroke-width:2px
  classDef dispatch fill:#dbeafe,stroke:#2563eb,stroke-width:2px
  classDef state fill:#dcfce7,stroke:#16a34a,stroke-width:2px
  classDef skill fill:#f3e8ff,stroke:#9333ea,stroke-width:2px
  classDef hook fill:#e5e7eb,stroke:#4b5563,stroke-width:2px
```
