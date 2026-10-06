"""pytest suite for check-tdd-coder-report-files.py.

The hook reads the SubagentStop payload's last_assistant_message and checks
the /tmp files it names, so every case writes real files under /tmp with a
label unique to this test run, feeds a realistic payload, and removes the
files afterwards. Nothing inside the hook is stubbed.

The last class reads tdd-coder.md itself, so a rename of the hook file or a
rewording of the agent's path templates fails a test here instead of
silently disabling the gate.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
HOOK = HOOKS_DIR / "check-tdd-coder-report-files.py"
AGENT_FILE = HOOKS_DIR.parent / "agents" / "tdd-coder.md"

RUN_LABEL = f"pytest-report-files-{os.getpid()}"
CHECKLIST = Path(f"/tmp/tdd-coder_substeps_{RUN_LABEL}.md")
EVIDENCE = Path(f"/tmp/tdd-coder_evidences_{RUN_LABEL}.txt")

PATH_TEMPLATE_PATTERN = re.compile(r"/tmp/tdd-coder_(?:substeps|evidences)_<run-label>\.(?:md|txt)")


@pytest.fixture
def run_files():
    """Write both run files with real content; remove them afterwards."""
    CHECKLIST.write_text("- [x] Unit 1: RED / CODE / GREEN\n", encoding="utf-8")
    EVIDENCE.write_text("=== GREEN ===\npytest exit 0\n", encoding="utf-8")
    yield
    CHECKLIST.unlink(missing_ok=True)
    EVIDENCE.unlink(missing_ok=True)


def report(*paths):
    """A tdd-coder final report ending with its Evidence and Checklist lines."""
    lines = [
        "**Status**: done",
        "**Commits**: 1a2b3c4d feat(hooks): block a tdd-coder stop missing its run files",
        "**Units**: 1/1 green",
    ]
    lines += [f"**File**: {path}" for path in paths]
    return "\n".join(lines)


def payload(last_assistant_message, stop_hook_active=False, agent_type="tdd-coder"):
    """The documented SubagentStop shape, trimmed to the fields the hook reads."""
    return {
        "session_id": "23c8cc27-309f-45ef-8092-971beda32766",
        "cwd": "/Users/brunoagostini/unix-utils",
        "hook_event_name": "SubagentStop",
        "stop_hook_active": stop_hook_active,
        "agent_type": agent_type,
        "agent_id": "a7f3c9e1b2d4",
        "agent_transcript_path": "/Users/brunoagostini/.claude/projects/x/subagents/agent-a7f3c9e1b2d4.jsonl",
        "last_assistant_message": last_assistant_message,
    }


def run_hook(stdin_text):
    """Run the hook through the interpreter, never a direct exec, so macOS
    XProtect never scans it on first run."""
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=stdin_text,
        capture_output=True,
        text=True,
        check=False,
    )


def block_reason(result):
    """Assert the hook blocked and return its reason."""
    assert result.returncode == 0
    decision = json.loads(result.stdout)
    assert decision["decision"] == "block"
    return decision["reason"]


class TestReportNamingBothRunFiles:
    def test_should_let_the_stop_through_when_both_named_files_exist_with_content(self, run_files):
        result = run_hook(json.dumps(payload(report(EVIDENCE, CHECKLIST))))

        assert result.stdout == ""
        assert result.returncode == 0


class TestBlockedStops:
    def test_should_block_when_the_report_names_no_checklist_path(self, run_files):
        result = run_hook(json.dumps(payload(report(EVIDENCE))))

        reason = block_reason(result)
        assert "checklist" in reason
        assert "/tmp/tdd-coder_substeps_<run-label>.md" in reason

    def test_should_block_when_the_report_names_no_evidence_path(self, run_files):
        result = run_hook(json.dumps(payload(report(CHECKLIST))))

        reason = block_reason(result)
        assert "evidence" in reason
        assert "/tmp/tdd-coder_evidences_<run-label>.txt" in reason

    @pytest.mark.parametrize("named_file", [CHECKLIST, EVIDENCE], ids=["checklist", "evidence"])
    def test_should_block_naming_the_file_when_a_named_run_file_does_not_exist(self, run_files, named_file):
        named_file.unlink()

        result = run_hook(json.dumps(payload(report(EVIDENCE, CHECKLIST))))

        reason = block_reason(result)
        assert f"{named_file} does not exist" in reason

    @pytest.mark.parametrize("named_file", [CHECKLIST, EVIDENCE], ids=["checklist", "evidence"])
    def test_should_block_naming_the_file_when_a_named_run_file_is_empty(self, run_files, named_file):
        named_file.write_text("", encoding="utf-8")

        result = run_hook(json.dumps(payload(report(EVIDENCE, CHECKLIST))))

        reason = block_reason(result)
        assert f"{named_file} is empty" in reason

    def test_should_ask_the_report_to_end_naming_both_paths(self, run_files):
        result = run_hook(json.dumps(payload(report())))

        reason = block_reason(result)
        assert "end naming both" in reason


class TestStopsLetThroughUnchecked:
    def test_should_let_a_second_stop_through_when_a_stop_hook_already_fired(self):
        result = run_hook(json.dumps(payload(report(), stop_hook_active=True)))

        assert result.stdout == ""
        assert result.returncode == 0

    def test_should_let_a_nested_explore_stop_through(self):
        result = run_hook(json.dumps(payload(report(), agent_type="Explore")))

        assert result.stdout == ""
        assert result.returncode == 0

    @pytest.mark.parametrize(
        "stdin_text",
        [
            "not json at all",
            json.dumps(["a", "json", "array"]),
            json.dumps({"hook_event_name": "SubagentStop", "stop_hook_active": False, "agent_type": "tdd-coder"}),
            json.dumps(payload(None)),
        ],
        ids=["not-json", "json-array", "no-report-field", "report-not-text"],
    )
    def test_should_fail_open_when_the_report_text_cannot_be_read(self, stdin_text):
        result = run_hook(stdin_text)

        assert result.stdout == ""
        assert result.returncode == 0


def frontmatter_stop_command():
    """The command wired under hooks: Stop: in tdd-coder.md's frontmatter."""
    frontmatter = AGENT_FILE.read_text(encoding="utf-8").split("---\n")[1]
    match = re.search(r"^  Stop:\n(?:^ {4,}.*\n)*?^ +command: \"(.+)\"$", frontmatter, re.MULTILINE)
    assert match, "tdd-coder.md frontmatter wires no hooks: Stop: command"
    return match.group(1)


