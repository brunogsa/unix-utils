"""Blackbox CLI tests for check-script-naming.py.

Fixtures: none on disk except what each test writes to tmp_path — every
script name is a minimal empty file under a synthetic scripts/ or
skills/<name>/scripts/ tree, small enough that the expected pass/fail
verdict is verifiable by eye against naming-rule-lexicon.json.

Usage:
  pytest configs/ai-docs/claude/skills/code-standards/scripts/tests/check-script-naming.test.py
"""

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "check-script-naming.py"


def _run(*args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
    )


def _write(path, content="# fixture script, body not read by the checker\n"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


class TestCheckScriptNamingHappy:
    def test_should_pass_a_name_built_as_verb_then_specific_object_in_kebab_case(self, tmp_path):
        script = _write(tmp_path / "scripts" / "check-density.py")

        result = _run(str(script))

        assert result.returncode == 0, result.stdout + result.stderr
        assert "OK" in result.stdout


class TestCheckScriptNamingFailure:
    def test_should_fail_a_name_whose_verb_carries_no_object(self, tmp_path):
        script = _write(tmp_path / "scripts" / "check.py")

        result = _run(str(script))

        assert result.returncode == 1, result.stdout + result.stderr
        assert "object" in (result.stdout + result.stderr).lower()

    def test_should_fail_a_name_whose_object_is_a_category_rather_than_a_specific_thing(self, tmp_path):
        script = _write(tmp_path / "scripts" / "check-shared.py")

        result = _run(str(script))

        assert result.returncode == 1, result.stdout + result.stderr
        assert "category" in (result.stdout + result.stderr).lower()

    def test_should_fail_a_name_that_repeats_the_skill_directory_the_script_already_lives_in(self, tmp_path):
        script = _write(
            tmp_path / "skills" / "coverage" / "scripts" / "check-coverage-report.py"
        )

        result = _run(str(script))

        assert result.returncode == 1, result.stdout + result.stderr
        assert "coverage" in (result.stdout + result.stderr).lower()

    def test_should_fail_a_name_carrying_an_abbreviation_outside_the_allowlist(self, tmp_path):
        script = _write(tmp_path / "scripts" / "check-sa-summary.py")

        result = _run(str(script))

        assert result.returncode == 1, result.stdout + result.stderr
        assert "sa" in (result.stdout + result.stderr).lower()

    def test_should_skip_excluded_and_vendored_paths_entirely_with_no_reporting(self, tmp_path):
        # A deliberately bad name (no object) under the vendored
        # skill-standards/scripts cluster — the one standing
        # exclusion reachable without a real oh-my-zsh checkout.
        vendored = _write(
            tmp_path / "skills" / "skill-standards" / "scripts" / "run.py"
        )

        result = _run(str(vendored))

        assert result.returncode == 0, result.stdout + result.stderr
        assert result.stdout.strip() == ""
        assert result.stderr.strip() == ""


class TestCheckScriptNamingTreeMode:
    def test_should_accumulate_results_across_repeated_tree_flags_and_label_each_trees_result(self, tmp_path):
        repo_a = tmp_path / "repo-a"
        repo_b = tmp_path / "repo-b"
        _write(repo_a / "scripts" / "check-density.py")
        _write(repo_b / "scripts" / "check.py")

        result = _run("--tree", str(repo_a), "--tree", str(repo_b))

        assert result.returncode == 1, result.stdout + result.stderr
        assert "repo-a" in result.stdout
        assert "repo-b" in result.stdout

        # Both the passing script (repo-a) and the failing one
        # (repo-b) must show up under their own tree's label.
        assert "check-density" in result.stdout
        assert "check.py" in result.stdout or "check " in result.stdout.lower()
