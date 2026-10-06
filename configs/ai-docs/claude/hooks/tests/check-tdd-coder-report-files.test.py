"""pytest suite for check-tdd-coder-report-files.py.

The hook takes the report from the SubagentStop payload's
last_assistant_message, or from the agent's own JSONL transcript when that
field is absent, and checks the /tmp files it names. Every case writes real
run files under /tmp with a label unique to this test run, writes any
transcript under tmp_path in the record shapes a real subagent transcript
holds, feeds a realistic payload, and removes the files afterwards. Nothing
inside the hook is stubbed.

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


OMITTED = object()


def payload(
    last_assistant_message=OMITTED,
    stop_hook_active=False,
    agent_type="tdd-coder",
    agent_transcript_path=OMITTED,
    transcript_path=OMITTED,
):
    """A SubagentStop payload; a field passed as OMITTED is left out, the
    way Claude Code 2.1.290 leaves out last_assistant_message."""
    fields = {
        "session_id": "23c8cc27-309f-45ef-8092-971beda32766",
        "cwd": "/Users/brunoagostini/unix-utils",
        "hook_event_name": "SubagentStop",
        "stop_hook_active": stop_hook_active,
        "agent_type": agent_type,
        "agent_id": "a7f3c9e1b2d4",
        "agent_transcript_path": agent_transcript_path,
        "transcript_path": transcript_path,
        "last_assistant_message": last_assistant_message,
    }
    return {key: value for key, value in fields.items() if value is not OMITTED}


def handback_record(report_text):
    """The assistant record of a SubagentHandback tool call."""
    return {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": "toolu_01KbE4X6FvgbGqqJ4QmTYcNo",
                    "name": "SubagentHandback",
                    "input": {"message": report_text},
                    "caller": {"type": "direct"},
                }
            ],
        },
    }


def text_record(text):
    """An assistant record holding one text block."""
    return {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": text}]}}


def bash_call_record():
    """An assistant record calling a tool other than SubagentHandback."""
    return {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [{"type": "tool_use", "id": "toolu_01Bash", "name": "Bash", "input": {"command": "git status"}}],
        },
    }


def prompt_record():
    """The user record carrying the dispatch prompt."""
    return {"type": "user", "message": {"role": "user", "content": "Run label: pytest-report-files"}}


def tool_result_record():
    """The user record carrying a tool call's result."""
    return {
        "type": "user",
        "message": {
            "role": "user",
            "content": [
                {
                    "tool_use_id": "toolu_01KbE4X6FvgbGqqJ4QmTYcNo",
                    "type": "tool_result",
                    "content": [{"type": "text", "text": '{"success":true,"message":"Report delivered to your caller."}'}],
                }
            ],
        },
    }


def prompt_snapshot_record():
    """The attachment record Claude Code writes around a handback."""
    return {"type": "attachment", "attachment": {"type": "prompt_snapshot", "systemPrompt": ["## Objective"]}}


def date_attachment_record():
    """An attachment record of the kind that can follow a text reply."""
    return {"type": "attachment", "attachment": {"type": "date", "date": "2026-10-06"}}


def write_transcript(path, records, trailing_newline=True):
    """Write JSONL the way Claude Code does: raw UTF-8, one record per line.
    A bytes item is written as-is, to plant a broken line."""
    lines = [r if isinstance(r, bytes) else json.dumps(r, ensure_ascii=False).encode("utf-8") for r in records]
    path.write_bytes(b"\n".join(lines) + (b"\n" if trailing_newline else b""))
    return str(path)


@pytest.fixture
def transcript(tmp_path):
    """The agent's own transcript path, under tmp_path."""
    return tmp_path / "agent-a7f3c9e1b2d4.jsonl"


def assert_let_through(result):
    """Assert the hook exited 0 and printed nothing."""
    assert result.stdout == ""
    assert result.returncode == 0


def assert_could_not_read_block(result):
    """Assert the hook blocked with its could-not-read reason."""
    reason = block_reason(result)
    assert "could not read" in reason
    assert "unchecked" in reason
    assert "end naming both" in reason
    assert "second stop ends the run" in reason


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


