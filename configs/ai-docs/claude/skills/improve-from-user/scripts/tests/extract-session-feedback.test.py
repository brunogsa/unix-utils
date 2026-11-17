"""Blackbox CLI tests for extract-session-feedback.py, plus one
in-process test of its count_real_user_turns function.

Each CLI test writes JSONL transcripts into a tmp_path project
directory and passes it through --project-dirs, so no test
reads the real ~/.claude/projects or resolves the default
read scope.

Usage:
  ./run-tests.py <this file>
"""

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "extract-session-feedback.py"

DAY = 86400

# What Claude Code injects as a type "user" record when a
# background subagent or command finishes - harness text, not
# the user's words. The leading newline checks that the filter
# still matches after whitespace.
BACKGROUND_TASK_NOTIFICATION = (
    "\n<task-notification>\n<task-id>b7f3c2a1</task-id>\n<status>completed</status>\n"
    '<summary>Background command "Run the test suite" completed (exit code 0)</summary>\n'
    "</task-notification>"
)


def _load_script_module():
    spec = importlib.util.spec_from_file_location("extract_session_feedback", SCRIPT)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot build an import spec for {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _user_line(text, timestamp="2026-01-01T00:00:00"):
    return json.dumps({"type": "user", "timestamp": timestamp, "message": {"content": text}})


def _assistant_line(text):
    return json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}})


def _two_turn_lines(first_turn, second_turn):
    return [
        _user_line(first_turn),
        _assistant_line("ack"),
        _user_line(second_turn, timestamp="2026-01-01T00:01:00"),
        _assistant_line("ack2"),
    ]


def _write_transcript(path, lines, seconds_ago=0):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    modified_at = path.stat().st_mtime - seconds_ago
    os.utime(path, (modified_at, modified_at))


def _run_script(args, session_id=None):
    # The inherited environment carries coverage's subprocess
    # hook; the running-session id is set or cleared explicitly.
    env = {**os.environ}
    env.pop("CLAUDE_CODE_SESSION_ID", None)
    if session_id:
        env["CLAUDE_CODE_SESSION_ID"] = session_id
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        env=env,
    )


class TestHappyPath:
    def test_should_select_a_transcript_modified_in_the_since_window_with_two_real_user_turns(self, tmp_path):
        _write_transcript(
            tmp_path / "qualifies.jsonl",
            _two_turn_lines("first real user correction about the API contract", "second real user correction about the same contract"),
            seconds_ago=DAY,
        )

        result = _run_script(["--since", "7", "--project-dirs", str(tmp_path)])

        assert "qualifies.jsonl" in result.stdout

    def test_should_skip_a_transcript_modified_before_the_since_window(self, tmp_path):
        _write_transcript(
            tmp_path / "too_old.jsonl",
            _two_turn_lines("an old correction outside the window", "a second old correction outside the window"),
            seconds_ago=10 * DAY,
        )

        result = _run_script(["--since", "7", "--project-dirs", str(tmp_path)])

        assert "too_old.jsonl" not in result.stdout

    def test_should_skip_a_transcript_with_fewer_than_two_real_user_turns(self, tmp_path):
        _write_transcript(
            tmp_path / "too_few_turns.jsonl",
            [_user_line("only one real user turn in this file"), _assistant_line("ack")],
            seconds_ago=DAY,
        )

        result = _run_script(["--since", "7", "--project-dirs", str(tmp_path)])

        assert "too_few_turns.jsonl" not in result.stdout

    def test_should_print_the_corpus_survey_before_any_session_content(self, tmp_path):
        _write_transcript(
            tmp_path / "session_one.jsonl",
            _two_turn_lines("first session first real user correction", "first session second real user correction"),
            seconds_ago=DAY,
        )
        _write_transcript(
            tmp_path / "session_two.jsonl",
            _two_turn_lines("second session first real user correction", "second session second real user correction"),
            seconds_ago=DAY,
        )

        result = _run_script(["--since", "7", "--project-dirs", str(tmp_path)])

        output_lines = result.stdout.splitlines()
        survey_index = next(i for i, line in enumerate(output_lines) if line.startswith("# corpus survey"))
        session_index = next(i for i, line in enumerate(output_lines) if line.startswith("## Session"))
        assert survey_index < session_index


