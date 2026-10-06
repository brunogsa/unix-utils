#!/usr/bin/env python3
# check-tdd-coder-report-files.py - block a tdd-coder stop whose
#   report does not name an existing, non-empty checklist and
#   evidence file.
#
# Usage (tdd-coder frontmatter Stop hook, run as SubagentStop):
#   check-tdd-coder-report-files.py
#
# stdin: the SubagentStop hook payload, as JSON
# reads: the JSONL transcript at agent_transcript_path, when
#   the payload carries no last_assistant_message
#
# stdout: {"decision": "block", "reason": "..."} when a file is
#   unnamed, missing or empty, or no report can be read;
#   nothing otherwise
# exit: always 0.

import json
import re
import sys
from collections.abc import Iterator
from pathlib import Path

AGENT_TYPE = "tdd-coder"
HANDBACK_TOOL = "SubagentHandback"
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


def is_non_empty_text(value: object) -> bool:
    return isinstance(value, str) and value != ""


def read_transcript_records(transcript_path: str) -> list[dict]:
    try:
        raw = Path(transcript_path).read_bytes()
    except (OSError, ValueError):
        return []

    # Split on newline bytes only: a raw U+2028 inside a JSON
    # string is valid JSONL, and str.splitlines() would cut the
    # record there.
    records = []
    for line in raw.split(b"\n"):
        try:
            record = json.loads(line.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        if isinstance(record, dict):
            records.append(record)
    return records


def iter_assistant_blocks(records: list[dict]) -> Iterator[dict]:
    for record in records:
        message = record.get("message")
        if record.get("type") != "assistant" or not isinstance(message, dict):
            continue
        content = message.get("content")
        if isinstance(content, list):
            yield from (block for block in content if isinstance(block, dict))


def get_transcript_report(transcript_path: str) -> object:
    has_handback = False
    handback_report: object = None
    text_report: object = None
    for block in iter_assistant_blocks(read_transcript_records(transcript_path)):
        if block.get("type") == "tool_use" and block.get("name") == HANDBACK_TOOL:
            has_handback = True
            tool_input = block.get("input")
            handback_report = tool_input.get("message") if isinstance(tool_input, dict) else None
        elif block.get("type") == "text":
            text_report = block.get("text")

    # A handback is the agent's declared report, so it outranks
    # any text, even text written after it.
    return handback_report if has_handback else text_report


def get_report(payload: dict) -> str | None:
    # Claude Code 2.1.290 leaves last_assistant_message out of
    # the SubagentStop payload that the hooks doc lists it in,
    # so the agent's own transcript is the fallback source.
    report = payload.get("last_assistant_message")
    if not is_non_empty_text(report):
        transcript_path = payload.get("agent_transcript_path")
        report = get_transcript_report(transcript_path) if isinstance(transcript_path, str) else None
    return report if isinstance(report, str) and report != "" else None


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


def print_block(reason: str) -> None:
    print(json.dumps({"decision": "block", "reason": reason}))


def main() -> int:
    payload = read_payload()
    if payload is None:
        return 0

    # One nudge, never a loop: block only when Claude Code says
    # no stop hook has fired yet, since any other value may be a
    # second stop that a block the agent cannot satisfy would
    # repeat.
    if payload.get("stop_hook_active") is not False:
        return 0

    if is_other_agent_stop(payload):
        return 0

    report = get_report(payload)
    if report is None:
        print_block(
            "tdd-coder's stop hook could not read the final report: the payload carries no "
            "last_assistant_message and the agent transcript holds no SubagentHandback message "
            "or assistant text, so the checklist and evidence file went unchecked. "
            f"Make sure both run files exist and are non-empty ({CHECKLIST_TEMPLATE} and "
            f"{EVIDENCE_TEMPLATE}), and make the report end naming both paths. "
            "This block fires once: a second stop ends the run."
        )
        return 0

    problems = get_file_problems(report, "checklist", CHECKLIST_PATTERN, CHECKLIST_TEMPLATE)
    problems += get_file_problems(report, "evidence file", EVIDENCE_PATTERN, EVIDENCE_TEMPLATE)
    if not problems:
        return 0

    print_block(
        "tdd-coder must keep both run files and name them in its report: "
        + "; ".join(problems)
        + f". Write the missing file, then make the report end naming both paths, "
        f"per tdd-coder.md's Evidence ({EVIDENCE_TEMPLATE}) and Checklist ({CHECKLIST_TEMPLATE}) lines."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