class TestReportFromTheAgentTranscript:
    @pytest.mark.parametrize(
        "records_after_handback",
        [[tool_result_record(), prompt_snapshot_record()], [prompt_snapshot_record(), tool_result_record()]],
        ids=["tool-result-then-snapshot", "snapshot-then-tool-result"],
    )
    def test_should_let_the_stop_through_when_the_handback_names_both_existing_run_files(
        self, run_files, transcript, records_after_handback
    ):
        records = [prompt_record(), bash_call_record(), handback_record(report(EVIDENCE, CHECKLIST))]
        transcript_path = write_transcript(transcript, records + records_after_handback)

        result = run_hook(json.dumps(payload(agent_transcript_path=transcript_path)))

        assert_let_through(result)

    @pytest.mark.parametrize(
        "records_after_handback",
        [[tool_result_record(), prompt_snapshot_record()], [prompt_snapshot_record(), tool_result_record()]],
        ids=["tool-result-then-snapshot", "snapshot-then-tool-result"],
    )
    def test_should_block_naming_the_file_when_the_handback_names_a_missing_run_file(
        self, run_files, transcript, records_after_handback
    ):
        EVIDENCE.unlink()
        records = [prompt_record(), handback_record(report(EVIDENCE, CHECKLIST))]
        transcript_path = write_transcript(transcript, records + records_after_handback)

        result = run_hook(json.dumps(payload(agent_transcript_path=transcript_path)))

        assert f"{EVIDENCE} does not exist" in block_reason(result)

    def test_should_block_when_an_earlier_handback_is_compliant_but_the_last_one_is_not(self, run_files, transcript):
        transcript_path = write_transcript(
            transcript,
            [
                handback_record(report(EVIDENCE, CHECKLIST)),
                tool_result_record(),
                handback_record(report(CHECKLIST)),
                tool_result_record(),
            ],
        )

        result = run_hook(json.dumps(payload(agent_transcript_path=transcript_path)))

        assert "the report names no evidence file path" in block_reason(result)

    def test_should_let_the_stop_through_when_the_last_handback_is_compliant_after_a_failing_one(
        self, run_files, transcript
    ):
        transcript_path = write_transcript(
            transcript,
            [
                handback_record(report(CHECKLIST)),
                tool_result_record(),
                handback_record(report(EVIDENCE, CHECKLIST)),
                tool_result_record(),
            ],
        )

        result = run_hook(json.dumps(payload(agent_transcript_path=transcript_path)))

        assert_let_through(result)

    def test_should_let_the_stop_through_when_a_plain_text_reply_names_both_existing_run_files(
        self, run_files, transcript
    ):
        transcript_path = write_transcript(transcript, [prompt_record(), text_record(report(EVIDENCE, CHECKLIST))])

        result = run_hook(json.dumps(payload(agent_transcript_path=transcript_path)))

        assert_let_through(result)

    def test_should_block_when_a_plain_text_reply_followed_by_an_attachment_names_no_checklist(
        self, run_files, transcript
    ):
        transcript_path = write_transcript(
            transcript, [prompt_record(), text_record(report(EVIDENCE)), date_attachment_record()]
        )

        result = run_hook(json.dumps(payload(agent_transcript_path=transcript_path)))

        assert "the report names no checklist path" in block_reason(result)

    def test_should_skip_a_broken_line_mid_file_and_a_truncated_last_line(self, run_files, transcript):
        EVIDENCE.unlink()
        truncated_compliant_handback = json.dumps(handback_record(report(EVIDENCE, CHECKLIST))).encode("utf-8")[:-40]
        transcript_path = write_transcript(
            transcript,
            [
                handback_record(report(EVIDENCE, CHECKLIST)),
                b'{"type": "user", "message": {"role"',
                b"\xff\xfe not utf-8",
                b'["a", "json", "array"]',
                tool_result_record(),
                truncated_compliant_handback,
            ],
            trailing_newline=False,
        )

        result = run_hook(json.dumps(payload(agent_transcript_path=transcript_path)))

        assert f"{EVIDENCE} does not exist" in block_reason(result)

    def test_should_read_a_report_holding_a_raw_line_separator_character(self, run_files, transcript):
        EVIDENCE.unlink()
        report_text = "**Notes**: a pasted log line ended here\n" + report(EVIDENCE, CHECKLIST)
        transcript_path = write_transcript(transcript, [handback_record(report_text), tool_result_record()])
        assert " ".encode("utf-8") in transcript.read_bytes()

        result = run_hook(json.dumps(payload(agent_transcript_path=transcript_path)))

        assert f"{EVIDENCE} does not exist" in block_reason(result)

    def test_should_block_when_the_parent_transcript_is_compliant_but_the_agent_transcript_is_not(
        self, run_files, tmp_path, transcript
    ):
        parent_path = write_transcript(tmp_path / "parent.jsonl", [text_record(report(EVIDENCE, CHECKLIST))])
        agent_path = write_transcript(transcript, [handback_record(report(CHECKLIST)), tool_result_record()])

        result = run_hook(json.dumps(payload(agent_transcript_path=agent_path, transcript_path=parent_path)))

        assert "the report names no evidence file path" in block_reason(result)

    def test_should_check_the_payload_report_over_the_transcript_when_the_payload_carries_one(
        self, run_files, transcript
    ):
        transcript_path = write_transcript(transcript, [handback_record(report(CHECKLIST)), tool_result_record()])

        result = run_hook(
            json.dumps(payload(report(EVIDENCE, CHECKLIST), agent_transcript_path=transcript_path))
        )

        assert_let_through(result)

    def test_should_read_the_transcript_when_the_payload_report_is_an_empty_string(self, run_files, transcript):
        transcript_path = write_transcript(
            transcript, [handback_record(report(EVIDENCE, CHECKLIST)), tool_result_record()]
        )

        result = run_hook(json.dumps(payload("", agent_transcript_path=transcript_path)))

        assert_let_through(result)


