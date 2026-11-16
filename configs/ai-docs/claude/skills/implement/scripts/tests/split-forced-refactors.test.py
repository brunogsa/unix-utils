import json
import os
import re
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "split-forced-refactors.py"
FEATURE_BRANCH = "feature/pr-3-metrics-gate"
REFACTOR_BRANCH = "refactor/pr-2-forced-refactors"

GIT_ENV = {
    **os.environ,
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "Test Author",
    "GIT_AUTHOR_EMAIL": "author@example.com",
    "GIT_COMMITTER_NAME": "Test Author",
    "GIT_COMMITTER_EMAIL": "author@example.com",
}


def git(repo, *args):
    result = subprocess.run(
        ["git", "-c", "commit.gpgsign=false", *args],
        cwd=repo, env=GIT_ENV, check=True, capture_output=True, text=True,
    )
    return result.stdout.strip()


def commit_files(repo, subject, line_counts, gate=None):
    for name, count in line_counts.items():
        body = "".join(f"{name} line {n}\n" for n in range(count))
        (repo / name).write_text(body)
        git(repo, "add", name)
    message = subject if gate is None else f"{subject}\n\nGate: {gate}"
    git(repo, "commit", "-m", message)


def build_feature_repo(tmp_path, commits):
    """A repo with a base commit, then `commits` on the feature branch.

    Each commit is (subject, {file name: line count}, gate trailer or None).
    Returns the repo path and the base commit's SHA.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-b", "master")
    commit_files(repo, "chore: base", {"README.md": 1})
    base = git(repo, "rev-parse", "HEAD")
    git(repo, "checkout", "-b", FEATURE_BRANCH)
    for subject, line_counts, gate in commits:
        commit_files(repo, subject, line_counts, gate)
    return repo, base


def run_split(repo, base, *extra_arguments):
    completed = subprocess.run(
        [
            sys.executable, str(SCRIPT),
            "--repo", str(repo),
            "--base", base,
            "--feature-branch", FEATURE_BRANCH,
            "--refactor-branch", REFACTOR_BRANCH,
            *extra_arguments,
        ],
        env=GIT_ENV, capture_output=True, text=True,
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)


def subjects_between(repo, older, newer):
    log = git(repo, "log", "--format=%s", f"{older}..{newer}")
    return log.splitlines()


SDD_SCRIPTS = Path.home() / ".claude/skills/spec-driven-development/scripts"

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


def run_plan_checker(checker, plan):
    return subprocess.run(
        [str(SDD_SCRIPTS / checker), str(plan)],
        capture_output=True, text=True,
    )


def get_pr_entry(plan_text, label):
    start = plan_text.index(f"### {label}.")
    following = plan_text.find("\n### ", start + 1)
    end = following if following != -1 else len(plan_text)
    return plan_text[start:end]


def test_should_move_forced_refactors_of_2_files_and_101_changed_lines_onto_a_new_branch_from_the_base(
    tmp_path,
):
    repo, base = build_feature_repo(tmp_path, [
        ("refactor: split parser", {"parser.py": 51}, "metrics"),
        ("refactor: split writer", {"writer.py": 50}, "metrics"),
        ("feat: add report", {"report.py": 3}, None),
    ])

    report = run_split(repo, base)

    assert report["outcome"] == "moved"
    assert report["files"] == 2
    assert report["lines"] == 101
    assert subjects_between(repo, base, REFACTOR_BRANCH) == [
        "refactor: split writer",
        "refactor: split parser",
    ]
    assert subjects_between(repo, REFACTOR_BRANCH, FEATURE_BRANCH) == [
        "feat: add report"
    ]
    assert report["needs_push"] == [
        {"branch": REFACTOR_BRANCH, "force_with_lease": False},
        {"branch": FEATURE_BRANCH, "force_with_lease": True},
    ]


def test_should_sum_three_40_line_forced_refactors_to_120_lines_and_move_them(
    tmp_path,
):
    repo, base = build_feature_repo(tmp_path, [
        ("refactor: split parser", {"parser.py": 40}, "metrics"),
        ("refactor: split writer", {"writer.py": 40}, "metrics"),
        ("refactor: split loader", {"loader.py": 40}, "metrics"),
    ])

    report = run_split(repo, base)

    assert report["outcome"] == "moved"
    assert report["files"] == 3
    assert report["lines"] == 120
    assert len(subjects_between(repo, base, REFACTOR_BRANCH)) == 3
    assert subjects_between(repo, REFACTOR_BRANCH, FEATURE_BRANCH) == []


def test_should_keep_exactly_5_files_and_100_changed_lines_in_the_feature_pr(
    tmp_path,
):
    repo, base = build_feature_repo(tmp_path, [
        (
            "refactor: split five modules",
            {f"module_{n}.py": 20 for n in range(5)},
            "metrics",
        ),
    ])
    feature_head = git(repo, "rev-parse", FEATURE_BRANCH)

    report = run_split(repo, base)

    assert report["outcome"] == "kept"
    assert report["files"] == 5
    assert report["lines"] == 100
    assert report["needs_push"] == []
    assert git(repo, "rev-parse", FEATURE_BRANCH) == feature_head
    assert git(repo, "branch", "--list", REFACTOR_BRANCH) == ""


def test_should_append_the_refactor_prs_entry_and_make_the_feature_pr_depend_on_it(
    tmp_path,
):
    repo, base = build_feature_repo(tmp_path, [
        ("refactor: split parser", {"parser.py": 51}, "metrics"),
        ("refactor: split writer", {"writer.py": 50}, "metrics"),
    ])
    plan = tmp_path / "plan_fixture.md"
    plan.write_text(PLAN_TEXT)

    report = run_split(
        repo, base, "--plan", str(plan), "--feature-pr", "PR-2"
    )

    plan_text = plan.read_text()
    new_entry = get_pr_entry(plan_text, "PR-3")
    assert report["pr_entry"] == "PR-3"
    assert re.findall(r"^### (PR-\d+)\.", plan_text, re.M) == [
        "PR-1", "PR-2", "PR-3",
    ]
    assert f"**Branch**: `{REFACTOR_BRANCH}`" in new_entry
    assert "**Depends on**: PR-1\n" in new_entry
    assert "**Depends on**: PR-1, PR-3\n" in get_pr_entry(plan_text, "PR-2")
    assert plan_text.index("### PR-3.") < plan_text.index("## Open Questions")
    assert run_plan_checker("check-pr-dag.sh", plan).returncode == 0
    projection = run_plan_checker("check-pr-task-projection.py", plan)
    assert projection.returncode == 0, projection.stderr


def test_should_sum_only_gate_metrics_refactor_commits_leaving_gate_forced_test_commits_out(
    tmp_path,
):
    repo, base = build_feature_repo(tmp_path, [
        ("refactor: split parser", {"parser.py": 30}, "metrics"),
        (
            "test: cover the parser branches",
            {"test_parser.py": 150},
            "changed-line coverage",
        ),
    ])
    refactor_sha = git(repo, "rev-parse", f"{FEATURE_BRANCH}~1")

    report = run_split(repo, base)

    assert report["outcome"] == "kept"
    assert report["files"] == 1
    assert report["lines"] == 30
    assert report["commits"] == [refactor_sha]


