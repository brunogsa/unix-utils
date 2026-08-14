"""pytest suite for check-uncollected-background-output.py.

The hook reads only its stdin payload plus the transcript that payload
points at, so every case here writes a synthetic JSONL transcript into
tmp_path and feeds a realistic SubagentStop payload naming it. Nothing is
stubbed: these tests assert the hook's real transcript walk and its
{"decision": "block"} contract.

The two transcript fixtures are the two ways a subagent reaches an
uncollected background job, both copied from the runner's own message
templates rather than invented:

  - agent-initiated   "Command running in background with ID: <id>."
  - harness-initiated "Command did not complete within its <n>s timeout and
                       was moved to the background (ID: <id>)."

They share one literal, "Output is being written to: <path>.", and that
shared literal is what the hook keys on.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parent.parent / "check-uncollected-background-output.py"

# The hook is wired into settings.json as
# `python3 ~/.claude/hooks/<name>.py`, and ~/.claude/hooks is a
# directory symlink into this repo.
#
# One case below runs through that path, because a hook that
# only works when invoked by its repo path never fires in
# production.
SYMLINK_HOOK = Path.home() / ".claude" / "hooks" / "check-uncollected-background-output.py"

SETTINGS = Path(__file__).resolve().parent.parent.parent / "settings.json"

# The realistic values every fixture shares, taken from a
# captured subagent transcript, so a path asserted in one case
# reads as the same job in the next.
SESSION_ID = "9eb4ea50-75a0-4262-b7e2-13609737e0c0"
AGENT_ID = "ad5e5c056fe011303"
TASKS_DIR = f"/private/tmp/claude-503/-Users-brunoagostini-unix-utils/{SESSION_ID}/tasks"
SUITE_JOB_ID = "bnrghbe7c"
SUITE_JOB_OUTPUT = f"{TASKS_DIR}/{SUITE_JOB_ID}.output"
PYTEST_JOB_ID = "b4i4bgxct"
PYTEST_JOB_OUTPUT = f"{TASKS_DIR}/{PYTEST_JOB_ID}.output"


def tool_use(tool_id, name, tool_input):
    """One assistant line carrying a single tool_use block."""
    return {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [
                {"type": "tool_use", "id": tool_id, "name": name, "input": tool_input}
            ],
        },
    }


def bash_call(tool_id, command):
    return tool_use(tool_id, "Bash", {"command": command, "description": "run the repo suite"})


def read_call(tool_id, file_path):
    return tool_use(tool_id, "Read", {"file_path": file_path})


def bash_output_call(tool_id, bash_id):
    return tool_use(tool_id, "BashOutput", {"bash_id": bash_id})


def tool_result(tool_id, content):
    """One user line carrying a plain-string tool_result, the shape the
    runner emits for a Bash result."""
    return {
        "type": "user",
        "message": {
            "role": "user",
            "content": [
                {
                    "tool_use_id": tool_id,
                    "type": "tool_result",
                    "content": content,
                    "is_error": False,
                }
            ],
        },
    }


def agent_backgrounded_result(tool_id, job_id, output_path):
    """The runner's message when the AGENT passed run_in_background: true."""
    return tool_result(
        tool_id,
        f"Command running in background with ID: {job_id}. "
        f"Output is being written to: {output_path}. "
        "If it exits while you are still working you will be notified, but it is "
        "terminated when you give your final response and no notification can follow "
        "that. To check interim output, use Read on that file path.",
    )


def harness_backgrounded_result(tool_id, job_id, output_path):
    """The runner's message when the command ran in the FOREGROUND and the
    harness auto-backgrounded it on timeout. The agent chose nothing here,
    which is why a PreToolUse payload check would miss this case."""
    return tool_result(
        tool_id,
        f"Command did not complete within its 600s timeout and was moved to the "
        f"background (ID: {job_id}). "
        f"Output is being written to: {output_path}. "
        "To check interim output, use Read on that file path.",
    )


def write_transcript(tmp_path, name, entries):
    """Write entries as JSONL and return the path."""
    path = tmp_path / f"{name}.jsonl"
    with path.open("w", encoding="utf-8") as handle:
        for entry in entries:
            handle.write(json.dumps(entry) + "\n")
    return path


