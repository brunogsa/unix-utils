#!/usr/bin/env python3
"""Behavior suite for get-repo-preflight.py, exercised at the CLI boundary.

Every case builds a real git repo under tmp_path and runs the script as a
subprocess, so what is pinned is the report a caller actually reads rather
than the internals that happen to produce it.
"""
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parent.parent / "get-repo-preflight.py"

# The global and system git configs are neutralized so
# this suite reads the same on a machine whose own config
# pins a default branch, a signing key, or a hooks path.
ISOLATED_GIT_ENV = {
    **os.environ,
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_SYSTEM": os.devnull,
}


def load_preflight_module():
    """Import the script by path so the suite can assert against its own
    caps instead of restating them as literals that drift."""
    spec = importlib.util.spec_from_file_location("get_repo_preflight", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


preflight = load_preflight_module()


def run_git(repo, *args):
    subprocess.run(
        ["git", *args], cwd=repo, env=ISOLATED_GIT_ENV, check=True, capture_output=True
    )


def commit_file(repo, filename, content, message):
    (repo / filename).write_text(content)
    run_git(repo, "add", filename)
    run_git(repo, "commit", "-m", message)


def get_report(cwd, *args):
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), *args],
        cwd=cwd,
        env=ISOLATED_GIT_ENV,
        capture_output=True,
        text=True,
    )


def get_section(report, name):
    """Return the non-blank lines under the `[name]` header, whose own
    line may carry a suffix (the log section names its range there)."""
    collected = []
    is_inside = False
    for line in report.splitlines():
        if line.startswith("["):
            is_inside = line.startswith(f"[{name}]")
            continue
        if is_inside and line.strip():
            collected.append(line)
    return collected


def get_log_subjects(report):
    return [line.split(" ", 1)[1] for line in get_section(report, "log")]


@pytest.fixture
def repo(tmp_path):
    """A git repo on branch `main` carrying a single seed commit."""
    run_git(tmp_path, "init", "-b", "main")
    run_git(tmp_path, "config", "user.email", "suite@example.test")
    run_git(tmp_path, "config", "user.name", "Preflight Suite")
    commit_file(tmp_path, "README.md", "# Fixture\n", "docs: seed the fixture repo")
    return tmp_path


class TestRepoIdentityAndState:
    def test_should_report_the_repo_root_the_current_branch_and_the_head_subject(
        self, repo
    ):
        result = get_report(repo)

        assert result.returncode == 0
        repo_lines = get_section(result.stdout, "repo")
        assert f"root: {repo.resolve()}" in repo_lines
        assert "branch: main" in repo_lines
        assert any(
            line.startswith("head: ") and line.endswith("docs: seed the fixture repo")
            for line in repo_lines
        )

    def test_should_list_every_modified_and_untracked_path_under_the_status_section(
        self, repo
    ):
        (repo / "README.md").write_text("# Fixture, edited\n")
        (repo / "scratch.txt").write_text("an untracked newcomer\n")

        status_lines = get_section(get_report(repo).stdout, "status")

        assert " M README.md" in status_lines
        assert "?? scratch.txt" in status_lines

    def test_should_report_a_clean_tree_when_nothing_was_touched(self, repo):
        assert get_section(get_report(repo).stdout, "status") == ["(clean)"]

    def test_should_report_a_detached_head_instead_of_naming_a_branch(self, repo):
        run_git(repo, "checkout", "-q", "--detach", "HEAD")

        assert "branch: (detached)" in get_section(get_report(repo).stdout, "repo")

    def test_should_report_the_branch_of_a_repo_that_has_no_commits_yet(self, tmp_path):
        run_git(tmp_path, "init", "-b", "main")

        result = get_report(tmp_path)

        assert result.returncode == 0
        repo_lines = get_section(result.stdout, "repo")
        assert "branch: main" in repo_lines
        assert "head: (no commits yet)" in repo_lines

    def test_should_truncate_an_oversized_status_listing_and_say_how_many_it_dropped(
        self, repo
    ):
        overflow = 3
        for index in range(preflight.STATUS_LINE_CAP + overflow):
            (repo / f"newcomer-{index:03}.txt").write_text("untracked\n")

        status_lines = get_section(get_report(repo).stdout, "status")

        assert len(status_lines) == preflight.STATUS_LINE_CAP + 1
        assert status_lines[-1] == f"... {overflow} more paths"

    def test_should_keep_the_untracked_count_honest_when_the_listing_is_truncated(
        self, repo
    ):
        untracked_total = preflight.STATUS_LINE_CAP + 3
        for index in range(untracked_total):
            (repo / f"newcomer-{index:03}.txt").write_text("untracked\n")

        assert (
            f"untracked-files: {untracked_total}"
            in get_section(get_report(repo).stdout, "repo")
        )


