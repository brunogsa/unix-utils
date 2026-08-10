#!/usr/bin/env python3
"""Prove the pytest/node test-discovery configuration this repo ships.

Exercises the repo's own `pytest.ini` plus Node's built-in `node --test`
discovery, both as real subprocesses against throwaway fixture files, so a
regression in either config shows up here instead of silently
de-collecting a suite on the next `pytest` run.

Usage:
  pytest configs/ai-docs/claude/scripts/tests/runner-config.test.py
"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# This file sits at configs/ai-docs/claude/scripts/tests/, so
# the repo root is five parents up: tests -> scripts -> claude
# -> ai-docs -> configs -> repo root.
REPO_ROOT = Path(__file__).resolve().parents[5]
PYTEST_INI = REPO_ROOT / "pytest.ini"

# The five suites that predate this work's *.test.py convention and must
# keep collecting once python_files also matches the new pattern.
PRE_EXISTING_SUITES = [
    "configs/ai-docs/claude/skills/brag/scripts/tests/test_parsers_parity.py",
    "configs/ai-docs/claude/skills/usage-audit/scripts/tests/test_build_usage_viewer.py",
    "configs/ai-docs/claude/skills/usage-audit/scripts/tests/test_claude_usage_report.py",
    "configs/ai-docs/claude/skills/usage-audit/scripts/tests/test_config_change_ledger.py",
    "configs/ai-docs/claude/skills/usage-audit/scripts/tests/test_delivered_work_ledger.py",
]

FIXTURE_PY_BODY = "def test_fixture_passes():\n    assert 1 + 1 == 2\n"


class TestRunnerConfigHappy(unittest.TestCase):
    def test_should_collect_and_run_a_hyphenated_stem_test_file_under_the_configured_python_files_pattern(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "pytest.ini").write_text(PYTEST_INI.read_text())
            (tmp_path / "sample-check.test.py").write_text(FIXTURE_PY_BODY)

            result = subprocess.run(
                [sys.executable, "-m", "pytest", "-q"],
                cwd=tmp_path, capture_output=True, text=True,
            )

            self.assertEqual(
                result.returncode, 0,
                msg=f"hyphenated-stem fixture did not pass:\n{result.stdout}{result.stderr}")
            self.assertIn("1 passed", result.stdout)

    def test_should_collect_and_run_a_stem_test_js_file_under_node_test_with_no_added_configuration(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            tests_dir = tmp_path / "tests"
            tests_dir.mkdir()
            (tests_dir / "sample-check.test.js").write_text(
                "const { test } = require('node:test');\n"
                "const assert = require('node:assert');\n"
                "test('fixture passes', () => { assert.strictEqual(1 + 1, 2); });\n"
            )

            # No path argument: node --test auto-discovers files under a
            # tests/ directory relative to cwd. Passing "tests/" explicitly
            # makes node treat it as a single module path to require, which
            # fails with MODULE_NOT_FOUND — the opposite of "no added
            # configuration" this test is proving.
            result = subprocess.run(
                ["node", "--test"],
                cwd=tmp_path, capture_output=True, text=True,
            )

            self.assertEqual(
                result.returncode, 0,
                msg=f"node --test did not discover the fixture:\n{result.stdout}{result.stderr}")
            self.assertIn("# pass 1", result.stdout)

    def test_should_list_each_pre_existing_suite_as_a_path_that_resolves_under_the_repo_root(self):
        for suite in PRE_EXISTING_SUITES:
            self.assertTrue(
                (REPO_ROOT / suite).is_file(),
                msg=f"{suite} does not resolve to a real file under "
                    f"{REPO_ROOT} — PRE_EXISTING_SUITES entries must be "
                    f"repo-root-relative paths, not substrings")

    def test_should_still_list_all_five_pre_existing_test_prefixed_suites_after_the_config_change(self):
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "--collect-only", "-q"],
            cwd=REPO_ROOT, capture_output=True, text=True,
        )

        for suite in PRE_EXISTING_SUITES:
            self.assertIn(
                suite, result.stdout,
                msg=f"{suite} missing from --collect-only output — the "
                    f"python_files config de-collected a pre-existing suite")


class TestRunnerConfigCorner(unittest.TestCase):
    def test_should_raise_no_module_import_error_for_a_hyphenated_test_stem_under_importlib_import_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "pytest.ini").write_text(PYTEST_INI.read_text())
            (tmp_path / "another-sample.test.py").write_text(FIXTURE_PY_BODY)

            result = subprocess.run(
                [sys.executable, "-m", "pytest", "-q"],
                cwd=tmp_path, capture_output=True, text=True,
            )

            combined_output = result.stdout + result.stderr
            self.assertEqual(
                result.returncode, 0,
                msg="hyphenated stem failed under importlib:"
                    f"\n{combined_output}")
            self.assertNotIn("ModuleNotFoundError", combined_output)
            self.assertNotIn("import file mismatch", combined_output)


if __name__ == "__main__":
    unittest.main()
