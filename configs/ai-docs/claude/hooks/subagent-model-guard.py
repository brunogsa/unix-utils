#!/usr/bin/env python3
"""subagent-model-guard - PreToolUse hard-deny gate for Agent tool model pins

Usage (Claude Code PreToolUse hook, matcher "Agent"):
  Reads the tool-call JSON from stdin, decides allow/deny for the dispatched
  subagent, and prints a deny decision to stdout when it fires. Exits 0 in
  every case (Claude Code's PreToolUse "deny" is expressed via JSON on stdout,
  not via exit code -- see the printf calls below).

Policy:
  Every agent-frontmatter file under ~/.claude/agents/*.md is the single
  source of truth for pins -- this hook carries no allowlist of its own, so
  it can never drift out of sync with the frontmatter.

  - PINNED subagent_type (frontmatter has `model:`): the dispatched
    tool_input.model must be absent or match the pin (aliases sonnet/opus/
    haiku/fable match any full model ID of that family, e.g. claude-sonnet-5).
    A present-but-mismatched model is denied -- the frontmatter outranks any
    skill or reference instructing a caller to override the pin, so such a
    doc is a conflict to surface rather than grounds to allow the dispatch.
    Only `model` is gated; `effort` is reported in the deny reason for
    context but never enforced, so overriding a pinned effort is legal.
  - PINNED WITH DECLARED OVERRIDES (frontmatter also has
    `allowedModelOverrides:`): the pin still binds when the caller names no
    model, but a model matching any listed family is allowed too. This is how
    an agent whose default tier fits most dispatches opts into a second tier
    for the minority that need it, without the escape hatch leaking to every
    other pinned agent. Declaring it in frontmatter keeps this hook free of an
    allowlist of its own -- the agent file stays the single source of truth.
  - UNPINNED subagent_type (no matching agent file, or a file without
    `model:`): tool_input.model must be present -- an omitted model on an
    unpinned type silently inherits the session's (possibly expensive) model,
    so it is denied. Any explicit model is accepted; the invoker decides --
    unless the file declares `deniedModels:` (see below), which still binds.
  - UNPINNED WITH DECLARED DENIALS (frontmatter has `deniedModels:` but no
    `model:`): the type stays otherwise unpinned -- any named model not on
    the list is accepted -- but a model matching a listed family is denied.
    This is how a type whose whole point is inheriting the caller's model
    (general-purpose) can still rule out specific expensive/lower-precision
    tiers without becoming pinned to a single one. Same reasoning as
    `allowedModelOverrides:`: declaring it in frontmatter keeps this hook
    free of an allowlist of its own.
  - A DISPATCH WITH NO `subagent_type` AT ALL resolves to `general-purpose`,
    mirroring the Agent tool's own documented default ("omitting it starts a
    fresh agent -- general-purpose by default"). It is not a fail-open case:
    treating it as unresolvable let a caller dodge every check below --
    including `general-purpose`'s own `deniedModels:` -- just by leaving the
    field out, which defeats the ban rather than being neutral to it.
  - THE `fork` TYPE is exempt from all of the above. A conversation fork has
    no agent file to pin and always runs the main session's model, so the
    unpinned branch's rationale -- that an omitted model silently inherits
    the session tier -- never applied to it: inheriting IS a fork's contract.
    Denying it merely forced callers to name a model the harness then ignored.
    This is a narrow exception for one literal type, not a loosened threshold,
    so every other unpinned type still has to name its tier.

  Fail-open on anything unexpected (malformed stdin, unreadable agents dir,
  unreadable agent file): exit 0 with no output, so a hook bug never bricks
  every subagent dispatch. A pinned type with a present-but-unparseable
  tool_input.model is NOT an "unexpected error" -- it is a normal mismatch,
  so it still denies (see PINNED case above).

Examples:
  echo '{"tool_name":"Agent","tool_input":{"subagent_type":"code-reviewer"}}' \
    | subagent-model-guard.py                          # allowed (omitted model, pinned)
  echo '{"tool_name":"Agent","tool_input":{"subagent_type":"code-reviewer","model":"haiku"}}' \
    | subagent-model-guard.py                          # denied (wrong model for the pin)
  echo '{"tool_name":"Agent","tool_input":{"subagent_type":"tdd-coder","model":"opus"}}' \
    | subagent-model-guard.py                          # allowed (declared override tier)
  echo '{"tool_name":"Agent","tool_input":{"subagent_type":"general-purpose"}}' \
    | subagent-model-guard.py                          # denied (unpinned, no model named)
  echo '{"tool_name":"Agent","tool_input":{"subagent_type":"general-purpose","model":"opus"}}' \
    | subagent-model-guard.py                          # denied (opus is on general-purpose's deniedModels)
  echo '{"tool_name":"Agent","tool_input":{"subagent_type":"general-purpose","model":"sonnet"}}' \
    | subagent-model-guard.py                          # allowed (sonnet is not denied)
  echo '{"tool_name":"Agent","tool_input":{"model":"opus"}}' \
    | subagent-model-guard.py                          # denied (no subagent_type resolves to general-purpose)
  echo '{"tool_name":"Agent","tool_input":{"subagent_type":"fork"}}' \
    | subagent-model-guard.py                          # allowed (a fork takes the session's model)
"""

import json
import re
import sys
from pathlib import Path

AGENTS_DIR = Path.home() / ".claude" / "agents"
FORK_SUBAGENT_TYPE = "fork"
MODEL_ALIASES = ("sonnet", "opus", "haiku", "fable")
DEFAULT_SUBAGENT_TYPE = "general-purpose"
FRONTMATTER_KEYS = ("name", "model", "effort", "allowedModelOverrides", "deniedModels")


