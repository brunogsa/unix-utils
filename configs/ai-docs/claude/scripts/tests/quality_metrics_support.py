"""Temp-git-repo and measure-script helpers the quality-metrics suites share.

Named without a `.test.py` or `test_` marker, so pytest imports it
and never collects it.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
MEASURE_SCRIPT = SCRIPTS_DIR / "measure-quality-metrics.py"
SHIPPED_DECLARATION = SCRIPTS_DIR / "quality-metrics.yaml"

GIT_ENV = {
    **os.environ,
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "Fixture Author",
    "GIT_AUTHOR_EMAIL": "fixture.author@example.com",
    "GIT_COMMITTER_NAME": "Fixture Author",
    "GIT_COMMITTER_EMAIL": "fixture.author@example.com",
}


def git(repo, *args):
    subprocess.run(["git", *args], cwd=repo, env=GIT_ENV, check=True, capture_output=True)


def make_repo(tmp_path, files):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "--quiet", "--initial-branch=main")
    for name, text in files.items():
        (repo / name).parent.mkdir(parents=True, exist_ok=True)
        (repo / name).write_text(text)
    git(repo, "add", "--all")
    git(repo, "commit", "--quiet", "-m", "base")
    return repo


def commit_all(repo, message):
    git(repo, "add", "--all")
    git(repo, "commit", "--quiet", "-m", message)


def head_of(repo):
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, env=GIT_ENV, check=True, capture_output=True, text=True
    ).stdout.strip()


def run_measure(repo, declaration_path, *arguments):
    return subprocess.run(
        [sys.executable, str(MEASURE_SCRIPT), *arguments, "--declaration", str(declaration_path)],
        cwd=repo, env=GIT_ENV, capture_output=True, text=True,
    )


def measure_report(repo, declaration_path, *arguments):
    """The measure script's parsed JSON report; fails loudly on no output."""
    result = run_measure(repo, declaration_path, *arguments)
    assert result.stdout, f"no output; stderr: {result.stderr}"
    return json.loads(result.stdout)
