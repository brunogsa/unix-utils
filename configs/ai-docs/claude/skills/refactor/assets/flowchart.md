# refactor — flow overview

Human-facing overview for auditing the flow at a glance. Non-authoritative — the numbered steps in [`../SKILL.md`](../SKILL.md) win on any conflict. Regenerate this file whenever the skill's flow changes.

Two renderings of the same flow, kept cross-checkable on purpose. The `# N` comments in the pseudo-code are the diagram's node ids, so an id with no matching comment is drift.

## Pseudo-code

Python-shaped for readability only; nothing here runs, and the function names stand for steps this skill performs, not real APIs.

```python
# 1 · Entry: /refactor, /refactor <path-or-glob>, or another
#     skill's dispatch (/implement's batch-end tail reaches
#     this lens through /quality-gate).
def refactor(arg):
    if arg.path_or_glob:                                   # 2
        path_args = [arg.path_or_glob]                     # 2a
    else:
        path_args = []                                     # 2b · covers the whole repo

    # 3 · Step 1 — mint a work dir, then hand everything to the
    #     script: base resolution (@{upstream}, falling back to
    #     resolve-base-ref.sh), the merge-base diff, and the
    #     untracked scan. Nothing here runs git directly anymore.
    work_dir = mktemp_dir("/tmp/refactor.XXXXXX")
    result = sh("prep-refactor-context.sh", work_dir, *path_args)

    if result.exit_code != 0:                              # 4
        # 4a · Collapsed: the script's own exit-1 reasons (not a
        #      git repo, no resolvable base ref, empty scope) are
        #      its business, not a branch this skill's flow makes —
        #      all three read here as one "nothing to refactor".
        return inform_user_and_stop()

    # 5 · Step 2 — mint the report path BEFORE dispatching. CWD, never
    #     /tmp: the user reads it beside the diff in their editor. The
    #     verdict_ prefix is mandatory — the write guard denies every
    #     other basename at exit 2 — and it beats report_/findings_
    #     because the harness intercepts those before any hook runs.
    #     One file per invocation; never reuse a prior run's path.
    VERDICT_PATH = sh('date "+verdict_refactor_%Y-%m-%d_%H:%M.md"')

    # ---- 6 · Step 2 — dispatch the reviewer. Report-only by
    #      construction: subAgent=refactor would silently turn this
    #      into an editing leg, so it is never the one dispatched.
    #      Reads step 3's four artifacts from disk instead of
    #      re-running git commands — ~12.5x cheaper than admitting a
    #      fresh tool result into context. ----
    agent = dispatch("deep-reviewer", background=True,      # 6
                     work_dir=work_dir,
                     context_files=["diff", "changed-files.txt",
                                     "untracked-files.txt",
                                     "commit-messages.txt"],
                     # 6 · the prompt also carries the analysis
                     #     constraints and the per-finding schema
                     #     verbatim, plus write-only-to-VERDICT_PATH.
                     verdict_path=VERDICT_PATH)
    # 6a · hook: deep-reviewer-write-guard backs that contract at the
    #      tool layer, so stating it only saves a blocked-write attempt.

    while not present_and_non_empty(VERDICT_PATH):         # 7
        # 7a · The run failed. Re-invoke rather than proceeding from
        #      the return message, which is capped and WILL truncate
        #      a long finding list.
        agent = redispatch(agent)

    # 8 · Step 3 — read the file end-to-end. The return carries only a
    #     count, the path, and one title line per finding, by design.
    findings = read_in_full(VERDICT_PATH)

    # 9 · Step 3 — one line per finding: <file>:<lines> — <title>
    #     [classification, risk, effort]. No Before/After inline; the
    #     user already has the full file open.
    print(compact_index(findings))

    # 10 · Step 3 — name the report path and invite the user to open it.
    print(f"Full report: {VERDICT_PATH}")

    # 11 · STOP. This skill never applies a finding and never seeds
    #      apply-tasks. /address-verdicts globs verdict_refactor_*.md
    #      and routes each one to the refactor AGENT, which applies it
    #      under a test gate — the artifact written above is exactly
    #      what that skill consumes.
    return
```

## Flowchart

