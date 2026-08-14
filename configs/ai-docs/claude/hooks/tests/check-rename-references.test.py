"""Blackbox CLI tests for check-rename-references.py.

Every repo, settings.json, and script referenced by a test is a fixture
built under tmp_path and passed explicitly via --repo/--settings/
--native-home/--foreign-home -- no test relies on this machine's real
unix-utils or oh-my-zsh checkout (the one exception, the 2-second-budget
corner test, says so explicitly). --settings defaults to a nonexistent
path in every test that isn't itself testing settings.json content, so
a test never accidentally reads this repo's real settings.json.

Usage:
  pytest configs/ai-docs/claude/hooks/tests/check-rename-references.test.py
"""

import json
import subprocess
import sys
import time
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "check-rename-references.py"


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


def _no_settings(tmp_path):
    """A --settings path that never exists, so tests not about
    settings.json content get a clean, empty scan of that source."""
    return str(tmp_path / "no-settings.json")


def _warn_lines(result):
    return [line for line in result.stdout.splitlines() if line.startswith("WARN:")]


def _fail_lines(result):
    return [line for line in result.stdout.splitlines() if line.startswith("FAIL:")]


class TestCheckRenameReferencesHappy:
    def test_should_exit_0_when_every_referenced_full_path_resolves_to_a_real_file_in_scope(self, tmp_path):
        repo = tmp_path / "repo"
        script = _write(repo / "hooks" / "foo.sh")
        _write(repo / "README.md", f"See {script} for details.\n")

        result = _run("--repo", str(repo), "--settings", _no_settings(tmp_path))

        assert result.returncode == 0, result.stdout + result.stderr
        assert result.stdout == ""

    def test_should_scan_settings_json_every_covered_install_sh_and_every_markdown_file_in_both_repos(self, tmp_path):
        repo1 = tmp_path / "unix-utils"
        repo2 = tmp_path / "oh-my-zsh"
        _write(repo1 / "install.sh", "bash hooks/repo1-install-missing.sh\n")
        _write(repo1 / "README.md", "See hooks/repo1-md-missing.sh\n")
        _write(repo2 / "install.sh", "bash hooks/repo2-install-missing.sh\n")
        _write(repo2 / "README.md", "See hooks/repo2-md-missing.sh\n")
        settings = tmp_path / "settings.json"
        settings.write_text(
            json.dumps({"marker": f"{repo1}/hooks/settings-missing.sh"}),
            encoding="utf-8",
        )

        result = _run(
            "--repo", str(repo1), "--repo", str(repo2), "--settings", str(settings)
        )

        assert result.returncode == 1, result.stdout + result.stderr
        for expected in (
            "repo1-install-missing.sh",
            "repo1-md-missing.sh",
            "repo2-install-missing.sh",
            "repo2-md-missing.sh",
            "settings-missing.sh",
        ):
            assert expected in result.stdout, f"{expected} missing from:\n{result.stdout}"

    def test_should_substitute_the_running_platforms_home_form_before_resolving_a_foreign_platform_reference(self, tmp_path):
        # foreign_home is deliberately a path INSIDE repo (not an alien
        # filesystem root): an unsubstituted token still resolves in
        # scope, to a location that does NOT exist -- so a checker that
        # skips substitution reports a dangling reference here instead
        # of silently classifying the token as out-of-scope. Only a
        # checker that actually substitutes lands on the real foo.sh
        # and stays clean.
        repo = tmp_path / "repo"
        _write(repo / "hooks" / "foo.sh")
        foreign_home = str(repo / "foreign-placeholder")
        _write(repo / "README.md", f"See {foreign_home}/hooks/foo.sh for details.\n")

        result = _run(
            "--repo", str(repo), "--settings", _no_settings(tmp_path),
            "--native-home", str(repo), "--foreign-home", foreign_home,
        )

        assert result.returncode == 0, result.stdout + result.stderr
        assert result.stdout == ""

    def test_should_exit_0_without_reporting_a_reference_that_resolves_outside_both_covered_repos(self, tmp_path):
        repo = tmp_path / "repo"
        outside = _write(tmp_path / "outside" / "other.sh")
        _write(repo / "README.md", f"See {outside} for context.\n")

        result = _run("--repo", str(repo), "--settings", _no_settings(tmp_path))

        assert result.returncode == 0, result.stdout + result.stderr
        assert result.stdout == ""