class TestCommitLog:
    def test_should_list_only_the_commits_a_feature_branch_adds_on_top_of_its_base(
        self, repo
    ):
        run_git(repo, "checkout", "-q", "-b", "feature-login")
        commit_file(repo, "login.py", "pass\n", "feat: add the login handler")
        commit_file(repo, "logout.py", "pass\n", "feat: add the logout handler")

        result = get_report(repo)

        assert "[log] main..HEAD" in result.stdout
        assert get_log_subjects(result.stdout) == [
            "feat: add the logout handler",
            "feat: add the login handler",
        ]

    def test_should_fall_back_to_recent_history_when_the_branch_adds_nothing_to_its_base(
        self, repo
    ):
        result = get_report(repo)

        assert "[log] HEAD" in result.stdout
        assert get_log_subjects(result.stdout) == ["docs: seed the fixture repo"]

    def test_should_cap_the_commit_list_at_the_requested_count(self, repo):
        run_git(repo, "checkout", "-q", "-b", "feature-batch")
        for index in range(4):
            commit_file(repo, f"unit-{index}.py", "pass\n", f"feat: add unit {index}")

        log_lines = get_section(get_report(repo, "--log-count", "2").stdout, "log")

        assert len(log_lines) == 2

    def test_should_log_against_the_base_ref_the_caller_named(self, repo):
        run_git(repo, "checkout", "-q", "-b", "feature-checkout")
        commit_file(repo, "first.py", "pass\n", "feat: add the first unit")
        commit_file(repo, "second.py", "pass\n", "feat: add the second unit")

        result = get_report(repo, "--base", "HEAD~1")

        assert "[log] HEAD~1..HEAD" in result.stdout
        assert get_log_subjects(result.stdout) == ["feat: add the second unit"]

    def test_should_report_the_base_as_unresolved_when_the_named_ref_does_not_exist(
        self, repo
    ):
        result = get_report(repo, "--base", "no-such-ref")

        assert result.returncode == 0
        assert "base: (unresolved: no-such-ref)" in get_section(result.stdout, "repo")


class TestDeclaredTestCommands:
    def test_should_report_the_commands_fenced_under_a_testing_heading_in_claude_md(
        self, repo
    ):
        (repo / "CLAUDE.md").write_text(
            "# Repo\n\n## Testing\n\n"
            "```bash\n./run-tests.sh   # every bash suite\npytest\n```\n"
        )

        command_lines = get_section(get_report(repo).stdout, "test-commands")

        assert "CLAUDE.md: ./run-tests.sh   # every bash suite" in command_lines
        assert "CLAUDE.md: pytest" in command_lines

    def test_should_ignore_fenced_commands_under_a_heading_unrelated_to_testing(
        self, repo
    ):
        (repo / "CLAUDE.md").write_text(
            "# Repo\n\n## Setup\n\n```bash\n./install.sh\n```\n"
        )

        command_lines = get_section(get_report(repo).stdout, "test-commands")

        assert command_lines == ["(none found)"]

    def test_should_report_each_package_json_script_whose_name_mentions_test(self, repo):
        (repo / "package.json").write_text(
            json.dumps({"scripts": {"test": "vitest run", "build": "tsc"}})
        )

        command_lines = get_section(get_report(repo).stdout, "test-commands")

        assert "package.json: npm run test" in command_lines
        assert not any("build" in line for line in command_lines)

    def test_should_prefix_package_json_scripts_with_pnpm_when_its_lockfile_is_present(
        self, repo
    ):
        (repo / "package.json").write_text(
            json.dumps({"scripts": {"test:unit": "vitest run"}})
        )
        (repo / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'\n")

        command_lines = get_section(get_report(repo).stdout, "test-commands")

        assert "package.json: pnpm run test:unit" in command_lines

    def test_should_report_pytest_when_the_repo_declares_a_pytest_configuration(
        self, repo
    ):
        (repo / "pytest.ini").write_text("[pytest]\npython_files = *.test.py\n")

        assert "pytest.ini: pytest" in get_section(
            get_report(repo).stdout, "test-commands"
        )

    def test_should_report_the_repo_root_run_tests_entry_point(self, repo):
        (repo / "run-tests.sh").write_text("#!/usr/bin/env bash\nexit 0\n")

        assert "run-tests.sh: ./run-tests.sh" in get_section(
            get_report(repo).stdout, "test-commands"
        )

    def test_should_report_each_makefile_target_whose_name_mentions_test(self, repo):
        (repo / "Makefile").write_text(
            "build:\n\ttsc\n\ntest-unit:\n\tpytest tests/unit\n"
        )

        command_lines = get_section(get_report(repo).stdout, "test-commands")

        assert "Makefile: make test-unit" in command_lines
        assert not any("make build" in line for line in command_lines)

    def test_should_say_no_command_was_found_when_nothing_in_the_repo_declares_one(
        self, repo
    ):
        assert get_section(get_report(repo).stdout, "test-commands") == ["(none found)"]


class TestCheckedPaths:
    def test_should_report_a_checked_path_that_exists_with_its_line_count(self, repo):
        checklist = repo / "checklist.md"
        checklist.write_text("- [ ] the first unit\n- [ ] the second unit\n")

        checked_lines = get_section(
            get_report(repo, "--check-path", str(checklist)).stdout, "checked-paths"
        )

        assert f"{checklist}: present (2 lines)" in checked_lines

    def test_should_report_a_checked_path_that_is_missing_as_absent(self, repo):
        missing = repo / "no-such-checklist.md"

        checked_lines = get_section(
            get_report(repo, "--check-path", str(missing)).stdout, "checked-paths"
        )

        assert f"{missing}: absent" in checked_lines


class TestFailureScenarios:
    def test_should_exit_non_zero_and_explain_when_the_directory_is_not_a_git_repo(
        self, tmp_path
    ):
        outside = tmp_path / "plain-directory"
        outside.mkdir()

        result = get_report(outside)

        assert result.returncode == 1
        assert "not a git work tree" in result.stderr
