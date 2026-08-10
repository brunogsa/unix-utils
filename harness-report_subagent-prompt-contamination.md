# Bug report: compaction resume block leaks into subagent dispatch prompts, letting a commit-capable subagent push to a remote with no human in the loop

## Summary

When Claude Code compacts a session, the resume block restates in-flight instructions verbatim. It then gets prepended to prompts for any subagents that session dispatches via the Agent tool.

If the parent's instruction included a remote-mutating command (observed: `git push -u origin HEAD`), the subagent receives it as its task. It lacks indication the command is the parent's or needs re-execution.

## Severity

A subagent with commit rights (write access, `git commit`/`git push` permission) can publish to a remote without the operator's approval, even though the parent never explicitly requested it.

The parent session's own permission system is bypassed entirely: permission prompts render only in the main session, so a subagent executing a leaked push instruction incurs no confirmation step of any kind.

The blast radius scales with how many subagents a session dispatches after compacting. Every post-compaction subagent inherits the same contamination until the resume block scrolls out of context or the session ends.

This is not a hypothetical: the contaminated-prompt pattern was observed twice in one session (see Evidence).

## Environment

- Claude Code CLI (agentic coding tool by Anthropic)
- macOS Darwin 25.6.0
- zsh shell
- Repo: a local git repository with a standard `origin` remote configured — unremarkable, the defect does not depend on repo-specific configuration

## Reproduction

The exact trigger sequence, as best determined from observing it:

1. Run a long session in which, at some point, the operator (or an in-flight task) issues an instruction that includes a remote git-publishing step —
   - in the observed case, `git push -u origin HEAD` as part of a multi-step task the session was midway through.

2. The session's context grows large enough that Claude Code auto-compacts (or the operator manually triggers `/compact`).
   - Compaction produces a resume block: a summary/restatement of the session's state that lets the session continue coherently after its transcript has been compacted away.
   - This resume block includes the in-flight instructions the session was executing at the time of compaction, verbatim or near-verbatim — including the `git push -u origin HEAD` step from (1).

3. After compaction, the session dispatches one or more subagents via the Agent tool (e.g., `general-purpose`, `deep-reviewer`, `tdd-coder`, or any other agent type) to continue the work.

4. The prompt text actually delivered to the dispatched subagent is observed to contain the parent session's compaction resume block prepended ahead of the task-specific prompt the calling session composed.
   - The resume block's content is addressed, semantically, to the parent session — it describes what "you" (the parent) were doing and instructs "you" to continue doing it, including the push.

5. A dispatched subagent cannot reliably distinguish "this is my actual task" from "this is contextual scaffolding from my caller" —
   - the resume block is not delimited, tagged, or otherwise marked as out-of-band caller context. It reads as an ordinary part of the prompt.

We do not have instrumented, byte-exact logging of the raw prompt Claude Code transmits to the subagent process, so we cannot paste the literal wire-level payload here.

Reconstructed from two independent occurrences in one session. Both followed the same compaction; both times, prompts carried `git push -u origin HEAD`. Neither the session's dispatch nor the task called for it.

## Observed vs expected behavior

**Observed:** a subagent dispatched after compaction receives the parent's in-flight task instructions in its prompt. Specifically, it receives remote-publishing git commands the parent's compaction summary restated.

The subagent has no signal that this content is not its own task.

**Expected:** a subagent's prompt should contain only the task-specific content the dispatching call composed (the `prompt` parameter passed to the Agent tool call).

Session-level continuity state — including the compaction resume block — is the parent session's own scaffolding for resuming itself, and should never be forwarded into a dispatched subagent's prompt.

An instruction to mutate remote state (git push, deploy) the parent ran should never re-surface in a *different* context. The subagent never decided to run it, and its approval doesn't cover it.

## Evidence

What was directly observed, and what is risk reasoning built on it — kept separate below, since the report's whole job is being checkable by a maintainer.

**Directly observed:** in one compacted session, a dispatched `deep-reviewer` subagent's prompt carried the parent session's leaked `git push -u origin HEAD` instruction.

`deep-reviewer`'s agent definition carries an explicit read-only boundary — "Never modify source, tests, configs, or any repository file" — and the agent refused to act on the push, citing that boundary.

This refusal surfaced the leak. Without it, the contamination would have gone unnoticed, since the refusal message was the only signal reaching the operator.

**Risk reasoning, not a second confirmed sighting:** `tdd-coder` has commit rights and runs `git commit` normally. At this report's time, it lacked boundaries against `git push` or remote publishing.

We didn't confirm `tdd-coder` received the leaked instruction. But nothing in its definition or the harness would have stopped it from executing a leaked push.

That gap is what makes the defect severe. Whether a leaked instruction gets executed depends on which agent receives it, not on any harness-level control.

The operator mitigated `tdd-coder` (see below). A boundary forbids `git push` "whatever the prompt says." Reasoning: push in a dispatched prompt signals contamination, not intent. Refuse and report.

## Why an agent-file boundary is a mitigation, not a fix

The boundary added to `tdd-coder` only protects that one agent definition, in this one local repository's configuration. It does nothing for:

- Any other subagent type — built-in (e.g. `general-purpose`, which has full tool access and no such boundary) or custom — that a user has not thought to guard the same way.

- Any other remote-mutating action besides `git push`.
  - The same mechanism could leak instructions to call paid APIs, send messages, deploy to production, delete resources, or take any side-effecting action the parent was mid-task on during compaction.

- Any user who has not independently discovered this defect and written the same defensive boundary into their own agent definitions.
  - The default posture for every out-of-the-box agent type, and for every custom agent a new user writes without knowing about this issue, remains vulnerable.

In short: the fix here is necessarily per-agent, per-action, and per-repo. It is applied only by operators who happen to have already been bitten by it.

The actual defect is upstream. It lies in how Claude Code constructs the prompt for dispatched subagents. It belongs in the harness, not in individual agent definitions.

## Suggested fix direction

The compaction resume block should be scoped to the session that produced it and excluded from any prompt Claude Code constructs for an outbound subagent dispatch (the Agent tool).

Concretely:

- When Claude Code builds a subagent's prompt, it should compose it from the caller's explicit parameters (task, context only). It should not splice in the calling session's resume/continuity state.

- If resume-derived context is genuinely useful (e.g., "here is the broader task"), it should be summarized and included deliberately by the calling session.
  - Handle it like any other context: explicitly written, never injected automatically and unfiltered by the harness.

- At minimum, content from the parent's resume state should be marked: "this describes your caller, not your task." This lets subagents recognize it as out-of-band, if exclusion fails.
