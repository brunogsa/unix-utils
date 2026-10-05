# capture-script-behavior.test.py - Blackbox CLI tests for
# capture-script-behavior.py: every test invokes the script's
# CLI via subprocess (never imports it directly - hyphenated
# filenames aren't importable via a plain `import` statement).
#
# Each test runs inside a fresh tempfile.TemporaryDirectory()
# per test so no run touches the real repo tree.

import contextlib
import hashlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPT = Path(__file__).parent.parent / "capture-script-behavior.py"
REPO_ROOT = Path(__file__).parent.parent.parent.parent.parent.parent.parent.parent


class _TempDirTestCase(unittest.TestCase):
    """Shared per-test isolation: a fresh temp dir any script-under-
    test or table file gets written into, torn down after."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()


def _run(*args, cwd=None, env=None):
    """Run capture-script-behavior.py with `args`, returning the
    completed subprocess. Blackbox by design: this is the only way
    the tool is ever invoked in production too."""
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True, text=True, cwd=cwd, env=env,
    )


def _write_executable(path: Path, content: str) -> Path:
    """Write `content` to `path` and mark it executable - every toy
    script-under-test is invoked directly (its own shebang decides
    the interpreter), matching how a real .sh or converted .py
    script is captured."""
    path.write_text(content)
    path.chmod(0o755)
    return path


def _write_table(path: Path, rows: list[dict], known_branches: list[str] | None = None) -> Path:
    path.write_text(json.dumps({
        "known_branches": known_branches or [],
        "rows": rows,
    }))
    return path


class TestCaptureScriptBehaviorHappy(_TempDirTestCase):
    def test_should_capture_stdout_stderr_exit_code_and_fixture_post_state_for_every_table_row(self):
        script = _write_executable(self.tmp_path / "toy.py", (
            "#!/usr/bin/env python3\n"
            "import sys\n"
            "open('output.txt', 'w').write('made-by-toy')\n"
            "sys.stdout.write('hello from toy\\n')\n"
            "sys.stderr.write('warning from toy\\n')\n"
            "sys.exit(7)\n"
        ))
        table = _write_table(self.tmp_path / "table.json", [
            {"name": "only-row", "argv": [], "stdin": "", "branch": None,
             "fixture_files": {}, "git_init": False},
        ])
        json_out = self.tmp_path / "captured.json"

        result = _run("capture", "--script", str(script), "--table", str(table),
                       "--json-out", str(json_out))

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        captured = json.loads(json_out.read_text())
        self.assertEqual(len(captured["rows"]), 1)
        row = captured["rows"][0]
        self.assertEqual(row["expected_stdout"], "hello from toy\n")
        self.assertEqual(row["expected_stderr"], "warning from toy\n")
        self.assertEqual(row["expected_exit_code"], 7)
        expected_hash = hashlib.sha256(b"made-by-toy").hexdigest()
        self.assertEqual(row["expected_post_state"]["tree"]["output.txt"], expected_hash)
        self.assertIsNone(row["expected_post_state"]["git_status"])

    def test_should_emit_the_captured_table_as_a_stem_test_file_that_replays_against_the_rewrite(self):
        script = _write_executable(self.tmp_path / "toy.sh", (
            "#!/bin/sh\necho hi\nexit 0\n"
        ))
        table = _write_table(self.tmp_path / "table.json", [
            {"name": "only-row", "argv": [], "stdin": "", "branch": None,
             "fixture_files": {}, "git_init": False},
        ])
        emitted = self.tmp_path / "toy.test.py"

        capture_result = _run("capture", "--script", str(script), "--table", str(table),
                               "--out", str(emitted))
        self.assertEqual(capture_result.returncode, 0, msg=capture_result.stderr)
        self.assertTrue(emitted.exists())
        text = emitted.read_text()
        self.assertIn("SCRIPT_UNDER_TEST", text)

        # Relative to __file__, not the absolute path captured
        # here. The relocatable-test-file test right below says
        # why. This test only checks that the emitted file still
        # works from where it was captured.
        self.assertNotIn(str(script), text)
        self.assertIn("Path(__file__).resolve().parent", text)

        replay_result = subprocess.run(
            [sys.executable, "-m", "pytest", "--import-mode=importlib", str(emitted), "-q"],
            capture_output=True, text=True,
        )
        self.assertEqual(replay_result.returncode, 0, msg=replay_result.stdout + replay_result.stderr)

    def test_should_emit_a_relocatable_test_file_with_no_hardcoded_absolute_paths(self):
        # A committed <stem>.test.py is cloned onto other
        # machines (CLAUDE.md's cross-platform MUST) and CI
        # runners with a different home-dir root.
        #
        # Both SCRIPT_UNDER_TEST and the harness import path
        # must resolve via the emitted file's own __file__, not
        # a path literal baked in at capture time on this
        # machine.
        fake_repo = self.tmp_path / "fake-repo"
        harness_copy = fake_repo / "test-standards" / "scripts" / "capture-script-behavior.py"
        harness_copy.parent.mkdir(parents=True)
        harness_copy.write_text(SCRIPT.read_text())
        harness_copy.chmod(0o755)

        script_path = fake_repo / "implement" / "scripts" / "toy.sh"
        script_path.parent.mkdir(parents=True)
        script = _write_executable(script_path, "#!/bin/sh\necho hi\nexit 0\n")
        emitted = fake_repo / "implement" / "scripts" / "tests" / "toy.test.py"
        emitted.parent.mkdir(parents=True)
        table = _write_table(self.tmp_path / "table.json", [
            {"name": "only-row", "argv": [], "stdin": "", "branch": None,
             "fixture_files": {}, "git_init": False},
        ])

        capture_result = subprocess.run(
            [sys.executable, str(harness_copy), "capture",
             "--script", str(script), "--table", str(table), "--out", str(emitted)],
            capture_output=True, text=True,
        )
        self.assertEqual(capture_result.returncode, 0, msg=capture_result.stderr)
        text = emitted.read_text()
        self.assertNotIn(str(fake_repo), text)

        # Move the whole fake repo to a new absolute root - same
        # internal layout, different mount point, like a fresh
        # clone on another machine.
        import shutil
        relocated_repo = self.tmp_path / "relocated" / "elsewhere" / "fake-repo"
        relocated_repo.parent.mkdir(parents=True)
        shutil.move(str(fake_repo), str(relocated_repo))
        relocated_emitted = relocated_repo / "implement" / "scripts" / "tests" / "toy.test.py"

        replay_result = subprocess.run(
            [sys.executable, "-m", "pytest", "--import-mode=importlib", str(relocated_emitted), "-q"],
            capture_output=True, text=True,
        )
        self.assertEqual(replay_result.returncode, 0, msg=replay_result.stdout + replay_result.stderr)

    def test_should_pass_every_row_when_the_rewrite_reproduces_the_full_captured_tuple_unchanged(self):
        script = _write_executable(self.tmp_path / "original.sh", (
            "#!/bin/sh\necho hi\nexit 0\n"
        ))
        table = _write_table(self.tmp_path / "table.json", [
            {"name": "only-row", "argv": [], "stdin": "", "branch": None,
             "fixture_files": {}, "git_init": False},
        ])
        emitted = self.tmp_path / "original.test.py"
        capture_result = _run("capture", "--script", str(script), "--table", str(table),
                               "--out", str(emitted))
        self.assertEqual(capture_result.returncode, 0, msg=capture_result.stderr)

        rewrite = _write_executable(self.tmp_path / "rewrite.sh", (
            "#!/bin/sh\necho hi\nexit 0\n"
        ))

        # The emitted file names the script by a path relative
        # to itself, so the substitution targets that relative
        # form.
        original_ref = repr(os.path.relpath(script, emitted.parent))
        rewrite_ref = repr(os.path.relpath(rewrite, emitted.parent))
        text = emitted.read_text().replace(original_ref, rewrite_ref)
        self.assertIn(rewrite_ref, text)
        self.assertNotIn(original_ref, text)
        emitted.write_text(text)

        # With the original gone, a replay can only pass by
        # running the rewrite.
        script.unlink()

        replay_result = subprocess.run(
            [sys.executable, "-m", "pytest", "--import-mode=importlib", str(emitted), "-q"],
            capture_output=True, text=True,
        )
        self.assertEqual(replay_result.returncode, 0, msg=replay_result.stdout + replay_result.stderr)


class TestCaptureScriptBehaviorCorner(_TempDirTestCase):
    def test_should_run_each_row_in_its_own_fixture_directory_and_leave_the_real_repo_untouched(self):
        canary_name = "capture-behavior-canary-8f3c1a.txt"
        script = _write_executable(self.tmp_path / "toy.sh", (
            f"#!/bin/sh\necho canary > {canary_name}\nexit 0\n"
        ))
        table = _write_table(self.tmp_path / "table.json", [
            {"name": "only-row", "argv": [], "stdin": "", "branch": None,
             "fixture_files": {}, "git_init": False},
        ])
        json_out = self.tmp_path / "captured.json"

        result = _run("capture", "--script", str(script), "--table", str(table),
                       "--json-out", str(json_out))

        self.assertEqual(result.returncode, 0, msg=result.stderr)

        # The row's canary file genuinely got written (proves
        # the row actually ran and the assertion below isn't
        # vacuous).
        captured = json.loads(json_out.read_text())
        self.assertIn(canary_name, captured["rows"][0]["expected_post_state"]["tree"])

        # ...yet it never touched the real repo tree.
        matches = list(REPO_ROOT.rglob(canary_name))
        self.assertEqual(matches, [], msg=f"canary leaked into the real repo at {matches}")
        porcelain = subprocess.run(
            ["git", "status", "--porcelain"], cwd=REPO_ROOT,
            capture_output=True, text=True,
        ).stdout
        self.assertNotIn(canary_name, porcelain)

    def test_should_include_a_recursive_listing_with_content_hashes_and_git_porcelain_status_in_the_post_state(self):
        script = _write_executable(self.tmp_path / "toy.sh", (
            "#!/bin/sh\nmkdir -p sub\necho nested > sub/nested.txt\necho top > top.txt\nexit 0\n"
        ))
        table = _write_table(self.tmp_path / "table.json", [
            {"name": "only-row", "argv": [], "stdin": "", "branch": None,
             "fixture_files": {"seed.txt": "seed-content"}, "git_init": True},
        ])
        json_out = self.tmp_path / "captured.json"

        result = _run("capture", "--script", str(script), "--table", str(table),
                       "--json-out", str(json_out))

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        row = json.loads(json_out.read_text())["rows"][0]
        tree = row["expected_post_state"]["tree"]
        self.assertEqual(tree["sub/nested.txt"], hashlib.sha256(b"nested\n").hexdigest())
        self.assertEqual(tree["top.txt"], hashlib.sha256(b"top\n").hexdigest())
        self.assertEqual(tree["seed.txt"], hashlib.sha256(b"seed-content").hexdigest())
        self.assertIsNotNone(row["expected_post_state"]["git_status"])
        self.assertIn("top.txt", row["expected_post_state"]["git_status"])

    def test_should_reject_a_dotdot_fixture_key_before_it_can_write_beside_the_fixture_directory(self):
        script = _write_executable(self.tmp_path / "toy.sh", (
            "#!/bin/sh\necho hi\nexit 0\n"
        ))
        table = _write_table(self.tmp_path / "table.json", [
            {"name": "escaping-row", "argv": [], "stdin": "", "branch": None,
             "fixture_files": {"../escape.txt": "should never land"}, "git_init": False},
        ])
        json_out = self.tmp_path / "captured.json"

        # A '..' key resolves against the fixture dir, so a leak
        # would land beside it, in the system temp dir.
        #
        # Point TMPDIR at a directory this test owns and expect
        # it empty after the run (a clean run deletes its
        # fixture dir).
        #
        # The directory must exist: tempfile silently falls back
        # to /tmp when TMPDIR names a missing one.
        tool_tmp = self.tmp_path / "tool-tmp"
        tool_tmp.mkdir()
        env = {**os.environ, "TMPDIR": str(tool_tmp)}

        # Crash, then a repeat run - both must leave it empty.
        for _ in range(2):
            result = _run("capture", "--script", str(script), "--table", str(table),
                           "--json-out", str(json_out), env=env)
            self.assertEqual(list(tool_tmp.iterdir()), [])
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("escape", result.stderr)

    def test_should_reject_an_absolute_fixture_key_before_it_can_write_into_a_repo_it_points_at(self):
        # An absolute key replaces the fixture dir outright, so
        # a leak lands wherever the key points.
        # Point it into a throwaway git repo and compare that
        # repo's porcelain before and after.
        repo = self.tmp_path / "victim-repo"
        repo.mkdir()
        script = _write_executable(repo / "toy.sh", (
            "#!/bin/sh\necho hi\nexit 0\n"
        ))
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
        leak_target = repo / "leaked.txt"
        table = _write_table(self.tmp_path / "table.json", [
            {"name": "escaping-row", "argv": [], "stdin": "", "branch": None,
             "fixture_files": {str(leak_target): "should never land"}, "git_init": False},
        ])
        json_out = self.tmp_path / "captured.json"

        def porcelain() -> str:
            return subprocess.run(
                ["git", "status", "--porcelain"], cwd=repo,
                capture_output=True, text=True, check=True,
            ).stdout

        before = porcelain()

        result = _run("capture", "--script", str(script), "--table", str(table),
                       "--json-out", str(json_out), cwd=repo)

        self.assertEqual(before, porcelain())
        self.assertFalse(leak_target.exists())
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("escape", result.stderr)

    def test_should_replay_a_git_init_row_unchanged_against_its_own_golden(self):
        # The row's git status is captured on its own, so the
        # volatile .git internals (the index differs run to run)
        # must stay out of the file hash.
        script = _write_executable(self.tmp_path / "toy.sh", (
            "#!/bin/sh\necho top > top.txt\nexit 0\n"
        ))
        table = _write_table(self.tmp_path / "table.json", [
            {"name": "git-row", "argv": [], "stdin": "", "branch": None,
             "fixture_files": {"seed.txt": "seed-content"}, "git_init": True},
        ])
        emitted = self.tmp_path / "toy.test.py"
        capture_result = _run("capture", "--script", str(script), "--table", str(table),
                               "--out", str(emitted))
        self.assertEqual(capture_result.returncode, 0, msg=capture_result.stderr)

        replay_result = subprocess.run(
            [sys.executable, "-m", "pytest", "--import-mode=importlib", str(emitted), "-q"],
            capture_output=True, text=True,
        )
        self.assertEqual(replay_result.returncode, 0, msg=replay_result.stdout + replay_result.stderr)

    def test_should_fail_naming_the_row_when_its_script_outlives_the_row_timeout(self):
        # The script blocks on a FIFO opened read-write via a
        # bash builtin, so it starts no child process a kill
        # could miss.
        fifo = self.tmp_path / "block.fifo"
        os.mkfifo(fifo)
        script = _write_executable(self.tmp_path / "hang.sh", (
            "#!/bin/bash\nexec 3<>\"$1\"\nread -t 600 -u 3\n"
        ))
        spec = importlib.util.spec_from_file_location("capture_script_behavior", SCRIPT)
        assert spec is not None and spec.loader is not None
        harness = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(harness)
        row = harness.Row.from_dict({"name": "hanging-row", "argv": [str(fifo)]})
        fixture_dir = self.tmp_path / "fixture"
        fixture_dir.mkdir()

        with self.assertRaises(harness.RowTimeoutError) as raised:
            harness.capture_row(script, row, fixture_dir=fixture_dir, timeout_seconds=1)

        self.assertIn("hanging-row", str(raised.exception))

    def test_should_normalize_duration_pid_temp_path_and_uuid_values_to_the_same_masked_value_across_captures(self):
        # One row, captured twice independently (two fresh
        # fixture dirs, guaranteed different paths) via a script
        # whose only non-constant output is exactly the four
        # masked value kinds.
        #
        # The resulting golden must be byte-identical across
        # both captures, proving the mask set (not just
        # per-script luck) absorbs the difference.
        script = _write_executable(self.tmp_path / "toy.sh", (
            "#!/bin/sh\n"
            'printf "cwd=%s dur=3.2s pid=1234 id=abcd1234-ab12-cd34-ef56-abcdef123456\\n" "$(pwd)"\n'
            "exit 0\n"
        ))
        table = _write_table(self.tmp_path / "table.json", [
            {"name": "only-row", "argv": [], "stdin": "", "branch": None,
             "fixture_files": {}, "git_init": False},
        ])

        first_out = self.tmp_path / "first.json"
        second_out = self.tmp_path / "second.json"
        first = _run("capture", "--script", str(script), "--table", str(table), "--json-out", str(first_out))
        second = _run("capture", "--script", str(script), "--table", str(table), "--json-out", str(second_out))

        self.assertEqual(first.returncode, 0, msg=first.stderr)
        self.assertEqual(second.returncode, 0, msg=second.stderr)
        first_row = json.loads(first_out.read_text())["rows"][0]
        second_row = json.loads(second_out.read_text())["rows"][0]
        self.assertEqual(first_row["expected_stdout"], second_row["expected_stdout"])
        self.assertIn("<DURATION>", first_row["expected_stdout"])
        self.assertIn("<PID>", first_row["expected_stdout"])
        self.assertIn("<UUID>", first_row["expected_stdout"])
        self.assertIn("<FIXTURE_DIR>", first_row["expected_stdout"])

    def test_should_record_a_branch_as_explicitly_unexercised_when_no_input_row_reaches_it(self):
        script = _write_executable(self.tmp_path / "toy.sh", "#!/bin/sh\nexit 0\n")
        table = _write_table(
            self.tmp_path / "table.json",
            [{"name": "row-a", "argv": [], "stdin": "", "branch": "branch-a",
              "fixture_files": {}, "git_init": False}],
            known_branches=["branch-a", "branch-b"],
        )
        json_out = self.tmp_path / "captured.json"

        result = _run("capture", "--script", str(script), "--table", str(table), "--json-out", str(json_out))

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        branch_hits = json.loads(json_out.read_text())["branch_hits"]
        self.assertIn("branch-b", branch_hits)
        self.assertEqual(branch_hits["branch-b"], 0)

    def test_should_emit_a_per_branch_hit_count_that_proves_every_branch_is_reached_by_at_least_one_row(self):
        script = _write_executable(self.tmp_path / "toy.sh", "#!/bin/sh\nexit 0\n")
        table = _write_table(
            self.tmp_path / "table.json",
            [
                {"name": "row-a1", "argv": [], "stdin": "", "branch": "branch-a",
                 "fixture_files": {}, "git_init": False},
                {"name": "row-a2", "argv": [], "stdin": "", "branch": "branch-a",
                 "fixture_files": {}, "git_init": False},
                {"name": "row-b1", "argv": [], "stdin": "", "branch": "branch-b",
                 "fixture_files": {}, "git_init": False},
            ],
            known_branches=["branch-a", "branch-b"],
        )
        json_out = self.tmp_path / "captured.json"
        emitted = self.tmp_path / "toy.test.py"

        result = _run("capture", "--script", str(script), "--table", str(table),
                       "--json-out", str(json_out), "--out", str(emitted))

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        branch_hits = json.loads(json_out.read_text())["branch_hits"]
        self.assertEqual(branch_hits, {"branch-a": 2, "branch-b": 1})
        text = emitted.read_text()
        self.assertIn("BRANCH_HITS", text)
        self.assertIn('"branch-a": 2', text)

    def test_should_capture_a_script_passed_as_a_relative_path(self):
        # capture_row runs each script with cwd=fixture_dir; a
        # relative --script path must still resolve against
        # the caller's original cwd.
        #
        # It must not silently look for the script inside the
        # (unrelated) fixture directory instead.
        #
        # Found via manual exploration, not one of the 13
        # planned titles - folded in as a Drift fix with its own
        # regression test.
        script = _write_executable(self.tmp_path / "toy.sh", "#!/bin/sh\necho hi\nexit 0\n")
        table = _write_table(self.tmp_path / "table.json", [
            {"name": "only-row", "argv": [], "stdin": "", "branch": None,
             "fixture_files": {}, "git_init": False},
        ])
        json_out = self.tmp_path / "captured.json"

        # `script.name` (not a hardcoded "toy.sh") is what
        # actually makes this a relative-path invocation: it's a
        # bare filename, resolved only via cwd=self.tmp_path
        # below.
        result = _run("capture", "--script", script.name, "--table", str(table),
                       "--json-out", str(json_out), cwd=str(self.tmp_path))

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        row = json.loads(json_out.read_text())["rows"][0]
        self.assertEqual(row["expected_stdout"], "hi\n")


class TestCaptureScriptBehaviorFailure(_TempDirTestCase):
    def test_should_fail_comparison_when_an_unmasked_value_legitimately_differs_between_captures(self):
        expected = self.tmp_path / "expected.json"
        actual = self.tmp_path / "actual.json"
        expected.write_text(json.dumps({
            "expected_stdout": "result: 42\n",
            "expected_stderr": "",
            "expected_exit_code": 0,
            "expected_post_state": None,
        }))
        actual.write_text(json.dumps({
            "name": "row", "branch": None,
            "stdout": "result: 43\n", "stderr": "", "exit_code": 0,
            "post_state": None,
        }))

        result = _run("compare", "--expected", str(expected), "--actual", str(actual))

        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["matches"])
        self.assertIn("stdout", payload["diff"])

    def test_should_fail_a_row_whose_streams_and_exit_code_match_but_whose_fixture_post_state_diverges(self):
        original = _write_executable(self.tmp_path / "original.sh", (
            "#!/bin/sh\necho ok\nprintf v1 > state.txt\nexit 0\n"
        ))
        table = _write_table(self.tmp_path / "table.json", [
            {"name": "only-row", "argv": [], "stdin": "", "branch": None,
             "fixture_files": {}, "git_init": False},
        ])
        captured = self.tmp_path / "captured.json"
        first = _run("capture", "--script", str(original), "--table", str(table), "--json-out", str(captured))
        self.assertEqual(first.returncode, 0, msg=first.stderr)

        # Same stdout/stderr/exit code, but writes different
        # fixture content - the old 3-tuple comparison this
        # harness replaces would have missed this entirely.
        rewrite = _write_executable(self.tmp_path / "rewrite.sh", (
            "#!/bin/sh\necho ok\nprintf v2 > state.txt\nexit 0\n"
        ))
        recapture_out = self.tmp_path / "recaptured.json"

        result = _run("capture", "--script", str(rewrite), "--table", str(captured),
                       "--json-out", str(recapture_out))

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("post_state", result.stderr)

    def test_should_reject_a_diverging_row_that_carries_no_divergence_comment_naming_the_change(self):
        original = _write_executable(self.tmp_path / "original.sh", (
            "#!/bin/sh\necho ok\nexit 0\n"
        ))
        table = _write_table(self.tmp_path / "table.json", [
            {"name": "only-row", "argv": [], "stdin": "", "branch": None,
             "fixture_files": {}, "git_init": False},
        ])
        captured = self.tmp_path / "captured.json"
        first = _run("capture", "--script", str(original), "--table", str(table), "--json-out", str(captured))
        self.assertEqual(first.returncode, 0, msg=first.stderr)

        rewrite = _write_executable(self.tmp_path / "rewrite.sh", (
            "#!/bin/sh\necho changed\nexit 0\n"
        ))
        recapture_out = self.tmp_path / "recaptured.json"
        emitted = self.tmp_path / "recaptured.test.py"

        result = _run("capture", "--script", str(rewrite), "--table", str(captured),
                       "--json-out", str(recapture_out), "--out", str(emitted))

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("divergence", result.stderr)
        self.assertFalse(emitted.exists())

        # The captured golden must NOT have been silently
        # overwritten.
        unchanged = json.loads(captured.read_text())["rows"][0]
        self.assertEqual(unchanged["expected_stdout"], "ok\n")

    def test_should_accept_a_diverging_row_that_carries_a_divergence_comment_naming_the_change(self):
        original = _write_executable(self.tmp_path / "original.sh", (
            "#!/bin/sh\necho ok\nexit 0\n"
        ))
        table = _write_table(self.tmp_path / "table.json", [
            {"name": "only-row", "argv": [], "stdin": "", "branch": None,
             "fixture_files": {}, "git_init": False},
        ])
        captured = self.tmp_path / "captured.json"
        first = _run("capture", "--script", str(original), "--table", str(table), "--json-out", str(captured))
        self.assertEqual(first.returncode, 0, msg=first.stderr)

        # A human amends the checked-in table with the accepted
        # reason.
        payload = json.loads(captured.read_text())
        payload["rows"][0]["divergence"] = "greeting message rewritten for clarity"
        captured.write_text(json.dumps(payload))

        rewrite = _write_executable(self.tmp_path / "rewrite.sh", (
            "#!/bin/sh\necho changed\nexit 0\n"
        ))
        recapture_out = self.tmp_path / "recaptured.json"
        emitted = self.tmp_path / "recaptured.test.py"

        result = _run("capture", "--script", str(rewrite), "--table", str(captured),
                       "--json-out", str(recapture_out), "--out", str(emitted))

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        updated = json.loads(recapture_out.read_text())["rows"][0]
        self.assertEqual(updated["expected_stdout"], "changed\n")
        text = emitted.read_text()
        self.assertIn("# DIVERGENCE: greeting message rewritten for clarity", text)

    def test_should_report_the_unreadable_harness_path_when_the_generated_test_cannot_load_its_harness(self):
        # The emitted file reaches its harness through a
        # relative `../../../` walk, which breaks the moment
        # either file is relocated.
        #
        # The reader's first question is then "which harness
        # path could it not load?", so that path has to be in
        # the message the failure prints.
        fake_repo = self.tmp_path / "fake-repo"
        harness_copy = fake_repo / "test-standards" / "scripts" / "capture-script-behavior.py"
        harness_copy.parent.mkdir(parents=True)
        harness_copy.write_text(SCRIPT.read_text())
        harness_copy.chmod(0o755)

        script_path = fake_repo / "implement" / "scripts" / "toy.sh"
        script_path.parent.mkdir(parents=True)
        script = _write_executable(script_path, "#!/bin/sh\necho hi\nexit 0\n")
        emitted = fake_repo / "implement" / "scripts" / "tests" / "toy.test.py"
        emitted.parent.mkdir(parents=True)
        table = _write_table(self.tmp_path / "table.json", [
            {"name": "only-row", "argv": [], "stdin": "", "branch": None,
             "fixture_files": {}, "git_init": False},
        ])

        capture_result = subprocess.run(
            [sys.executable, str(harness_copy), "capture",
             "--script", str(script), "--table", str(table), "--out", str(emitted)],
            capture_output=True, text=True,
        )
        self.assertEqual(capture_result.returncode, 0, msg=capture_result.stderr)

        # Delete only the harness, leaving the emitted test
        # where it was captured - the exact state a relocated or
        # renamed harness leaves behind.
        harness_copy.unlink()

        replay_result = subprocess.run(
            [sys.executable, "-m", "pytest", "--import-mode=importlib", str(emitted), "-q"],
            capture_output=True, text=True,
        )
        output = replay_result.stdout + replay_result.stderr

        self.assertNotEqual(replay_result.returncode, 0)
        self.assertIn(str(harness_copy), output)
        self.assertIn("ImportError", output)

        # An AttributeError from inside importlib names its own
        # internals rather than the file the reader has to go
        # fix.
        self.assertNotIn("AttributeError", output)


class TestCaptureScriptBehaviorRowEnv(_TempDirTestCase):
    def test_should_run_a_row_with_its_env_set_and_unset_and_keep_the_fixture_dir_token_in_the_stored_row(self):
        script = _write_executable(self.tmp_path / "toy.sh", (
            "#!/bin/sh\n"
            'cat "$MY_VAR"\n'
            'echo "$MY_VAR"\n'
            'echo "${HOME-unset}"\n'
        ))
        table = _write_table(self.tmp_path / "table.json", [
            {"name": "env-row", "fixture_files": {"x": "hello\n"},
             "env": {"MY_VAR": "<FIXTURE_DIR>/x", "HOME": None}},
        ])
        json_out = self.tmp_path / "captured.json"

        result = _run("capture", "--script", str(script), "--table", str(table),
                       "--json-out", str(json_out))

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        row = json.loads(json_out.read_text())["rows"][0]
        self.assertEqual(row["expected_stdout"], "hello\n<FIXTURE_DIR>/x\nunset\n")
        self.assertEqual(row["env"], {"MY_VAR": "<FIXTURE_DIR>/x", "HOME": None})


class TestCaptureScriptBehaviorExecutableFiles(_TempDirTestCase):
    def test_should_let_a_script_run_a_fixture_file_listed_as_executable_from_path_with_the_index_recording_the_bit(self):
        # One fake tool is the only extra executable this file
        # pays a first-exec scan for, so keep it to one row.
        script = _write_executable(self.tmp_path / "toy.sh", (
            "#!/bin/sh\n"
            "fake\n"
            "git ls-files -s bin/fake | cut -d' ' -f1\n"
        ))
        table = _write_table(self.tmp_path / "table.json", [
            {"name": "fake-tool-row", "git_init": True,
             "fixture_files": {"bin/fake": "#!/bin/sh\necho fake-marker\n"},
             "executable_files": ["bin/fake"],
             "env": {"PATH": "<FIXTURE_DIR>/bin:/usr/bin:/bin"}},
        ])
        json_out = self.tmp_path / "captured.json"

        result = _run("capture", "--script", str(script), "--table", str(table),
                       "--json-out", str(json_out))

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        row = json.loads(json_out.read_text())["rows"][0]
        self.assertEqual(row["expected_stdout"], "fake-marker\n100755\n")
        self.assertEqual(row["expected_exit_code"], 0)
        self.assertEqual(row["expected_post_state"]["git_status"], "A  bin/fake\n")


class TestCaptureScriptBehaviorScriptRelpath(_TempDirTestCase):
    def test_should_run_a_copy_of_the_script_inside_the_fixture_so_it_finds_its_siblings_and_leave_the_copy_out_of_the_tree(self):
        script = _write_executable(self.tmp_path / "toy.sh", (
            "#!/bin/sh\n"
            'cat "$(dirname "$0")/data.txt"\n'
            'echo "$0"\n'
        ))
        table = _write_table(self.tmp_path / "table.json", [
            {"name": "sibling-row", "git_init": True,
             "fixture_files": {"tools/data.txt": "sibling-data\n"},
             "script_relpath": "tools/toy.sh"},
        ])
        json_out = self.tmp_path / "captured.json"

        result = _run("capture", "--script", str(script), "--table", str(table),
                       "--json-out", str(json_out))

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        row = json.loads(json_out.read_text())["rows"][0]
        self.assertEqual(row["expected_stdout"], "sibling-data\n./tools/toy.sh\n")
        post_state = row["expected_post_state"]
        self.assertEqual(list(post_state["tree"]), ["tools/data.txt"])
        self.assertEqual(post_state["git_status"], "A  tools/data.txt\nA  tools/toy.sh\n")


class TestCaptureScriptBehaviorInvalidRow(_TempDirTestCase):
    """A row the tool rejects before running anything: the toy
    script path is never executed, so it need not exist."""

    def _capture_rejecting(self, rows):
        table = _write_table(self.tmp_path / "table.json", rows)
        json_out = self.tmp_path / "captured.json"
        emitted = self.tmp_path / "toy.test.py"
        result = _run("capture", "--script", str(self.tmp_path / "never-run.sh"),
                       "--table", str(table), "--json-out", str(json_out), "--out", str(emitted))
        self.assertEqual(result.returncode, 1, msg=result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertFalse(json_out.exists())
        self.assertFalse(emitted.exists())
        return result.stderr

    def test_should_reject_a_row_with_a_misspelled_key_naming_the_row_and_every_unknown_key(self):
        stderr = self._capture_rejecting([
            {"name": "typo-row", "expected_stdut": "hi\n", "fixture_file": {"a": "b"}},
        ])

        self.assertEqual(len(stderr.splitlines()), 1, msg=stderr)
        self.assertTrue(stderr.startswith("error: row 'typo-row': "), msg=stderr)
        self.assertIn("expected_stdut", stderr)
        self.assertIn("fixture_file", stderr)

    def test_should_report_a_row_that_outlives_its_timeout_as_a_one_line_error_and_write_nothing(self):
        # subprocess.run is patched to time out, so no script
        # runs and no executable is needed. The real kill is
        # covered by the row-timeout test above.
        spec = importlib.util.spec_from_file_location("capture_script_behavior", SCRIPT)
        assert spec is not None and spec.loader is not None
        harness = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(harness)
        table = _write_table(self.tmp_path / "table.json", [{"name": "slow-row"}])
        json_out = self.tmp_path / "captured.json"
        emitted = self.tmp_path / "toy.test.py"

        timed_out = subprocess.TimeoutExpired(cmd="never-run.sh", timeout=60)
        stderr = io.StringIO()
        with mock.patch.object(harness.subprocess, "run", side_effect=timed_out), \
                contextlib.redirect_stderr(stderr):
            exit_code = harness.main(["capture", "--script", str(self.tmp_path / "never-run.sh"),
                                       "--table", str(table), "--json-out", str(json_out),
                                       "--out", str(emitted)])

        self.assertEqual(exit_code, 1)
        lines = stderr.getvalue().splitlines()
        self.assertEqual(len(lines), 1, msg=stderr.getvalue())
        self.assertTrue(lines[0].startswith("error: row 'slow-row': ran past 60"), msg=lines[0])
        self.assertEqual(lines[0].count("slow-row"), 1, msg=lines[0])
        self.assertFalse(json_out.exists())
        self.assertFalse(emitted.exists())

    def test_should_reject_an_env_that_is_not_an_object_naming_the_row(self):
        stderr = self._capture_rejecting([{"name": "env-list-row", "env": ["MY_VAR=1"]}])

        self.assertEqual(len(stderr.splitlines()), 1, msg=stderr)
        self.assertTrue(stderr.startswith("error: row 'env-list-row': "), msg=stderr)
        self.assertIn("must be an object", stderr)

    def test_should_reject_an_env_value_that_is_neither_a_string_nor_null_naming_the_row_and_variable(self):
        stderr = self._capture_rejecting([{"name": "env-number-row", "env": {"RETRIES": 3}}])

        self.assertEqual(len(stderr.splitlines()), 1, msg=stderr)
        self.assertTrue(stderr.startswith("error: row 'env-number-row': "), msg=stderr)
        self.assertIn("RETRIES", stderr)

    def test_should_reject_an_executable_file_that_is_not_a_fixture_file_naming_the_row_and_the_key(self):
        stderr = self._capture_rejecting([
            {"name": "ghost-exec-row", "fixture_files": {"a": "x"}, "executable_files": ["bin/ghost"]},
        ])

        self.assertEqual(len(stderr.splitlines()), 1, msg=stderr)
        self.assertTrue(stderr.startswith("error: row 'ghost-exec-row': "), msg=stderr)
        self.assertIn("bin/ghost", stderr)

    def test_should_reject_a_script_relpath_that_leaves_the_fixture_naming_the_row_and_the_field(self):
        for bad_relpath in ("/etc/toy.sh", "../toy.sh"):
            with self.subTest(script_relpath=bad_relpath):
                stderr = self._capture_rejecting([{"name": "escape-row", "script_relpath": bad_relpath}])

                self.assertEqual(len(stderr.splitlines()), 1, msg=stderr)
                self.assertTrue(stderr.startswith("error: row 'escape-row': "), msg=stderr)
                self.assertIn("script_relpath", stderr)
                self.assertIn(bad_relpath, stderr)

    def test_should_reject_a_script_relpath_that_collides_with_a_fixture_file_naming_the_row_and_the_field(self):
        collisions = (
            ("tools/toy.sh", {"tools/toy.sh": "x"}),
            ("tools/toy.sh", {"tools": "x"}),
            ("tools", {"tools/data.txt": "x"}),
        )
        for relpath, fixture_files in collisions:
            with self.subTest(script_relpath=relpath, fixture_files=list(fixture_files)):
                stderr = self._capture_rejecting([
                    {"name": "clash-row", "script_relpath": relpath, "fixture_files": fixture_files},
                ])

                self.assertEqual(len(stderr.splitlines()), 1, msg=stderr)
                self.assertTrue(stderr.startswith("error: row 'clash-row': "), msg=stderr)
                self.assertIn("script_relpath", stderr)

    def test_should_name_a_row_without_a_name_by_its_position_in_the_table(self):
        stderr = self._capture_rejecting([
            {"name": "first-row"},
            {"name": "second-row"},
            {"argv": ["--flag"]},
        ])

        self.assertEqual(len(stderr.splitlines()), 1, msg=stderr)
        self.assertTrue(stderr.startswith("error: row #2: "), msg=stderr)
        self.assertIn("name", stderr)