```mermaid
flowchart TD
  n1(["1. /refactor, or /refactor &lt;path-or-glob&gt;<br/><br/>or another skill's dispatch — /implement's<br/>batch-end tail arrives via /quality-gate"]):::start
  n2{"2. Was a path or glob passed?"}
  n2a["2a. Pass it as prep-refactor-context.sh's<br/>trailing path argument"]
  n2b["2b. Call prep-refactor-context.sh with no<br/>path arguments — covers the whole repo"]
  n3["3. Step 1 · Mint work_dir = mktemp -d<br/>/tmp/refactor.XXXXXX, then run<br/>prep-refactor-context.sh work_dir [path...].<br/>Resolves base via @{upstream}, falling back to<br/>resolve-base-ref.sh — all a fresh /implement branch<br/>has, its tail running before the first push.<br/>Diffs -U20 from the merge-base to the working tree;<br/>writes diff, changed-files.txt, untracked-files.txt,<br/>commit-messages.txt into work_dir"]:::state
  n4{"4. Script exited 0 (found target files)?"}
  n4a["4a. Inform the user and stop — script exited 1:<br/>not a git repo, no resolvable base ref, or nothing<br/>changed/untracked in the given scope (reason on<br/>stderr). Collapsed: the script's own reason, not a<br/>branch this skill's flow makes"]:::gate
  n5["5. Step 2 · Mint VERDICT_PATH =<br/>date +verdict_refactor_&lt;ts&gt;.md, in CWD not /tmp<br/>— the user reads it beside the diff in their editor.<br/>The verdict_ prefix is mandatory: the write guard<br/>denies every other basename at exit 2, and it beats<br/>report_/findings_ because the harness intercepts<br/>those before any hook runs. One file per invocation"]:::state
  n6["6. Step 2 · Dispatch deep-reviewer<br/>(agent-pinned, background) — report-only by<br/>construction; subAgent=refactor would silently<br/>make this an editing leg.<br/>Hands it work_dir plus the four files step 3 wrote<br/>(diff, changed-files.txt, untracked-files.txt,<br/>commit-messages.txt), told to read them from disk,<br/>not re-run git commands — ~12.5x cheaper than<br/>admitting a fresh tool result into context.<br/>Prompt also carries the analysis constraints and<br/>per-finding schema verbatim, plus<br/>write-only-to-VERDICT_PATH"]:::dispatch
  n6a["6a. Hook: deep-reviewer-write-guard<br/>— backs the report-only contract at the tool layer"]:::hook
  n7{"7. VERDICT_PATH present and non-empty?"}
  n7a["7a. Treat the run as failed and re-invoke.<br/>Never proceed from the return message —<br/>it is capped and WILL truncate a long list"]:::dispatch
  n8["8. Step 3 · Read VERDICT_PATH end-to-end.<br/>The return carries only a count, the path, and<br/>one title line per finding, by design"]
  n9["9. Step 3 · Print the compact index — one line per<br/>finding: &lt;file&gt;:&lt;lines&gt; — &lt;title&gt;<br/>[classification, risk, effort].<br/>No Before/After; the user has the file open"]
  n10["10. Step 3 · Name the report path and invite<br/>the user to open it (tail -f or editor)"]
  n11(["11. STOP — report only. No finding is applied and<br/>no apply-task is seeded. /address-verdicts globs<br/>verdict_refactor_*.md and routes each finding to<br/>the refactor AGENT, which applies it under a<br/>test gate; this file is what that skill consumes"])

  n1 --> n2
  n2 -->|"yes"| n2a --> n3
  n2 -->|"no"| n2b --> n3
  n3 --> n4
  n4 -->|"no"| n4a
  n4 -->|"yes"| n5
  n5 --> n6
  n6 -.->|"guards"| n6a
  n6 --> n7
  n7 -->|"no"| n7a --> n6
  n7 -->|"yes"| n8 --> n9 --> n10 --> n11

  classDef start fill:#fef3c7,stroke:#d97706,stroke-width:2px
  classDef gate fill:#fee2e2,stroke:#dc2626,stroke-width:2px
  classDef dispatch fill:#dbeafe,stroke:#2563eb,stroke-width:2px
  classDef state fill:#dcfce7,stroke:#16a34a,stroke-width:2px
  classDef skill fill:#f3e8ff,stroke:#9333ea,stroke-width:2px
  classDef hook fill:#e5e7eb,stroke:#4b5563,stroke-width:2px
```
