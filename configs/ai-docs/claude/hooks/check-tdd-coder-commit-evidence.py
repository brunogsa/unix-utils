#!/usr/bin/env python3
# check-tdd-coder-commit-evidence.py - deny a tdd-coder git
#   commit until its run's evidence file holds a RED entry
#   followed by a GREEN entry.
#
# Usage (tdd-coder frontmatter PreToolUse Bash hook):
#   check-tdd-coder-commit-evidence.py
#
# stdin: the PreToolUse hook payload, as JSON
# reads: the agent's own JSONL transcript, for the run label,
#   and /tmp/tdd-coder_evidences_<run-label>.txt
#
# stdout: a PreToolUse deny decision as JSON when the commit
#   lacks that evidence; nothing otherwise
# exit: always 0; stdin that is not a JSON object fails open

import importlib.util
import json
import re
import shlex
import sys
from pathlib import Path
from types import ModuleType

HOOKS_DIR = Path(__file__).resolve().parent


def load_module(name: str, path: Path) -> ModuleType:
    # Hyphenated filenames cannot be named by a bare import.
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


report_files = load_module("check_tdd_coder_report_files", HOOKS_DIR / "check-tdd-coder-report-files.py")
parse_shell_command = load_module("parse_shell_command", HOOKS_DIR / "lib" / "parse-shell-command.py")

EVIDENCE_PATH = "/tmp/tdd-coder_evidences_{label}.txt"
RED_HEADER = "=== RED <timestamp> ==="
GREEN_HEADER = "=== GREEN <timestamp> ==="

# Labels are plain tokens, so a test source's f-string such as
# {RUN_LABEL} or a * glob never reads as a run label.
RUN_FILE_LABEL = re.compile(r"/tmp/tdd-coder_(?:substeps|evidences)_([A-Za-z0-9._-]+?)\.(?:md|txt)\b")
SAFE_AGENT_ID = re.compile(r"[A-Za-z0-9_-]+")

GIT_OPTIONS_TAKING_A_VALUE = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--config-env"}

# Unbalanced quotes stop shlex, so the gate falls back to a
# plain match that errs toward reading a commit.
UNPARSED_GIT_COMMIT = re.compile(r"\bgit\b[^;&|\n]*\bcommit\b")


def read_payload() -> dict | None:
    try:
        payload = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def get_git_subcommand(tokens: list[str], git_index: int) -> str | None:
    index = git_index + 1
    while index < len(tokens):
        token = tokens[index]
        if token in GIT_OPTIONS_TAKING_A_VALUE:
            index += 2
        elif token.startswith("-"):
            index += 1
        else:
            return token
    return None


def get_shell_words(text: str) -> list[str] | None:
    lexer = shlex.shlex(text, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    try:
        return list(lexer)
    except ValueError:
        return None


def runs_git_commit(command: str) -> bool:
    # A heredoc body or a quoted argument is data, so the
    # call that appends "git commit" text to the evidence
    # file is never read as a commit.
    text = parse_shell_command.strip_heredoc_bodies(command)
    words = get_shell_words(text)
    if words is None:
        return UNPARSED_GIT_COMMIT.search(text) is not None

    subcommands = [get_git_subcommand(words, index) for index, word in enumerate(words) if Path(word).name == "git"]
    return "commit" in subcommands


def get_agent_transcript_path(payload: dict) -> Path | None:
    named_path = payload.get("agent_transcript_path")
    if isinstance(named_path, str) and named_path:
        return Path(named_path)

    # Claude Code keeps a subagent's transcript beside the
    # session's, at <session>/subagents/agent-<agent_id>.jsonl.
    session_path = payload.get("transcript_path")
    agent_id = payload.get("agent_id")
    if not isinstance(session_path, str) or not isinstance(agent_id, str):
        return None
    if not SAFE_AGENT_ID.fullmatch(agent_id):
        return None
    return Path(session_path).with_suffix("") / "subagents" / f"agent-{agent_id}.jsonl"


def get_tool_call_labels(block: dict) -> list[str]:
    tool_input = block.get("input")
    if block.get("type") != "tool_use" or not isinstance(tool_input, dict):
        return []
    path_texts = [str(tool_input.get("file_path", "")), str(tool_input.get("command", ""))]
    return RUN_FILE_LABEL.findall("\n".join(path_texts))


def get_run_label(transcript_path: Path) -> str | None:
    # Only the agent's own tool calls count: its dispatch prompt
    # can name a sibling or prior run's files in prose.
    records = report_files.read_transcript_records(str(transcript_path))
    labels = []
    for block in report_files.iter_assistant_blocks(records):
        labels += get_tool_call_labels(block)
    return labels[-1] if labels else None


def get_evidence_problem(evidence_path: Path) -> str | None:
    try:
        text = evidence_path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return f"{evidence_path} does not exist"
    except OSError as error:
        return f"{evidence_path} cannot be read ({error})"

    return None


def print_deny(problem: str) -> None:
    reason = (
        f"tdd-coder commits only after its evidence file holds a confirmed {RED_HEADER} entry "
        f"followed by a confirmed {GREEN_HEADER} entry, appended as each run is read, "
        f"never reconstructed afterwards: {problem}."
    )
    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
    print(json.dumps(output))


def is_tdd_coder_commit(payload: dict) -> bool:
    # A nested Explore's call can reach this agent's hooks, and
    # main never carries tdd-coder as its agent_type.
    tool_input = payload.get("tool_input")
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    is_tdd_coder = payload.get("agent_type") == report_files.AGENT_TYPE
    return is_tdd_coder and isinstance(command, str) and runs_git_commit(command)


def get_commit_problem(payload: dict) -> str | None:
    transcript_path = get_agent_transcript_path(payload)
    label = get_run_label(transcript_path) if transcript_path is not None else None
    if label is None:
        return (
            "no tool call of this run named its checklist or evidence file, so its run label is "
            f"unknown. Write {report_files.CHECKLIST_TEMPLATE} and append to "
            f"{report_files.EVIDENCE_TEMPLATE} under your run label first"
        )
    return get_evidence_problem(Path(EVIDENCE_PATH.format(label=label)))


def main() -> int:
    payload = read_payload()
    if payload is None or not is_tdd_coder_commit(payload):
        return 0

    problem = get_commit_problem(payload)
    if problem is not None:
        print_deny(problem)
    return 0


if __name__ == "__main__":
    sys.exit(main())
