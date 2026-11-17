"""measure-quality-metrics.py records, on each measurement, how
many commits touched its file in the last 90 days."""

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_support import GIT_ENV, git, make_repo, run_measure

CART_PYTHON = (
    "def apply_discount(total, rate):\n"
    "    return total - total * rate\n"
)

DECLARATION_TEXT = """\
excluded_paths: []
ignored_extensions: [.md]
per_unit: []
languages:
  python:
    extensions: [.py]
    metrics: [nesting, parameters]
"""

DAYS_BEYOND_THE_WINDOW = 120


def commit_dated(repo, message, days_ago):
    when = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()
    git_env = {**GIT_ENV, "GIT_AUTHOR_DATE": when, "GIT_COMMITTER_DATE": when}
    subprocess.run(["git", "add", "--all"], cwd=repo, env=git_env, check=True)
    subprocess.run(
        ["git", "commit", "--quiet", "-m", message], cwd=repo, env=git_env, check=True
    )


def churn_by_file(repo, tmp_path, *files):
    declaration_path = tmp_path / "declaration.yaml"
    declaration_path.write_text(DECLARATION_TEXT)
    result = run_measure(repo, declaration_path, "--files", *files)
    assert result.returncode in (0, 1), result.stderr
    report = json.loads(result.stdout)
    return {record["file"]: record["churn"] for record in report["measurements"]}


def test_should_count_only_the_commits_of_the_last_90_days_for_a_file_with_an_older_commit(
    tmp_path
):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "--quiet", "--initial-branch=main")
    (repo / "a.py").write_text(CART_PYTHON)
    commit_dated(repo, "first change", days_ago=DAYS_BEYOND_THE_WINDOW)
    (repo / "a.py").write_text(CART_PYTHON + "\n# second\n")
    commit_dated(repo, "second change", days_ago=30)
    (repo / "a.py").write_text(CART_PYTHON + "\n# third\n")
    commit_dated(repo, "third change", days_ago=1)

    churn = churn_by_file(repo, tmp_path, "a.py")

    assert churn == {"a.py": 2}


def test_should_count_a_repo_wide_sweep_commit_that_changed_50_files_as_one_commit_of_each_file(
    tmp_path
):
    sweep_files = {f"pkg/module_{number}.py": CART_PYTHON for number in range(50)}
    repo = make_repo(tmp_path, sweep_files)

    churn = churn_by_file(repo, tmp_path, "pkg/module_7.py")

    assert churn == {"pkg/module_7.py": 1}


def test_should_record_no_churn_for_a_file_outside_any_repo_and_still_measure_it(tmp_path):
    folder = tmp_path / "loose"
    folder.mkdir()
    (folder / "a.py").write_text(CART_PYTHON)

    churn = churn_by_file(folder, tmp_path, "a.py")

    assert churn == {"a.py": None}
