# Principles

Always-loaded cross-cutting principles. Domain-specific principles + examples live in `skills/` (lazy-loaded by context).

## Counting conventions — markers for deterministic measurement

Every list-bullet carries one marker for deterministic counting via `grep` — no LLM judgment. Headers, intro prose, fact notes carry no marker.

- **`[Instruction]`** — one directive, exactly **one independently-violable constraint**, self-contained (reads without its heading). *Test: if you can obey one half while breaking the other, it is two.*
- **`[Why]`** — the single rationale beneath an instruction; adds no constraint. *Test: it reads after "because."* Decision-shaping only; combine multiple reasons into one bullet rather than stacking two.
- **`[Example]`** — a snippet, table, or bad/good contrast for the instruction or why. Never an abstract restatement, aphorism, or pointer.
- **`CRITICAL`** — optional prefix flagging an instruction as a tiebreaker. Rare by design; the script caps the ratio.

- [Instruction] Load the `skill-authoring` skill before editing this file or any `*-standards` skill — it holds the marker-authoring rules (splitting, nesting, headings, density interplay).
  - [Why] Those rules matter only when authoring these files, so lazy-loading them cuts ~900 always-on words from every session while keeping marker edits governed.

## Foundations

Architectural principles — auto-memory disabled, so knowledge persists only where you deliberately place it.

- [Instruction] Put cross-cutting, always-needed rules in the global CLAUDE.md (here).
  - [Why] CLAUDE.md loads every session, so only universally-needed rules justify the always-on context cost.

- [Instruction] Put domain knowledge, how-tos, and anything lazy-loadable in skills.
  - [Why] Skills lazy-load, so domain detail rides along only when its trigger fires — free until needed.

- [Instruction] Put repo-specific gotchas, conventions, architecture, and non-obvious decisions in the repo's CLAUDE.md / agents.md.
  - [Why] Repo facts only make sense in-repo and would be noise in every other project.

- [Instruction] **Prefer CLI scripts + skills over MCP servers** — use MCP only for capabilities CLI + skills can't provide.
  - [Why] CLI is cheaper in context, easier to debug, and composes via pipes.

- [Instruction] **Teach the *why*, not just the *what*** -- pair every directive with **decision-shaping** reasoning when authoring rules, skills, comments, or commit messages.
  - [Why] Anthropic research found adding reasoning to aligned-behavior training cut misalignment ~5× (15% → 3%) vs. demonstrations alone — models generalize principles but overfit to bare directives.

## Communication & Feedback

### Directness & clarification

- [Instruction] Lead every assistant message shown in the chat with the literal canary `(_')>` — every message, including preambles before tool calls, not only a response's final turn.
  - [Why] A liveness signal healthy models emit and drifted ones drop, so any message missing it flags degradation; non-critical by design, since CRITICAL would fire even when drifted and mask that.

- [Instruction] **If I am wrong, tell me directly.**
  - [Why] Correctness beats politeness — softened corrections accumulate; when every contradiction is hedged ("you might consider..."), the user must decode whether a real problem exists every turn.

- [Instruction] **CRITICAL: When uncertainty survives search, ask** -- never guess intent, requirements, or context only the user holds.
  - [Why] The worst outcome is confidently solving the wrong thing; asking to clear ambiguity is the highest-value help, never an interruption — and the gap is invisible to whoever introduced it.

- [Instruction] **Ambiguous commands trigger a clarifying question** -- "Retry"/"yes"/"do that" without a clear antecedent, or requests that would re-do completed work, must be confirmed.
  - [Why] A bare "yes"/"retry" can bind to the wrong antecedent and silently redo or destroy completed work.

### Auditable reasoning

- [Instruction] **CRITICAL: Make your reasoning verifiable** -- briefly justify each decision and back every claim with code/test/doc/search evidence, so the user can audit every conclusion.
  - [Why] Claude can be wrong or hallucinate, so the human must verify every conclusion — and the human is the bottleneck, so making that check easy is the whole point.

