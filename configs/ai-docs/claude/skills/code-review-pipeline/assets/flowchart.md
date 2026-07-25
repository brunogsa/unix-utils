# code-review-pipeline — flow overview

Human-facing overview for auditing the flow at a glance. Non-authoritative — the numbered steps in [`../SKILL.md`](../SKILL.md) win on any conflict. Regenerate this file whenever the skill's flow changes.

```mermaid
flowchart TD
  start(["Caller invokes /auto-review (local) or /pr-review (github)"]):::start
  dispatchDecision{"Mode local, or --isolate passed?"}
  spawnIsolated["Spawn Agent (sonnet)<br/>runs whole pipeline standalone"]:::dispatch
  runInline["Run inline in fresh main session<br/>(github, no --isolate)"]
  parseHeader["Parse input header<br/>(mode, PR/branch, language)"]

  wave0Guard{"Wave 0: github — PR closed/merged,<br/>or prior review detected?"}
  abortWave0(["Abort: PR closed/merged<br/>or prior review found"])

  wave1["Wave 1: context prep<br/>(clone/diff, commentable-lines)"]
  abortClone(["Abort: clone failed"])

  tinyDecision{"added_lines less than 100?<br/>(tiny_pr)"}
  tinyFastPath["Tiny-PR fast-path:<br/>one pass, 2-sentence summary,<br/>skip guide writer and Wave 3"]

  specialistLoop["Wave 2: run next specialist<br/>(8 total, resume from progress)"]

  guideModeDecision{"Mode local?"}
  guideWriter["Write Review Guide<br/>(github only, max 400 words)"]

  wave3["Wave 3: batched validation<br/>(drop false positives, tighten lines)"]
  wave4["Wave 4: drop off-diff findings"]

  findingsDecision{"Any findings survive Wave 4?"}
  noFindingsModeDecision{"Mode?"}
  noFindingsGithub["Skip pending review"]
  noFindingsLocal["Write verdict file:<br/>'no findings'"]

  wave5ModeDecision{"Mode?"}

  densitySessionDecision{"Running as isolated subagent?"}
  dispatchDensityFixer["Dispatch density-fixer agent<br/>to fix over-cap comment lines"]:::dispatch
  selfFixDensity["Fix density violations inline<br/>(already a subagent)"]

  buildPayloadPost["Build review-payload.json,<br/>POST pending review (single batch call)"]
  post422Decision{"POST returned 422?"}
  retry422["Drop unresolvable anchors,<br/>retry once (same batch shape)"]
  retryFailDecision{"Retry also failed?"}
  abortReport422(["Stop: report 422 body to user"])

  verifyPendingDecision{"Re-fetched state is PENDING<br/>and comments match payload?"}
  abortMismatch(["Stop: report mismatch,<br/>no GitHub cleanup without go-ahead"])

  postGuideComment["Post Review Guide as<br/>standalone PR comment"]

  localHtmlDecision{"html-artifacts routing:<br/>.md or .html?"}
  writeVerdictFile["Write verdict_auto-review_TIMESTAMP<br/>file to CWD"]
  localDensityFix["Fix density violations<br/>(local always isolated)"]

  wave6["Wave 6: print terminal summary"]

  start --> dispatchDecision
  dispatchDecision -->|"local, or --isolate"| spawnIsolated
  dispatchDecision -->|"github, no --isolate"| runInline
  spawnIsolated --> parseHeader
  runInline --> parseHeader
  parseHeader --> wave0Guard

  wave0Guard -->|"yes"| abortWave0
  wave0Guard -->|"no / local always proceeds"| wave1

  wave1 -->|"clone fails"| abortClone
  wave1 -->|"context on disk"| tinyDecision

  tinyDecision -->|"yes"| tinyFastPath
  tinyDecision -->|"no"| specialistLoop

  specialistLoop -->|"next specialist"| specialistLoop
  specialistLoop -->|"all 8 done"| guideModeDecision

  tinyFastPath --> wave4

  guideModeDecision -->|"yes, skip guide"| wave3
  guideModeDecision -->|"no, github"| guideWriter
  guideWriter --> wave3

  wave3 --> wave4
  wave4 --> findingsDecision

  findingsDecision -->|"none"| noFindingsModeDecision
  findingsDecision -->|"some"| wave5ModeDecision

  noFindingsModeDecision -->|"github"| noFindingsGithub
  noFindingsModeDecision -->|"local"| noFindingsLocal
  noFindingsGithub --> postGuideComment
  noFindingsLocal --> wave6

  wave5ModeDecision -->|"github"| densitySessionDecision
  wave5ModeDecision -->|"local"| localHtmlDecision

  densitySessionDecision -->|"no, calling session"| dispatchDensityFixer
  densitySessionDecision -->|"yes, isolated"| selfFixDensity
  dispatchDensityFixer --> buildPayloadPost
  selfFixDensity --> buildPayloadPost

  buildPayloadPost --> post422Decision
  post422Decision -->|"no"| verifyPendingDecision
  post422Decision -->|"yes"| retry422
  retry422 --> retryFailDecision
  retryFailDecision -->|"yes"| abortReport422
  retryFailDecision -->|"no"| verifyPendingDecision

  verifyPendingDecision -->|"yes"| postGuideComment
  verifyPendingDecision -->|"no"| abortMismatch

  postGuideComment --> wave6

  localHtmlDecision --> writeVerdictFile
  writeVerdictFile --> localDensityFix
  localDensityFix --> wave6

  classDef dispatch fill:#e0e7ff,stroke:#4338ca,stroke-width:2px
  classDef start fill:#fef3c7,stroke:#d97706,stroke-width:2px
```
