import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "check-plan-id-leaks.py"

GIT_IDENTITY = ["-c", "user.name=Test Runner", "-c", "user.email=test@example.com"]

SPEC_PATH = "core/test/foo.spec.ts"

BASE_SPEC = (
    "describe('sales agreement merge', () => {\n"
    "  // AC-1 legacy annotation already on the base branch\n"
    "  it('accepts a valid contract set', () => {});\n"
    "});\n"
)


def git(repo, *args):
    return subprocess.run(
        ["git", *GIT_IDENTITY, *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )


def write(repo, relative_path, content):
    path = repo / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content)


def commit_all(repo, message):
    git(repo, "add", "-A")
    git(repo, "commit", "--quiet", "-m", message)


def make_repo(tmp_path, base_branch="main"):
    """A repo whose base branch holds one spec and one design doc, with
    the feature branch checked out on top of it."""
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "--quiet", "--initial-branch", base_branch)
    write(repo, SPEC_PATH, BASE_SPEC)
    write(repo, "docs/designs/merge_lld.md", "# Merge LLD\n\n### AC-4 - merge rule\n")
    commit_all(repo, "Base work")
    git(repo, "checkout", "--quiet", "-b", "feat/merge")
    return repo


def run_script(repo, *args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=repo,
        capture_output=True,
        text=True,
    )


def add_spec_lines(repo, *lines):
    """Insert lines after the spec's `it(...)` line, so the hunk starts
    past line 1 of an already-tracked file."""
    base_lines = BASE_SPEC.splitlines(keepends=True)
    added = [line + "\n" for line in lines]
    write(repo, SPEC_PATH, "".join(base_lines[:3] + added + base_lines[3:]))
    commit_all(repo, "Feature work")


class TestHappyPath:
    def test_flags_a_plan_annotation_copied_into_a_test_file_with_its_path_and_line(self, tmp_path):
        repo = make_repo(tmp_path)
        add_spec_lines(repo, "    // AC-9 T4", "    it('rejects a contract set without a sales contract', () => {});")

        result = run_script(repo, "--base", "main")

        assert result.returncode == 1
        assert result.stdout.splitlines() == [
            f"{SPEC_PATH}:4: AC-9 - // AC-9 T4",
            f"{SPEC_PATH}:4: T4 - // AC-9 T4",
        ]

    def test_ignores_a_plan_id_already_on_the_base_branch(self, tmp_path):
        repo = make_repo(tmp_path)
        add_spec_lines(repo, "    it('rejects a contract set without a sales contract', () => {});")

        result = run_script(repo, "--base", "main")

        assert result.returncode == 0
        assert result.stdout == ""

    def test_passes_when_the_branch_adds_code_without_plan_ids(self, tmp_path):
        repo = make_repo(tmp_path)
        add_spec_lines(repo, "    // a sales contract is mandatory in every set")

        result = run_script(repo, "--base", "main")

        assert result.returncode == 0
        assert result.stdout == ""

    def test_compares_against_the_repo_base_branch_when_no_base_is_given(self, tmp_path):
        repo = make_repo(tmp_path)
        add_spec_lines(repo, "    // AC-9")

        result = run_script(repo)

        assert result.returncode == 1
        assert result.stdout.splitlines() == [f"{SPEC_PATH}:4: AC-9 - // AC-9"]


class TestCornerCases:
    @pytest.mark.parametrize(
        "doc_path",
        [
            "plan_2027-contract-merge.md",
            "spec_2027-contract-merge.md",
            "docs/designs/contract-merge_lld.md",
        ],
    )
    def test_ignores_plan_ids_in_spec_plan_and_design_docs(self, tmp_path, doc_path):
        repo = make_repo(tmp_path)
        write(repo, doc_path, "- it('rejects a set without a sales contract') // AC-9 T4\n")
        commit_all(repo, "Docs")

        result = run_script(repo, "--base", "main")

        assert result.returncode == 0
        assert result.stdout == ""

    def test_ignores_plan_ids_in_a_path_the_caller_excludes(self, tmp_path):
        repo = make_repo(tmp_path)
        write(repo, "notes/session-log.md", "- covered by AC-9 T4\n")
        commit_all(repo, "Notes")

        result = run_script(repo, "--base", "main", "--exclude", "notes/*.md")

        assert result.returncode == 0
        assert result.stdout == ""

    def test_ignores_plan_ids_a_renamed_file_carries_over_from_the_base_branch(self, tmp_path):
        repo = make_repo(tmp_path)
        git(repo, "mv", SPEC_PATH, "core/test/merge.spec.ts")
        commit_all(repo, "Rename spec")

        result = run_script(repo, "--base", "main")

        assert result.returncode == 0
        assert result.stdout == ""

    def test_passes_an_acceptance_criterion_that_cites_its_committed_design_doc(self, tmp_path):
        repo = make_repo(tmp_path)
        add_spec_lines(repo, "    // AC-4 - docs/designs/merge_lld.md#ac-4")

        result = run_script(repo, "--base", "main")

        assert result.returncode == 0
        assert result.stdout == ""

    def test_flags_an_acceptance_criterion_citing_a_doc_that_is_not_committed(self, tmp_path):
        repo = make_repo(tmp_path)
        add_spec_lines(repo, "    // AC-9 - plan_2027-contract-merge.md")

        result = run_script(repo, "--base", "main")

        assert result.returncode == 1
        assert result.stdout.splitlines() == [
            f"{SPEC_PATH}:4: AC-9 - // AC-9 - plan_2027-contract-merge.md"
        ]

    def test_flags_a_plan_task_id_alone_in_a_code_comment(self, tmp_path):
        repo = make_repo(tmp_path)
        add_spec_lines(repo, "    // covered by T4")

        result = run_script(repo, "--base", "main")

        assert result.returncode == 1
        assert result.stdout.splitlines() == [f"{SPEC_PATH}:4: T4 - // covered by T4"]

    def test_passes_numbered_type_parameters_in_code(self, tmp_path):
        repo = make_repo(tmp_path)
        add_spec_lines(repo, "    type Pair<T1, T2> = [T1, T2];")

        result = run_script(repo, "--base", "main")

        assert result.returncode == 0
        assert result.stdout == ""

    def test_skips_binary_files(self, tmp_path):
        repo = make_repo(tmp_path)
        write(repo, "assets/fixture.bin", b"\x00\x01// AC-9 T4\x00")
        commit_all(repo, "Binary fixture")

        result = run_script(repo, "--base", "main")

        assert result.returncode == 0
        assert result.stdout == ""

    def test_passes_when_the_branch_adds_no_commits(self, tmp_path):
        repo = make_repo(tmp_path)

        result = run_script(repo, "--base", "main")

        assert result.returncode == 0
        assert result.stdout == ""


class TestFailureScenarios:
    def test_rejects_a_base_ref_that_does_not_exist(self, tmp_path):
        repo = make_repo(tmp_path)

        result = run_script(repo, "--base", "origin/no-such-branch")

        assert result.returncode == 2
        assert "origin/no-such-branch" in result.stderr

    def test_asks_for_an_explicit_base_when_the_repo_has_no_main_master_or_origin_head(self, tmp_path):
        repo = make_repo(tmp_path, base_branch="trunk")

        result = run_script(repo)

        assert result.returncode == 2
        assert "--base" in result.stderr

    def test_rejects_a_directory_outside_any_git_repo(self, tmp_path):
        outside = tmp_path / "not-a-repo"
        outside.mkdir()

        result = run_script(outside, "--base", "main")

        assert result.returncode == 2
        assert "not a git repository" in result.stderr