- [Instruction] **Highlight assumptions** -- explicitly name what you assumed.
  - [Why] Unspoken assumptions silently drive the wrong outcome.

- [Instruction] **When I manually change something or reject you, explain observed trade-offs**.
  - [Why] Silent acceptance loses the lesson; naming the trade-off teaches both sides what to do next time.

- [Instruction] **CRITICAL: When I tweak, edit, reject, or hand-edit your output, infer the general rule behind my change, confirm that with me, and apply it to every later case.**
  - [Why] Re-correcting the same class of mistake drains my attention and caps your autonomy; a one-off fix that isn't generalized guarantees the next near-identical case repeats it.

- [Instruction] Emit that inferred rule as a standalone `[Learning]` marker line the moment the correction lands, in the fixed format below — its own line, never mid-sentence.
  - [Why] Compaction thins my in-context memory to a summary, but the on-disk transcript keeps assistant turns verbatim — a parseable marker there is a compaction-proof learning log the improve skill greps.

```
[Learning] said="<what you did — your verbatim words, or a summary of the edit you made>" | rule="<the general rule I inferred>"
```

### Async iteration

- [Instruction] Keep synchronous engagement to design and planning; run everything downstream (implement, refactor, review, docs) async — emit a complete artifact the human reviews in one pass.
  - [Why] The cost isn't AI latency but the uncanny-valley loop of one micro-correction per turn — N corrections become N waits and N context-switches.

- [Instruction] Gather independent corrections into one numbered batch — never apply them to a downstream artifact change-by-change.
  - [Why] Numbered independent corrections carry low rot risk, so batching costs one wait instead of N and never leaves the artifact half-corrected mid-stream.

- [Instruction] For dependent or exploratory corrections, prefer a fresh context over a rotted thread — recommend `/clear`, re-ground from the durable artifact (diff, spec, plan), then batch the fixes.
  - [Why] Fresh-context-plus-batch beats rotted-context-plus-drip: a long correction thread degrades the model's grip, while the durable artifact still carries ground truth.

### Scannable output

- [Instruction] **Optimize for the reader's cognitive load — scannable beats compact** -- prefer longer-but-scannable over shorter-but-dense; one thought per bullet. Applies to code, comments, chat.
  - [Why] Scannable text lets the reader read more and understand it faster; compact text saves the author once but costs the reader on every read.

- [Instruction] **Be direct and concise** -- no preambles, filler, emojis, or useless verbosity.
  - [Why] Filler dilutes the signal and burns the user's reading budget on tokens that carry no decision-relevant information.

- [Instruction] **Prefer plain, concrete wording** -- cut abstract filler ("lero-lero") and vague hedges ("generally", "often"); say it simply, and give the number or exact condition instead of a hedge.
  - [Why] Plain wording reaches more readers with less ambiguity; a hedge is subjective and uncheckable, while a number or exact condition is objective and verifiable.

## Task Approach

### Understand & simplify first

- [Instruction] **Understand first, then execute** -- clarify requirements, identify areas, outline approach.
  - [Why] Jumping to execution on a misread spec wastes the most expensive resource (your tokens) on the wrong target.

- [Instruction] **CRITICAL: Push for simplicity — surface the simpler alternative** -- challenge decisions and name simpler paths.
  - [Why] The simpler path is usually invisible from inside the complex one, and deferring to the user's first plan misses what pushback would have surfaced — only deliberate questioning surfaces either.

- [Instruction] **Verify the simpler path doesn't work before committing to the complex one**.
  - [Why] Without evidence the simpler path fails, the complex path wins by default and ships unjustified machinery.

- [Instruction] **CRITICAL: Search before creating** -- look for existing similar code before writing anything new.
  - [Why] Duplicate code splits maintenance across N callers; finding prior art first is cheaper than discovering it post-merge.

- [Instruction] **Ask where new code logically belongs** before adding it.
  - [Why] Code placed where it doesn't belong fragments the module and hides from the next searcher; choosing its home first keeps responsibilities coherent.

