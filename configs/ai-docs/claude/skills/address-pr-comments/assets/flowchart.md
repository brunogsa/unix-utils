# address-pr-comments — flow overview

Human-facing overview for auditing the flow at a glance. Non-authoritative — the numbered steps in [`../SKILL.md`](../SKILL.md) win on any conflict. Regenerate this file whenever the skill's flow changes.

```mermaid
flowchart TD
  invoke(["/address-pr-comments PR# [filters]"]):::start
  createState["Create run-state file<br/>/tmp/address-pr-comments_&lt;session_id&gt;_&lt;ts&gt;.json"]:::state
  remindTask0["Global CLAUDE.md rule:<br/>add [Reminder] TaskList entry<br/>per remaining step (0-8)"]:::state
  probe0["Step 0: git status --porcelain;<br/>probe lint/test runner markers (read-only)"]
  askBatch["Step 0: Ask in ONE message<br/>(only conditions that hold)<br/><br/>- Dirty tree -&gt; commit now? (if dirty)<br/>- Green baseline check? (default no)<br/>- Runner pick (if ambiguous/none)<br/>- Tails after this batch? (default no)"]:::gate
  persistAnswers["Persist step-0 answers to<br/>run-state file - survives compaction"]:::state
  chk1a{"1a. On PR's branch?<br/>(1a-1d run sequentially, fail-fast<br/>on first failure)"}
  abort1a["Abort: not on PR branch<br/>run gh pr checkout"]
  chk1b{"1b. Working tree clean?<br/>(persisted step-0 answer)"}
  skillCommit1["Load commit-standards<br/>(Skill tool)"]:::skill
  commitStash["User commits or stashes<br/>the dirty files"]
  rerun1["Re-run skill from Step 0"]
  chk1cOptIn{"1c. Baseline check<br/>opted in (step 0)?"}
  runBaseline["1c. Run lint then test"]
  chk1cGreen{"1c. Lint and test green?"}
  skillDebug1c["Load debug-standards<br/>(Skill tool)"]:::skill
  abort1c["Abort: fix pre-existing<br/>breakage first"]
  step2["Step 2: Resolve owner/repo<br/>and own gh login"]
  step3["Step 3: Dispatch subagent<br/>general-purpose &middot; sonnet &middot; medium<br/>background (single, serial)<br/><br/>Reads step-3-fetch-cluster-propose.md<br/>+ review-principles.md<br/>fetch, filter, cluster, rank, propose"]:::dispatch
  chk3zero{"Subagent found<br/>zero matching comments?"}
  stop3["Stop - no clusters to address"]
  proposal["Return proposal block to user"]
  userEdit["User edits proposal block<br/>one round: flip actions, edit reasons, delete clusters<br/>(per-cluster action approval)"]:::gate
  step4["Step 4: Parse edited block"]
  chk4parse{"Parse succeeded?"}
  askResend["Surface exact issue,<br/>ask user to re-send"]
  createTasks["Create one [Task] per applied cluster<br/>(TaskList)"]:::state
  loop5{"5. More apply<br/>clusters to commit?"}
  skillStandards5["Load code-standards / test-standards /<br/>doc-standards as applicable<br/>(Skill tool)"]:::skill
  makeChanges["Make code changes for cluster;<br/>stage only relevant files"]
  skillCommit5["Load commit-standards<br/>(Skill tool)"]:::skill
  commitCluster["Commit the cluster's<br/>staged changes"]
  updateState5["Update cluster's [Task] metadata<br/>+ scratchpad file<br/>(action, commit_sha, status)"]:::state
  chk5drift{"Edits touched files<br/>outside cluster scope?"}
  askDrift["Ask user: a separate<br/>Drift commit, or bundle"]
  step6confirm["Step 6: Confirm git push with user<br/>(batch push gate)"]:::gate
  push["git push - single batch push"]
  chk6rejected{"Push rejected<br/>remote moved?"}
  abort6["Abort: stop, surface to user<br/>per-cluster commits stand<br/>user resolves divergence manually<br/>(never auto-rebase)"]
  loop7{"7. More comments<br/>in surviving clusters?"}
  postReply["Post reply per 7a-7c templates<br/>apply/answer/drop, signature rules<br/>(permission-gated per reply)"]:::gate
  chk7perm{"Permission<br/>denied?"}
  skipLogPerm["Skip reply;<br/>list in final report"]
  chk7api{"gh api<br/>call failed?"}
  retryApi["Retry gh api once"]
  chk7apiRetry{"Retry<br/>succeeded?"}
  skipLogApi["Skip reply;<br/>list in final report"]
  chk7d{"7d. Tails toggle on<br/>step 0 answer?"}
  dispatchTails["Step 7d: Dispatch deep-reviewer tail pair<br/>2x subagent_type=deep-reviewer<br/>model/effort pinned by agent, no override<br/>parallel (∥), background<br/><br/>Reads deep-reviewer-tail-pair.md<br/>Lens A simplification -&gt; verdict_refactor_*.md<br/>Lens B correctness -&gt; verdict_auto-review_*.md"]:::dispatch
  hookGuard["PreToolUse hook:<br/>deep-reviewer-write-guard.sh<br/><br/>Auto-approves writes to verdict_*.md or /tmp;<br/>denies all other writes/mutations"]:::hook
  triageTails["Read both verdict reports;<br/>synthesize prioritized summary;<br/>offer to apply (report-only by default)"]
  chk7dApply{"User names specific<br/>findings to apply?"}
  dispatchFixer["Dispatch fresh general-purpose subagent<br/>model sonnet, effort inherits<br/>serial per named finding<br/><br/>test-first: confirm RED, apply fix, confirm GREEN"]:::dispatch
  step8["Step 8: Print final summary<br/>applied/answered/dropped/skipped counts"]

  invoke --> createState
  createState --> remindTask0
  remindTask0 --> probe0
  probe0 --> askBatch
  askBatch --> persistAnswers
  persistAnswers --> chk1a
  chk1a -->|"no"| abort1a
  chk1a -->|"yes"| chk1b
  chk1b -->|"dirty"| skillCommit1
  skillCommit1 --> commitStash
  commitStash --> rerun1
  chk1b -->|"clean"| chk1cOptIn
  chk1cOptIn -->|"no / unanswered"| step2
  chk1cOptIn -->|"yes"| runBaseline
  runBaseline --> chk1cGreen
  chk1cGreen -->|"red"| skillDebug1c
  skillDebug1c --> abort1c
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
  loop5 -->|"yes"| skillStandards5
  skillStandards5 --> makeChanges
  makeChanges --> skillCommit5
  skillCommit5 --> commitCluster
  commitCluster --> updateState5
  updateState5 --> chk5drift
  chk5drift -->|"yes"| askDrift
  askDrift -->|"resumes current cluster,<br/>then next"| loop5
  chk5drift -->|"no"| loop5
  loop5 -->|"no - all committed"| step6confirm
  step6confirm --> push
  push --> chk6rejected
  chk6rejected -->|"yes"| abort6
  abort6 -.->|"retry push only,<br/>not step-5 commit logic"| push
  chk6rejected -->|"no"| loop7
  loop7 -->|"yes"| postReply
  postReply --> chk7perm
  chk7perm -->|"yes"| skipLogPerm
  skipLogPerm --> loop7
  chk7perm -->|"no"| chk7api
  chk7api -->|"no"| loop7
  chk7api -->|"yes"| retryApi
  retryApi --> chk7apiRetry
  chk7apiRetry -->|"yes"| loop7
  chk7apiRetry -->|"no"| skipLogApi
  skipLogApi --> loop7
  loop7 -->|"no - all replied"| chk7d
  chk7d -->|"yes"| dispatchTails
  dispatchTails --> hookGuard
  hookGuard --> triageTails
  triageTails --> chk7dApply
  chk7dApply -->|"yes, named findings"| dispatchFixer
  dispatchFixer --> step8
  chk7dApply -->|"no / not asked"| step8
  chk7d -->|"no"| step8

  classDef start fill:#fef3c7,stroke:#d97706,stroke-width:2px
  classDef gate fill:#fee2e2,stroke:#dc2626,stroke-width:2px
  classDef dispatch fill:#dbeafe,stroke:#2563eb,stroke-width:2px
  classDef state fill:#dcfce7,stroke:#16a34a,stroke-width:2px
  classDef skill fill:#f3e8ff,stroke:#9333ea,stroke-width:2px
  classDef hook fill:#e5e7eb,stroke:#4b5563,stroke-width:2px
```
