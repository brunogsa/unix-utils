"""Prove the /implement §2.3 state-file skip is detected instead of silently ignored.

The gap this suite covers, end to end:

  implement/SKILL.md §2.3 requires writing /tmp/implement_<session_id>.json
  before the first task dispatch. On 2026-08-10 a whole six-task batch ran with
  NO state file and nothing noticed — implement-loop-state.py already errors on
  a missing path, but nothing ever called it, and
  claude-implement-stop-hook.sh's session scoping treats an empty glob as
  "no /implement in this session" and exits silently.

Two scripts close it, and both are exercised here against real fixtures:

  build-implement-invocation-marker.sh   (UserPromptSubmit)
      writes /tmp/implement_<session_id>.expected when the submitted prompt is
      a /implement slash-command invocation.

  claude-implement-stop-hook.sh          (Stop, via claude-stop-orchestrator.sh)
      now separates the two empty-glob cases: marker absent → unchanged silent
      exit 0; marker present with no §2.3 evidence → block naming the path.

Every test drives the REAL scripts as subprocesses over REAL /tmp fixtures,
because /tmp/implement_<session_id>* paths are hardcoded in both hooks and are
exactly what the guard keys on — a test that stubbed the path would not be
testing the guard.

Session ids are all prefixed "pyb1-" so they can never collide with
hooks/tests/test-claude-implement-stop-hook.sh, whose EXIT trap cleans only
/tmp/implement_sess-*.json. Teardown here removes every /tmp/implement_pyb1-*
artifact — .json, .md and .expected alike — so a crashed run cannot leave a
stale marker that makes the bash suite block unexpectedly.

Usage:
  pytest configs/ai-docs/claude/hooks/tests/implement-state-file-guard.test.py
"""

import glob
import json
import os
import shutil
import subprocess
import tempfile
import unittest
import uuid
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent.parent
MARKER_HOOK = HOOKS_DIR / "build-implement-invocation-marker.sh"
STOP_HOOK = HOOKS_DIR / "claude-implement-stop-hook.sh"

BASH = shutil.which("bash") or "/bin/bash"


def session_id(name: str) -> str:
    """Return a session id unique to this run AND to this suite.

    The uuid suffix keeps two concurrent pytest runs (or a re-run racing its
    own teardown) from sharing fixture files; the pyb1- prefix keeps the bash
    suite's sess-* namespace disjoint from this one in both directions.
    """
    return f"pyb1-{name}-{uuid.uuid4().hex[:8]}"


def marker_path(sid: str) -> Path:
    return Path(f"/tmp/implement_{sid}.expected")


def state_path(sid: str) -> Path:
    return Path(f"/tmp/implement_{sid}.json")


def scratchpad_path(sid: str) -> Path:
    return Path(f"/tmp/implement_{sid}.md")


def cleanup(sid: str) -> None:
    for path in glob.glob(f"/tmp/implement_{sid}*"):
        if os.path.isdir(path) and not os.path.islink(path):
            shutil.rmtree(path, ignore_errors=True)
        else:
            try:
                os.unlink(path)
            except FileNotFoundError:
                pass


def run_hook(script: Path, stdin_text: str, args=(), path_override=None):
    env = dict(os.environ)
    if path_override is not None:
        env["PATH"] = str(path_override)
    return subprocess.run(
        [BASH, str(script), *args],
        input=stdin_text, capture_output=True, text=True, env=env,
    )


def run_marker_hook(prompt=None, sid=None, raw=None, path_override=None):
    """Drive the UserPromptSubmit hook. raw bypasses payload construction so a
    test can feed malformed or empty stdin, the two gaps the harness itself can
    produce."""
    if raw is None:
        payload = {"hook_event_name": "UserPromptSubmit", "cwd": "/tmp"}
        if sid is not None:
            payload["session_id"] = sid
        if prompt is not None:
            payload["prompt"] = prompt
        raw = json.dumps(payload)
    return run_hook(MARKER_HOOK, raw, path_override=path_override)


def run_stop_hook(sid=None, stop_hook_active=False, args=(), raw=None,
                  path_override=None):
    if raw is None:
        payload = {"hook_event_name": "Stop", "stop_hook_active": stop_hook_active}
        if sid is not None:
            payload["session_id"] = sid
        raw = json.dumps(payload)
    return run_hook(STOP_HOOK, raw, args=args, path_override=path_override)