def payload(agent_transcript_path, stop_hook_active=False):
    """The captured real SubagentStop shape, trimmed to the fields the hook
    reads. transcript_path (the PARENT session's file) is kept alongside
    agent_transcript_path (the subagent's own) precisely because the runner
    sends both and only the second one holds this agent's tool calls."""
    return {
        "session_id": SESSION_ID,
        "transcript_path": (
            "/Users/brunoagostini/.claude/projects/"
            f"-Users-brunoagostini-unix-utils/{SESSION_ID}.jsonl"
        ),
        "cwd": "/Users/brunoagostini/unix-utils",
        "agent_id": AGENT_ID,
        "agent_type": "",
        "hook_event_name": "SubagentStop",
        "stop_hook_active": stop_hook_active,
        "agent_transcript_path": str(agent_transcript_path),
    }


def run_hook(hook_payload, hook=HOOK):
    """Feed one SubagentStop payload to the hook and return its
    CompletedProcess."""
    return subprocess.run(
        [sys.executable, str(hook)],
        input=json.dumps(hook_payload),
        capture_output=True,
        text=True,
        check=False,
    )


def decision_of(result):
    """The .decision field of the hook's stdout, or "" when it printed
    nothing at all (its silent-allow shape)."""
    if not result.stdout.strip():
        return ""
    return json.loads(result.stdout)["decision"]


def reason_of(result):
    if not result.stdout.strip():
        return ""
    return json.loads(result.stdout)["reason"]


