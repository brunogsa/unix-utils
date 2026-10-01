# personal-format — flow overview

Human-facing overview for auditing the flow at a glance. Non-authoritative — the numbered steps in [`../SKILL.md`](../SKILL.md) win on any conflict. Regenerate this file whenever the skill's flow changes.

```mermaid
flowchart TD
  n1(["1. /personal-format, or asked to format or clean up comments or markdown"]):::start
  n2["2. Step 1 · Resolve changed files: union of git diff --name-only<br/>and git ls-files --others --exclude-standard"]
  n3{"3. Step 2 · Union empty?"}
  n3a(["3a. STOP — report nothing to check.<br/>Dispatch no fixer agent"]):::done
  n4["4. Step 3 · Classify by extension:<br/>ts, js, sh, py to the comment batch, md to the markdown batch"]
  n4a["4a. Any other extension is skipped silently, not an error"]
  n5["5. Step 4 · Drop deleted files from each batch<br/>and name each in the report as skipped-because-deleted"]
  n6{"6. Step 5 · Which batches are non-empty?"}
  n6a["6a. Both: dispatch comment-format-fixer and<br/>markdown-standards-fixer in parallel, each on its own files only"]:::dispatch
  n6b["6b. One: dispatch just that fixer"]:::dispatch
  n7["7. Step 6 · Report each file individually:<br/>fixed, not-reached, or failed. Never merge a failure into a success summary.<br/>No automatic retry on a fixer failure"]
  n8(["8. Done"]):::done

  n1 --> n2 --> n3
  n3 -->|"yes"| n3a
  n3 -->|"no"| n4 --> n5
  n4 -.-> n4a
  n5 --> n6
  n6 -->|"both"| n6a --> n7
  n6 -->|"one"| n6b --> n7
  n7 --> n8

  classDef start fill:#d4edda,stroke:#28a745
  classDef gate fill:#fff3cd,stroke:#d39e00
  classDef dispatch fill:#d6e9f8,stroke:#2f7fc1
  classDef done fill:#d4edda,stroke:#28a745
```
