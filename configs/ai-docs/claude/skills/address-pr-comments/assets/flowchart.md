# address-pr-comments — flow overview

Human-facing overview for auditing the flow at a glance. Non-authoritative — the numbered steps in [`../SKILL.md`](../SKILL.md) win on any conflict. Regenerate this file whenever the skill's flow changes.

```mermaid
flowchart TD
  invoke(["/address-pr-comments PR# [filters]"]):::start
  step0["Step 0: Pre-flight interview<br/><br/>git status; probe lint/test runners;<br/>ask dirty-tree, baseline, tails questions in one message"]
  persist["Persist step-0 answers to<br/>the run's scratchpad JSON file"]
  chk1a{"1a. On PR's branch?"}
  abort1a["Abort: not on PR branch<br/>run gh pr checkout"]
  chk1b{"1b. Working tree clean?"}
  commitStash["User commits/stashes<br/>via commit-standards"]
  rerun1["Re-run skill from Step 0"]
  chk1cOptIn{"1c. Baseline check<br/>opted in (step 0)?"}
  runBaseline["1c. Run lint then test"]
  chk1cGreen{"1c. Lint and test green?"}
  abort1c["Abort: fix pre-existing<br/>breakage first"]
  step2["Step 2: Resolve owner/repo<br/>and own gh login"]
  step3["Step 3: Dispatch subagent<br/>fetch, filter, cluster, rank, propose"]:::dispatch
  chk3zero{"Subagent found<br/>zero matching comments?"}
  stop3["Stop - no clusters to address"]
  proposal["Return proposal block to user"]
  userEdit["User edits proposal block<br/>one round: flip actions, edit reasons, delete clusters"]
  step4["Step 4: Parse edited block"]
  chk4parse{"Parse succeeded?"}
  askResend["Surface exact issue,<br/>ask user to re-send"]
  createTasks["Create one TaskList task<br/>per applied cluster"]
  loop5{"5. More apply<br/>clusters to commit?"}
  makeChanges["Make code changes for cluster;<br/>stage only relevant files"]
  commitCluster["Commit via commit-standards;<br/>capture SHA into task and scratchpad"]
  chk5drift{"Edits touched files<br/>outside cluster scope?"}
  askDrift["Ask user: a separate<br/>Drift commit, or bundle"]
  step6confirm["Step 6: Confirm git push with user"]
  push["git push - single batch push"]
  chk6rejected{"Push rejected<br/>remote moved?"}
  abort6["Abort: tell user to git pull<br/>--rebase, re-run from Step 5"]
  loop7{"7. More comments<br/>in surviving clusters?"}
  postReply["Post reply per 7a-7c templates<br/>apply/answer/drop, signature rules"]
  chk7d{"7d. Tails toggle on<br/>step 0 answer?"}
  dispatchTails["Dispatch deep-reviewer<br/>tail pair: refactor plus auto-review"]:::dispatch
  step8["Step 8: Print final summary<br/>applied/answered/dropped/skipped counts"]

  invoke --> step0
  step0 --> persist
  persist --> chk1a
  chk1a -->|"no"| abort1a
  chk1a -->|"yes"| chk1b
  chk1b -->|"dirty"| commitStash
  commitStash --> rerun1
  chk1b -->|"clean"| chk1cOptIn
  chk1cOptIn -->|"no / unanswered"| step2
  chk1cOptIn -->|"yes"| runBaseline
  runBaseline --> chk1cGreen
  chk1cGreen -->|"red"| abort1c
  chk1cGreen -->|"green"| step2
  step2 --> step3
  step3 --> chk3zero
  chk3zero -->|"yes"| stop3
  chk3zero -->|"no"| proposal
  proposal --> userEdit
  userEdit --> step4
  step4 --> chk4parse
  chk4parse -->|"fails"| askResend
  askResend --> userEdit
  chk4parse -->|"succeeds"| createTasks
  createTasks --> loop5
  loop5 -->|"yes"| makeChanges
  makeChanges --> commitCluster
  commitCluster --> chk5drift
  chk5drift -->|"yes"| askDrift
  askDrift --> loop5
  chk5drift -->|"no"| loop5
  loop5 -->|"no - all committed"| step6confirm
  step6confirm --> push
  push --> chk6rejected
  chk6rejected -->|"yes"| abort6
  chk6rejected -->|"no"| loop7
  loop7 -->|"yes"| postReply
  postReply --> loop7
  loop7 -->|"no - all replied"| chk7d
  chk7d -->|"yes"| dispatchTails
  dispatchTails --> step8
  chk7d -->|"no"| step8

  classDef start fill:#fef3c7,stroke:#d97706,stroke-width:2px
  classDef dispatch fill:#dbeafe,stroke:#2563eb,stroke-width:2px
```
