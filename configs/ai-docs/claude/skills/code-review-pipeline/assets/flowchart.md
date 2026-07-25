# code-review-pipeline — flow overview

Human-facing overview for auditing the flow at a glance. Non-authoritative — the numbered steps in [`../SKILL.md`](../SKILL.md) win on any conflict. Regenerate this file whenever the skill's flow changes.

```mermaid
flowchart TD
  start(["Invoke /auto-review (local) or /pr-review (github)<br/>flag: --isolate forces isolated path"]):::start
  dispatchDecision{"Mode local, or --isolate passed?"}
  spawnIsolated["Dispatch Agent<br/>model: sonnet, effort: inherits<br/>serial -- one instance runs whole pipeline"]:::dispatch
  runInline["Run inline in fresh main session<br/>(github, no --isolate)"]
  parseHeader["Parse input header<br/>(mode, PR/branch, language)"]
  loadWave0Refs["Load review-principles.md<br/>+ review-checklists.md<br/>(grounds every wave)"]:::skill

  wave0Guard{"Wave 0: github -- PR closed/merged,<br/>or prior review detected?"}
  abortWave0(["Abort: PR closed/merged<br/>or prior review found"])

  wave1["Wave 1: context prep<br/>create $work_dir, clone/diff,<br/>commentable-lines, skipped-files"]
  wave1Scripts["extract-commentable-lines.sh<br/>extract-skipped-files.sh"]:::hook
  wave1Jira["jira-cli skill: fetch-jira-review-context.sh<br/>(github + Jira URL given, optional)"]:::skill
  wave1RepoWide["Repo-wide static checks<br/>lint/typecheck/dead-code/circular,<br/>tests, coverage (local mode only)"]:::hook
  abortClone(["Abort: clone failed"])
  wave1State["Persist to $work_dir:<br/>diff, changed-files, commit-messages,<br/>commentable-lines, skipped-files"]:::state

  tinyDecision{"added_lines less than 100?<br/>(tiny_pr)"}
  tinyFastPath["Tiny-PR fast-path:<br/>one pass, 2-sentence summary,<br/>skip guide writer and Wave 3"]

  loadWave2Standards["Load code-standards, test-standards,<br/>doc-standards SKILL.md<br/>+ repo CLAUDE.md"]:::skill
  wave2ResumeDecision{"$work_dir/wave2-progress.txt<br/>exists?"}
  specialistLoop["Wave 2: run next specialist<br/>(8 total: correctness, corner-cases,<br/>testing, security, design, ai-slop,<br/>docs, performance)<br/><br/>60-80% confidence emitted as QUESTION tag;<br/>persist wave2-findings.json + progress.txt<br/>before each next specialist"]

  guideModeDecision{"Mode local?"}
  guideResumeDecision{"$work_dir/wave2-guide.md<br/>exists? (github only)"}
  guideWriter["Write Review Guide<br/>(github only, max 400 words)<br/>persist wave2-guide.md"]

  wave3ResumeDecision{"$work_dir/wave3-findings.json<br/>exists?"}
  wave3["Wave 3: batched validation<br/>(drop false positives, tighten lines)<br/>threshold LOW -- keep when in doubt<br/>persist wave3-findings.json + drop-log.txt"]

  wave4ResumeDecision{"$work_dir/wave4-findings.json<br/>exists?"}
  wave4["Wave 4: drop off-diff findings<br/>(anchor outside commentable-lines.txt)<br/>persist wave4-findings.json"]

  findingsDecision{"Any findings survive Wave 4?"}
  noFindingsModeDecision{"Mode?"}
  noFindingsGithub["Skip pending review"]
  noFindingsLocal["Write verdict file:<br/>'no findings'"]:::state

  wave5ModeDecision{"Mode?"}

  checkDensityGithub["check-density.sh on<br/>wave5-comment-*.md + wave2-guide.md<br/>(cap: 256 chars / 32 words per line)"]:::hook
  dispatchDensityFixer["Dispatch density-fixer agent<br/>model: haiku, serial<br/>splits over-cap lines, loops<br/>internally until exit 0"]:::dispatch
  selfFixDensity["Fix density violations inline<br/>(already a subagent, no re-spawn)<br/>loop until exit 0"]

  buildPayloadPost["Build review-payload.json,<br/>POST pending review (single batch call)"]:::state
  post422Decision{"POST returned 422?"}
  retry422["Drop unresolvable anchors,<br/>retry once (same batch shape)"]
  retryFailDecision{"Retry also failed?"}
  abortReport422(["Stop: report 422 body to user"]):::gate

  verifyPendingDecision{"Re-fetched state is PENDING<br/>and comments match payload?"}
  abortMismatch(["Stop: report mismatch,<br/>no GitHub cleanup without go-ahead"]):::gate

  postGuideComment["Post Review Guide as<br/>standalone PR comment<br/>(guide-payload.json)"]:::state

  loadHtmlArtifacts["Consult html-artifacts skill<br/>routing table (.md vs .html)<br/>fixed verdict = standing approval"]:::skill
  localHtmlDecision{"Router verdict: .md or .html?"}
  writeVerdictFile["Write verdict_auto-review_TIMESTAMP<br/>file to CWD"]:::state
  checkDensityLocal["check-density.sh on out_file<br/>(.md output only)"]:::hook
  localDensityFix["Fix density violations inline<br/>(local mode is always isolated)<br/>loop until exit 0"]

  wave6["Wave 6: print terminal summary"]
  humanGate(["Pending review (github) or verdict file (local)<br/>awaits human read/submit -- nothing auto-submits"]):::gate

  start --> dispatchDecision
  dispatchDecision -->|"local, or --isolate"| spawnIsolated
  dispatchDecision -->|"github, no --isolate"| runInline
  spawnIsolated --> parseHeader
  runInline --> parseHeader
  parseHeader --> loadWave0Refs
  loadWave0Refs --> wave0Guard

  wave0Guard -->|"yes"| abortWave0
  wave0Guard -->|"no / local always proceeds"| wave1

  wave1 --> wave1Scripts
  wave1 -.->|"github + Jira URL given"| wave1Jira
  wave1 -.->|"local mode only"| wave1RepoWide
  wave1 -->|"clone fails (github)"| abortClone
  wave1Scripts --> wave1State
  wave1Jira --> wave1State
  wave1RepoWide --> wave1State
  wave1State --> tinyDecision

  tinyDecision -->|"yes"| tinyFastPath
  tinyDecision -->|"no"| loadWave2Standards
  loadWave2Standards --> wave2ResumeDecision
  wave2ResumeDecision -->|"yes -- resume after last<br/>completed specialist"| specialistLoop
  wave2ResumeDecision -->|"no -- start at correctness"| specialistLoop

  specialistLoop -->|"next specialist"| specialistLoop
  specialistLoop -->|"all 8 done"| guideModeDecision

  tinyFastPath --> wave4

  guideModeDecision -->|"yes, skip guide"| wave3ResumeDecision
  guideModeDecision -->|"no, github"| guideResumeDecision
  guideResumeDecision -->|"yes -- load persisted guide"| wave3ResumeDecision
  guideResumeDecision -->|"no"| guideWriter
  guideWriter --> wave3ResumeDecision

  wave3ResumeDecision -->|"yes -- skip Wave 3"| wave4ResumeDecision
  wave3ResumeDecision -->|"no"| wave3
  wave3 --> wave4ResumeDecision

  wave4ResumeDecision -->|"yes -- skip Wave 4"| findingsDecision
  wave4ResumeDecision -->|"no"| wave4
  wave4 --> findingsDecision

  findingsDecision -->|"none"| noFindingsModeDecision
  findingsDecision -->|"some"| wave5ModeDecision

  noFindingsModeDecision -->|"github"| noFindingsGithub
  noFindingsModeDecision -->|"local"| noFindingsLocal
  noFindingsGithub --> postGuideComment
  noFindingsLocal --> wave6

  wave5ModeDecision -->|"github"| checkDensityGithub
  wave5ModeDecision -->|"local"| loadHtmlArtifacts

  checkDensityGithub -->|"violations found"| densityFixRoute{"Session is<br/>calling (not isolated)?"}
  checkDensityGithub -->|"clean"| buildPayloadPost
  densityFixRoute -->|"yes"| dispatchDensityFixer
  densityFixRoute -->|"no, already isolated"| selfFixDensity
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

  loadHtmlArtifacts --> localHtmlDecision
  localHtmlDecision --> writeVerdictFile
  writeVerdictFile --> checkDensityLocal
  checkDensityLocal -->|"violations found"| localDensityFix
  checkDensityLocal -->|"clean"| wave6
  localDensityFix --> wave6

  wave6 --> humanGate

  classDef start fill:#fef3c7,stroke:#d97706,stroke-width:2px
  classDef gate fill:#fee2e2,stroke:#dc2626,stroke-width:2px
  classDef dispatch fill:#dbeafe,stroke:#2563eb,stroke-width:2px
  classDef state fill:#dcfce7,stroke:#16a34a,stroke-width:2px
  classDef skill fill:#f3e8ff,stroke:#9333ea,stroke-width:2px
  classDef hook fill:#e5e7eb,stroke:#4b5563,stroke-width:2px
```