class TestCheckRenameReferencesCorner:
    def test_should_exit_0_when_a_filesystem_absolute_glob_uses_the_double_leading_slash_for_both_the_symlink_path_and_its_target(self, tmp_path):
        settings = tmp_path / "settings.json"
        settings.write_text(
            json.dumps({"permissions": {"allow": ["Edit(//tmp/**)", "Edit(//private/tmp/**)"]}}),
            encoding="utf-8",
        )

        result = _run("--repo", str(tmp_path), "--settings", str(settings))

        assert result.returncode == 0, result.stdout + result.stderr
        assert result.stdout == ""

    def test_should_report_a_basename_referenced_from_several_markdown_files_once(self, tmp_path):
        repo = tmp_path / "repo"
        _write(repo / "a.md", "See missing-basename.sh here\n")
        _write(repo / "b.md", "Also see missing-basename.sh here\n")

        result = _run("--repo", str(repo), "--settings", _no_settings(tmp_path))

        assert result.returncode == 0, result.stdout + result.stderr
        assert result.stdout.count("missing-basename.sh") == 1, result.stdout
        warn_lines = _warn_lines(result)
        assert len(warn_lines) == 1
        assert "a.md" in warn_lines[0] and "b.md" in warn_lines[0]

    def test_should_not_evaluate_a_reference_sitting_only_in_an_uncovered_repo_or_the_stale_worktree(self, tmp_path):
        repo_covered = tmp_path / "covered"
        repo_uncovered = tmp_path / "uncovered"
        _write(repo_uncovered / "README.md", "See truly-missing-elsewhere.sh\n")
        _write(
            repo_covered / "worktrees" / "stacked-prs-pr2" / "myrepo" / "README.md",
            "See stale-worktree-missing.sh\n",
        )
        _write(repo_covered / "README.md", "Nothing missing here.\n")

        result = _run("--repo", str(repo_covered), "--settings", _no_settings(tmp_path))

        assert result.returncode == 0, result.stdout + result.stderr
        assert result.stdout == ""

    def test_should_not_read_perf_check_sh_as_a_reference_to_check_sh(self, tmp_path):
        repo = tmp_path / "repo"
        _write(repo / "hooks" / "check.sh")
        _write(repo / "README.md", "Run perf-check.sh before merging.\n")

        result = _run("--repo", str(repo), "--settings", _no_settings(tmp_path))

        assert result.returncode == 0, result.stdout + result.stderr
        assert "perf-check.sh" in result.stdout
        assert "WARN: check.sh:" not in result.stdout

    def test_should_not_read_config_json_as_a_reference_to_a_script_named_config_js(self, tmp_path):
        repo = tmp_path / "repo"
        _write(repo / "hooks" / "config.js")
        _write(repo / "README.md", "Edit config.json to configure.\n")

        result = _run("--repo", str(repo), "--settings", _no_settings(tmp_path))

        assert result.returncode == 0, result.stdout + result.stderr
        assert result.stdout == ""

    def test_should_let_a_test_prefixed_harness_neither_satisfy_nor_falsify_its_scripts_existence_check(self, tmp_path):
        repo = tmp_path / "repo"
        _write(repo / "hooks" / "test-widget.sh")
        _write(
            repo / "README.md",
            "See widget.sh for the entry point; "
            "test-widget.sh already covers the CLI wiring.\n",
        )

        result = _run("--repo", str(repo), "--settings", _no_settings(tmp_path))

        assert result.returncode == 0, result.stdout + result.stderr
        warn_lines = _warn_lines(result)
        assert len(warn_lines) == 1, result.stdout
        assert warn_lines[0].split(":", 2)[1].strip() == "widget.sh"

    def test_should_finish_the_full_in_scope_scan_within_the_2_second_budget(self):
        budget_seconds = 2.0
        samples = []
        for _ in range(3):
            start = time.perf_counter()
            run_result = _run()
            samples.append((time.perf_counter() - start, run_result))

        # A shared machine can run other processes during any single sample,
        # and contention can only ever make a sample slower, never faster.
        # The minimum across several samples is therefore the closest
        # observable estimate of what the scan costs when nothing else is
        # competing for the CPU -- the floor is the real signal, everything
        # above it is noise from machine load.
        fastest = min(elapsed for elapsed, _ in samples)
        sample_report = ", ".join(f"{elapsed:.3f}s" for elapsed, _ in samples)
        last_result = samples[-1][1]

        assert fastest < budget_seconds, (
            f"fastest of 3 runs took {fastest:.3f}s (budget {budget_seconds}s); "
            f"samples: {sample_report}\n{last_result.stdout}{last_result.stderr}"
        )
        assert last_result.returncode in (0, 1), last_result.stdout + last_result.stderr

    def test_should_be_reachable_from_the_stop_hook_entry_in_settings_json_through_the_orchestrator_at_its_own_resolved_path(self):
        # [Drift] Task 26's own working title for this test assumed
        # settings.json would name this checker directly in its Stop
        # array. Reading claude-stop-orchestrator.sh (Task 26's design
        # investigation) found every Stop-event gate dispatches through
        # that single orchestrator instead of a direct settings.json
        # entry -- a second, independent blocking Stop entry would race
        # the orchestrator's own "done" notification (Stop hooks run in
        # parallel with no short-circuit) and reintroduce the
        # double-notify bug the orchestrator's header docstring says it
        # exists to prevent.
        #
        # This test asserts the real chain instead: settings.json's Stop
        # array names the orchestrator; the orchestrator names this
        # checker's wrapper (claude-rename-guard-stop-hook.sh) at a path
        # that resolves to a real file; the wrapper names this checker
        # (SCRIPT, imported above) at its own resolved path.
        #
        # Reads the real repo files on purpose -- the second explicit
        # exception to this suite's fixtures-only convention, alongside
        # the 2-second-budget corner test above.
        repo_root = SCRIPT.parents[4]
        settings_path = repo_root / "configs" / "ai-docs" / "claude" / "settings.json"
        hooks_dir = SCRIPT.parent
        orchestrator_path = hooks_dir / "claude-stop-orchestrator.sh"
        wrapper_path = hooks_dir / "claude-rename-guard-stop-hook.sh"

        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        stop_commands = " ".join(
            hook.get("command", "")
            for group in settings.get("hooks", {}).get("Stop", [])
            for hook in group.get("hooks", [])
        )
        assert "claude-stop-orchestrator.sh" in stop_commands, stop_commands

        assert orchestrator_path.is_file(), orchestrator_path
        orchestrator_src = orchestrator_path.read_text(encoding="utf-8")
        assert "claude-rename-guard-stop-hook.sh" in orchestrator_src

        assert wrapper_path.is_file(), wrapper_path
        wrapper_src = wrapper_path.read_text(encoding="utf-8")
        assert "check-rename-references.py" in wrapper_src

        assert SCRIPT.is_file(), SCRIPT

    def test_should_not_extract_a_bare_extension_glob_mention_as_a_reference(self, tmp_path):
        # [Drift] regression: a real-corpus run against production
        # surfaced '.py'/'*.py' prose mentions ("the .py extension")
        # extracted as a bogus zero-basename token and reported as a
        # permanent FAIL -- not a rename gap, a false positive in
        # extraction itself.
        repo = tmp_path / "repo"
        _write(repo / "README.md", "Every hook here uses the *.py extension.\n")

        result = _run("--repo", str(repo), "--settings", _no_settings(tmp_path))

        assert result.returncode == 0, result.stdout + result.stderr
        assert result.stdout == ""

    def test_should_not_extract_an_ellipsis_prefixed_filename_as_a_reference(self, tmp_path):
        # [Drift] regression: a real-corpus run surfaced '...check.sh'
        # (an ellipsis abbreviation in prose, e.g. 'rename ...check.sh')
        # extracted whole, including the leading dots, as a bogus
        # dangling reference.
        repo = tmp_path / "repo"
        _write(repo / "README.md", "Rename every ...check.sh script in this batch.\n")

        result = _run("--repo", str(repo), "--settings", _no_settings(tmp_path))

        assert result.returncode == 0, result.stdout + result.stderr
        assert result.stdout == ""

    def test_should_warn_without_failing_when_an_illustrative_filename_appears_in_prose_or_a_fenced_code_block(self, tmp_path):
        repo = tmp_path / "repo"
        _write(
            repo / "README.md",
            "Prose example: run `example-script.sh` to see how it works.\n\n"
            "```bash\nexample-script.sh --flag\n```\n",
        )

        result = _run("--repo", str(repo), "--settings", _no_settings(tmp_path))

        assert result.returncode == 0, result.stdout + result.stderr
        assert "example-script.sh" in result.stdout
        assert "WARN" in result.stdout
        assert "FAIL" not in result.stdout


