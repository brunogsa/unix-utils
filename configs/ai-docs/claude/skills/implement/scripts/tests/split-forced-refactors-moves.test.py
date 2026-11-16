"""split-forced-refactors moves or keeps the forced refactors,
by the file and changed-line limits."""

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import split_forced_refactors_support as support
from split_forced_refactors_support import (
    FEATURE_BRANCH,
    REFACTOR_BRANCH,
    SCRIPT,
    build_feature_repo,
    get_split_arguments,
    git,
    subjects_between,
)

# Re-bound at module level so pytest finds the shared fixtures.
isolated_git_env = support.isolated_git_env
run_split = support.run_split


def test_should_print_the_json_report_and_exit_0_when_run_as_a_command(
    tmp_path,
):
    repo, base = build_feature_repo(tmp_path, [
        ("refactor: split parser", {"parser.py": 51}, "metrics"),
        ("refactor: split writer", {"writer.py": 50}, "metrics"),
    ])

    completed = subprocess.run(
        [
            sys.executable, str(SCRIPT),
            *get_split_arguments(repo, base, []),
        ],
        capture_output=True, text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)["outcome"] == "moved"


def test_should_move_forced_refactors_of_2_files_and_101_changed_lines_onto_a_new_branch_from_the_base(
    tmp_path, run_split,
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
    tmp_path, run_split,
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


def test_should_move_6_files_of_60_changed_lines_because_only_the_file_limit_is_exceeded(
    tmp_path, run_split,
):
    repo, base = build_feature_repo(tmp_path, [
        (
            "refactor: split six modules",
            {f"module_{n}.py": 10 for n in range(6)},
            "metrics",
        ),
    ])

    report = run_split(repo, base)

    assert report["outcome"] == "moved"
    assert report["files"] == 6
    assert report["lines"] == 60
    assert len(subjects_between(repo, base, REFACTOR_BRANCH)) == 1


def test_should_keep_exactly_5_files_and_100_changed_lines_in_the_feature_pr(
    tmp_path, run_split,
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


def test_should_sum_only_gate_metrics_refactor_commits_leaving_gate_forced_test_commits_out(
    tmp_path, run_split,
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


def test_should_keep_nothing_and_leave_both_branches_alone_on_a_rerun_after_the_forced_refactors_moved(
    tmp_path, run_split,
):
    repo, base = build_feature_repo(tmp_path, [
        ("refactor: split parser", {"parser.py": 51}, "metrics"),
        ("refactor: split writer", {"writer.py": 50}, "metrics"),
        ("feat: add report", {"report.py": 3}, None),
    ])
    assert run_split(repo, base)["outcome"] == "moved"
    refactor_head = git(repo, "rev-parse", REFACTOR_BRANCH)
    feature_head = git(repo, "rev-parse", FEATURE_BRANCH)

    report = run_split(repo, base)

    assert report["outcome"] == "kept"
    assert report["commits"] == []
    assert report["needs_push"] == []
    assert git(repo, "rev-parse", REFACTOR_BRANCH) == refactor_head
    assert git(repo, "rev-parse", FEATURE_BRANCH) == feature_head
