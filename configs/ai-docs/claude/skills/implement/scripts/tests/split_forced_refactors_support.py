"""Temp-git-repo helpers and fixtures the split-forced-refactors
suites share.

Named without a `.test.py` or `test_` marker, so pytest
imports it and never collects it.
"""

import importlib.machinery
import json
import subprocess
import types
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "split-forced-refactors.py"
FEATURE_BRANCH = "feature/pr-3-metrics-gate"
REFACTOR_BRANCH = "refactor/pr-2-forced-refactors"


def load_script():
    loader = importlib.machinery.SourceFileLoader(
        "split_forced_refactors", str(SCRIPT)
    )
    module = types.ModuleType(loader.name)
    module.__file__ = str(SCRIPT)
    loader.exec_module(module)
    return module


split_forced_refactors = load_script()

GIT_ENV = {
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "Test Author",
    "GIT_AUTHOR_EMAIL": "author@example.com",
    "GIT_COMMITTER_NAME": "Test Author",
    "GIT_COMMITTER_EMAIL": "author@example.com",
}


@pytest.fixture(autouse=True)
def isolated_git_env(monkeypatch):
    for name, value in GIT_ENV.items():
        monkeypatch.setenv(name, value)


def git(repo, *args):
    result = subprocess.run(
        ["git", "-c", "commit.gpgsign=false", *args],
        cwd=repo, check=True, capture_output=True, text=True,
    )
    return result.stdout.strip()


def commit_files(repo, subject, line_counts, gate=None):
    for name, count in line_counts.items():
        body = "".join(f"{name} line {n}\n" for n in range(count))
        (repo / name).write_text(body)
        git(repo, "add", name)
    message = subject if gate is None else f"{subject}\n\nGate: {gate}"
    git(repo, "commit", "-m", message)


def build_feature_repo(tmp_path, commits, base_files=None):
    """A repo with a base commit, then `commits` on the feature
    branch.

    Each commit is (subject, {file name: line count}, gate
    trailer or None).
    `base_files` ({file name: line count}) joins README.md in
    the base.
    Returns the repo path and the base commit's SHA.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-b", "master")
    for name in base_files or {}:
        (repo / name).parent.mkdir(parents=True, exist_ok=True)
    commit_files(repo, "chore: base", {"README.md": 1, **(base_files or {})})
    base = git(repo, "rev-parse", "HEAD")
    git(repo, "checkout", "-b", FEATURE_BRANCH)
    for subject, line_counts, gate in commits:
        commit_files(repo, subject, line_counts, gate)
    return repo, base


def get_split_arguments(repo, base, extra_arguments):
    return [
        "--repo", str(repo),
        "--base", base,
        "--feature-branch", FEATURE_BRANCH,
        "--refactor-branch", REFACTOR_BRANCH,
        *extra_arguments,
    ]


@pytest.fixture
def run_split(capsys):
    def run(repo, base, *extra_arguments):
        arguments = get_split_arguments(repo, base, extra_arguments)
        assert split_forced_refactors.main(arguments) == 0
        return json.loads(capsys.readouterr().out)

    return run


def subjects_between(repo, older, newer):
    log = git(repo, "log", "--format=%s", f"{older}..{newer}")
    return log.splitlines()


PLAN_TEXT = """\
## Task Breakdown

### 1. Parse the declaration

**Depends on**: none

### 2. Gate the metrics

**Depends on**:
- Task 1

## PR Breakdown

### PR-1. Parse the declaration

**Tasks**: 1

**Depends on**: none

**Gates**: none

**Branch**: `master`

**Linear**:

The declaration is parsed.

### PR-2. Gate the metrics

**Tasks**: 2

**Depends on**: PR-1

**Gates**: none

**Branch**: `feature/pr-3-metrics-gate`

**Linear**:

The metrics gate runs.

---

## Open Questions

None.
"""
