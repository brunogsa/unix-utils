---
name: audit-session
description: "Audit one Claude Code session's time, money, work done, and status, and render a self-contained audit_session-<sid>.html. Defaults to the current session; takes an optional [sid] to audit a different, e.g. finished, session."
user-invocable: true
---

# Audit Session

Resolves a session id, then dispatches the `session-auditor` agent with that one token.

The agent owns the entire audit: extraction, 5 shards (S1-S4 parallel, S5 sequential), the merge, and render. Read `assets/subagent-prompt.md` for the full routine; this file dispatches only.

## Usage

```
/audit-session [sid]
```

With no argument, audits the current session.

With `[sid]`, audits that session instead — this is what makes a finished, possibly large or heavily-compacted, session auditable from a fresh window without resuming it first.

## Resolving the sid

1. **When `[sid]` was given**, use it directly — skip every step below entirely.

2. **Otherwise, parse the harness's own scratchpad path.** The scratchpad directory path embeds the session id as the segment immediately before `scratchpad`.
   - `/private/tmp/claude-<N>/-Users-.../<sid>/scratchpad` — the sid is `<sid>`. Split that path on `/` and take the segment that precedes `scratchpad`.

3. **When that parse fails** (no scratchpad path, or invalid segment), use `english-coach`'s heuristic.

   Walk up to find `~/.claude/projects/<encoded-cwd>/`, then take the most-recently-modified `.jsonl`. Its filename stem, minus `.jsonl`, is the sid.

   This fallback is ambiguous when multiple terminals have active sessions for the same directory. "Most recently modified" picks whichever wrote last, not the invoker of `/audit-session`.

   Note this ambiguity to the user rather than silently guessing.

## Run

1. Resolve the sid per the steps above.

2. Dispatch `agent(subAgent=session-auditor, title=Audit session <sid>)`, with no `model=` param.

   `session-auditor`'s own frontmatter pins `model: sonnet`, so naming it here is redundant at best, and a denied mismatch at worst if the two ever drift.

   Pass only the resolved sid as the prompt — no procedure, no schema, no file paths.

   The agent already knows its own routine from `assets/subagent-prompt.md`; forwarding instructions here would just be a second copy that can drift from that file.

3. Report back to the user exactly what the agent returns: the artifact's absolute path plus its 3-line headline.
   - Don't re-read or re-summarize the artifact yourself — that is what the agent already condensed it to.

## Files

- `assets/subagent-prompt.md` — the self-contained routine the `session-auditor` agent reads for the full procedure.
  - The 5 fixed shard dispatches (S1-S4 parallel, S5 sequential), the digest schema, the retry-once-then-INCOMPLETE rule, and the `/tmp/audit-session-<sid>/` working-directory layout.
  - S2 (money) compares the session's per-skill spend against `~/.claude/skills/usage-audit/usage-history/targets.md` — the same per-skill cost ceilings `usage-audit` reads, not a copy of them.
