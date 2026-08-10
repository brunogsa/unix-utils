"""Blackbox CLI tests for check-shell-harness-orphans.py.

Fixtures: none on disk except what each test writes to tmp_path.
Directory shapes mirror three real harnesses in this repo
(test-global-config-invariants.sh, test-check-bullet-gap-fix.sh,
test-check-missing-why.sh) closely enough to reproduce the exact
resolution puzzle each one poses, but every file the tests write and
read lives under tmp_path — never against the live repo tree, which
concurrent sibling tasks are actively editing.

Usage:
  pytest configs/ai-docs/claude/scripts/tests/check-shell-harness-orphans.test.py
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent.parent / "check-shell-harness-orphans.py"


def _run(*args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
    )


def _write(path, content="# fixture, body not read by the checker\n"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _write_overrides(tmp_path, mapping):
    overrides_path = tmp_path / "overrides.json"
    overrides_path.write_text(json.dumps(mapping), encoding="utf-8")
    return overrides_path


class TestCheckShellHarnessOrphansHappy:
    def test_should_exit_0_when_a_test_prefixed_harness_pairs_with_a_stem_that_is_still_shell(
        self, tmp_path
    ):
        _write(tmp_path / "scripts" / "check-density.sh")
        harness = _write(tmp_path / "scripts" / "tests" / "test-check-density.sh")

        result = _run("--tree", str(tmp_path))

        assert result.returncode == 0, result.stdout + result.stderr
        assert "OK" in result.stdout
        assert str(harness) in result.stdout


class TestCheckShellHarnessOrphansFailure:
    @pytest.mark.parametrize("converted_extension", [".py", ".js"])
    def test_should_exit_non_zero_naming_the_harness_left_behind_for_a_stem_that_now_ships_as_py_or_js(
        self, tmp_path, converted_extension
    ):
        _write(tmp_path / "scripts" / f"check-density{converted_extension}")
        harness = _write(tmp_path / "scripts" / "tests" / "test-check-density.sh")

        result = _run("--tree", str(tmp_path))

        assert result.returncode == 1, result.stdout + result.stderr
        assert "FAIL" in result.stdout
        assert str(harness) in result.stdout

    def test_should_exit_non_zero_without_inferring_a_subject_when_a_mismatched_stem_harness_has_no_override_entry(
        self, tmp_path
    ):
        # Mirrors test-check-bullet-gap-fix.sh: the harness stem
        # carries a trailing qualifier ("-fix") its real subject
        # doesn't have, so naive stem-matching finds nothing. The
        # real subject genuinely exists on disk in the subject dir,
        # but with NO override entry naming it. A checker that
        # "helpfully" trims/guesses the subject from the filename
        # would wrongly resolve and clear this harness -- exactly
        # what Scout #119 warned would destroy real coverage. This
        # test asserts the opposite: loud failure, and the would-be
        # subject never named as resolved.
        _write(tmp_path / "skills" / "doc" / "scripts" / "check-bullet-gap.py")
        harness = _write(
            tmp_path
            / "skills"
            / "doc"
            / "scripts"
            / "tests"
            / "test-check-bullet-gap-fix.sh"
        )

        result = _run("--tree", str(tmp_path))

        assert result.returncode == 1, result.stdout + result.stderr
        assert str(harness) in result.stdout
        assert "no override entry" in result.stdout
        assert "check-bullet-gap.py" not in result.stdout

    def test_should_exit_non_zero_naming_the_harness_when_it_cannot_be_resolved_and_has_no_override_entry(
        self, tmp_path
    ):
        # Generic unmapped case, distinct fixture from the
        # mismatched-stem test above: no sibling subject file at all,
        # and no --overrides flag given.
        harness = _write(tmp_path / "scripts" / "tests" / "test-mystery-thing.sh")

        result = _run("--tree", str(tmp_path))

        assert result.returncode == 1, result.stdout + result.stderr
        assert str(harness) in result.stdout
        assert "no override entry" in result.stdout


class TestCheckShellHarnessOrphansCorner:
    def test_should_exit_0_and_explicitly_report_no_resolvable_subject_when_a_harness_spans_multiple_files_with_no_single_subject(
        self, tmp_path
    ):
        # Mirrors test-global-config-invariants.sh: no single
        # resolvable subject (it spans install.sh, settings.json,
        # CLAUDE.md). Must be handled LOUDLY via an explicit
        # override entry naming "no subject" -- never a silent
        # fall-through to a bare, unexplained exit 0.
        harness = _write(tmp_path / "tests" / "test-global-config-invariants.sh")
        rel_key = str(harness.relative_to(tmp_path))
        overrides = _write_overrides(tmp_path, {rel_key: None})

        result = _run("--tree", str(tmp_path), "--overrides", str(overrides))

        assert result.returncode == 0, result.stdout + result.stderr
        assert str(harness) in result.stdout
        assert "no single subject" in result.stdout

    def test_should_trust_an_override_entry_over_the_harness_filename_when_resolving_a_mismatched_stem_harnesss_still_shell_subject(
        self, tmp_path
    ):
        # Mirrors test-check-missing-why.sh: the harness stem
        # describes the CHECK, not the file -- naive stem-matching
        # fails -- but an override entry names its real, still-shell
        # subject. Proves the map, not the filename, decides.
        _write(tmp_path / "skills" / "perf" / "scripts" / "check.sh")
        harness = _write(
            tmp_path
            / "skills"
            / "perf"
            / "scripts"
            / "tests"
            / "test-check-missing-why.sh"
        )
        rel_key = str(harness.relative_to(tmp_path))
        overrides = _write_overrides(
            tmp_path, {rel_key: "skills/perf/scripts/check.sh"}
        )

        result = _run("--tree", str(tmp_path), "--overrides", str(overrides))

        assert result.returncode == 0, result.stdout + result.stderr
        assert "OK" in result.stdout
        assert str(harness) in result.stdout

    def test_should_skip_a_harness_nested_under_the_stale_worktree_checkout(
        self, tmp_path
    ):
        # Same stale-worktree exclusion check-script-naming.py
        # already applies -- reused, not reinvented. This harness
        # would otherwise fail as unresolved (no sibling subject,
        # no override), so a non-empty, exit-0 result proves it was
        # genuinely excluded, not accidentally resolved OK.
        repo = tmp_path / "worktrees" / "stacked-prs-pr2" / "myrepo"
        _write(repo / "scripts" / "tests" / "test-check-density.sh")

        result = _run("--tree", str(repo))

        assert result.returncode == 0, result.stdout + result.stderr
        assert result.stdout.strip() == ""