class TestCornerCases:
    def test_should_skip_the_running_sessions_own_transcript_even_when_it_qualifies(self, tmp_path):
        _write_transcript(
            tmp_path / "current-session-id.jsonl",
            _two_turn_lines("this run mining its own prompts, first turn", "this run mining its own prompts, second turn"),
            seconds_ago=DAY,
        )
        _write_transcript(
            tmp_path / "other-session-id.jsonl",
            _two_turn_lines("an unrelated other session, first turn", "an unrelated other session, second turn"),
            seconds_ago=DAY,
        )

        result = _run_script(["--since", "7", "--project-dirs", str(tmp_path)], session_id="current-session-id")

        assert "current-session-id.jsonl" not in result.stdout

    def test_should_keep_other_qualifying_transcripts_when_the_running_session_is_excluded(self, tmp_path):
        _write_transcript(
            tmp_path / "current-session-id.jsonl",
            _two_turn_lines("this run mining its own prompts, first turn", "this run mining its own prompts, second turn"),
            seconds_ago=DAY,
        )
        _write_transcript(
            tmp_path / "other-session-id.jsonl",
            _two_turn_lines("an unrelated other session, first turn", "an unrelated other session, second turn"),
            seconds_ago=DAY,
        )

        result = _run_script(["--since", "7", "--project-dirs", str(tmp_path)], session_id="current-session-id")

        assert "other-session-id.jsonl" in result.stdout

    def test_should_include_a_transcript_modified_6_days_ago_when_since_is_omitted(self, tmp_path):
        _write_transcript(
            tmp_path / "within_default.jsonl",
            _two_turn_lines("six days ago first real user correction", "six days ago second real user correction"),
            seconds_ago=6 * DAY,
        )

        result = _run_script(["--project-dirs", str(tmp_path)])

        assert "within_default.jsonl" in result.stdout

    def test_should_skip_a_transcript_modified_10_days_ago_when_since_is_omitted(self, tmp_path):
        _write_transcript(
            tmp_path / "outside_default.jsonl",
            _two_turn_lines("ten days ago first real user correction", "ten days ago second real user correction"),
            seconds_ago=10 * DAY,
        )

        result = _run_script(["--project-dirs", str(tmp_path)])

        assert "outside_default.jsonl" not in result.stdout

    def test_should_report_zero_qualifying_sessions_when_the_project_dir_holds_no_transcripts(self, tmp_path):
        result = _run_script(["--since", "7", "--project-dirs", str(tmp_path)])

        assert "0 qualifying sessions" in result.stdout

    def test_should_print_no_estimated_tokens_line_when_zero_sessions_qualify(self, tmp_path):
        result = _run_script(["--since", "7", "--project-dirs", str(tmp_path)])

        assert "estimated tokens" not in result.stdout

    def test_should_still_exit_0_when_a_live_appending_transcript_ends_in_a_malformed_line(self, tmp_path):
        lines = _two_turn_lines("first real user correction before truncation", "second real user correction before truncation")
        lines.append('{"type":"user","timestamp":"2026-01-01T00:02:00","message":{"content":"trunc')
        _write_transcript(tmp_path / "live_appending.jsonl", lines, seconds_ago=DAY)

        result = _run_script(["--since", "7", "--project-dirs", str(tmp_path)])

        assert result.returncode == 0

    def test_should_keep_the_turns_before_a_malformed_trailing_line(self, tmp_path):
        lines = _two_turn_lines("first real user correction before truncation", "second real user correction before truncation")
        lines.append('{"type":"user","timestamp":"2026-01-01T00:02:00","message":{"content":"trunc')
        _write_transcript(tmp_path / "live_appending.jsonl", lines, seconds_ago=DAY)

        result = _run_script(["--since", "7", "--project-dirs", str(tmp_path)])

        assert "second real user correction before truncation" in result.stdout

    def test_should_mark_a_7000_char_user_turn_as_truncated_with_its_full_length(self, tmp_path):
        lines = [
            _user_line("x" * 7000),
            _assistant_line("ack"),
            _user_line("a short second real user turn", timestamp="2026-01-01T00:01:00"),
            _assistant_line("ack2"),
        ]
        _write_transcript(tmp_path / "oversized_turn.jsonl", lines, seconds_ago=DAY)

        result = _run_script(["--since", "7", "--project-dirs", str(tmp_path)])

        assert "…[truncated, 7000 chars total]" in result.stdout

    def test_should_still_count_a_truncated_user_turn_toward_the_two_turn_filter(self, tmp_path):
        lines = [
            _user_line("x" * 7000),
            _assistant_line("ack"),
            _user_line("a short second real user turn", timestamp="2026-01-01T00:01:00"),
            _assistant_line("ack2"),
        ]
        _write_transcript(tmp_path / "oversized_turn.jsonl", lines, seconds_ago=DAY)

        result = _run_script(["--since", "7", "--project-dirs", str(tmp_path)])

        assert "oversized_turn.jsonl" in result.stdout

    def test_should_count_only_real_user_prose_turns_not_tool_result_meta_slash_command_or_compaction_summary(self, tmp_path):
        fixture = tmp_path / "mixed_turns.jsonl"
        fixture.write_text(
            "\n".join(
                [
                    json.dumps({"type": "user", "message": {"content": "a real prose correction about the API contract"}}),
                    json.dumps({"type": "user", "isMeta": True, "message": {"content": "meta housekeeping turn"}}),
                    json.dumps({"type": "user", "message": {"content": [{"type": "tool_result", "content": "tool output"}]}}),
                    json.dumps({"type": "user", "message": {"content": "<command-name>improve-from-user</command-name>\n<command-message>run it</command-message>"}}),
                    json.dumps({"type": "user", "isCompactSummary": True, "message": {"content": "compaction summary text"}}),
                    _assistant_line("ack"),
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        count = _load_script_module().count_real_user_turns(str(fixture))

        assert count == 1

    def test_should_skip_a_transcript_whose_only_second_user_turn_is_a_background_task_notification(self, tmp_path):
        _write_transcript(
            tmp_path / "one_real_turn_plus_notification.jsonl",
            _two_turn_lines("the only real user correction in this session", BACKGROUND_TASK_NOTIFICATION),
            seconds_ago=DAY,
        )

        result = _run_script(["--since", "7", "--project-dirs", str(tmp_path)])

        assert "one_real_turn_plus_notification.jsonl" not in result.stdout

    def test_should_leave_background_task_notifications_out_of_the_survey_turn_count(self, tmp_path):
        lines = _two_turn_lines("first real user correction about retries", "second real user correction about retries")
        lines.append(_user_line(BACKGROUND_TASK_NOTIFICATION, timestamp="2026-01-01T00:02:00"))
        _write_transcript(tmp_path / "with_notification.jsonl", lines, seconds_ago=DAY)

        result = _run_script(["--since", "7", "--project-dirs", str(tmp_path)])

        assert "1 files · 2 real user turns" in result.stdout

    def test_should_leave_background_task_notifications_out_of_the_emitted_user_turns(self, tmp_path):
        lines = _two_turn_lines("first real user correction about retries", "second real user correction about retries")
        lines.append(_user_line(BACKGROUND_TASK_NOTIFICATION, timestamp="2026-01-01T00:02:00"))
        _write_transcript(tmp_path / "with_notification.jsonl", lines, seconds_ago=DAY)

        result = _run_script(["--since", "7", "--project-dirs", str(tmp_path)])

        assert "task-notification" not in result.stdout


class TestSurveyEstimate:
    def test_should_estimate_the_size_of_the_extract_text_that_follows_the_survey_line(self, tmp_path):
        # Short turns make the per-turn header, NEXT line and
        # session header a large share of the emitted text.
        lines = []
        for n in range(20):
            lines.append(_user_line(f"fix {n}", timestamp=f"2026-01-01T00:{n:02d}:00"))
            lines.append(_assistant_line(f"ok {n}"))
        _write_transcript(tmp_path / "short_turns.jsonl", lines, seconds_ago=DAY)

        result = _run_script(["--since", "7", "--project-dirs", str(tmp_path)])

        survey_line, extract_text = result.stdout.split("\n", 1)
        reported = int(survey_line.rsplit("~", 1)[1].split(" ")[0])
        assert reported == len(extract_text) // 4


class TestBrokenPipe:
    def test_should_exit_quietly_when_the_reader_closes_stdout_early(self, tmp_path):
        # ~150KB of output overflows the 64KB pipe buffer, so
        # the write lands after the reader is gone.
        lines = []
        for n in range(30):
            lines.append(_user_line("x" * 5000, timestamp=f"2026-01-01T00:{n:02d}:00"))
            lines.append(_assistant_line("ack"))
        _write_transcript(tmp_path / "big.jsonl", lines, seconds_ago=DAY)
        env = {**os.environ}
        env.pop("CLAUDE_CODE_SESSION_ID", None)

        proc = subprocess.Popen(
            [sys.executable, str(SCRIPT), "--since", "7", "--project-dirs", str(tmp_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )
        proc.stdout.readline()
        proc.stdout.close()
        stderr = proc.stderr.read()
        proc.wait()

        assert "Traceback" not in stderr and "BrokenPipeError" not in stderr


class TestFailureScenarios:
    def test_should_exit_nonzero_when_given_the_removed_session_id_project_dir_and_cwd_flags(self):
        result = _run_script(["--session-id", "fake-session", "--project-dir", "/nonexistent", "--cwd", "/nonexistent"])

        assert result.returncode != 0

    def test_should_report_unrecognized_arguments_when_given_the_removed_session_id_project_dir_and_cwd_flags(self):
        result = _run_script(["--session-id", "fake-session", "--project-dir", "/nonexistent", "--cwd", "/nonexistent"])

        assert "unrecognized arguments" in result.stderr