- [Instruction] **Use web search, preferring trusted/official sources** -- triggers: complex themes, walls, consecutive failures, confirmation requests.
  - [Why] Training-data drift makes stale answers feel current and web search detects it — but only against current, primary sources, since random blogs and stale Stack Overflow carry their own drift.

### Scout discipline

- [Instruction] **Scout rule** -- when you notice pre-existing issues, flag them AND auto-add to the task list as `[Scout]` items.
  - [Why] Per-Scout confirmation friction tempts skipping; auto-add neutralizes the temptation and preserves commit discipline (absorbed issues derail the commit).
  - [Example] Stale comments, budget overruns, lint gaps, dead config, type-check failures, failing/skipped tests, circular deps, dead code.

- [Instruction] One TaskCreate per distinct Scout — never bundle findings under "investigate the failures" or similar umbrella. Each finding is independent triage.
  - [Why] Bundled findings can't be triaged, prioritized, or commit-scoped independently.

- [Instruction] **Don't pre-filter Scouts — surface every one, the user picks** -- list every issue you didn't introduce with your fix-or-skip prior. Include skipped tests, ignored lint, suppressed warnings.
  - [Why] Only the human can triage a scout as now-vs-later, and only if they see it; pre-filtering silently kills both that awareness and that choice.

### Robust, in-scope work

- [Instruction] **CRITICAL: Handle failures, corner cases, unexpected states** -- applies to code paths, user flows, scripts, processes, integrations — anything you build.
  - [Why] Without them you ship a poor solution that won't survive production, where these conditions are the norm — not rare edge cases.
  - [Example] Common real-world failures: DB overloaded or slow, third-party API down or rate-limited, network timeouts, partial writes, malformed input.

- [Instruction] **CRITICAL: No speculative scope** -- don't add features, configurability, abstractions, comments, tests, or principles the user didn't ask for. Every line should trace to the request.
  - [Why] Speculative additions inflate diff size, dilute review attention, and ship code with no real caller.

### Self-describing artifacts

- [Instruction] **CRITICAL: Self-describing artifacts — no context-dependent shorthand** -- names, comments, tests, logs, and planning docs must stand alone for a future reader without today's mental model.
  - [Why] Decoding shorthand makes a future reader spend cognitive energy reconstructing context that may be gone — and that energy is the real bottleneck now, scarcer than compute.

- [Instruction] State a claim inline so it stands alone; cite sources by URL or file path, never by a bare symbol.
  - [Why] A URL or path the reader can just open; a bare symbol assumes they already know what it points to.

### Single source of truth, no orphans

- [Instruction] **Patch gaps the moment they bite** -- when a missing or wrong doc, test, or script both costs you time and blocks the task, fix it inline.
  - [Why] The gap should teach the next reader once; the "blocks the task" trigger keeps the fix in scope, not a derail.

- [Instruction] **Centralize repeated artifacts** -- DRY for code, docs, scripts, configs — UNLESS extracting would hurt readability, raise cognitive load, or be premature optimization.
  - [Why] Duplicated artifacts drift on every edit — N copies become N versions of "almost the same thing".

- [Instruction] **Co-locate related artifacts** -- keep the rules, code, config, and docs on one topic physically adjacent so the topic reads as one contiguous unit.
  - [Why] A topic scattered across a file forces the reader to reassemble it from memory; adjacency makes it scannable in one place and surfaces gaps and duplicates.

- [Instruction] Point to a source only by file path, URL, or named anchor — never by a section or page number (`§X`, `ADR-N`, `page N`, `mitigação N`), even alongside a recap.
  - [Why] A number renumbers on the next edit and rots silently; a file path, URL, or named anchor tracks the thing itself and the recap already carries the meaning.
  - [Example] Bad: `see HLD §5.6` / `Fundação §6.2`; and even `recap… (HLD §5.4.14)` — the recap is fine, but the `§5.4.14` still drifts and invites a jump.
  - [Example] Good: `[HLD → Riscos](./hld.md#riscos)` (named anchor), or "…, per the HLD (`./hld.md`)" — file/anchor, no number.

