import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "get-push-route.py"


def make_repo(tmp_path, branch):
    repo = tmp_path / "repo"
    subprocess.run(["git", "init", "--quiet", "-b", branch, str(repo)], check=True)
    return repo


def run_script(cwd):
    # why: stops git walking up from the temp dir into
    # whatever repo the machine's temp dir sits under.
    env = {**os.environ, "GIT_CEILING_DIRECTORIES": str(Path(cwd).parent)}
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=cwd,
        capture_output=True,
        text=True,
        env=env,
    )


class TestDefaultBranch:
    @pytest.mark.parametrize("branch", ["master", "main"])
    def test_hands_the_push_to_the_human_when_the_checked_out_branch_is_a_default_branch(self, tmp_path, branch):
        result = run_script(make_repo(tmp_path, branch))

        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "by-hand"


class TestFeatureBranch:
    def test_lets_the_skill_push_when_the_checked_out_branch_is_a_feature_branch(self, tmp_path):
        result = run_script(make_repo(tmp_path, "feat-checkout-retry"))

        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "push"
