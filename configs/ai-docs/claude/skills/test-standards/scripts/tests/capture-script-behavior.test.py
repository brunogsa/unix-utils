# capture-script-behavior.test.py - Blackbox CLI tests for
# capture-script-behavior.py: every test invokes the script's CLI
# via subprocess (never imports it directly — hyphenated filenames
# aren't importable via a plain `import` statement), inside a fresh
# tempfile.TemporaryDirectory() per test so no run touches the real
# repo tree.

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

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


def _run(*args, cwd=None):
    """Run capture-script-behavior.py with `args`, returning the
    completed subprocess. Blackbox by design: this is the only way
    the tool is ever invoked in production too."""
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True, text=True, cwd=cwd,
    )


def _write_executable(path: Path, content: str) -> Path:
    """Write `content` to `path` and mark it executable — every toy
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
        self.assertIn(str(script), text)

        replay_result = subprocess.run(
            [sys.executable, "-m", "pytest", "--import-mode=importlib", str(emitted), "-q"],
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
        text = emitted.read_text().replace(str(script), str(rewrite))
        emitted.write_text(text)

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
        # The row's canary file genuinely got written (proves the row
        # actually ran and the assertion below isn't vacuous).
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

    def test_should_leave_the_real_repo_untouched_when_a_capture_crashes_midway_or_is_re_run(self):
        script = _write_executable(self.tmp_path / "toy.sh", (
            "#!/bin/sh\necho hi\nexit 0\n"
        ))
        table = _write_table(self.tmp_path / "table.json", [
            {"name": "escaping-row", "argv": [], "stdin": "", "branch": None,
             "fixture_files": {"../escape.txt": "should never land"}, "git_init": False},
        ])
        json_out = self.tmp_path / "captured.json"

        before = subprocess.run(
            ["git", "status", "--porcelain"], cwd=REPO_ROOT,
            capture_output=True, text=True,
        ).stdout

        for _ in range(2):  # crash, then a repeat run — both must leave the repo untouched
            result = _run("capture", "--script", str(script), "--table", str(table),
                           "--json-out", str(json_out))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("escape", result.stderr)

        after = subprocess.run(
            ["git", "status", "--porcelain"], cwd=REPO_ROOT,
            capture_output=True, text=True,
        ).stdout
        self.assertEqual(before, after)
        self.assertFalse((REPO_ROOT.parent / "escape.txt").exists())
        self.assertFalse((REPO_ROOT / "escape.txt").exists())

    def test_should_normalize_duration_pid_temp_path_and_uuid_values_to_the_same_masked_value_across_captures(self):
        # One row, captured twice independently (two fresh fixture
        # dirs, guaranteed different paths) via a script whose only
        # non-constant output is exactly the four masked value kinds
        # — the resulting golden must be byte-identical across both
        # captures, proving the mask set (not just per-script luck)
        # absorbs the difference.
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
        # relative --script path must still resolve against the
        # caller's original cwd, not silently look for the script
        # inside the (unrelated) fixture directory instead. Found
        # via manual exploration, not one of the 13 planned titles —
        # folded in as a Drift fix with its own regression test.
        script = _write_executable(self.tmp_path / "toy.sh", "#!/bin/sh\necho hi\nexit 0\n")
        table = _write_table(self.tmp_path / "table.json", [
            {"name": "only-row", "argv": [], "stdin": "", "branch": None,
             "fixture_files": {}, "git_init": False},
        ])
        json_out = self.tmp_path / "captured.json"

        # `script.name` (not a hardcoded "toy.sh") is what actually
        # makes this a relative-path invocation: it's a bare
        # filename, resolved only via cwd=self.tmp_path below.
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

        # Same stdout/stderr/exit code, but writes different fixture
        # content — the old 3-tuple comparison this harness replaces
        # would have missed this entirely.
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
        # The captured golden must NOT have been silently overwritten.
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

        # A human amends the checked-in table with the accepted reason.
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