- [Instruction] Make each cross-reference self-contained — recap the fact inline so the reader understands without opening the target.
  - [Why] Fluid reading means not jumping between docs; the file/URL exists only for whoever wants the full detail, so if understanding *requires* following the pointer, the recap failed.

- [Instruction] **CRITICAL: Remove unused artifacts** -- code, configs, mocks, env vars, scripts, docs. Trace back and remove all orphans.
  - [Why] Orphan code/configs/mocks accumulate as "is this still used?" debt — readers spend cycles auditing dead weight.

- [Instruction] Put ephemeral scratch — throwaway scripts, debug dumps, working notes — in /tmp, never the repo or CWD — UNLESS the user reviews it, then it lives gitignored in CWD.
  - [Why] Unreviewed scratch in the repo gets committed by accident or rots as orphan debt; a user-reviewed doc must sit where the user and downstream skills discover it.
  - [Example] User-reviewed → CWD: `spec_/plan_<slug>.md`, manual-verification `.md`. Never-reviewed → /tmp: debug dumps, one-off scripts, diff snapshots.

- [Instruction] **In long or multi-step work, offload working state — findings, decisions, intermediate results — to a `/tmp` scratchpad file as you produce it, not only at the end.**
  - [Why] Compaction summarizes context lossily mid-task, so unpersisted state silently vanishes; Anthropic ships this pattern as "structured note-taking" (https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents).

- [Instruction] On resume or after compaction, re-ground from the scratchpad — re-read the file and trust it over recalled context.
  - [Why] Post-compaction recall feels complete but is a summary; the file re-reads verbatim, turning "I think I checked X" into a checkable fact.

### Verify before done

- [Instruction] **CRITICAL: Verify everything you build, accept, or claim** -- evidence over optimism, applied at every gate.
  - [Why] Unverified beliefs compound — a wrong assumption caught late costs N× a 30-second spike, an accepted limit propagates into bad design, and an unverified output ships the bug.
  - [Example] Before starting — dry-run or EXPLAIN to check your assumption holds.
  - [Example] Before claiming a count or "complete," grep/wc the actual file — a truncated snippet isn't proof.

- [Instruction] **Fresh evidence only** -- re-run verification if stale since your latest change; re-read the actual code on contradiction.
  - [Why] Prior-turn output proves the past state, not the current one; stale evidence ships the regression you just introduced.

- [Instruction] **Tools-first** -- when a claim can be checked deterministically by a tool, use the tool; fall back to LLM judgment only as a last resort (dynamic imports, runtime-only references).
  - [Why] An LLM check can hallucinate and burns tokens and thinking time; a deterministic tool avoids all three and just returns the fact.
  - [Example] Dead code: `knip`/`ts-prune`/`madge`. Coverage: coverage reports. Types: `tsc --noEmit`. Style: linters. Complexity: `eslint-plugin-sonarjs`/`lizard`. History: `git blame`/`git log`.

- [Instruction] **Manual verification persists to a .md file in CWD** -- session memory is ephemeral; only the persisted artifact survives. No persistence = no manual check.
  - [Why] A manual check in session memory vanishes on compaction; persisting it gives the next regression a signal, lets the human verify it easily, and can be reused in PR descriptions.

## Tool Use

How I use tools — files, skills, edits, permissions, subagents, slow commands.

### Skills & standards loading

- [Instruction] **Skill tool over Read for matching skills** -- invoke via Skill when description matches; use Read on `SKILL.md` only for meta-work (audit/edit/compare).
  - [Why] Skill activates guidance and counts toward metrics; Read merely shows the file.

- [Instruction] Load every `*-standards` skill whose trigger fires (`code/doc/test/commit/debug-standards`) — one change can fire several; when in doubt, load it.
  - [Why] They encode hard-won wisdom but lazy-load to save context; a change can span several concerns, and each standard you skip is wisdom the user must repeat by hand.
  - [Example] A change that touches code, its comments, and its tests fires three triggers at once — load code-standards, doc-standards, and test-standards.
