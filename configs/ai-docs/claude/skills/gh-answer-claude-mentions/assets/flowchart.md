# gh-answer-claude-mentions — flow overview

Human-facing overview for auditing the flow at a glance. Non-authoritative — the numbered steps in [`../SKILL.md`](../SKILL.md) win on any conflict. Regenerate this file whenever the skill's flow changes.

```mermaid
flowchart TD
  n1(["1. /gh-answer-claude-mentions, user-invoked only<br/>PR given as a URL or a number"]):::start
  n2["2. Step 1 · Fetch the PR comments with gh api into a file under /tmp, then filter locally.<br/>From a URL take owner, repo, number; from a bare number infer the repo from the git remote"]
  n3["3. Step 2 · Keep comments with @claude, Claude: or a question aimed at the assistant.<br/>Skip bot comments unless the user asks"]
  n4{"4. Any comment addressed to Claude?"}
  n4a(["4a. STOP — tell the user there are none"]):::done
  n5["5. For each comment: show author, file and line, full body, existing replies"]
  n6["6. Step 3 · Discuss on the terminal: trade-offs, alternatives, code references"]:::gate
  n7{"7. User explicitly approved a conclusion?"}
  n7a["7a. Adjust the wording, skip the comment, or the user handles it.<br/>NEVER post without approval"]
  n8{"8. Comment already has a Claude reply?"}
  n8a["8a. Show it and ask: PATCH the existing reply, or add a new one"]:::gate
  n9["9. Step 4 · Post the reply with gh api POST in_reply_to.<br/>Body starts with Claude: and a blank line, then a concise summary of the conclusion"]:::dispatch
  n10{"10. More comments left?"}
  n11(["11. Step 5 · Confirm which comments were answered and link the PR"]):::done

  n1 --> n2 --> n3 --> n4
  n4 -->|"no"| n4a
  n4 -->|"yes"| n5 --> n6 --> n7
  n7 -->|"no"| n7a --> n10
  n7 -->|"yes"| n8
  n8 -->|"yes"| n8a --> n9
  n8 -->|"no"| n9
  n9 --> n10
  n10 -->|"yes"| n5
  n10 -->|"no"| n11

  classDef start fill:#d4edda,stroke:#28a745
  classDef gate fill:#fff3cd,stroke:#d39e00
  classDef dispatch fill:#d6e9f8,stroke:#2f7fc1
  classDef done fill:#d4edda,stroke:#28a745
```
