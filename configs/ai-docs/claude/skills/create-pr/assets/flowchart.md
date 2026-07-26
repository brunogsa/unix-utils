# create-pr — flow overview

Human-facing overview for auditing the flow at a glance. Non-authoritative — the numbered steps in [`../SKILL.md`](../SKILL.md) win on any conflict. Regenerate this file whenever the skill's flow changes.

```mermaid
flowchart TD
  start(["/create-pr — no flags"]):::start
  loadStd["Load doc-standards before drafting —<br/>a PR body is a standalone doc, so its density cap,<br/>BLUF ordering, and collapse rules all apply"]:::skill
  glob["1. Glob cwd top-level for spec_*.md / plan_*.md;<br/>extract every mermaid fence from what resolved —<br/>those become Architecture, and leave the appendix"]
  qcheck{"Anything left ambiguous?<br/>(A) several spec/plan files matched<br/>(B) several PR-N entries in the plan's PR Breakdown"}
  ask["Ask (A) and (B) together in ONE message,<br/>before continuing; skip any label that auto-resolved"]:::gate
  seedFile["Create ./pr-descr_&lt;slug&gt;_pr&lt;N&gt;.md right away, with an<br/>HTML comment logging each answer — this skill's durable<br/>record, surviving a mid-flow compaction that drops them"]:::state
  derive["Derive the appendix's section list — never ask for it:<br/>the resolved spec/plan MINUS every section the body renders"]
  extractSh["extract-md-sections.sh &lt;file&gt; &lt;section&gt; ..."]:::hook
  baseBranch["Resolve the base branch:<br/>git symbolic-ref refs/remotes/origin/HEAD;<br/>empty -&gt; omit --base in step 5. Check if the branch is pushed"]
  digestDispatch[["Dispatch: Gather PR changes digest<br/>general-purpose · sonnet · effort inherits · foreground (step 2 gates on it)<br/>reads git log vs base with FULL commit bodies + git diff;<br/>returns only the changes digest, never the raw diff"]]:::dispatch
  composeDispatch[["2. Dispatch: Compose ideal PR description<br/>general-purpose · sonnet · effort inherits · foreground (step 3 gates on it)<br/>main session orchestrates and never composes the prose itself"]]:::dispatch
  idealFile["Ideal description written to ./pr-descr_&lt;slug&gt;_pr&lt;N&gt;.md<br/>in THIS skill's own format, ignoring any repo template —<br/>page-fit can only budget a section it recognizes"]:::state
  todoCheck["3. Resolve every // TODO: Question marker — answer it inline<br/>when that adds reviewer value, else strip it entirely.<br/>None may survive into the pushed body"]
  densityDispatch[["Dispatch: density-fixer on the ideal description<br/>density-fixer · agent-pinned · foreground<br/>must exit clean: 256 chars / 32 words per line"]]:::dispatch
  pagefitSh["check-pr-page-fit.sh pr-descr_&lt;slug&gt;_pr&lt;N&gt;.md<br/>— 64 rendered lines, allocated per section"]:::hook
  pagefitGate{"Page-fit exit code?"}
  cut["Apply the cut order: repack lines past the wrap width, drop bullets<br/>a diagram already encodes, cut Decisions to behavior/cost/risk,<br/>merge Changes bullets, move methodology inside its collapsed block"]
  tooBig["A body that cannot fit after every cut is a PR that is too big:<br/>say so and recommend splitting the PR,<br/>rather than raising the budget silently"]:::gate
  tplCheck{"4. Does .github/ carry a PR template?<br/>(pull_request_template.md / PULL_REQUEST_TEMPLATE.md)"}
  idealIsFinal["No template -&gt; the ideal description IS the final body"]
  fitDispatch[["Dispatch: Fit PR description to repo template<br/>general-purpose · sonnet · effort inherits · foreground (step 5 gates on it)<br/>exactly two inputs: the verified ideal description + the template"]]:::dispatch
  finalFile["Final body written to ./pr-body_&lt;slug&gt;_pr&lt;N&gt;.md — the repo's<br/>template is the base structure, never the thing replaced.<br/>NEVER page-fit-checked: its structure is arbitrary, so the<br/>script cannot attribute its lines to a budgeted section"]:::state
  sizeSh["5. check-pr-body-size.sh on the file THIS step pushes —<br/>the repo's template adds content the ideal never carried"]:::hook
  sizeGate{"Body-size exit code?"}
  trim["Drop the appendix's lowest-value sections via extract-md-sections.sh<br/>— Test Design first, then Non-Functional Requirements"]
  push["Push the branch with -u if needed; then<br/>gh pr create --draft --body-file &lt;file&gt; --base &lt;base-branch&gt;"]
  url["Return the PR URL"]
  feedback{"6. Does the user later change the pushed body,<br/>in chat or by hand-editing either .md?"}
  reapply["Apply the fix to pr-descr_&lt;slug&gt;_pr&lt;N&gt;.md FIRST, then<br/>regenerate the final body from it, so the two never drift"]:::state
  proposeRule["Infer the general rule behind the edit and propose it<br/>as a Writing Style update; apply it only once approved"]:::gate
  done(["Done"])

  start --> loadStd
  loadStd --> glob
  glob --> qcheck
  qcheck -->|"yes"| ask
  qcheck -->|"no, all auto-resolved"| seedFile
  ask --> seedFile
  seedFile --> derive
  derive -.->|"extracted with"| extractSh
  derive --> baseBranch
  baseBranch --> digestDispatch
  digestDispatch --> composeDispatch
  composeDispatch --> idealFile
  idealFile --> todoCheck
  todoCheck --> densityDispatch
  densityDispatch --> pagefitSh
  pagefitSh --> pagefitGate
  pagefitGate -->|"0 — fits, but still read the breakdown<br/>and hold every section to its own budget"| tplCheck
  pagefitGate -->|"2 — close; trim the worst section"| cut
  pagefitGate -->|"3 — over the 64-line budget"| cut
  cut --> pagefitSh
  cut -.->|"no cut left to make"| tooBig
  tplCheck -->|"no"| idealIsFinal
  tplCheck -->|"yes"| fitDispatch
  fitDispatch --> finalFile
  idealIsFinal --> sizeSh
  finalFile --> sizeSh
  sizeSh --> sizeGate
  sizeGate -->|"0 or 2 — under the 65536-char API cap"| push
  sizeGate -->|"3 — over the cap"| trim
  trim --> sizeSh
  push --> url
  url --> feedback
  feedback -->|"yes"| reapply
  feedback -->|"no"| done
  reapply --> proposeRule
  proposeRule --> done

  classDef start fill:#fef3c7,stroke:#d97706,stroke-width:2px
  classDef gate fill:#fee2e2,stroke:#dc2626,stroke-width:2px
  classDef dispatch fill:#dbeafe,stroke:#2563eb,stroke-width:2px
  classDef state fill:#dcfce7,stroke:#16a34a,stroke-width:2px
  classDef skill fill:#f3e8ff,stroke:#9333ea,stroke-width:2px
  classDef hook fill:#e5e7eb,stroke:#4b5563,stroke-width:2px
```
