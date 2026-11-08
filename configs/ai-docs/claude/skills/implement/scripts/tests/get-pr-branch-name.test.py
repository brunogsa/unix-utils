import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "get-pr-branch-name.py"

GIT_IDENTITY = ["-c", "user.name=Test Runner", "-c", "user.email=test@example.com"]


def git(repo, *args):
    return subprocess.run(
        ["git", *GIT_IDENTITY, *args],
        cwd=repo,
        capture_output=True,
        text=True,
    )


def make_pushed_repo(tmp_path, branch):
    origin = tmp_path / "origin.git"
    repo = tmp_path / "repo"
    subprocess.run(["git", "init", "--quiet", "--bare", str(origin)], check=True)
    subprocess.run(["git", "init", "--quiet", str(repo)], check=True)
    git(repo, "checkout", "--quiet", "-b", branch)
    git(repo, "commit", "--quiet", "--allow-empty", "-m", "Root PR work")
    git(repo, "remote", "add", "origin", str(origin))
    git(repo, "push", "--quiet", "origin", branch)
    return repo


def run_script(repo, *args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=repo,
        capture_output=True,
        text=True,
    )


class TestHappyPath:
    def test_should_let_a_dependent_pr_branch_be_created_while_the_root_pr_feature_branch_exists(self, tmp_path):
        repo = make_pushed_repo(tmp_path, "project/new-account")

        result = run_script(repo, "PR-2")
        checkout = git(repo, "checkout", "--quiet", "-b", result.stdout.strip())

        assert result.returncode == 0
        assert checkout.returncode == 0, checkout.stderr

    def test_should_let_a_dependent_pr_branch_be_pushed_while_the_root_pr_feature_branch_is_on_the_remote(self, tmp_path):
        repo = make_pushed_repo(tmp_path, "project/new-account")
        dependent_branch = run_script(repo, "PR-2").stdout.strip()
        git(repo, "branch", dependent_branch)

        push = git(repo, "push", "--quiet", "origin", dependent_branch)

        assert push.returncode == 0, push.stderr


class TestCornerCases:
    def test_should_name_the_next_pr_after_the_feature_branch_when_head_sits_on_the_previous_pr_stacked_task_layer(self, tmp_path):
        repo = make_pushed_repo(tmp_path, "project/new-account-pr2-t4")

        result = run_script(repo, "PR-3")

        assert result.stdout.strip() == "project/new-account-pr3"

    def test_should_name_the_next_pr_after_the_feature_branch_when_head_sits_on_a_pr_branch_named_under_the_old_nested_scheme(self, tmp_path):
        repo = make_pushed_repo(tmp_path, "project/new-account/pr2")

        result = run_script(repo, "PR-3")

        assert result.stdout.strip() == "project/new-account-pr3"


class TestFailureScenarios:
    def test_should_refuse_to_name_a_branch_when_head_is_detached(self, tmp_path):
        repo = make_pushed_repo(tmp_path, "project/new-account")
        git(repo, "checkout", "--quiet", "--detach")

        result = run_script(repo, "PR-2")

        assert (result.returncode, result.stdout) == (2, "")

    @pytest.mark.parametrize("label", ["4", "pr-2", "PR-", "PR-2a"])
    def test_should_refuse_a_label_that_is_not_a_pr_n_label(self, tmp_path, label):
        repo = make_pushed_repo(tmp_path, "project/new-account")

        result = run_script(repo, label)

        assert (result.returncode, result.stdout) == (2, "")

    def test_should_refuse_a_call_with_no_label(self, tmp_path):
        repo = make_pushed_repo(tmp_path, "project/new-account")

        result = run_script(repo)

        assert (result.returncode, result.stdout) == (2, "")
