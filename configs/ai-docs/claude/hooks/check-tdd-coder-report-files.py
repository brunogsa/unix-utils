#!/usr/bin/env python3
# check-tdd-coder-report-files.py - block a tdd-coder stop whose
#   report does not name an existing, non-empty checklist and
#   evidence file.
#
# Usage (tdd-coder frontmatter Stop hook, run as SubagentStop):
#   check-tdd-coder-report-files.py
#
# stdin: the SubagentStop hook payload, as JSON
# stdout: {"decision": "block", "reason": "..."} when a file is
#   unnamed, missing or empty, nothing otherwise
# exit: always 0.

import json
import re
import sys
from pathlib import Path

AGENT_TYPE = "tdd-coder"
CHECKLIST_TEMPLATE = "/tmp/tdd-coder_substeps_<run-label>.md"
EVIDENCE_TEMPLATE = "/tmp/tdd-coder_evidences_<run-label>.txt"

# The label stops at whitespace, quotes, backticks, brackets and
# slashes, so markdown around a path never joins the label.
LABEL = r"[^\s`'\"()<>\[\]/]+?"
CHECKLIST_PATTERN = re.compile(rf"/tmp/tdd-coder_substeps_{LABEL}\.md")
EVIDENCE_PATTERN = re.compile(rf"/tmp/tdd-coder_evidences_{LABEL}\.txt")


def read_payload() -> dict | None:
    try:
        payload = json.loads(sys.stdin.read())
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def is_other_agent_stop(payload: dict) -> bool:
    # A nested Explore's stop can reach this agent's hooks, but
    # an empty agent_type is not proof of another agent, so it
    # stays checked.
    agent_type = payload.get("agent_type")
    return isinstance(agent_type, str) and agent_type != "" and agent_type != AGENT_TYPE


def get_file_problems(report: str, kind: str, pattern: re.Pattern[str], template: str) -> list[str]:
    named_paths = sorted(set(pattern.findall(report)))
    if not named_paths:
        return [f"the report names no {kind} path ({template})"]

    problems = []
    for named_path in named_paths:
        path = Path(named_path)
        if not path.is_file():
            problems.append(f"the {kind} {named_path} does not exist")
        elif path.stat().st_size == 0:
            problems.append(f"the {kind} {named_path} is empty")
    return problems


def main() -> int:
    payload = read_payload()
    if payload is None:
        return 0

    # One nudge, never a loop: a second stop ends the run.
    if payload.get("stop_hook_active") is True:
        return 0

    if is_other_agent_stop(payload):
        return 0

    report = payload.get("last_assistant_message")
    if not isinstance(report, str):
        return 0

    problems = get_file_problems(report, "checklist", CHECKLIST_PATTERN, CHECKLIST_TEMPLATE)
    problems += get_file_problems(report, "evidence file", EVIDENCE_PATTERN, EVIDENCE_TEMPLATE)
    if not problems:
        return 0

    reason = (
        "tdd-coder must keep both run files and name them in its report: "
        + "; ".join(problems)
        + f". Write the missing file, then make the report end naming both paths, "
        f"per tdd-coder.md's Evidence ({EVIDENCE_TEMPLATE}) and Checklist ({CHECKLIST_TEMPLATE}) lines."
    )
    print(json.dumps({"decision": "block", "reason": reason}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
