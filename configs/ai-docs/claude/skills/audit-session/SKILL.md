---
name: audit-session
description: "Audit one Claude Code session's time, money, work done, and status, and render a self-contained audit_session-<sid>.html. Defaults to the current session; takes an optional [sid] to audit a different, e.g. finished, session."
user-invocable: true
---

# Audit Session

Resolves a session id, then dispatches the `session-auditor` agent with that
one token. The agent owns the entire audit — extraction, the 4 fixed
shards, the merge, and the render — read `assets/subagent-prompt.md` for
that routine; this file is only the dispatcher.

## Usage

```
/audit-session [sid]
```

With no argument, audits the current session. With `[sid]`, audits that
session instead — this is what makes a finished, possibly large or
heavily-compacted, session auditable from a fresh window without resuming
it first.

## Resolving the sid

1. **When `[sid]` was given**, use it directly — skip every step below
   entirely.

2. **Otherwise, parse the harness's own scratchpad path.** This system
   prompt's own working environment carries a scratchpad directory whose
   path embeds the current session id as the path segment immediately
   before the literal `scratchpad` component, e.g.
   `/private/tmp/claude-<N>/-Users-.../<sid>/scratchpad` — the sid is
   `<sid>`. Split that path on `/` and take the segment that precedes
   `scratchpad`.

3. **When that parse fails** (no scratchpad path is present, or the
   segment before `scratchpad` doesn't look like a session id), fall back
   to `english-coach`'s heuristic: walk up from the current working
   directory to find `~/.claude/projects/<encoded-cwd>/`, then take the
   most-recently-modified `.jsonl` in it — its filename stem (minus
   `.jsonl`) is the sid.

   This fallback is ambiguous when more than one terminal or window has
   an active session against the same project directory — "most recently
   modified" picks whichever one wrote last, not necessarily the one that
   invoked `/audit-session`. Note that ambiguity to the user in this case
   rather than silently trusting the guess.

## Run

1. Resolve the sid per the steps above.

2. Dispatch `agent(subAgent=session-auditor, title=Audit session <sid>)` —
   no `model=` param: `session-auditor`'s own frontmatter pins `model:
   opus`, so naming it here would be redundant at best and a denied
   mismatch at worst if the two ever drift.

   Pass only the resolved sid as the prompt — no procedure, no schema, no
   file paths. The agent already knows its own routine from
   `assets/subagent-prompt.md`; forwarding instructions here would just be
   a second copy that can drift from that file.

3. Report back to the user exactly what the agent returns: the artifact's
   absolute path plus its 3-line headline. Don't re-read or re-summarize
   the artifact yourself — that is what the agent already condensed it to.

## Files

- `assets/subagent-prompt.md` — the self-contained routine the
  `session-auditor` agent reads for the full procedure: the 4 fixed shard
  dispatches, the digest schema, the retry-once-then-INCOMPLETE rule, and
  the `/tmp/audit-session-<sid>/` working-directory layout.