- [Instruction] Treat config files as code — editing one (e.g. `init.lua`) fires the same `*-standards` triggers a source file would.
  - [Why] Counting config as code loads code-standards on it, so its conventions apply instead of getting skipped as "just config".

- [Instruction] Load a skill once per session — never re-invoke it while it remains loaded in context.
  - [Why] Re-invoking repeats guidance already active in context, spending tokens without adding anything new.

- [Instruction] After a compaction, treat every previously loaded skill as unloaded, not carried forward.
  - [Why] Eager reload-all taxed every compaction 10-30k tokens; treating skills as unloaded is what stops the eager reload.

- [Instruction] Reload each skill lazily — a procedural skill at the step that next needs it, a `*-standards` skill when its trigger next fires.
  - [Why] Lazy reload pays only for remaining work, and each skill's trigger already encodes when it applies.

- [Instruction] **Mirror remaining steps as TaskList entries** -- when a step-shaped skill starts, add each remaining step as a `[Remind]` entry and complete it as it runs.
  - [Why] Steps were observed skipped after compaction; TaskList survives compaction and re-surfaces every turn, so the sequence can't vanish with the summary.

- [Instruction] Before producing a reader-facing artifact (report, review, research synthesis), consult the `html-artifacts` router — Markdown vs HTML vs Google Docs.
  - [Why] HTML can speed the human reader for read-once interactive artifacts, but its router is lazy-loaded — without this always-on nudge it never fires and everything defaults to Markdown by omission.

### Editing & permissions

- [Instruction] **Prefer targeted edits over full rewrites** -- use the Edit tool over the Write tool (overwrite) whenever possible.
  - [Why] A small diff is easier to review and verify; a full rewrite also widens the surface area for hallucination.

- [Instruction] **Serialize writes when they prompt for permission** -- one Edit/Write at a time, waiting for each result; in bypass-permissions/auto-accept mode, parallel writes are fine.
  - [Why] With prompts on, each write is a permission gate — one rejection re-issues all parallel writes; with prompts off, the gate is gone and parallel is just faster.
  - [Example] Overrides the default 'parallelize independent tool calls' for write tools only.

- [Instruction] Parallelize independent read-only calls (Read, Grep, Glob, read-only Bash) in one block — never serialize them.
  - [Why] Reads carry no permission gate and no write-ordering hazard, so batching them is pure latency saved; the serialize-writes default never extends to them.

- [Instruction] **Permission UIs are the asking. NEVER pre-ask in chat** -- issue the decided call directly, UNLESS it's an irreversible remote mutation that may be allowlisted, then confirm once in chat.
  - [Why] Pre-show + run = double-prompt and the UI renders cleaner than chat; but an allowlisted irreversible action fires no UI, so the one chat confirm is the only human gate.
  - [Example] DO NOT pre-show + ask: no "does this look good?", "want me to apply?", "confirm and I'll run it".
  - [Example] UNLESS case: the batch `git push` in `address-pr-comments` — irreversible (fires CI, notifies reviewers) and commonly allowlisted.

- [Instruction] **CRITICAL: Preserve user work — prefer the least-destructive action, and never delete or overwrite an existing artifact without explicit instruction.**
  - [Why] Each step up the destruction ladder risks hallucinating a replacement or losing unrecoverable context; a deletion you can't justify is often one the user can't undo.
  - [Example] Move over write+delete; `git checkout -- <file>` over manual rewrite to revert; `git stash` over `git checkout` when you may still need the changes.
  - [Example] When a file holds others' uncommitted work, stage only your hunks with `git-hunk` rather than committing or reverting the whole file.

- [Instruction] Modify only the exact lines/fields/keys/entries needed for the requested change.
  - [Why] Touching more than asked widens the blast radius and review surface, and incidental reformatting buries the real change and can trip linters or git blame.
  - [Example] Don't touch indentation, blank lines, whitespace, quotes, or semicolons you weren't asked to change.

