#!/usr/bin/env python3
"""subagent-disallowed-tools-guard - PreToolUse hard-deny gate that
evaluates a subagent's disallowedTools/allowedSubagents frontmatter
at call time.

Usage (Claude Code PreToolUse hook, matcher "Agent|Workflow"):
  Reads the tool-call JSON from stdin, resolves the CALLING agent's
  file (not the dispatch target named in tool_input), and denies the
  call when the invoked tool_name appears in that caller's
  disallowedTools list, or (for Agent calls specifically) when the
  requested subagent_type is absent from that caller's
  allowedSubagents list, if declared. Exits 0 in every case (Claude
  Code's PreToolUse "deny" is expressed via JSON on stdout, not via
  exit code -- see the deny() calls below).

Why this hook exists:
  Claude Code reads and caches an agent file's frontmatter at SESSION
  START. Editing disallowedTools mid-session (e.g. adding Agent to
  tdd-coder.md so it can never dispatch another tdd-coder) does not
  bind until a new session starts -- until then the restriction reads
  as enforced but silently does nothing. This hook re-evaluates the
  restriction from the file on every call, so an edit binds
  immediately.

Policy:
  - No calling-agent context (agent_type absent -- a main-session
    call): allow. There is no agent file to restrict a top-level
    session.
  - agent_type present but resolves to no agent file under
    ~/.claude/agents/*.md: allow. Absence of a file is not a
    restriction -- most agent types have no file at all.
  - agent_type resolves to a file that reads and parses cleanly:
    deny iff tool_name is one of the comma-separated names in its
    disallowedTools: field; allow otherwise.
  - That same file additionally declares allowedSubagents: for
    Agent calls (never Workflow, which carries no subagent_type):
    deny unless the call's subagent_type is one of the
    comma-separated names in that list. subagent_type missing
    entirely, and allowedSubagents present-but-empty, both fail
    closed for the same reason as the frontmatter-parse-failure
    case below: a carve-out that can be silently bypassed by
    omitting a value would defeat the reason this hook exists. No
    allowedSubagents: key at all leaves this axis unrestricted, same
    as no disallowedTools: key.
  - agent_type resolves to a file that CANNOT be read or whose
    frontmatter cannot be parsed (I/O error, decode error, truncated
    frontmatter that never closes): DENY, failing closed. This is
    unlike the "no file" case above -- here a candidate file exists,
    so there is positive reason to think a restriction might apply
    that we simply could not confirm. This hook exists specifically
    so a real restriction is never silently inert; treating an
    unreadable file as "unrestricted" would reproduce that exact bug
    at the parsing layer instead of the session-cache layer.

  Fail-open only on hook mechanics we cannot recover from at all:
  unparseable stdin, or an unreadable/nonexistent agents directory
  (no candidate file was ever found, so there is nothing to fail
  closed on) -- exit 0 with no output, so a hook bug never bricks
  every Agent/Workflow dispatch.

Examples:
  echo '{"tool_name":"Agent","agent_type":"tdd-coder"}' \
    | subagent-disallowed-tools-guard.py   # denied (tdd-coder disallows Agent)
  echo '{"tool_name":"Workflow","agent_type":"tdd-coder"}' \
    | subagent-disallowed-tools-guard.py   # denied (tdd-coder disallows Workflow)
  echo '{"tool_name":"Agent","agent_type":"Explore"}' \
    | subagent-disallowed-tools-guard.py   # allowed (Explore has no disallowedTools pin)
  echo '{"tool_name":"Agent"}' \
    | subagent-disallowed-tools-guard.py   # allowed (main session, no calling agent)
  echo '{"tool_name":"Agent","agent_type":"tdd-coder","tool_input":{"subagent_type":"Grep"}}' \
    | subagent-disallowed-tools-guard.py   # denied once tdd-coder declares allowedSubagents: Explore
"""

import json
import re
import sys
from pathlib import Path

AGENTS_DIR = Path.home() / ".claude" / "agents"
GATED_TOOLS = ("Agent", "Workflow")
FRONTMATTER_KEYS = ("name", "disallowedTools", "allowedSubagents")