class TestBlocksAnUncollectedBackgroundJob:
    def test_should_block_the_stop_when_the_agent_backgrounded_a_command_itself_and_never_read_its_output(
        self, tmp_path
    ):
        transcript = write_transcript(
            tmp_path,
            "agent-initiated",
            [
                bash_call("toolu_01M2imnnoG9wXKgz7hp8ivKs", "./run-tests.sh"),
                agent_backgrounded_result(
                    "toolu_01M2imnnoG9wXKgz7hp8ivKs", SUITE_JOB_ID, SUITE_JOB_OUTPUT
                ),
            ],
        )

        result = run_hook(payload(transcript))

        assert decision_of(result) == "block", result.stdout + result.stderr
        assert SUITE_JOB_OUTPUT in reason_of(result)

    def test_should_block_the_stop_when_the_harness_auto_backgrounded_a_foreground_command_on_timeout(
        self, tmp_path
    ):
        transcript = write_transcript(
            tmp_path,
            "harness-initiated",
            [
                bash_call(
                    "toolu_01ELHh7pKmXHdT7UNtBFZ8DZ",
                    "./run-tests.sh > /tmp/green.txt 2>&1",
                ),
                harness_backgrounded_result(
                    "toolu_01ELHh7pKmXHdT7UNtBFZ8DZ", SUITE_JOB_ID, SUITE_JOB_OUTPUT
                ),
            ],
        )

        result = run_hook(payload(transcript))

        assert decision_of(result) == "block", result.stdout + result.stderr

    def test_should_block_when_the_only_read_of_the_output_path_happened_before_the_job_was_backgrounded(
        self, tmp_path
    ):
        transcript = write_transcript(
            tmp_path,
            "read-before-job",
            [
                read_call("toolu_01QCmzR6Q5t6CJ2j6XR4kYUr", SUITE_JOB_OUTPUT),
                bash_call("toolu_01M2imnnoG9wXKgz7hp8ivKs", "./run-tests.sh"),
                agent_backgrounded_result(
                    "toolu_01M2imnnoG9wXKgz7hp8ivKs", SUITE_JOB_ID, SUITE_JOB_OUTPUT
                ),
            ],
        )

        result = run_hook(payload(transcript))

        assert decision_of(result) == "block", result.stdout + result.stderr

    def test_should_name_only_the_uncollected_job_when_a_sibling_background_job_was_collected(
        self, tmp_path
    ):
        transcript = write_transcript(
            tmp_path,
            "one-of-two",
            [
                bash_call("toolu_01M2imnnoG9wXKgz7hp8ivKs", "./run-tests.sh"),
                agent_backgrounded_result(
                    "toolu_01M2imnnoG9wXKgz7hp8ivKs", SUITE_JOB_ID, SUITE_JOB_OUTPUT
                ),
                read_call("toolu_01QCmzR6Q5t6CJ2j6XR4kYUr", SUITE_JOB_OUTPUT),
                bash_call("toolu_013rdnbDSsPgJaY7ATC15Fcr", "pytest"),
                agent_backgrounded_result(
                    "toolu_013rdnbDSsPgJaY7ATC15Fcr", PYTEST_JOB_ID, PYTEST_JOB_OUTPUT
                ),
            ],
        )

        result = run_hook(payload(transcript))
        reason = reason_of(result)

        assert decision_of(result) == "block", result.stdout + result.stderr
        assert PYTEST_JOB_OUTPUT in reason
        assert SUITE_JOB_OUTPUT not in reason

    def test_should_still_block_when_a_truncated_final_line_follows_the_backgrounded_job(
        self, tmp_path
    ):
        """A transcript still being written ends mid-line. That must not
        blind the guard to the complete lines before it."""
        transcript = write_transcript(
            tmp_path,
            "truncated-tail",
            [
                bash_call("toolu_01M2imnnoG9wXKgz7hp8ivKs", "./run-tests.sh"),
                agent_backgrounded_result(
                    "toolu_01M2imnnoG9wXKgz7hp8ivKs", SUITE_JOB_ID, SUITE_JOB_OUTPUT
                ),
            ],
        )
        with transcript.open("a", encoding="utf-8") as handle:
            handle.write('{"type": "assistant", "message": {"role": "assistant", "content": [{"typ')

        result = run_hook(payload(transcript))

        assert decision_of(result) == "block", result.stdout + result.stderr

    def test_should_block_the_same_way_when_invoked_through_the_home_hooks_symlink(
        self, tmp_path
    ):
        transcript = write_transcript(
            tmp_path,
            "through-symlink",
            [
                bash_call("toolu_01M2imnnoG9wXKgz7hp8ivKs", "./run-tests.sh"),
                agent_backgrounded_result(
                    "toolu_01M2imnnoG9wXKgz7hp8ivKs", SUITE_JOB_ID, SUITE_JOB_OUTPUT
                ),
            ],
        )

        result = run_hook(payload(transcript), hook=SYMLINK_HOOK)

        assert decision_of(result) == "block", result.stdout + result.stderr


class TestBlockReasonNamesTheFix:
    @pytest.fixture
    def reason(self, tmp_path):
        transcript = write_transcript(
            tmp_path,
            "block-reason",
            [
                bash_call("toolu_01M2imnnoG9wXKgz7hp8ivKs", "./run-tests.sh"),
                agent_backgrounded_result(
                    "toolu_01M2imnnoG9wXKgz7hp8ivKs", SUITE_JOB_ID, SUITE_JOB_OUTPUT
                ),
            ],
        )
        return reason_of(run_hook(payload(transcript)))

    def test_should_tell_the_agent_the_output_is_a_plain_file_it_can_read_right_now(self, reason):
        assert "plain file" in reason

    def test_should_offer_the_foreground_rerun_with_redirected_output_as_the_second_way_out(
        self, reason
    ):
        assert "foreground" in reason

    def test_should_explain_that_a_subagent_owned_background_job_dies_with_the_final_response(
        self, reason
    ):
        assert "final response" in reason