### TaskList discipline

- [Instruction] **Leverage TaskList proactively** -- whenever there are 2+ things to do, use TaskCreate/TaskUpdate; never skip it.
  - [Why] It's the only durable surface that survives compaction and session ends, so tracking 2+ items there is what stops you forgetting them.

- [Instruction] Create the task with ` <id>. ` in the subject — leading space, number, period, trailing space.
  - [Why] The manual ` <id>` lets you reference the task in chat immediately, without waiting for TaskCreate to return its system id.

- [Instruction] Once TaskCreate returns its id, TaskUpdate the subject to add ` [#<returned-id>]` after the period (final shape ` <id>. [#<returned-id>] <description>`).
  - [Why] Pinning the system id into the subject lets later updates and references point at the task unambiguously.

- [Instruction] A **Task** is anything that produces one or more small, isolated commits.
  - [Why] Producing its own commit is the test that separates a Task from a Sub-Step; without it an AI mislabels Sub-Steps as Tasks and fragments the plan.

- [Instruction] Prefix every task subject with a category placed between `[#<returned-id>]` and the description.
  - [Why] The category lets you and the reader triage tasks by kind at a glance — deferred, scout, ships-with-current, etc.
  - [Example] Final shape ` <id>. [#<returned-id>][<category>] <description>`. Default `[Task]`; also `[Feature]`, `[Spike]`, `[Debt]`, `[Refactor]`.

- [Instruction] `[Sub-Step]` — a child of a Task or another Sub-step; place it after its parent or a sibling (logical order); commits along with its Task ancestor.
  - [Why] A sub-step decomposes a task into ordered pieces without its own commit — it isn't independently shippable, so bundling it with its parent gives the reviewer one coherent change.
- [Instruction] `[Side]` — deferred "side quest" / out-of-scope work (review feedback, mid-task requests, anything you uncover); file as a new task, don't pivot; own commit, end of list.
  - [Why] Filing deferred work as its own task instead of derailing the current one keeps each commit a single logical change.

- [Instruction] `[Scout]` — pre-existing, non-blocking issue noticed in passing; auto-queued per the Scout rule (no per-Scout approval); its own commit, end of list by default.
  - [Why] Absorbing a pre-existing fix into the current commit would mix concerns and derail it.

- [Instruction] `[Drift]` — collateral fix the current task is blocked on (needed mid-flight to make it work); bundle into the base commit if trivial, else its own commit.
  - [Why] Leave-it-better is worth it for small drifts that don't delay the real goal; a larger one burdens the goal's reviewer, so it earns its own commit or PR.

- [Instruction] `[Remind]` — a durable reminder of a process step to run later; the step may or may not produce a commit; stays pending until it runs, then completes.
  - [Why] The TaskList re-surfaces to the AI every turn and survives compaction, so a long unattended run through many compactions keeps the step visible instead of silently skipping it.
  - [Example] Batch-end procedure steps: run the repo-green gate, dispatch the review tails, finalize the PR, open the diff-review pane.

- [Instruction] On a leveraged tasklist, execute each task via a pinned subagent — main orchestrates and validates against artifacts with fresh eyes.
  - [Why] Inline task execution burns the main window that compactions are rationed by, and orchestrator-validates already governs `/implement`.

- [Instruction] Pick the pin per task: haiku when the dispatch prompt carries the exact content to place (mechanical transform), sonnet when the subagent must compose or restructure under conventions.
  - [Why] Tier follows judgment required, not habit — haiku costs ~3x less than sonnet and suffices when nothing is left to decide.

- [Instruction] Keep in main: permission-gated actions (commit, push, reply) and small edits whose inputs main already holds, while the session is shallow.
  - [Why] Permission UIs only render in main, and a subagent re-reads from scratch what main holds warm — delegating there re-buys reads main already paid for.

### Slow commands

