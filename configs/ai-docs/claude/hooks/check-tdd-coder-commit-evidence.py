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
from datetime import datetime
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
ENTRY_HEADER = re.compile(r"^=== (RED|GREEN)\b", re.MULTILINE)
SAFE_AGENT_ID = re.compile(r"[A-Za-z0-9_-]+")

GIT_OPTIONS_TAKING_A_VALUE = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--config-env"}

# The gated agent is the adversary, so a command that hands
# its script to a shell or to eval is read through to that
# script; the POSIX shells that run a -c string are a fixed
# set, not a ledger of seen commands.
SHELLS = {"sh", "bash", "zsh", "dash", "ksh"}
SHELL_OPTIONS_TAKING_A_VALUE = {"-o", "+o", "-O", "+O"}
SHELL_READS_STDIN = ""
MAX_NESTED_SCRIPTS = 8

# A shell reading its script from stdin gets it from a pipe or
# a heredoc body, so only a plain match over the raw command
# can see that script.
RAW_GIT_COMMIT = re.compile(r"\bgit\b[^;&|\n]*\bcommit\b")

# Only the agent's file writes bind its run label: a Bash
# string or a Read can name any other run's files at will.
WRITE_TOOLS = {"Write", "Edit", "MultiEdit"}


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


def is_separator(word: str) -> bool:
    return word != "" and set(word) <= set("();<>|&")


def get_shell_script(words: list[str], shell_index: int) -> str | None:
    # Returns the -c string, SHELL_READS_STDIN, or None when the
    # shell runs a script file.
    index = shell_index + 1
    while index < len(words) and not is_separator(words[index]):
        option = words[index]
        if option in SHELL_OPTIONS_TAKING_A_VALUE:
            index += 2
        elif option.startswith("-") and not option.startswith("--") and "c" in option:
            return words[index + 1] if index + 1 < len(words) else SHELL_READS_STDIN
        elif option.startswith(("-", "+")):
            index += 1
        else:
            return None
    return SHELL_READS_STDIN


def get_eval_script(words: list[str], eval_index: int) -> str:
    arguments = []
    for word in words[eval_index + 1 :]:
        if is_separator(word):
            break
        arguments.append(word)
    return " ".join(arguments)


def get_substituted_script(word: str) -> str | None:
    # A quoted $(...) or `...` stays one shell word, so its
    # command is read back out of that word.
    if "$(" not in word and "`" not in word:
        return None
    return word.replace("$(", ";").replace("`", ";").replace(")", ";")


def get_handed_script(words: list[str], index: int) -> str | None:
    if Path(words[index]).name in SHELLS:
        return get_shell_script(words, index)
    if words[index] == "eval":
        return get_eval_script(words, index)
    return None


def get_handed_scripts(words: list[str]) -> list[str | None]:
    return [get_handed_script(words, index) for index in range(len(words))]


def get_nested_scripts(words: list[str], text: str) -> list[str]:
    whole_text = [text.replace("`", ";")] if "`" in text else []
    scripts = [*map(get_substituted_script, words), *get_handed_scripts(words), *whole_text]
    return [script for script in scripts if script is not None]


def names_git_commit(words: list[str]) -> bool:
    subcommands = [get_git_subcommand(words, index) for index, word in enumerate(words) if Path(word).name == "git"]
    return "commit" in subcommands


def runs_git_commit(command: str, depth: int = 0) -> bool:
    # A heredoc body or a quoted argument is data, so the
    # call that appends "git commit" text to the evidence
    # file is never read as a commit.
    text = parse_shell_command.strip_heredoc_bodies(command)
    words = get_shell_words(text)
    if words is None or depth > MAX_NESTED_SCRIPTS:
        return True

    nested_scripts = get_nested_scripts(words, text)
    return names_git_commit(words) or any(runs_nested_commit(script, command, depth) for script in nested_scripts)


def runs_nested_commit(script: str, command: str, depth: int) -> bool:
    if script == SHELL_READS_STDIN:
        return RAW_GIT_COMMIT.search(command) is not None
    return runs_git_commit(script, depth + 1)


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


def get_written_label(block: dict) -> str | None:
    tool_input = block.get("input")
    is_file_write = block.get("type") == "tool_use" and block.get("name") in WRITE_TOOLS
    if not is_file_write or not isinstance(tool_input, dict):
        return None
    match = RUN_FILE_LABEL.search(str(tool_input.get("file_path", "")))
    return match.group(1) if match else None


def get_written_labels(records: list[dict]) -> list[str]:
    # The dispatch prompt's prose is not a tool call, so a
    # sibling or prior run's files named there never count.
    labels = {get_written_label(block) for block in report_files.iter_assistant_blocks(records)}
    return sorted(label for label in labels if label is not None)


def get_run_start(records: list[dict]) -> float | None:
    starts = []
    for record in records:
        stamp = record.get("timestamp")
        try:
            starts.append(datetime.fromisoformat(str(stamp).replace("Z", "+00:00")).timestamp())
        except ValueError:
            continue
    return min(starts) if starts else None


def get_staleness_problem(evidence_path: Path, records: list[dict]) -> str | None:
    # An evidence file this run never wrote to proves another
    # run's attempt, however well-formed its entries are.
    run_start = get_run_start(records)
    if run_start is None:
        return f"{evidence_path} cannot be checked against this run's start: its transcript carries no timestamp"
    if evidence_path.stat().st_mtime < run_start:
        return f"{evidence_path} was last written before this run started, so it records another run's attempt"
    return None


def get_evidence_problem(evidence_path: Path) -> str | None:
    try:
        text = evidence_path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return f"{evidence_path} does not exist"
    except OSError as error:
        return f"{evidence_path} cannot be read ({error})"

    # A re-dispatch appends to the same file, so only a GREEN
    # after the latest RED proves this attempt went green.
    entry_kinds = ENTRY_HEADER.findall(text)
    if "RED" not in entry_kinds:
        return f"{evidence_path} holds no {RED_HEADER} entry"
    latest_red_index = len(entry_kinds) - 1 - entry_kinds[::-1].index("RED")
    if "GREEN" not in entry_kinds[latest_red_index + 1 :]:
        return f"{evidence_path} holds no {GREEN_HEADER} entry after its latest RED entry"
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
    records = report_files.read_transcript_records(str(transcript_path)) if transcript_path is not None else []
    labels = get_written_labels(records)
    if not labels:
        return (
            "no Write or Edit of this run created its checklist or evidence file, so its run label "
            f"is unknown. Write {report_files.CHECKLIST_TEMPLATE} and append to "
            f"{report_files.EVIDENCE_TEMPLATE} under your run label first"
        )
    if len(labels) > 1:
        evidence_paths = ", ".join(EVIDENCE_PATH.format(label=label) for label in labels)
        return f"this run's file writes name {len(labels)} run labels ({evidence_paths}); one run owns one label"

    evidence_path = Path(EVIDENCE_PATH.format(label=labels[0]))
    return get_evidence_problem(evidence_path) or get_staleness_problem(evidence_path, records)


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