class TestIgnoresTextThatMerelyQuotesTheAnnouncement:
    """Reading ABOUT a background job is not starting one.

    Every case here was produced by running this guard against the
    transcript of the run that wrote it. It reported four jobs, and
    three of them were text that merely contained the announcement's
    trailing clause. A guard that fires on its own documentation
    blocks the very agents maintaining it."""

    def test_should_stay_silent_when_a_tool_result_only_quotes_the_hook_header(
        self, tmp_path
    ):
        transcript = write_transcript(
            tmp_path,
            "quotes-own-header",
            [
                read_call("toolu_01Ct6WhkXbBTjEuS4nkkVN9y", str(HOOK)),
                tool_result(
                    "toolu_01Ct6WhkXbBTjEuS4nkkVN9y",
                    "# The runner prints one of two announcements, and they\n"
                    "# share exactly one literal -- "
                    '"Output is being written to: <path>."\n'
                    "# That literal is what this keys on.\n",
                ),
            ],
        )

        result = run_hook(payload(transcript))

        assert result.stdout == ""
        assert result.returncode == 0

    def test_should_stay_silent_when_a_tool_result_holds_the_runners_own_source(
        self, tmp_path
    ):
        transcript = write_transcript(
            tmp_path,
            "quotes-runner-source",
            [
                bash_call(
                    "toolu_01LiDjLZKMZFxNBHphmZAqLd",
                    "grep -n 'Output is being written to' /tmp/cc-strings-bg.txt",
                ),
                tool_result(
                    "toolu_01LiDjLZKMZFxNBHphmZAqLd",
                    "Command running in background with ID: ${e}. "
                    "Output is being written to: ${t}.`:`Command did not complete "
                    "within its ${Math.max(1,Math.round(n/1000))}s timeout and was "
                    "moved to the background (ID: ${e}). "
                    'Output is being written to: ${t}.`,a=o?"If it exits while you',
                ),
            ],
        )

        result = run_hook(payload(transcript))

        assert result.stdout == ""
        assert result.returncode == 0

    def test_should_still_block_a_real_job_announced_among_quoted_ones(
        self, tmp_path
    ):
        """The discriminator must not be "any transcript that mentions the
        literal is exempt" -- a real job alongside quoted text still blocks,
        and the reason names only the real one."""
        transcript = write_transcript(
            tmp_path,
            "real-job-beside-quoted",
            [
                read_call("toolu_01Ct6WhkXbBTjEuS4nkkVN9y", str(HOOK)),
                tool_result(
                    "toolu_01Ct6WhkXbBTjEuS4nkkVN9y",
                    '# share exactly one literal -- "Output is being written to: '
                    '<path>."\n',
                ),
                bash_call("toolu_01M2imnnoG9wXKgz7hp8ivKs", "./run-tests.sh"),
                harness_backgrounded_result(
                    "toolu_01M2imnnoG9wXKgz7hp8ivKs", SUITE_JOB_ID, SUITE_JOB_OUTPUT
                ),
            ],
        )

        result = run_hook(payload(transcript))

        assert decision_of(result) == "block"
        assert SUITE_JOB_OUTPUT in reason_of(result)
        assert "<path>" not in reason_of(result)


class TestAllowsACollectedOrAbsentBackgroundJob:
    def test_should_stay_silent_when_the_agent_read_the_background_output_file_afterwards(
        self, tmp_path
    ):
        transcript = write_transcript(
            tmp_path,
            "collected-by-read",
            [
                bash_call("toolu_01M2imnnoG9wXKgz7hp8ivKs", "./run-tests.sh"),
                agent_backgrounded_result(
                    "toolu_01M2imnnoG9wXKgz7hp8ivKs", SUITE_JOB_ID, SUITE_JOB_OUTPUT
                ),
                read_call("toolu_01QCmzR6Q5t6CJ2j6XR4kYUr", SUITE_JOB_OUTPUT),
            ],
        )

        result = run_hook(payload(transcript))

        assert result.stdout == ""
        assert result.returncode == 0

    def test_should_stay_silent_when_the_agent_tailed_the_background_output_file_through_bash(
        self, tmp_path
    ):
        transcript = write_transcript(
            tmp_path,
            "collected-by-tail",
            [
                bash_call("toolu_01M2imnnoG9wXKgz7hp8ivKs", "./run-tests.sh"),
                agent_backgrounded_result(
                    "toolu_01M2imnnoG9wXKgz7hp8ivKs", SUITE_JOB_ID, SUITE_JOB_OUTPUT
                ),
                bash_call("toolu_01SQFLyPpufJLiAsjg7vwHih", f"tail -40 {SUITE_JOB_OUTPUT}"),
            ],
        )

        result = run_hook(payload(transcript))

        assert result.stdout == ""
        assert result.returncode == 0

    def test_should_stay_silent_when_the_agent_polled_the_background_job_by_its_id(self, tmp_path):
        transcript = write_transcript(
            tmp_path,
            "collected-by-poll",
            [
                bash_call("toolu_01M2imnnoG9wXKgz7hp8ivKs", "./run-tests.sh"),
                agent_backgrounded_result(
                    "toolu_01M2imnnoG9wXKgz7hp8ivKs", SUITE_JOB_ID, SUITE_JOB_OUTPUT
                ),
                bash_output_call("toolu_01JsKUc1xT6B7Gt37b4HUGBA", SUITE_JOB_ID),
            ],
        )

        result = run_hook(payload(transcript))

        assert result.stdout == ""
        assert result.returncode == 0

    def test_should_stay_silent_when_the_agent_ran_no_background_job_at_all(self, tmp_path):
        transcript = write_transcript(
            tmp_path,
            "no-background",
            [
                bash_call("toolu_01M2imnnoG9wXKgz7hp8ivKs", "./run-tests.sh"),
                tool_result("toolu_01M2imnnoG9wXKgz7hp8ivKs", "12 suites passed, 0 failed"),
            ],
        )

        result = run_hook(payload(transcript))

        assert result.stdout == ""
        assert result.returncode == 0


