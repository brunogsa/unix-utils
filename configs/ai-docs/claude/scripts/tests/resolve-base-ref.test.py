"""Blackbox CLI tests for resolve-base-ref.sh.

The script prints the base branch ref the five skill docs diff
against: origin/HEAD's remote-tracking branch, else local main,
else local master, else nothing and exit 1.

Fixtures: every test builds its own throwaway git repo under
tmp_path and runs the script with that repo as CWD. The live
repo and the user's git config are never touched.

Usage:
  ./run-tests.py <this file>
"""

import os
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "resolve-base-ref.sh"

# Isolated identity and no global/system config, so a fixture
# never depends on the machine's real git settings.
GIT_ENV = {
    **os.environ,
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "Test",
    "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_COMMITTER_NAME": "Test",
    "GIT_COMMITTER_EMAIL": "test@example.com",
}


def _git(repo, *args):
    subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
        env=GIT_ENV,
    )


def _fresh_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    return repo


def _commit_on(repo, branch):
    """Create or switch to branch and add one empty commit."""
    _git(repo, "checkout", "-q", "-B", branch)
    _git(repo, "commit", "-q", "--allow-empty", "-m", f"commit on {branch}")


def _set_fake_origin_head(repo, branch):
    """Point origin/HEAD at an existing origin/<branch>."""
    _git(repo, "update-ref", f"refs/remotes/origin/{branch}", "HEAD")
    _git(
        repo,
        "symbolic-ref",
        "refs/remotes/origin/HEAD",
        f"refs/remotes/origin/{branch}",
    )


def _set_dangling_origin_head(repo, branch):
    """Point origin/HEAD at a missing origin/<branch>."""
    _git(
        repo,
        "symbolic-ref",
        "refs/remotes/origin/HEAD",
        f"refs/remotes/origin/{branch}",
    )


def _clone_with_lagging_local_main(tmp_path):
    """Clone whose local main sits one commit behind origin/main."""
    origin = tmp_path / "origin.git"
    seed = tmp_path / "seed"
    clone = tmp_path / "clone"
    subprocess.run(
        ["git", "init", "-q", "--bare", "--initial-branch=main", str(origin)],
        check=True,
        capture_output=True,
        env=GIT_ENV,
    )
    subprocess.run(
        ["git", "init", "-q", "--initial-branch=main", str(seed)],
        check=True,
        capture_output=True,
        env=GIT_ENV,
    )
    _git(seed, "commit", "-q", "--allow-empty", "-m", "first commit on main")
    _git(seed, "push", "-q", str(origin), "main")
    subprocess.run(
        ["git", "clone", "-q", str(origin), str(clone)],
        check=True,
        capture_output=True,
        env=GIT_ENV,
    )
    _git(
        seed,
        "commit",
        "-q",
        "--allow-empty",
        "-m",
        "upstream commit the clone's local main lacks",
    )
    _git(seed, "push", "-q", str(origin), "main")
    _git(clone, "fetch", "-q", "origin")
    _git(clone, "remote", "set-head", "origin", "-a")
    return clone


def _resolve(repo):
    result = subprocess.run(
        [str(SCRIPT)],
        cwd=repo,
        capture_output=True,
        text=True,
        env=GIT_ENV,
    )
    return result.stdout.rstrip("\n"), result.returncode


class TestResolveBaseRefHappy:
    def test_should_print_origin_head_remote_tracking_branch_when_it_is_set(
        self, tmp_path
    ):
        repo = _fresh_repo(tmp_path)
        _commit_on(repo, "trunk")
        _set_fake_origin_head(repo, "trunk")

        # main also exists, so origin/HEAD must win over it.
        _commit_on(repo, "main")

        assert _resolve(repo) == ("origin/trunk", 0)

    def test_should_print_origin_main_not_the_lagging_local_main_when_origin_head_points_at_main(
        self, tmp_path
    ):
        clone = _clone_with_lagging_local_main(tmp_path)

        assert _resolve(clone) == ("origin/main", 0)


class TestResolveBaseRefFallback:
    def test_should_print_local_main_when_origin_head_points_at_a_remote_branch_that_no_longer_exists(
        self, tmp_path
    ):
        repo = _fresh_repo(tmp_path)
        _commit_on(repo, "main")
        _set_dangling_origin_head(repo, "trunk")

        assert _resolve(repo) == ("main", 0)

    def test_should_print_local_main_when_origin_head_is_unset(self, tmp_path):
        repo = _fresh_repo(tmp_path)
        _commit_on(repo, "main")

        assert _resolve(repo) == ("main", 0)

    def test_should_print_local_master_when_origin_head_and_main_are_both_absent(
        self, tmp_path
    ):
        repo = _fresh_repo(tmp_path)
        _commit_on(repo, "master")

        assert _resolve(repo) == ("master", 0)

    def test_should_prefer_main_over_master_when_both_exist(self, tmp_path):
        repo = _fresh_repo(tmp_path)
        _commit_on(repo, "master")
        _commit_on(repo, "main")

        assert _resolve(repo) == ("main", 0)


class TestResolveBaseRefFailure:
    def test_should_exit_1_with_empty_stdout_when_origin_head_main_and_master_all_miss(
        self, tmp_path
    ):
        # A repo with no commits has no resolvable ref at all.
        repo = _fresh_repo(tmp_path)

        assert _resolve(repo) == ("", 1)