class TestCheckRenameReferencesFailure:
    def test_should_exit_non_zero_listing_every_dangling_reference_by_full_path_not_only_the_first(self, tmp_path):
        repo = tmp_path / "repo"
        _write(
            repo / "install.sh",
            f"bash {repo}/hooks/missing-one.sh\nbash {repo}/hooks/missing-two.sh\n",
        )

        result = _run("--repo", str(repo), "--settings", _no_settings(tmp_path))

        assert result.returncode == 1, result.stdout + result.stderr
        fail_lines = _fail_lines(result)
        # install.sh is a hard-fail source: both dangling scripts must
        # surface as their own FAIL line, not merely appear somewhere
        # in stdout (a single combined or truncated-to-one-line report
        # would still pass a bare substring check).
        assert len(fail_lines) == 2, result.stdout
        assert any("missing-one.sh" in line for line in fail_lines)
        assert any("missing-two.sh" in line for line in fail_lines)

    def test_should_exit_non_zero_when_a_full_path_stops_resolving_while_its_basename_survives_elsewhere(self, tmp_path):
        repo = tmp_path / "repo"
        _write(repo / "other-dir" / "widget.sh")
        _write(repo / "install.sh", f"bash {repo}/hooks/widget.sh\n")

        result = _run("--repo", str(repo), "--settings", _no_settings(tmp_path))

        assert result.returncode == 1, result.stdout + result.stderr
        fail_lines = _fail_lines(result)
        # Must be reported as a FAIL (install.sh is a hard-fail source)
        # keyed by the full dangling path -- not silently downgraded to
        # a WARN, and not satisfied by other-dir/widget.sh's existence.
        assert len(fail_lines) == 1, result.stdout
        assert str(Path(repo, "hooks", "widget.sh")) in fail_lines[0]

    def test_should_exit_non_zero_when_a_rename_updates_one_platforms_entry_and_leaves_its_pair_stale(self, tmp_path):
        repo = tmp_path / "repo"
        _write(repo / "hooks" / "new-name.sh")
        foreign_home = "/foreign-marker-home2"
        _write(
            repo / "install.sh",
            f"bash {tmp_path}/repo/hooks/new-name.sh\n"
            f"bash {foreign_home}/repo/hooks/old-name.sh\n",
        )

        result = _run(
            "--repo", str(repo), "--settings", _no_settings(tmp_path),
            "--native-home", str(tmp_path), "--foreign-home", foreign_home,
        )

        assert result.returncode == 1, result.stdout + result.stderr
        assert "old-name.sh" in result.stdout
        assert "new-name.sh" not in result.stdout

    def test_should_exit_non_zero_when_a_filesystem_absolute_glob_uses_a_single_leading_slash(self, tmp_path):
        settings = tmp_path / "settings.json"
        settings.write_text(
            json.dumps({"permissions": {"allow": ["Edit(/tmp/**)"]}}),
            encoding="utf-8",
        )

        result = _run("--repo", str(tmp_path), "--settings", str(settings))

        assert result.returncode == 1, result.stdout + result.stderr
        assert "Edit(/tmp/**)" in result.stdout

    def test_should_exit_non_zero_when_install_sh_still_names_a_pre_rename_script_path(self, tmp_path):
        repo = tmp_path / "repo"
        _write(repo / "install.sh", "ln -sf pre-rename-script.sh ~/.claude/\n")

        result = _run("--repo", str(repo), "--settings", _no_settings(tmp_path))

        assert result.returncode == 1, result.stdout + result.stderr
        assert "pre-rename-script.sh" in result.stdout