class TestFailsOpenRatherThanTrappingTheAgent:
    def test_should_stay_silent_when_its_own_block_caused_this_stop(self, tmp_path):
        transcript = write_transcript(
            tmp_path,
            "loop-guard",
            [
                bash_call("toolu_01M2imnnoG9wXKgz7hp8ivKs", "./run-tests.sh"),
                agent_backgrounded_result(
                    "toolu_01M2imnnoG9wXKgz7hp8ivKs", SUITE_JOB_ID, SUITE_JOB_OUTPUT
                ),
            ],
        )

        result = run_hook(payload(transcript, stop_hook_active=True))

        assert result.stdout == ""
        assert result.returncode == 0

    def test_should_stay_silent_when_the_payload_carries_no_agent_transcript_path(self):
        result = run_hook(
            {
                "session_id": SESSION_ID,
                "hook_event_name": "SubagentStop",
                "stop_hook_active": False,
            }
        )

        assert result.stdout == ""
        assert result.returncode == 0

    def test_should_stay_silent_when_the_agent_transcript_file_is_missing_from_disk(self, tmp_path):
        result = run_hook(payload(tmp_path / "never-written.jsonl"))

        assert result.stdout == ""
        assert result.returncode == 0

    def test_should_stay_silent_when_the_agent_transcript_is_empty(self, tmp_path):
        transcript = tmp_path / "empty.jsonl"
        transcript.write_text("", encoding="utf-8")

        result = run_hook(payload(transcript))

        assert result.stdout == ""
        assert result.returncode == 0

    def test_should_stay_silent_when_the_stdin_payload_is_not_valid_json(self):
        result = subprocess.run(
            [sys.executable, str(HOOK)],
            input="not json at all",
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.stdout == ""
        assert result.returncode == 0

    def test_should_stay_silent_when_the_agent_transcript_is_a_directory_it_cannot_read(
        self, tmp_path
    ):
        unreadable = tmp_path / "transcript-as-a-directory.jsonl"
        unreadable.mkdir()

        result = run_hook(payload(unreadable))

        assert result.stdout == ""
        assert result.returncode == 0


class TestIsWiredIntoTheHarness:
    def test_should_be_registered_on_the_subagent_stop_event_in_settings_json(self):
        settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
        commands = [
            hook.get("command", "")
            for matcher in settings["hooks"]["SubagentStop"]
            for hook in matcher.get("hooks", [])
        ]

        registered = [c for c in commands if "check-uncollected-background-output.py" in c]

        assert len(registered) == 1, commands

    def test_should_be_reachable_through_the_home_hooks_symlink(self):
        assert os.path.exists(SYMLINK_HOOK)