def run_stop_command(home, stdin_text):
    """Run the frontmatter Stop command the way Claude Code does, via a shell."""
    return subprocess.run(
        ["bash", "-c", frontmatter_stop_command()],
        input=stdin_text,
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "HOME": str(home)},
    )


class TestAgentFileWiring:
    def test_should_block_through_the_frontmatter_command_when_home_links_this_repo_hooks(self, tmp_path):
        (tmp_path / ".claude").mkdir()
        (tmp_path / ".claude" / "hooks").symlink_to(HOOKS_DIR)

        result = run_stop_command(tmp_path, json.dumps(payload(report())))

        assert json.loads(result.stdout)["decision"] == "block"
        assert result.returncode == 0

    def test_should_let_the_stop_through_when_the_hook_file_is_missing(self, tmp_path):
        result = run_stop_command(tmp_path, json.dumps(payload(report())))

        assert result.stdout == ""
        assert result.returncode == 0

    def test_should_accept_every_run_file_path_template_the_agent_body_names(self):
        templates = set(PATH_TEMPLATE_PATTERN.findall(AGENT_FILE.read_text(encoding="utf-8")))
        filled_paths = [Path(template.replace("<run-label>", RUN_LABEL)) for template in templates]
        assert {path.suffix for path in filled_paths} == {".md", ".txt"}

        try:
            for path in filled_paths:
                path.write_text("filled from the tdd-coder.md template\n", encoding="utf-8")

            result = run_hook(json.dumps(payload(report(*filled_paths))))
        finally:
            for path in filled_paths:
                path.unlink(missing_ok=True)

        assert result.stdout == ""
        assert result.returncode == 0