def normalize_model(value):
    """Collapse a model alias or full model ID to its family alias.

    claude-sonnet-5, claude-3-5-sonnet-20241022, and "sonnet" all normalize
    to "sonnet" so a pin survives model-ID version bumps. A value with no
    recognized family name is returned lowercased and unchanged, so it still
    compares (and correctly fails to match) against a real pin.
    """
    if value is None:
        return None
    lowered = value.strip().lower()
    for alias in MODEL_ALIASES:
        if alias in lowered:
            return alias
    return lowered


def parse_model_list(value):
    """Normalize an `allowedModelOverrides:`/`deniedModels:` value into family aliases.

    Accepts both spellings the frontmatter can carry -- a comma-separated
    scalar (`opus` / `opus, fable`) and YAML's inline flow list
    (`[opus, fable]`) -- because the agent file is hand-edited and neither
    form is wrong there. An absent or empty key yields an empty tuple, which
    is what keeps every agent that never declares either key unaffected.
    """
    if not value:
        return ()
    entries = value.strip().strip("[]").split(",")
    aliases = [normalize_model(entry) for entry in entries if entry.strip()]
    return tuple(alias for alias in aliases if alias)


def parse_agent_frontmatter(path):
    """Naively extract the flat name:/model:/effort: keys between the --- delimiters.

    Only zero-indented `key: value` lines count, so nested block keys (e.g. a
    hooks: sub-block's `command: ...`) can never be mistaken for a top-level
    pin -- they're indented and this parser only matches line-start keys.
    """
    lines = path.read_text().splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    fields = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        match = re.match(r"^(\w+):\s*(.*)$", line)
        if not match:
            continue
        key, value = match.group(1), match.group(2).strip()
        if key in FRONTMATTER_KEYS and key not in fields:
            fields[key] = value
    return fields


def load_agent_pins():
    """Map every known subagent_type spelling to its {model, effort} pin (if any).

    Each agent file is indexed under both its frontmatter `name:` and its
    filename stem, so a dispatch can resolve either way. A subagent_type with
    no entry here is UNPINNED by definition -- there is no local agent file
    governing it.
    """
    pins = {}
    for md_file in AGENTS_DIR.glob("*.md"):
        fields = parse_agent_frontmatter(md_file)
        for key in (fields.get("name"), md_file.stem):
            if key:
                pins[key] = fields
    return pins


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
        if payload.get("tool_name") != "Agent":
            return  # not our matcher's concern; allow silently

        tool_input = payload.get("tool_input") or {}
        subagent_type = tool_input.get("subagent_type") or DEFAULT_SUBAGENT_TYPE

        if subagent_type == FORK_SUBAGENT_TYPE:
            # A fork inherits the main session's model, so
            # there is no tier here to get wrong, and no
            # agent file to read one from. Checked before
            # the pins load, since "fork" never resolves.
            return

        requested_model = tool_input.get("model") or None
        pins = load_agent_pins()
        pin = pins.get(subagent_type)
        pinned_model = pin.get("model") if pin else None
    except Exception:
        # fail open: malformed stdin or unreadable agents dir
        return

    if pin and pinned_model:
        pinned_effort = pin.get("effort", "inherited")
        allowed_overrides = parse_model_list(pin.get("allowedModelOverrides"))
        if requested_model is None:
            return  # allow: omitted model takes the pin
        if normalize_model(requested_model) == normalize_model(pinned_model):
            return  # allow: explicit model matches the pin
        if normalize_model(requested_model) in allowed_overrides:
            # allow: the agent file declares this tier
            # as a legal override
            return
        override_note = (
            f"It declares allowedModelOverrides={','.join(allowed_overrides)}, "
            f"and the model you named is not among them. "
            if allowed_overrides
            else ""
        )
        deny(
            f"subagent '{subagent_type}' is pinned to model={pinned_model} "
            f"(effort={pinned_effort}, which this guard does not gate — "
            f"override effort freely). {override_note}That frontmatter is the "
            f"only place a model tier is decided, so it outranks any skill or "
            f"reference telling you to override the pin. Either omit the model "
            f"param and take the pin, or dispatch a different agent type when "
            f"you need another tier. If a doc told you to override, that is a "
            f"real conflict, not your misreading — surface it so the pin or "
            f"the doc gets changed, and do not retry this dispatch."
        )
        return

    # Unpinned: no agent file matched subagent_type, or its file
    # has no model:
    if requested_model is None:
        deny(
            f"agent type '{subagent_type}' has no frontmatter model pin — "
            f"name a model explicitly (haiku = mechanical transforms, "
            f"sonnet = compose under conventions, opus/fable = judgment); "
            f"an omitted model silently inherits the session's expensive tier."
        )
        return

    denied_models = parse_model_list(pin.get("deniedModels")) if pin else ()
    if normalize_model(requested_model) in denied_models:
        deny(
            f"agent type '{subagent_type}' declares deniedModels="
            f"{','.join(denied_models)}, and the model you named is one of "
            f"them. That frontmatter is the only place this is decided, so "
            f"it outranks any skill or reference telling you to use that "
            f"tier here. Dispatch a different, pinned agent type that "
            f"legitimately needs that tier instead of forcing it through "
            f"this one. If a doc told you to do this, that is a real "
            f"conflict, not your misreading — surface it so the doc or the "
            f"ban gets changed, and do not retry this dispatch."
        )
        return

    # else: allow: unpinned type with an explicit, non-denied model —
    # the invoker decides


if __name__ == "__main__":
    main()
