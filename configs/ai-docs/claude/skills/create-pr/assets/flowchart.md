# create-pr — flow overview

Human-facing overview for auditing the flow at a glance. Non-authoritative — the numbered steps in [`../SKILL.md`](../SKILL.md) win on any conflict. Regenerate this file whenever the skill's flow changes.

```mermaid
flowchart TD
  n1(["1. /create-pr — no flags"]):::start
  n2["2. Load doc-standards before drafting —<br/>a PR body is a standalone doc, so its density cap,<br/>BLUF ordering, and collapse rules all apply"]:::skill

  subgraph n3["3. Seed the TaskList before step 1 runs — a skipped step then stays<br/>visible as pending across a compaction, which the steps alone do not survive.<br/>Steps 1-5 only: step 6 runs only if the user asks after the push"]
    n3a["3a. [Reminder] Step 1: gather context"]:::state
    n3b["3b. [Reminder] Step 2: compose the ideal description"]:::state
    n3c["3c. [Reminder] Step 3: verify the ideal description"]:::state
    n3d["3d. [Reminder] Step 4: fit it to the repo's PR template"]:::state
    n3e["3e. [Reminder] Step 5: create the draft PR"]:::state
  end

  n4["4. Step 1 · Glob cwd top-level for spec_*.md / plan_*.md;<br/>none found -&gt; author from the changes digest alone"]
  n5{"5. Anything left ambiguous?<br/>(A) several spec/plan files matched<br/>(B) several PR-N entries in the plan's PR Breakdown"}
  n5a["5a. ONE AskUserQuestion carrying (A) and (B) as two<br/>SEPARATE questions — they resolve different things, so one<br/>merged question would force two answers into one choice"]:::gate
  n6["6. Create ./pr_&lt;slug&gt;_pr&lt;N&gt;.ideal.md right away, with an<br/>HTML comment logging each answer — this skill's durable<br/>record, surviving a mid-flow compaction that drops them"]:::state
  n7["7. Derive the appendix's section list — never ask for it:<br/>the resolved spec/plan MINUS every section the body renders.<br/>The list is handed to step 2's agent, which extracts sections with<br/>extract-md-sections.sh and diagrams with extract-mermaid-blocks.sh —<br/>a re-summarized section or re-drawn diagram diverges silently"]
  n8["8. Resolve the base branch:<br/>git symbolic-ref refs/remotes/origin/HEAD;<br/>empty -&gt; omit --base when the PR is created"]
  n9[["9. Dispatch: Gather PR changes digest<br/>changes-gatherer · agent-pinned · foreground (step 2 gates on it)<br/>writes the full commit log + diff to a /tmp artifact and returns<br/>only the digest, so the raw diff never enters the main session"]]:::dispatch

  n10[["10. Step 2 · Dispatch: Compose ideal PR description<br/>pr-writer · agent-pinned · mode ideal · foreground (step 3 gates on it)<br/>main session orchestrates and never composes the prose itself"]]:::dispatch
  n11["11. Ideal description written to ./pr_&lt;slug&gt;_pr&lt;N&gt;.ideal.md<br/>in THIS skill's own format, ignoring any repo template —<br/>page-fit can only budget a section it recognizes"]:::state

  n12["12. Step 3 · Re-run both gates in the main session:<br/>check-density.sh and check-pr-page-fit.sh —<br/>what is confirmed is the artifact, not the agent's account of it"]:::hook
  n13{"13. Both gates clean?<br/>density silent, page-fit exit 0"}
  n13a[["13a. Dispatch: Fix the flagged ideal description<br/>pr-writer · agent-pinned · mode ideal · foreground<br/>hand it the script output; never hand-fix the prose in main"]]:::dispatch

  n14{"14. Step 4 · Does .github/ carry a PR template?<br/>(pull_request_template.md / PULL_REQUEST_TEMPLATE.md)"}
  n14a["14a. No template -&gt; cp the ideal to ./pr_&lt;slug&gt;_pr&lt;N&gt;.final.md,<br/>so one push path serves both branches"]:::state
  n14b[["14b. Dispatch: Fit PR description to repo template<br/>pr-writer · agent-pinned · mode final · foreground (step 5 gates on it)<br/>exactly three paths: the verified ideal, the template, the output"]]:::dispatch
  n14c["14c. Final body written to ./pr_&lt;slug&gt;_pr&lt;N&gt;.final.md — the repo's<br/>template is the base structure, never the thing replaced.<br/>NEVER page-fit-checked: its structure is arbitrary, so the<br/>script cannot attribute its lines to a budgeted section"]:::state

  n15["15. Step 5 · check-pr-body-size.sh on the .final.md —<br/>the only gate the no-template copy path has run on that file"]:::hook
  n16{"16. Body-size exit code?"}
  n16a[["16a. Dispatch: Trim the oversized final body<br/>pr-writer · agent-pinned · mode final · foreground<br/>drops the appendix's lowest-value sections and re-checks"]]:::dispatch
  n17["17. Only NOW push: git push -u origin &lt;branch&gt; when it has no<br/>upstream. The push is the run's first outward-facing act — it fires<br/>CI and makes the branch visible, while every step above only wrote<br/>local files, so a failed compose or gate leaves nothing on the remote"]:::gate
  n18["18. gh pr create --draft --body-file &lt;final&gt; --base &lt;base-branch&gt;,<br/>with NO chat-side review gate — the user reviews the rendered<br/>body on GitHub, which is the artifact they will actually judge"]
  n19["19. Return the PR URL"]

  n20{"20. Step 6 · Does the user hand-edit the body on GitHub,<br/>or ask for a change in chat?"}
  n20a["20a. Pull GitHub's current body into the file first —<br/>gh pr view &lt;n&gt; --json body — so a hand-edit made<br/>there is not overwritten by the next push"]
  n20b["20b. Edit ./pr_&lt;slug&gt;_pr&lt;N&gt;.final.md ONLY; the .ideal.md is<br/>deliberately left to drift, since re-deriving the final body<br/>would discard the user's own edits"]:::state
  n20c["20c. Confirm with the user before writing to GitHub —<br/>the local edit is cheap to revise, the pushed body notifies reviewers"]:::gate
  n20d["20d. gh api --method PATCH repos/&lt;owner&gt;/&lt;repo&gt;/pulls/&lt;n&gt; -F body=@&lt;file&gt;<br/>— never gh pr edit --body-file, which queries Projects-classic<br/>projectCards and can fail the write while still exiting 0.<br/>Read the body back and confirm it matches the file"]
  n21(["21. Done"])

  n1 --> n2
  n2 --> n3
  n3 --> n4
  n4 --> n5
  n5 -->|"yes"| n5a
  n5 -->|"no, all auto-resolved"| n6
  n5a --> n6
  n6 --> n7
  n7 --> n8
  n8 --> n9
  n9 --> n10
  n10 --> n11
  n11 --> n12
  n12 --> n13
  n13 -->|"no"| n13a
  n13a --> n12
  n13 -->|"yes — never pause for user review"| n14
  n14 -->|"no"| n14a
  n14 -->|"yes"| n14b
  n14b --> n14c
  n14a --> n15
  n14c --> n15
  n15 --> n16
  n16 -->|"0 or 2 — under the 65536-char API cap"| n17
  n16 -->|"3 — over the cap"| n16a
  n16a --> n15
  n17 --> n18
  n18 --> n19
  n19 --> n20
  n20 -->|"yes"| n20a
  n20 -->|"no"| n21
  n20a --> n20b
  n20b --> n20c
  n20c --> n20d
  n20d --> n20

  classDef start fill:#fef3c7,stroke:#d97706,stroke-width:2px
  classDef gate fill:#fee2e2,stroke:#dc2626,stroke-width:2px
  classDef dispatch fill:#dbeafe,stroke:#2563eb,stroke-width:2px
  classDef state fill:#dcfce7,stroke:#16a34a,stroke-width:2px
  classDef skill fill:#f3e8ff,stroke:#9333ea,stroke-width:2px
  classDef hook fill:#e5e7eb,stroke:#4b5563,stroke-width:2px
```
