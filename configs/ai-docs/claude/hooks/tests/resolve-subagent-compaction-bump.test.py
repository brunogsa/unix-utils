"""Blackbox CLI tests for resolve-subagent-compaction-bump.py.

The hook is the only production caller of tmux-window-title.sh's
--bump-subagent-counter, so these tests pin the two things that
decide whether the tmux title's subagent half is ever right:

  - how many `compact_boundary` entries a subagent transcript
    really holds, counted by parsing each line as JSON rather than
    by matching the literal string (ordinary conversation text
    mentions `compact_boundary` and inflates a text match);

  - how many of those are NEW since the last SubagentStop for the
    same agent, since Claude Code fires SubagentStop again every
    time a resumed agent stops.

Every test drives a COPY of the hook under tmp_path, beside a stub
tmux-window-title.sh that records its argv instead of driving tmux,
and with HOME pointed at a throwaway directory — so no assertion
can reach the developer's real tmux window or real ~/.claude state.

Usage:
  pytest configs/ai-docs/claude/hooks/tests/resolve-subagent-compaction-bump.test.py
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOK_SOURCE = Path(__file__).resolve().parent.parent / "resolve-subagent-compaction-bump.py"

BUMP_FLAG = "--bump-subagent-counter"

SESSION_ID = "e9373a7e-046b-4807-b242-ddeb49455a43"
AGENT_ID = "a859f1768d6aa9f18"


def _install_hook(tmp_path, title_exit=0):
    """Mirror the real hooks/ + scripts/ sibling layout the hook
    resolves its title script against, with the title script stubbed
    out to append its argv to a capture file."""
    hooks_dir = tmp_path / "hooks"
    scripts_dir = tmp_path / "scripts"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    scripts_dir.mkdir(parents=True, exist_ok=True)

    hook_copy = hooks_dir / HOOK_SOURCE.name
    hook_copy.write_text(HOOK_SOURCE.read_text(encoding="utf-8"), encoding="utf-8")

    capture_path = tmp_path / "title-script-argv.txt"
    stub = scripts_dir / "tmux-window-title.sh"
    stub.write_text(
        "#!/bin/bash\n"
        f'printf "%s\\n" "$*" >> "{capture_path}"\n'
        f"exit {title_exit}\n",
        encoding="utf-8",
    )
    stub.chmod(0o755)

    return hook_copy, capture_path


def _run_hook(hook_copy, payload, home_dir):
    """Feed one SubagentStop payload to the hook copy. `payload` is a
    dict (serialized here) or a raw string for malformed-stdin cases."""
    stdin = payload if isinstance(payload, str) else json.dumps(payload)
    home_dir.mkdir(parents=True, exist_ok=True)

    return subprocess.run(
        [sys.executable, str(hook_copy)],
        input=stdin,
        capture_output=True,
        text=True,
        env={"HOME": str(home_dir), "PATH": "/usr/bin:/bin:/usr/local/bin"},
    )


def _bump_calls(capture_path):
    if not capture_path.exists():
        return []
    return [line for line in capture_path.read_text(encoding="utf-8").splitlines() if line]


def _boundary_entry(agent_id, timestamp):
    """One real compact_boundary system entry, shaped as Claude Code
    writes it into a subagent transcript."""
    return {
        "parentUuid": None,
        "logicalParentUuid": "4188096c-c11b-4f18-b61e-f07242656eaa",
        "isSidechain": True,
        "agentId": agent_id,
        "type": "system",
        "subtype": "compact_boundary",
        "content": "Conversation compacted",
        "isMeta": False,
        "timestamp": timestamp,
        "level": "info",
        "compactMetadata": {"trigger": "auto", "preTokens": 204212},
    }


def _decoy_entry(agent_id):
    """An ordinary assistant turn whose TEXT mentions compact_boundary.

    This is the entry a `grep -c compact_boundary` counts and a JSON
    parse does not — the exact miscount that made the counter wrong
    while it was being diagnosed."""
    return {
        "parentUuid": "1d4e8a02-77c4-4b91-9b0a-2c6f31f0a7e2",
        "isSidechain": True,
        "agentId": agent_id,
        "type": "assistant",
        "timestamp": "2026-08-12T18:04:11.220Z",
        "message": {
            "role": "assistant",
            "content": [
                {
                    "type": "text",
                    "text": (
                        "A subagent compaction surfaces only as a "
                        "compact_boundary entry in its transcript, with "
                        "no hook event at all."
                    ),
                }
            ],
        },
    }


def _write_transcript(path, entries):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(entry) + "\n" for entry in entries),
        encoding="utf-8",
    )
    return path


def _transcript_with(tmp_path, boundary_count, agent_id=AGENT_ID, with_decoy=True):
    entries = []
    if with_decoy:
        entries.append(_decoy_entry(agent_id))
    for index in range(boundary_count):
        entries.append(
            _boundary_entry(agent_id, f"2026-08-12T1{index}:08:58.615Z")
        )
    return _write_transcript(
        tmp_path / "transcripts" / SESSION_ID / f"agent-{agent_id}.jsonl",
        entries,
    )


def _payload(transcript_path, agent_id=AGENT_ID, session_id=SESSION_ID):
    """The captured real SubagentStop shape, trimmed to the fields the
    hook reads. agent_type is an EMPTY STRING in production, so it is
    kept empty here — branching on it is what made the previous hook
    dead code."""
    return {
        "session_id": session_id,
        "transcript_path": f"/Users/brunoagostini/.claude/projects/-Users-brunoagostini-unix-utils/{session_id}.jsonl",
        "cwd": "/Users/brunoagostini/unix-utils",
        "agent_id": agent_id,
        "agent_type": "",
        "hook_event_name": "SubagentStop",
        "stop_hook_active": False,
        "agent_transcript_path": str(transcript_path),
    }


class TestResolveSubagentCompactionBumpHappy:
    def test_should_bump_the_subagent_counter_once_per_compaction_the_transcript_records_and_stay_silent_when_that_same_subagent_stops_again(
        self, tmp_path
    ):
        hook, capture = _install_hook(tmp_path)
        transcript = _transcript_with(tmp_path, boundary_count=2)
        home = tmp_path / "fake_home"

        first = _run_hook(hook, _payload(transcript), home)

        assert first.returncode == 0, first.stdout + first.stderr
        assert _bump_calls(capture) == [BUMP_FLAG, BUMP_FLAG]

        second = _run_hook(hook, _payload(transcript), home)

        assert second.returncode == 0, second.stdout + second.stderr
        assert _bump_calls(capture) == [BUMP_FLAG, BUMP_FLAG]

    def test_should_bump_only_the_compaction_appended_since_the_previous_stop_when_a_resumed_subagent_compacts_again(
        self, tmp_path
    ):
        hook, capture = _install_hook(tmp_path)
        transcript = _transcript_with(tmp_path, boundary_count=1)
        home = tmp_path / "fake_home"

        _run_hook(hook, _payload(transcript), home)
        assert _bump_calls(capture) == [BUMP_FLAG]

        _transcript_with(tmp_path, boundary_count=3)
        _run_hook(hook, _payload(transcript), home)

        assert _bump_calls(capture) == [BUMP_FLAG] * 3

    def test_should_not_bump_the_subagent_counter_when_the_subagent_never_compacted(
        self, tmp_path
    ):
        hook, capture = _install_hook(tmp_path)
        transcript = _transcript_with(tmp_path, boundary_count=0)

        result = _run_hook(hook, _payload(transcript), tmp_path / "fake_home")

        assert result.returncode == 0, result.stdout + result.stderr
        assert _bump_calls(capture) == []

    def test_should_leave_stdout_empty_so_the_hook_adds_no_context_to_the_session(
        self, tmp_path
    ):
        hook, _capture = _install_hook(tmp_path)
        transcript = _transcript_with(tmp_path, boundary_count=1)

        result = _run_hook(hook, _payload(transcript), tmp_path / "fake_home")

        assert result.stdout == ""


class TestResolveSubagentCompactionBumpCorner:
    def test_should_count_two_subagents_of_one_session_separately_rather_than_charging_one_for_the_others_compactions(
        self, tmp_path
    ):
        hook, capture = _install_hook(tmp_path)
        home = tmp_path / "fake_home"
        first_agent = "a2453ade78294120c"
        second_agent = "af6cf3725e1603b98"
        first_transcript = _transcript_with(tmp_path, 2, agent_id=first_agent)
        second_transcript = _transcript_with(tmp_path, 1, agent_id=second_agent)

        _run_hook(hook, _payload(first_transcript, agent_id=first_agent), home)
        _run_hook(hook, _payload(second_transcript, agent_id=second_agent), home)

        assert _bump_calls(capture) == [BUMP_FLAG] * 3

    def test_should_count_the_same_agent_id_seen_under_two_sessions_separately_so_a_second_session_starts_from_zero(
        self, tmp_path
    ):
        hook, capture = _install_hook(tmp_path)
        home = tmp_path / "fake_home"
        other_session = "b7c1f0d2-3a45-4e6b-8c9d-0e1f2a3b4c5d"
        transcript = _transcript_with(tmp_path, boundary_count=1)

        _run_hook(hook, _payload(transcript), home)
        _run_hook(hook, _payload(transcript, session_id=other_session), home)

        assert _bump_calls(capture) == [BUMP_FLAG, BUMP_FLAG]

    def test_should_still_count_the_readable_compactions_when_one_transcript_line_is_truncated_json(
        self, tmp_path
    ):
        hook, capture = _install_hook(tmp_path)
        transcript = tmp_path / "transcripts" / SESSION_ID / f"agent-{AGENT_ID}.jsonl"
        transcript.parent.mkdir(parents=True, exist_ok=True)
        transcript.write_text(
            json.dumps(_boundary_entry(AGENT_ID, "2026-08-12T10:08:58.615Z")) + "\n"
            + '{"type":"assistant","message":{"role":"assist\n'
            + json.dumps(_boundary_entry(AGENT_ID, "2026-08-12T11:08:58.615Z")) + "\n",
            encoding="utf-8",
        )

        result = _run_hook(hook, _payload(transcript), tmp_path / "fake_home")

        assert result.returncode == 0, result.stdout + result.stderr
        assert _bump_calls(capture) == [BUMP_FLAG, BUMP_FLAG]

    def test_should_not_re_bump_a_compaction_it_already_reported_even_when_the_title_script_failed_on_that_report(
        self, tmp_path
    ):
        # Under-counting once beats re-adding the agent's
        # whole history on every later stop, so a failed
        # title call still counts as reported.
        failing_tree = tmp_path / "failing"
        hook, capture = _install_hook(failing_tree, title_exit=1)
        transcript = _transcript_with(tmp_path, boundary_count=1)
        home = tmp_path / "fake_home"

        first = _run_hook(hook, _payload(transcript), home)

        assert first.returncode == 0, first.stdout + first.stderr
        assert _bump_calls(capture) == [BUMP_FLAG]

        working_tree = tmp_path / "working"
        working_hook, working_capture = _install_hook(working_tree)
        _run_hook(working_hook, _payload(transcript), home)

        assert _bump_calls(working_capture) == []


class TestResolveSubagentCompactionBumpFailure:
    def test_should_exit_0_without_bumping_when_the_transcript_line_only_mentions_compact_boundary_in_conversation_text(
        self, tmp_path
    ):
        hook, capture = _install_hook(tmp_path)
        transcript = _write_transcript(
            tmp_path / "transcripts" / SESSION_ID / f"agent-{AGENT_ID}.jsonl",
            [_decoy_entry(AGENT_ID)],
        )

        result = _run_hook(hook, _payload(transcript), tmp_path / "fake_home")

        assert result.returncode == 0, result.stdout + result.stderr
        assert _bump_calls(capture) == []

    @pytest.mark.parametrize(
        "missing_field", ["agent_id", "session_id", "agent_transcript_path"]
    )
    def test_should_exit_0_without_bumping_when_the_payload_omits_a_field_the_count_cannot_be_keyed_without(
        self, tmp_path, missing_field
    ):
        hook, capture = _install_hook(tmp_path)
        transcript = _transcript_with(tmp_path, boundary_count=2)
        payload = _payload(transcript)
        del payload[missing_field]

        result = _run_hook(hook, payload, tmp_path / "fake_home")

        assert result.returncode == 0, result.stdout + result.stderr
        assert _bump_calls(capture) == []

    def test_should_exit_0_without_bumping_when_the_agent_transcript_file_does_not_exist(
        self, tmp_path
    ):
        hook, capture = _install_hook(tmp_path)
        missing = tmp_path / "transcripts" / SESSION_ID / f"agent-{AGENT_ID}.jsonl"

        result = _run_hook(hook, _payload(missing), tmp_path / "fake_home")

        assert result.returncode == 0, result.stdout + result.stderr
        assert _bump_calls(capture) == []

    @pytest.mark.parametrize(
        "malformed_stdin", ['{"agent_id": "a859f1768d6', '"just-a-string"', ""]
    )
    def test_should_exit_0_without_bumping_when_stdin_is_not_a_readable_hook_payload_object(
        self, tmp_path, malformed_stdin
    ):
        hook, capture = _install_hook(tmp_path)

        result = _run_hook(hook, malformed_stdin, tmp_path / "fake_home")

        assert result.returncode == 0, result.stdout + result.stderr
        assert _bump_calls(capture) == []

    def test_should_exit_0_without_bumping_when_an_agent_id_carries_path_separators_that_would_escape_the_count_store(
        self, tmp_path
    ):
        hook, capture = _install_hook(tmp_path)
        transcript = _transcript_with(tmp_path, boundary_count=2)

        result = _run_hook(
            hook, _payload(transcript, agent_id="../../../etc/passwd"), tmp_path / "fake_home"
        )

        assert result.returncode == 0, result.stdout + result.stderr
        assert _bump_calls(capture) == []
