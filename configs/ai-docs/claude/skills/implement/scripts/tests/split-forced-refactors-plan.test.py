"""split-forced-refactors writes the refactor PR into the plan's
PR Breakdown, and refuses a plan that has none."""

import re
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import split_forced_refactors_support as support
from split_forced_refactors_support import (
    FEATURE_BRANCH,
    PLAN_TEXT,
    REFACTOR_BRANCH,
    build_feature_repo,
    get_split_arguments,
    git,
    split_forced_refactors,
)

# Re-bound at module level so pytest finds the shared fixtures.
isolated_git_env = support.isolated_git_env
run_split = support.run_split

SKILLS_DIR = Path(__file__).resolve().parents[3]
SDD_SCRIPTS = SKILLS_DIR / "spec-driven-development/scripts"


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
