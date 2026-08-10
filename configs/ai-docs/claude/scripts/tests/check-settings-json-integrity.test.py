"""Prove check-settings-json-integrity.py catches a detached settings.json symlink.

configs/ai-docs/claude/settings.json is symlinked to ~/.claude/settings.json by
install.sh. Claude Code's /config command and the update-config skill write
settings.json through temp+rename, which replaces that symlink with a regular
file and silently detaches it from the repo (see the repo CLAUDE.md's
"settings.json caveat"). This script is the deterministic check for that one
failure mode.

Every test drives the script against a temp fixture directory via
--settings-path/--source-path, never the real ~/.claude/settings.json — that
is a live user file whose symlink status is exactly what this script exists
to detect, so a test reading it would be non-deterministic depending on
whichever machine and session runs it.

Usage:
  pytest configs/ai-docs/claude/scripts/tests/check-settings-json-integrity.test.py
"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = (
    Path(__file__).resolve().parent.parent
    / "check-settings-json-integrity.py"
)


def run_check(settings_path: Path, source_path: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable, str(SCRIPT),
            "--settings-path", str(settings_path),
            "--source-path", str(source_path),
        ],
        capture_output=True, text=True,
    )


class TestCheckSettingsJsonIntegrityHappy(unittest.TestCase):
    def test_should_exit_0_when_the_settings_file_is_still_a_symlink_onto_its_configs_source_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source_path = tmp_path / "configs" / "ai-docs" / "claude" / "settings.json"
            source_path.parent.mkdir(parents=True)
            source_path.write_text('{"model": "sonnet"}\n')

            settings_path = tmp_path / "dot-claude" / "settings.json"
            settings_path.parent.mkdir(parents=True)
            settings_path.symlink_to(source_path)

            result = run_check(settings_path, source_path)

            self.assertEqual(
                result.returncode, 0,
                msg=f"expected exit 0 for a live symlink:\n{result.stdout}{result.stderr}")


class TestCheckSettingsJsonIntegrityFailure(unittest.TestCase):
    def test_should_exit_non_zero_when_the_settings_symlink_has_been_detached_into_a_regular_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source_path = tmp_path / "configs" / "ai-docs" / "claude" / "settings.json"
            source_path.parent.mkdir(parents=True)
            source_path.write_text('{"model": "sonnet"}\n')

            settings_path = tmp_path / "dot-claude" / "settings.json"
            settings_path.parent.mkdir(parents=True)
            # Simulates /config's temp+rename: a regular file lands where
            # the symlink onto the repo source used to be.
            settings_path.write_text('{"model": "sonnet"}\n')

            result = run_check(settings_path, source_path)

            self.assertNotEqual(
                result.returncode, 0,
                msg=f"expected non-zero exit for a detached regular file:\n{result.stdout}{result.stderr}")
            self.assertIn(str(settings_path), result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