def transcript_without_report(tmp_path):
    """A transcript with a prompt and a Bash call but no handback and no text."""
    return write_transcript(
        tmp_path / "agent-no-report.jsonl", [prompt_record(), bash_call_record(), tool_result_record()]
    )


def empty_transcript(tmp_path):
    """A transcript file with zero bytes."""
    path = tmp_path / "agent-empty.jsonl"
    path.write_bytes(b"")
    return str(path)


class TestReportThatCannotBeRead:
    @pytest.mark.parametrize(
        "build_payload",
        [
            lambda tmp_path: {"hook_event_name": "SubagentStop", "stop_hook_active": False, "agent_type": "tdd-coder"},
            lambda tmp_path: payload(None),
            lambda tmp_path: payload(agent_transcript_path=12345),
            lambda tmp_path: payload(agent_transcript_path=str(tmp_path / "agent-never-written.jsonl")),
            lambda tmp_path: payload(agent_transcript_path=empty_transcript(tmp_path)),
            lambda tmp_path: payload(agent_transcript_path=str(tmp_path)),
            lambda tmp_path: payload(agent_transcript_path=transcript_without_report(tmp_path)),
        ],
        ids=[
            "no-report-field",
            "report-not-text",
            "transcript-path-not-text",
            "transcript-missing",
            "transcript-empty",
            "transcript-is-a-directory",
            "transcript-without-handback-or-text",
        ],
    )
    def test_should_block_once_saying_the_report_could_not_be_read(self, tmp_path, build_payload):
        result = run_hook(json.dumps(build_payload(tmp_path)))

        assert_could_not_read_block(result)


class TestStopsLetThroughUnchecked:
    @pytest.mark.parametrize(
        "stop_hook_active",
        [OMITTED, "false", 0, True],
        ids=["missing", "string-false", "zero", "true"],
    )
    @pytest.mark.parametrize(
        "unread_report", [report(), None], ids=["report-with-file-problems", "report-that-cannot-be-read"]
    )
    def test_should_let_the_stop_through_unless_stop_hook_active_is_exactly_false(
        self, stop_hook_active, unread_report
    ):
        result = run_hook(json.dumps(payload(unread_report, stop_hook_active=stop_hook_active)))

        assert_let_through(result)

    @pytest.mark.parametrize(
        "unread_report", [report(), None], ids=["report-with-file-problems", "report-that-cannot-be-read"]
    )
    def test_should_let_a_nested_explore_stop_through(self, unread_report):
        result = run_hook(json.dumps(payload(unread_report, agent_type="Explore")))

        assert_let_through(result)

    @pytest.mark.parametrize(
        "stdin_text",
        ["not json at all", json.dumps(["a", "json", "array"])],
        ids=["not-json", "json-array"],
    )
    def test_should_fail_open_when_stdin_is_not_a_json_object(self, stdin_text):
        result = run_hook(stdin_text)

        assert_let_through(result)


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