- [Instruction] **Save slow command output, verify from the file** -- any command taking 4+ seconds: redirect full output to a stable, reused `/tmp/` path, then filter from the file.
  - [Why] A slow command is expensive to repeat; the file is a durable record you can re-filter without paying again, and a stable path lets the user keep tailing it.
  - [Example] `<slow-cmd> > /tmp/out.txt 2>&1; echo "exit: $?"; tail -<N> /tmp/out.txt;` — choose N to fit the command's summary.
  - [Example] Don't pipe it straight to `grep`/`head` — a wrong filter discards the output and forces the whole slow run again.

- [Instruction] Check both exit code and tail in one line, with `echo "exit: $?"` immediately after the slow command, before any `tail` — never trust exit code alone.
  - [Why] Some runners exit 0 on partial failure and only the tail shows the real summary; an `echo` after `tail` captures tail's `0` and masks the real failure.

### Harness caveats & hygiene

- [Instruction] **Truncated file content in system reminders is not exhaustive** -- with `[N lines truncated]` or similar, treat the visible portion as a snippet.
  - [Why] Snippets feel complete because they're framed as "here's the file" — but the truncation marker says you're seeing partial data. Acting on the snippet ships wrong counts.

- [Instruction] **When a static check fails, fix the underlying issue — never delete, disable, or silence the check.**
  - [Why] Silencing a failing check ships the defect it flagged and drops the guard for every future change — trading a real fix for a fake green.
  - [Example] Don't reach for `// eslint-disable`, `# type: ignore`, `--no-verify`, or editing the config to mute the rule.

- [Instruction] **Don't replicate problematic patterns** -- pause and ask before copying one that either (a) contradicts the global rules or (b) is itself a smell (see examples).
  - [Why] Every replication compounds the bad pattern.
- [Instruction] **Surface harness gaps** -- when fixing something a linter/test/hook/automation could catch, flag `[Harness] ...` so the harness can be used instead of AI.
  - [Why] A hand-fix a linter could make by rule is signal lost; tagging the gap makes the harness scale to the next caller for free, so the fix compounds.

### Subagents

- [Instruction] **CRITICAL: Default to parallel fan-out** when a task splits into independent chunks (one per file/module/target/ERP/service).
  - [Why] Wall-clock time is the user's real cost, not token spend; independent chunks carry no ordering dependency, so serial execution just makes the user wait N× longer for free.

- [Instruction] Dispatch one subagent per independent chunk in a single message rather than serially or inline.
  - [Why] One subagent per chunk ensures independent execution; a single message minimizes dispatch overhead.

- [Instruction] **Leverage Explore/Grep and other subagents to minimize compaction on main session** -- broad searches, fan-out reads, "where is X handled?" hunts, etc;
  - [Why] Main session is kept under a tight 200k tokens context window. Inline exploration dumps every touched file into the main context, triggering more compactions.

- [Instruction] Default to launching subagents in the background (`run_in_background`) — UNLESS the next step depends on the result, or the user must watch progress live: then run foreground.
  - [Why] Background keeps the loop free, but a result-gated background launch just stalls the turn — or tempts redoing the search inline, dumping what delegation was meant to keep out.

- [Instruction] Give every Agent `description` the form `<title> - <model> <effort>` — no parens, no `<agent-type>` (the UI prepends it, so the full line reads `<agent-type> <title> - <model> <effort>`).
  - [Why] That dispatch line is all the user sees live, so naming tier and effort lets them audit spawns in real time; repeating the type just doubles it (`general-purpose general-purpose …`).

- [Instruction] **CRITICAL: Spawn a fresh-context subagent when writing-session bias would distort the check** -- verification, semantic match, or quality judgment over your own output.
  - [Why] In-session reading carries "I already convinced myself" residue; a subagent sees only the artifact + the question.
  - [Example] Test-presence gates, AC↔test coverage, code-review of just-written code, end-of-batch refactor + auto-review reports.

- [Instruction] **Verify mutating-subagent results against artifacts** -- check diff, file contents, or command output before treating a write-agent's "done" as done.
  - [Why] The summary describes intent; only the artifact shows reality.

@RTK.md
