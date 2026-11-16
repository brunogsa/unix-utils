"""split-forced-refactors keeps the forced refactors in the
feature PR, with a metrics finding, when a move conflicts."""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import split_forced_refactors_support as support
from split_forced_refactors_support import (
    FEATURE_BRANCH,
    PLAN_TEXT,
    REFACTOR_BRANCH,
    build_feature_repo,
    commit_files,
    git,
)

# Re-bound at module level so pytest finds the shared fixtures.
isolated_git_env = support.isolated_git_env
run_split = support.run_split

FINDING_CHECKER = (
    Path(__file__).resolve().parents[3]
    / "code-review-pipeline/scripts/check-finding-bodies.py"
)


def run_split_expecting_conflict(run_split, tmp_path, repo, base):
    plan = tmp_path / "plan_fixture.md"
    plan.write_text(PLAN_TEXT)
    finding = tmp_path / "finding_fixture.md"
    report = run_split(
        repo, base,
        "--plan", str(plan), "--feature-pr", "PR-2",
        "--finding-out", str(finding),
    )
    return report, plan, finding


def build_cherry_pick_conflict_repo(tmp_path):
    # The refactor rewrites parser.py, made by a feature commit,
    # so the base has no parser.py: a modify/delete conflict.
    return build_feature_repo(tmp_path, [
        ("feat: add parser", {"parser.py": 3}, None),
        ("refactor: rewrite parser", {"parser.py": 120}, "metrics"),
    ])


def split_cherry_pick_conflict(run_split, tmp_path):
    repo, base = build_cherry_pick_conflict_repo(tmp_path)
    original_head = git(repo, "rev-parse", "HEAD")
    report, plan, finding = run_split_expecting_conflict(
        run_split, tmp_path, repo, base
    )
    return repo, original_head, report, plan, finding


def assert_repo_restored_after_conflict(repo, original_head):
    assert git(repo, "rev-parse", "--abbrev-ref", "HEAD") == FEATURE_BRANCH
    assert git(repo, "rev-parse", "HEAD") == original_head
    for leftover in ("CHERRY_PICK_HEAD", "rebase-merge", "rebase-apply"):
        assert not (repo / ".git" / leftover).exists()
    assert git(repo, "branch", "--list", REFACTOR_BRANCH) == ""
    assert git(repo, "status", "--porcelain") == ""


def assert_finding_passes_the_body_checker(finding):
    assert finding.read_text().startswith("### 1. [MEDIUM][metrics] ")
    checked = subprocess.run(
        [sys.executable, str(FINDING_CHECKER), str(finding)],
        capture_output=True, text=True,
    )
    assert checked.returncode == 0, checked.stdout + checked.stderr


def assert_conflict_kept_the_commits_in_the_feature_pr(
    repo, report, finding, operation, original_head
):
    # Each fixture's only forced refactor is the branch head.
    assert report["outcome"] == "conflict"
    assert report["conflict_operation"] == operation
    assert report["commits"] == [original_head]
    assert report["refactor_branch"] is None
    assert report["needs_push"] == []
    assert report["pr_entry"] is None
    assert report["finding"] == str(finding)
    assert_repo_restored_after_conflict(repo, original_head)
    assert_finding_passes_the_body_checker(finding)


def test_should_keep_the_forced_refactors_in_the_feature_pr_with_a_metrics_finding_when_the_cherry_pick_conflicts(
    tmp_path, run_split,
):
    repo, original_head, report, plan, finding = (
        split_cherry_pick_conflict(run_split, tmp_path)
    )

    assert_conflict_kept_the_commits_in_the_feature_pr(
        repo, report, finding, "cherry-pick", original_head
    )
    assert plan.read_text() == PLAN_TEXT


def test_should_restore_the_detached_head_at_the_starting_commit_when_the_cherry_pick_conflicts(
    tmp_path, run_split,
):
    repo, base = build_cherry_pick_conflict_repo(tmp_path)
    original_head = git(repo, "rev-parse", "HEAD")
    git(repo, "checkout", "--detach", original_head)

    report, _, _ = run_split_expecting_conflict(
        run_split, tmp_path, repo, base
    )

    assert report["outcome"] == "conflict"
    assert git(repo, "rev-parse", "HEAD") == original_head
    assert git(repo, "branch", "--show-current") == ""
    assert git(repo, "branch", "--list", REFACTOR_BRANCH) == ""


def test_should_keep_the_forced_refactors_in_the_feature_pr_with_a_metrics_finding_when_the_rebase_conflicts(
    tmp_path, run_split,
):
    # The cherry-pick works: the refactor moves pkg/parser.py
    # to core/ and adds loader.py. The rebase then replays the
    # feature commit adding pkg/report.py into pkg/, a directory
    # the refactor branch moved away: a file-location conflict.
    repo, base = build_feature_repo(
        tmp_path, [], base_files={"pkg/parser.py": 20}
    )
    commit_files(repo, "feat: add report", {"pkg/report.py": 3})
    (repo / "core").mkdir()
    git(repo, "mv", "pkg/parser.py", "core/parser.py")
    commit_files(
        repo, "refactor: move parser and add loader",
        {"loader.py": 120}, "metrics",
    )
    original_head = git(repo, "rev-parse", "HEAD")

    report, plan, finding = run_split_expecting_conflict(
        run_split, tmp_path, repo, base
    )

    assert_conflict_kept_the_commits_in_the_feature_pr(
        repo, report, finding, "rebase", original_head
    )
    assert plan.read_text() == PLAN_TEXT


def test_should_report_the_same_conflict_again_on_a_rerun_after_a_cherry_pick_conflict(
    tmp_path, run_split,
):
    repo, original_head, first_report, _, _ = (
        split_cherry_pick_conflict(run_split, tmp_path)
    )
    base = git(repo, "rev-parse", "master")

    report, plan, finding = run_split_expecting_conflict(
        run_split, tmp_path, repo, base
    )

    assert report == first_report
    assert_conflict_kept_the_commits_in_the_feature_pr(
        repo, report, finding, "cherry-pick", original_head
    )
    assert plan.read_text() == PLAN_TEXT