def cat_only_bin(tmp_dir: Path) -> Path:
    """Return a PATH directory holding cat and nothing else.

    Both hooks read stdin with `input=$(cat)` before reaching their jq guard,
    so a jq-unavailable fixture has to keep cat reachable — the same
    construction test-claude-implement-stop-hook.sh uses for its own jq test.
    """
    fake_bin = tmp_dir / "fake-bin"
    fake_bin.mkdir(parents=True, exist_ok=True)
    cat_path = shutil.which("cat")
    assert cat_path is not None, "cat must be on PATH for this fixture to work"
    (fake_bin / "cat").symlink_to(cat_path)
    return fake_bin


class MarkerHookTestCase(unittest.TestCase):
    """build-implement-invocation-marker.sh — writes the marker, or nothing."""

    def setUp(self):
        self.sid = session_id("marker")
        self.addCleanup(cleanup, self.sid)

    def assert_inert(self, result, note):
        """A UserPromptSubmit hook must never print to stdout (stdout is
        injected into the conversation as context) and must never exit
        non-zero (a non-zero exit interferes with the human's prompt)."""
        self.assertEqual(result.returncode, 0, msg=f"{note}: exit\n{result.stderr}")
        self.assertEqual(result.stdout, "", msg=f"{note}: stdout must stay empty")

    def test_should_write_the_marker_when_the_prompt_invokes_implement_with_task_ids(self):
        result = run_marker_hook(prompt="/implement 5, 6", sid=self.sid)

        self.assert_inert(result, "slash-command invocation")
        self.assertTrue(
            marker_path(self.sid).exists(),
            msg=f"expected {marker_path(self.sid)} to be written")

    def test_should_write_the_marker_when_the_prompt_is_bare_implement_with_no_arguments(self):
        result = run_marker_hook(prompt="/implement", sid=self.sid)

        self.assert_inert(result, "bare invocation")
        self.assertTrue(marker_path(self.sid).exists())

    def test_should_write_the_marker_when_the_invocation_carries_leading_whitespace(self):
        result = run_marker_hook(prompt="   /implement PR-1", sid=self.sid)

        self.assert_inert(result, "leading whitespace")
        self.assertTrue(marker_path(self.sid).exists())

    def test_should_not_write_the_marker_when_implement_only_appears_as_a_word_in_prose(self):
        result = run_marker_hook(
            prompt="please implement the parser, then implement the tests",
            sid=self.sid)

        self.assert_inert(result, "prose mention")
        self.assertFalse(
            marker_path(self.sid).exists(),
            msg="a substring match would arm the guard on ordinary conversation")

    def test_should_not_write_the_marker_for_a_different_slash_command_sharing_the_prefix(self):
        result = run_marker_hook(prompt="/implement-something 5", sid=self.sid)

        self.assert_inert(result, "prefix-sharing command")
        self.assertFalse(
            marker_path(self.sid).exists(),
            msg="/implement-something is a different command, not this one")

    def test_should_not_write_the_marker_when_the_slash_command_is_not_at_the_start(self):
        result = run_marker_hook(prompt="later I will run /implement 5", sid=self.sid)

        self.assert_inert(result, "mid-prompt mention")
        self.assertFalse(marker_path(self.sid).exists())

    def test_should_stay_inert_when_jq_is_unavailable(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_marker_hook(
                prompt="/implement 5", sid=self.sid,
                path_override=cat_only_bin(Path(tmp)))

        self.assert_inert(result, "jq unavailable")
        self.assertFalse(marker_path(self.sid).exists())

    def test_should_stay_inert_when_the_payload_carries_no_session_id(self):
        result = run_marker_hook(prompt="/implement 5", sid=None)

        self.assert_inert(result, "no session_id")

    def test_should_stay_inert_when_the_payload_carries_no_prompt_field(self):
        result = run_marker_hook(prompt=None, sid=self.sid)

        self.assert_inert(result, "no prompt field")
        self.assertFalse(marker_path(self.sid).exists())

    def test_should_stay_inert_when_stdin_is_malformed_json(self):
        result = run_marker_hook(raw="{not json at all")

        self.assert_inert(result, "malformed stdin")

    def test_should_stay_inert_when_stdin_is_empty(self):
        result = run_marker_hook(raw="")

        self.assert_inert(result, "empty stdin")

    def test_should_stay_inert_when_the_marker_path_cannot_be_written(self):
        # A directory sitting on the marker path makes the write fail the same
        # way an unwritable /tmp would, without touching /tmp's permissions.
        marker_path(self.sid).mkdir()

        result = run_marker_hook(prompt="/implement 5", sid=self.sid)

        self.assert_inert(result, "unwritable marker path")

    def test_should_stay_inert_when_the_same_session_invokes_implement_twice(self):
        run_marker_hook(prompt="/implement 5", sid=self.sid)
        result = run_marker_hook(prompt="/implement 6", sid=self.sid)

        self.assert_inert(result, "second invocation")
        self.assertTrue(marker_path(self.sid).exists())


class StopHookStateFileGuardTestCase(unittest.TestCase):
    """claude-implement-stop-hook.sh — the two empty-glob cases, told apart."""

    def setUp(self):
        self.sid = session_id("stop")
        self.addCleanup(cleanup, self.sid)

    def arm(self):
        marker_path(self.sid).write_text("")
        return marker_path(self.sid)

    def write_scratchpad(self, offset_seconds):
        """Write the §2.3 scratchpad with an mtime offset from the marker's.

        Positive means "written after this run's /implement prompt" — real §2.3
        evidence. Negative means a leftover from an EARLIER /implement in the
        same session, which must not disarm the guard for the new run.
        """
        path = scratchpad_path(self.sid)
        path.write_text("# implement scratchpad\n")
        marker_mtime = marker_path(self.sid).stat().st_mtime
        stamp = marker_mtime + offset_seconds
        os.utime(path, (stamp, stamp))
        return path

    def write_state(self, phase):
        state_path(self.sid).write_text(json.dumps({
            "version": 4, "session_id": self.sid, "slug": "demo",
            "pr_label": "", "phase": phase,
        }))
        return state_path(self.sid)

    def decision(self, result):
        if not result.stdout.strip():
            return None
        return json.loads(result.stdout)

    def test_should_exit_silently_when_no_marker_and_no_state_file_exist(self):
        result = run_stop_hook(sid=self.sid)

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(
            result.stdout, "",
            msg="a session with no /implement run must pay one failed glob and nothing else")

    def test_should_block_the_stop_when_the_marker_exists_but_no_state_file_was_ever_written(self):
        self.arm()

        result = run_stop_hook(sid=self.sid)

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        decision = self.decision(result)
        self.assertIsNotNone(decision, msg="expected a block decision on stdout")
        assert decision is not None
        self.assertEqual(decision["decision"], "block")
        self.assertIn(
            str(state_path(self.sid)), decision["reason"],
            msg="the reason must name the exact missing path, not just describe it")

    def test_should_name_both_the_write_fix_and_the_clear_marker_escape_in_the_block_reason(self):
        self.arm()

        decision = self.decision(run_stop_hook(sid=self.sid))

        assert decision is not None, "expected a block decision on stdout"
        self.assertIn("2.3", decision["reason"])
        self.assertIn(
            f"trash {marker_path(self.sid)}", decision["reason"],
            msg="an aborted pre-flight leaves the marker behind; the reason must "
                "say how to clear it, and with trash (claude-rm-guard.sh blocks rm "
                "on /tmp paths)")

    def test_should_leave_the_marker_in_place_when_it_blocks_so_a_later_stop_still_blocks(self):
        self.arm()

        run_stop_hook(sid=self.sid)

        self.assertTrue(
            marker_path(self.sid).exists(),
            msg="consuming the marker on the first block would reopen the gap: the "
                "very batch this guard exists for may stop only once")

    def test_should_allow_the_stop_when_a_fresh_scratchpad_shows_2_3_ran_and_the_state_file_was_disposed(self):
        self.arm()
        self.write_scratchpad(offset_seconds=+30)

        result = run_stop_hook(sid=self.sid)

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(
            result.stdout, "",
            msg="§8.3 trashes the state file but not the scratchpad, so a completed "
                "run whose only Stop is the batch-end one must not be blocked")

    def test_should_disarm_the_marker_once_a_fresh_scratchpad_has_witnessed_2_3(self):
        self.arm()
        self.write_scratchpad(offset_seconds=+30)

        run_stop_hook(sid=self.sid)

        self.assertFalse(
            marker_path(self.sid).exists(),
            msg="a marker that outlives its run would false-block every later stop")

    def test_should_still_block_when_the_only_scratchpad_predates_this_implement_invocation(self):
        stale = scratchpad_path(self.sid)
        stale.write_text("# leftover from an earlier run\n")
        self.arm()
        stale_stamp = marker_path(self.sid).stat().st_mtime - 600
        os.utime(stale, (stale_stamp, stale_stamp))

        decision = self.decision(run_stop_hook(sid=self.sid))

        self.assertIsNotNone(
            decision,
            msg="a second /implement in the same session must not be disarmed by "
                "the first run's leftover scratchpad")
        assert decision is not None
        self.assertEqual(decision["decision"], "block")

    def test_should_keep_blocking_a_mid_flight_batch_when_the_state_file_says_phase_tasks(self):
        self.arm()
        self.write_state("tasks")

        decision = self.decision(run_stop_hook(sid=self.sid))

        self.assertIsNotNone(decision, msg="existing mid-flight behavior must survive")
        assert decision is not None
        self.assertEqual(decision["decision"], "block")
        self.assertIn("phase", decision["reason"])

    def test_should_disarm_the_marker_once_a_real_state_file_exists(self):
        self.arm()
        self.write_state("tasks")

        run_stop_hook(sid=self.sid)

        self.assertFalse(
            marker_path(self.sid).exists(),
            msg="§2.3 is witnessed: the state file itself now drives every later stop")

    def test_should_allow_the_stop_when_the_state_file_says_phase_presented(self):
        self.arm()
        self.write_state("presented")

        result = run_stop_hook(sid=self.sid)

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(result.stdout, "", msg="existing release behavior must survive")

    def test_should_stay_silent_when_stop_hook_active_is_true_even_with_the_marker_armed(self):
        self.arm()

        result = run_stop_hook(sid=self.sid, stop_hook_active=True)

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(
            result.stdout, "",
            msg="the loop guard must cap this block at one extra turn, like every other")
        self.assertTrue(
            marker_path(self.sid).exists(),
            msg="the loop guard suppresses the block, it does not resolve the gap")

    def test_should_report_not_mid_flight_under_check_instead_of_blocking(self):
        self.arm()

        result = run_stop_hook(sid=self.sid, args=("--check",))

        self.assertEqual(
            result.returncode, 1,
            msg="query mode answers 'is a batch mid-flight', and a run with no "
                "state file is not mid-flight; the gate call blocks the chain first")
        self.assertEqual(result.stdout, "")

    def test_should_not_mutate_the_marker_under_check(self):
        self.arm()
        self.write_state("presented")

        run_stop_hook(sid=self.sid, args=("--check",))

        self.assertTrue(
            marker_path(self.sid).exists(),
            msg="query mode is a read-only question; the orchestrator calls it after "
                "the gate and it must not change what the gate decided")

    def test_should_stay_silent_with_the_marker_armed_when_jq_is_unavailable(self):
        self.arm()

        with tempfile.TemporaryDirectory() as tmp:
            result = run_stop_hook(
                sid=self.sid, path_override=cat_only_bin(Path(tmp)))

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(result.stdout, "")

    def test_should_stay_silent_when_the_payload_carries_no_session_id(self):
        self.arm()

        result = run_stop_hook(sid=None)

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(result.stdout, "")

    def test_should_stay_silent_when_stdin_is_malformed_json(self):
        self.arm()

        result = run_stop_hook(raw="{not json at all")

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(result.stdout, "")

    def test_should_ignore_a_directory_sitting_on_the_marker_path(self):
        # Only a regular file arms the guard. A directory there is not a marker
        # any hook wrote, and treating it as one would both false-block and
        # hand the disarm an rm it can never satisfy.
        marker_path(self.sid).mkdir()

        result = run_stop_hook(sid=self.sid)

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