def parse_agent_frontmatter(path):
    """Extract the flat name:/disallowedTools: keys between --- delimiters.

    Raises ValueError when the frontmatter block never closes (the
    file is truncated or genuinely malformed) instead of returning
    the partial fields seen so far -- a caller relying on a partial
    read could wrongly conclude disallowedTools is absent when the
    real value sits past the point the read stopped.
    """
    lines = path.read_text().splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError(f"{path} has no opening frontmatter delimiter")
    fields = {}
    closed = False
    for line in lines[1:]:
        if line.strip() == "---":
            closed = True
            break
        match = re.match(r"^(\w+):\s*(.*)$", line)
        if not match:
            continue
        key, value = match.group(1), match.group(2).strip()
        if key in FRONTMATTER_KEYS and key not in fields:
            fields[key] = value
    if not closed:
        raise ValueError(f"{path} frontmatter never closes")
    return fields


def parse_comma_list(raw):
    """Split a comma-separated frontmatter value into stripped names.

    Shared by disallowedTools and allowedSubagents -- both are the
    same flat comma-list shape, just gating a different axis (tool
    name vs. dispatched subagent_type).
    """
    return [name.strip() for name in raw.split(",") if name.strip()]


def resolve_agent_file(agent_type):
    """Find agent_type's .md file by filename stem, else frontmatter name.

    The stem check is a plain path existence test -- it never reads
    the file, so a malformed file is still correctly resolved (found)
    here and only fails later when its frontmatter is actually parsed
    for disallowedTools. Returns None only when no candidate file
    exists under AGENTS_DIR at all.
    """
    if not AGENTS_DIR.is_dir():
        return None

    by_stem = AGENTS_DIR / f"{agent_type}.md"
    if by_stem.is_file():
        return by_stem

    for md_file in AGENTS_DIR.glob("*.md"):
        try:
            fields = parse_agent_frontmatter(md_file)
        except Exception:
            continue  # not readable/parseable by name; not our candidate
        if fields.get("name") == agent_type:
            return md_file
    return None


def deny(reason):
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return  # fail open: can't even parse the hook's own stdin

    tool_name = payload.get("tool_name")
    if tool_name not in GATED_TOOLS:
        return  # not our matcher's concern; allow silently

    agent_type = payload.get("agent_type")
    if not agent_type:
        return  # main-session call: no calling-agent file to restrict

    try:
        agent_file = resolve_agent_file(agent_type)
    except Exception:
        return  # fail open: can't even enumerate the agents dir

    if agent_file is None:
        return  # allow: absence of an agent file is not a restriction

    try:
        fields = parse_agent_frontmatter(agent_file)
    except Exception:
        deny(
            f"'{agent_type}' resolves to {agent_file}, but its "
            f"frontmatter could not be read or parsed, so whether it "
            f"disallows {tool_name} cannot be confirmed. Failing "
            f"closed rather than assuming unrestricted -- this hook "
            f"exists so a real disallowedTools restriction can never "
            f"silently do nothing, and treating an unparseable file "
            f"as unrestricted would reproduce that exact bug here. "
            f"Report this block: a human needs to fix that file's "
            f"frontmatter before this dispatch can be retried."
        )
        return

    disallowed = parse_comma_list(fields.get("disallowedTools", ""))
    if tool_name in disallowed:
        deny(
            f"'{agent_type}' ({agent_file}) disallows the {tool_name} "
            f"tool in its frontmatter. That restriction binds "
            f"immediately through this hook rather than waiting for "
            f"the next session start, so it applies even though the "
            f"frontmatter may have been cached before this edit. "
            f"Report this block instead of retrying: only the caller "
            f"that owns this subagent's dispatch (its orchestrator) "
            f"can decide to widen the frontmatter."
        )
        return

    # else: allow -- tool_name isn't in disallowedTools

    if tool_name == "Agent" and "allowedSubagents" in fields:
        allowed_subagents = parse_comma_list(fields["allowedSubagents"])
        requested_subagent_type = (payload.get("tool_input") or {}).get("subagent_type")
        if requested_subagent_type not in allowed_subagents:
            deny(
                f"'{agent_type}' ({agent_file}) declares "
                f"allowedSubagents in its frontmatter, restricting "
                f"which subagent_type it may dispatch via Agent. The "
                f"requested subagent_type "
                f"({requested_subagent_type!r}) is not in that list "
                f"-- this includes the case where subagent_type is "
                f"missing entirely, since an unnamed target can never "
                f"be confirmed as permitted. Failing closed rather "
                f"than assuming permitted mirrors this hook's posture "
                f"on unparseable disallowedTools. Report this block "
                f"instead of retrying: only the caller that owns this "
                f"agent's frontmatter can widen allowedSubagents to "
                f"permit this dispatch."
            )

        # else: allow -- subagent_type is in allowedSubagents


if __name__ == "__main__":
    main()
