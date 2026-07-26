# create-pr — flow overview

Human-facing overview for auditing the flow at a glance. Non-authoritative — the numbered steps in [`../SKILL.md`](../SKILL.md) win on any conflict. Regenerate this file whenever the skill's flow changes.

```mermaid
flowchart TD
  n1(["1. /create-pr — no flags"]):::start
  n2["2. Load doc-standards before drafting —<br/>a PR body is a standalone doc, so its density cap,<br/>BLUF ordering, and collapse rules all apply"]:::skill
  n3["3. Step 1 · Glob cwd top-level for spec_*.md / plan_*.md;<br/>extract every mermaid fence from what resolved —<br/>those become Architecture, and leave the appendix"]
  n4{"4. Anything left ambiguous?<br/>(A) several spec/plan files matched<br/>(B) several PR-N entries in the plan's PR Breakdown"}
  n4a["4a. Ask (A) and (B) together in ONE message,<br/>before continuing; skip any label that auto-resolved"]:::gate
  n5["5. Create ./pr-descr_&lt;slug&gt;_pr&lt;N&gt;.md right away, with an<br/>HTML comment logging each answer — this skill's durable<br/>record, surviving a mid-flow compaction that drops them"]:::state
  n6["6. Derive the appendix's section list — never ask for it:<br/>the resolved spec/plan MINUS every section the body renders"]
  n6a["6a. extract-md-sections.sh &lt;file&gt; &lt;section&gt; ..."]:::hook
  n7["7. Resolve the base branch:<br/>git symbolic-ref refs/remotes/origin/HEAD;<br/>empty -&gt; omit --base in step 5. Check if the branch is pushed"]
  n8[["8. Dispatch: Gather PR changes digest<br/>general-purpose · sonnet · effort inherits · foreground (step 2 gates on it)<br/>reads git log vs base with FULL commit bodies + git diff;<br/>returns only the changes digest, never the raw diff"]]:::dispatch
  n9[["9. Step 2 · Dispatch: Compose ideal PR description<br/>general-purpose · sonnet · effort inherits · foreground (step 3 gates on it)<br/>main session orchestrates and never composes the prose itself"]]:::dispatch
  n10["10. Ideal description written to ./pr-descr_&lt;slug&gt;_pr&lt;N&gt;.md<br/>in THIS skill's own format, ignoring any repo template —<br/>page-fit can only budget a section it recognizes"]:::state
  n11["11. Step 3 · Resolve every // TODO: Question marker — answer it inline<br/>when that adds reviewer value, else strip it entirely.<br/>None may survive into the pushed body"]
  n12[["12. Dispatch: density-fixer on the ideal description<br/>density-fixer · agent-pinned · foreground<br/>must exit clean: 256 chars / 32 words per line"]]:::dispatch
  n13["13. check-pr-page-fit.sh pr-descr_&lt;slug&gt;_pr&lt;N&gt;.md<br/>— 64 rendered lines, allocated per section"]:::hook
  n14{"14. Page-fit exit code?"}
  n14a["14a. Apply the cut order: repack lines past the wrap width, drop bullets<br/>a diagram already encodes, cut Decisions to behavior/cost/risk,<br/>merge Changes bullets, move methodology inside its collapsed block"]
  n14a1["14a1. A body that cannot fit after every cut is a PR that is too big:<br/>say so and recommend splitting the PR,<br/>rather than raising the budget silently"]:::gate
  n15{"15. Step 4 · Does .github/ carry a PR template?<br/>(pull_request_template.md / PULL_REQUEST_TEMPLATE.md)"}
  n15a["15a. No template -&gt; the ideal description IS the final body"]
  n15b[["15b. Dispatch: Fit PR description to repo template<br/>general-purpose · sonnet · effort inherits · foreground (step 5 gates on it)<br/>exactly two inputs: the verified ideal description + the template"]]:::dispatch
  n15c["15c. Final body written to ./pr-body_&lt;slug&gt;_pr&lt;N&gt;.md — the repo's<br/>template is the base structure, never the thing replaced.<br/>NEVER page-fit-checked: its structure is arbitrary, so the<br/>script cannot attribute its lines to a budgeted section"]:::state
  n16["16. Step 5 · check-pr-body-size.sh on the file THIS step pushes —<br/>the repo's template adds content the ideal never carried"]:::hook
  n17{"17. Body-size exit code?"}
  n17a["17a. Drop the appendix's lowest-value sections via extract-md-sections.sh<br/>— Test Design first, then Non-Functional Requirements"]
  n18["18. Push the branch with -u if needed; then<br/>gh pr create --draft --body-file &lt;file&gt; --base &lt;base-branch&gt;"]
  n19["19. Return the PR URL"]
  n20{"20. Step 6 · Does the user later change the pushed body,<br/>in chat or by hand-editing either .md?"}
  n20a["20a. Apply the fix to pr-descr_&lt;slug&gt;_pr&lt;N&gt;.md FIRST, then<br/>regenerate the final body from it, so the two never drift"]:::state
  n20b["20b. Infer the general rule behind the edit and propose it<br/>as a Writing Style update; apply it only once approved"]:::gate
  n21(["21. Done"])

  n1 --> n2
  n2 --> n3
  n3 --> n4
  n4 -->|"yes"| n4a
  n4 -->|"no, all auto-resolved"| n5
  n4a --> n5
  n5 --> n6
  n6 -.->|"extracted with"| n6a
  n6 --> n7
  n7 --> n8
  n8 --> n9
  n9 --> n10
  n10 --> n11
  n11 --> n12
  n12 --> n13
  n13 --> n14
  n14 -->|"0 — fits, but still read the breakdown<br/>and hold every section to its own budget"| n15
  n14 -->|"2 — close; trim the worst section"| n14a
  n14 -->|"3 — over the 64-line budget"| n14a
  n14a --> n13
  n14a -.->|"no cut left to make"| n14a1
  n15 -->|"no"| n15a
  n15 -->|"yes"| n15b
  n15b --> n15c
  n15a --> n16
  n15c --> n16
  n16 --> n17
  n17 -->|"0 or 2 — under the 65536-char API cap"| n18
  n17 -->|"3 — over the cap"| n17a
  n17a --> n16
  n18 --> n19
  n19 --> n20
  n20 -->|"yes"| n20a
  n20 -->|"no"| n21
  n20a --> n20b
  n20b --> n21

  classDef start fill:#fef3c7,stroke:#d97706,stroke-width:2px
  classDef gate fill:#fee2e2,stroke:#dc2626,stroke-width:2px
  classDef dispatch fill:#dbeafe,stroke:#2563eb,stroke-width:2px
  classDef state fill:#dcfce7,stroke:#16a34a,stroke-width:2px
  classDef skill fill:#f3e8ff,stroke:#9333ea,stroke-width:2px
  classDef hook fill:#e5e7eb,stroke:#4b5563,stroke-width:2px
```
