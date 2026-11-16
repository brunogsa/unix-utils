#!/usr/bin/env python3
# check-tdd-coder-commit-evidence.py - deny a tdd-coder Bash
#   call that may run a git commit until its run's evidence
#   file holds a RED entry followed by a GREEN entry.
#
# Usage (tdd-coder frontmatter PreToolUse Bash hook):
#   check-tdd-coder-commit-evidence.py
#
# stdin: the PreToolUse hook payload, as JSON
# reads: the agent's own JSONL transcript, for the run label,
#   /tmp/tdd-coder_evidences_<run-label>.txt, and the git
#   aliases visible from the payload's cwd
#
# stdout: a PreToolUse deny decision as JSON when a possible
#   commit lacks that evidence; nothing otherwise
# exit: always 0; stdin that is not a JSON object fails open
#
# The gated agent is the adversary, so this screens instead of
# parsing: any call whose raw text names the word commit, or
# runs a git alias whose value does, is a possible commit.
#
# Known limits: a name built at run time - concatenated
# strings, base64, an env var holding "commit" - passes the
# screen. The real check stays with the caller, who re-runs
# Verification and reads the evidence file's entry order.

import importlib.util
import json
import re
import shlex
import subprocess
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

# A path such as check-tdd-coder-commit-evidence.test.py is
# not the word, so Verification itself is never screened out.
COMMIT_WORD = re.compile(r"(?<![\w./-])commit(?:-tree)?(?![\w./-])", re.IGNORECASE)
GIT_WORD = re.compile(r"\bgit\b")
GIT_TIMEOUT_SECONDS = 3

# A newline ends a command just as ; does, so a heredoc's
# closing delimiter line reads as its own command.
SHELL_PUNCTUATION = "();<>|&\n"

SCREEN_GUIDANCE = (
    "This hook screens every Bash call: one whose text names the word commit, or runs a git alias "
    "whose value names it, counts as a possible commit. If this call is no commit, reword it so it "
    "no longer does that; if it is one, append the GREEN entry first"
)

# Only the agent's file writes bind its run label: a Bash
# string or a Read can name any other run's files at will.
WRITE_TOOLS = {"Write", "Edit", "MultiEdit"}


def read_payload() -> dict | None:
    try:
        payload = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def get_shell_words(text: str) -> list[str] | None:
    lexer = shlex.shlex(text, posix=True, punctuation_chars=SHELL_PUNCTUATION)
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    try:
        return list(lexer)
    except ValueError:
        return None


def run_git(cwd: str | None, *arguments: str) -> subprocess.CompletedProcess | None:
    try:
        return subprocess.run(
            ["git", *arguments], cwd=cwd, capture_output=True, text=True, timeout=GIT_TIMEOUT_SECONDS, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def get_alias_values(cwd: str | None) -> dict[str, str] | None:
    # Exit 1 means no alias is set; any other failure leaves
    # the aliases unknown, which the caller reads as a commit.
    result = run_git(cwd, "config", "--get-regexp", r"^alias\.")
    if result is None or result.returncode not in (0, 1):
        return None
    pairs = (line.partition(" ") for line in result.stdout.splitlines())
    return {name.removeprefix("alias."): value for name, _, value in pairs}


def get_word_pattern(names: set[str]) -> re.Pattern | None:
    if not names:
        return None
    alternatives = "|".join(sorted(map(re.escape, names)))
    return re.compile(rf"(?<![\w.-])(?:{alternatives})(?![\w.-])")


def get_commit_aliases(values: dict[str, str]) -> set[str]:
    # An alias may run another alias, so the set grows until
    # no further alias names one already in it.
    names: set[str] = set()
    while True:
        pattern = get_word_pattern(names)
        found = {name for name, value in values.items() if COMMIT_WORD.search(value) or (pattern and pattern.search(value))}
        if found == names:
            return names
        names = found


def runs_commit_alias(command: str, cwd: str | None) -> bool:
    if not GIT_WORD.search(command):
        return False
    values = get_alias_values(cwd)
    if values is None:
        return True
    pattern = get_word_pattern(get_commit_aliases(values))
    return pattern is not None and pattern.search(command) is not None


def is_possible_commit(command: str, cwd: str | None) -> bool:
    # The raw text includes heredoc bodies and quoted code, so
    # a script fed to any interpreter is screened with it.
    if COMMIT_WORD.search(command):
        return True
    if get_shell_words(parse_shell_command.strip_heredoc_bodies(command)) is None:
        return True
    return runs_commit_alias(command, cwd)


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
        f"never reconstructed afterwards: {problem}. {SCREEN_GUIDANCE}."
    )
    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
    print(json.dumps(output))


def get_label_problem(labels: list[str]) -> str | None:
    if not labels:
        return (
            "no Write or Edit of this run created its checklist or evidence file, so its run label "
            f"is unknown. Write {report_files.CHECKLIST_TEMPLATE} and append to "
            f"{report_files.EVIDENCE_TEMPLATE} under your run label first"
        )
    if len(labels) > 1:
        evidence_paths = ", ".join(EVIDENCE_PATH.format(label=label) for label in labels)
        return f"this run's file writes name {len(labels)} run labels ({evidence_paths}); one run owns one label"
    return None


def get_commit_problem(payload: dict, command: str) -> str | None:
    cwd = payload.get("cwd") if isinstance(payload.get("cwd"), str) else None
    if not is_possible_commit(command, cwd):
        return None

    transcript_path = get_agent_transcript_path(payload)
    records = report_files.read_transcript_records(str(transcript_path)) if transcript_path is not None else []
    labels = get_written_labels(records)
    label_problem = get_label_problem(labels)
    if label_problem is not None:
        return label_problem

    evidence_path = Path(EVIDENCE_PATH.format(label=labels[0]))
    return get_evidence_problem(evidence_path) or get_staleness_problem(evidence_path, records)


def get_tdd_coder_command(payload: dict | None) -> str | None:
    # A nested Explore's call can reach this agent's hooks, and
    # main never carries tdd-coder as its agent_type.
    is_tdd_coder = payload is not None and payload.get("agent_type") == report_files.AGENT_TYPE
    tool_input = payload.get("tool_input") if is_tdd_coder else None
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    return command if isinstance(command, str) else None


def main() -> int:
    payload = read_payload()
    command = get_tdd_coder_command(payload)
    if command is None:
        return 0

    problem = get_commit_problem(payload, command)
    if problem is not None:
        print_deny(problem)
    return 0


if __name__ == "__main__":
    sys.exit(main())
