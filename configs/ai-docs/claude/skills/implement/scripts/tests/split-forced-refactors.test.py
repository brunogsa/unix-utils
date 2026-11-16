import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "split-forced-refactors.py"
SKILLS_DIR = Path(__file__).resolve().parents[3]
SDD_SCRIPTS = SKILLS_DIR / "spec-driven-development/scripts"
FINDING_CHECKER = (
    SKILLS_DIR / "code-review-pipeline/scripts/check-finding-bodies.py"
)
FEATURE_BRANCH = "feature/pr-3-metrics-gate"
REFACTOR_BRANCH = "refactor/pr-2-forced-refactors"


def load_script():
    spec = importlib.util.spec_from_file_location(
        "split_forced_refactors", SCRIPT
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
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


def test_should_append_the_refactor_prs_entry_and_make_the_feature_pr_depend_on_it(
    tmp_path, run_split,
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
    repo, base = build_cherry_pick_conflict_repo(tmp_path)
    original_head = git(repo, "rev-parse", "HEAD")

    report, plan, finding = run_split_expecting_conflict(
        run_split, tmp_path, repo, base
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


def test_should_exit_2_and_leave_the_repo_untouched_when_the_plan_has_no_pr_breakdown(
    tmp_path,
):
    repo, base = build_feature_repo(tmp_path, [
        ("refactor: rewrite parser", {"parser.py": 101}, "metrics"),
    ])
    feature_head = git(repo, "rev-parse", FEATURE_BRANCH)
    plan = tmp_path / "plan_fixture.md"
    plan_without_breakdown = "## Task Breakdown\n\nNothing to split.\n"
    plan.write_text(plan_without_breakdown)
    arguments = get_split_arguments(
        repo, base, ["--plan", str(plan), "--feature-pr", "PR-2"]
    )

    with pytest.raises(SystemExit) as exit_info:
        split_forced_refactors.main(arguments)

    assert exit_info.value.code == 2
    assert git(repo, "rev-parse", FEATURE_BRANCH) == feature_head
    assert git(repo, "branch", "--list", REFACTOR_BRANCH) == ""
    assert plan.read_text() == plan_without_breakdown


def test_should_report_the_same_conflict_again_on_a_rerun_after_a_cherry_pick_conflict(
    tmp_path, run_split,
):
    repo, base = build_cherry_pick_conflict_repo(tmp_path)
    original_head = git(repo, "rev-parse", "HEAD")
    first_report, _, _ = run_split_expecting_conflict(
        run_split, tmp_path, repo, base
    )

    report, plan, finding = run_split_expecting_conflict(
        run_split, tmp_path, repo, base
    )

    assert report == first_report
    assert report["conflict_operation"] == "cherry-pick"
    assert report["finding"] == str(finding)
    assert_repo_restored_after_conflict(repo, original_head)
    assert plan.read_text() == PLAN_TEXT


