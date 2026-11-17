"""Blackbox CLI tests for check-bullet-gap.py.

Covers which list shapes the scan reports, the --fix rewrite,
and the --changed-only scoping. Every fixture is a file or git
repo under pytest's tmp_path.

Usage:
  ./run-tests.py <this file>
"""

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "check-bullet-gap.py"

SUB_BULLET_VIOLATION = (
    "- Parent bullet with a nested child right below it.\n"
    "  - Child sub-bullet, one level deeper.\n"
    "- Sibling bullet flush against the child above (no gap).\n"
)
SUB_BULLET_FIXED = (
    "- Parent bullet with a nested child right below it.\n"
    "  - Child sub-bullet, one level deeper.\n"
    "\n"
    "- Sibling bullet flush against the child above (no gap).\n"
)


def run(tmp_path, content):
    """Write one fixture and run the checker over it as a
    subprocess, the way the prose-format PostToolUse hook
    calls it."""
    path = tmp_path / "doc.md"
    path.write_text(content, encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(path)],
        capture_output=True,
        text=True,
    )


def hits(result):
    """The `<line>:<detail>` rows as [(int, str)], dropping the
    `==` header.

    Asserts the checker actually ran first (exit 0 or 1): a
    crash prints no rows, which would otherwise pass every
    "is not reported" test.
    """
    assert result.returncode in (0, 1), result.stderr
    rows = []
    for line in result.stdout.splitlines():
        if not line.strip() or line.startswith("== "):
            continue
        number, detail = line.split(":", 1)
        rows.append((int(number), detail))
    return rows


def test_should_accept_a_team_pr_template_checklist_whose_nested_checkboxes_have_no_blank_lines(tmp_path):
    # Shape of the Checklist section in a team repo's
    # .github/PULL_REQUEST_TEMPLATE.md, which PR bodies
    # copy verbatim.
    content = (
        "Esse PR:\n"
        "\n"
        "- [x] Foi testado localmente\n"
        "- [ ] Nova migração no DB\n"
        "  - [X] Ativado run-migrations nas pipelines de qa, stage e prod\n"
        "- [ ] Novos recursos de infra que precisam ser criados no localstack\n"
        "  - [ ] Fila nova adicionada em scripts/testing/local-resources/setup_sqs.sh\n"
        "  - [ ] Tópico novo adicionado em scripts/testing/local-resources/setup_sns.sh\n"
        "- [ ] Nova variavel de ambiente\n"
    )

    result = run(tmp_path, content)

    assert hits(result) == []
    assert result.returncode == 0


def test_should_still_report_a_plain_nested_bullet_list_with_no_blank_line_after_the_child(tmp_path):
    content = (
        "- Retry the upload when the bucket returns 503\n"
        "  - Cap the retries at three attempts\n"
        "- Log the final failure with the object key\n"
    )

    result = run(tmp_path, content)

    assert hits(result) == [(2, "sub-bullet")]
    assert result.returncode == 1


def test_should_still_report_a_nested_checkbox_ending_flush_against_a_plain_bullet(tmp_path):
    content = (
        "- [ ] Nova variavel de ambiente\n"
        "  - [ ] cadastrada na AWS (QA, STAGE, PROD)\n"
        "- Observações do revisor sobre o deploy\n"
    )

    result = run(tmp_path, content)

    assert hits(result) == [(2, "sub-bullet")]
    assert result.returncode == 1


def _cli(*args, cwd=None):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        cwd=cwd,
    )


def _new_repo(tmp_path, name):
    # resolve() maps macOS /var to /private/var, the form
    # git rev-parse --show-toplevel reports.
    repo = tmp_path.resolve() / name
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "."], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=repo, check=True)
    return repo


def _commit_all(repo):
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "base"], cwd=repo, check=True)


def _violation_section(letter):
    return (
        f"- Parent {letter} with a nested child right below it.\n"
        f"  - Child {letter} sub-bullet, one level deeper.\n"
        f"- Sibling {letter} flush against the child above (no gap).\n"
    )


class TestFixMode:
    def test_should_insert_a_blank_line_after_a_sub_bullet_hit(self, tmp_path):
        path = tmp_path / "sub-bullet.md"
        path.write_text(SUB_BULLET_VIOLATION, encoding="utf-8")

        result = _cli("--fix", str(path))

        assert result.returncode == 0
        assert path.read_text(encoding="utf-8") == SUB_BULLET_FIXED

    def test_should_pass_the_plain_check_after_fixing_a_sub_bullet_hit(self, tmp_path):
        path = tmp_path / "sub-bullet.md"
        path.write_text(SUB_BULLET_VIOLATION, encoding="utf-8")
        _cli("--fix", str(path))

        result = _cli(str(path))

        assert result.returncode == 0

    def test_should_insert_a_blank_line_after_a_bullet_over_80_percent_of_the_density_cap(self, tmp_path):
        # 210 chars: over the 205-char gap threshold, under the
        # 256-char cap check-density.sh enforces separately.
        long_bullet = (
            "- This bullet is deliberately long enough to cross the eighty percent gap threshold "
            "used by check-bullet-gap.py, comfortably under the two-hundred-fifty-six character "
            "density cap check-density.sh enforces separately."
        )
        sibling = "- Sibling bullet flush against the long one above (no gap).\n"
        path = tmp_path / "over-80pct.md"
        path.write_text(f"{long_bullet}\n{sibling}", encoding="utf-8")

        result = _cli("--fix", str(path))

        assert result.returncode == 0
        assert path.read_text(encoding="utf-8") == f"{long_bullet}\n\n{sibling}"

    def test_should_pass_the_plain_check_after_fixing_an_over_80_percent_hit(self, tmp_path):
        long_bullet = (
            "- This bullet is deliberately long enough to cross the eighty percent gap threshold "
            "used by check-bullet-gap.py, comfortably under the two-hundred-fifty-six character "
            "density cap check-density.sh enforces separately."
        )
        path = tmp_path / "over-80pct.md"
        path.write_text(f"{long_bullet}\n- Sibling bullet flush against the long one above (no gap).\n", encoding="utf-8")
        _cli("--fix", str(path))

        result = _cli(str(path))

        assert result.returncode == 0

    def test_should_leave_the_file_byte_identical_when_fix_flag_is_omitted(self, tmp_path):
        path = tmp_path / "no-fix.md"
        path.write_text(SUB_BULLET_VIOLATION, encoding="utf-8")

        _cli(str(path))

        assert path.read_text(encoding="utf-8") == SUB_BULLET_VIOLATION

    def test_should_exit_1_when_fix_flag_is_omitted_and_a_violation_exists(self, tmp_path):
        path = tmp_path / "no-fix.md"
        path.write_text(SUB_BULLET_VIOLATION, encoding="utf-8")

        result = _cli(str(path))

        assert result.returncode == 1


class TestChangedOnly:
    def test_should_hide_a_pre_existing_violation_when_a_newly_added_one_is_reported(self, tmp_path):
        repo = _new_repo(tmp_path, "mixed-scope-check")
        (repo / "mixed.md").write_text(_violation_section("A"), encoding="utf-8")
        _commit_all(repo)

        # Section A matches HEAD; only section B is newly added.
        (repo / "mixed.md").write_text(
            _violation_section("A") + _violation_section("B"), encoding="utf-8"
        )

        result = _cli("--changed-only", "mixed.md", cwd=repo)

        assert result.stdout == "== mixed.md\n5:sub-bullet\n"

    def test_should_exit_1_when_one_in_scope_violation_remains_under_changed_only(self, tmp_path):
        repo = _new_repo(tmp_path, "mixed-scope-check")
        (repo / "mixed.md").write_text(_violation_section("A"), encoding="utf-8")
        _commit_all(repo)
        (repo / "mixed.md").write_text(
            _violation_section("A") + _violation_section("B"), encoding="utf-8"
        )

        result = _cli("--changed-only", "mixed.md", cwd=repo)

        assert result.returncode == 1

    def test_should_fix_only_the_newly_added_hit_and_leave_the_pre_existing_one_untouched(self, tmp_path):
        repo = _new_repo(tmp_path, "mixed-scope-fix")
        (repo / "mixed.md").write_text(_violation_section("A"), encoding="utf-8")
        _commit_all(repo)
        (repo / "mixed.md").write_text(
            _violation_section("A") + _violation_section("B"), encoding="utf-8"
        )

        _cli("--fix", "--changed-only", "mixed.md", cwd=repo)

        expected = (
            _violation_section("A")
            + "- Parent B with a nested child right below it.\n"
            "  - Child B sub-bullet, one level deeper.\n"
            "\n"
            "- Sibling B flush against the child above (no gap).\n"
        )
        assert (repo / "mixed.md").read_text(encoding="utf-8") == expected

    def test_should_exit_0_after_fixing_every_in_scope_violation_while_a_pre_existing_one_stays(self, tmp_path):
        repo = _new_repo(tmp_path, "mixed-scope-fix")
        (repo / "mixed.md").write_text(_violation_section("A"), encoding="utf-8")
        _commit_all(repo)
        (repo / "mixed.md").write_text(
            _violation_section("A") + _violation_section("B"), encoding="utf-8"
        )

        result = _cli("--fix", "--changed-only", "mixed.md", cwd=repo)

        assert result.returncode == 0

    def test_should_print_nothing_and_exit_0_for_a_tracked_unmodified_file_with_a_pre_existing_violation(self, tmp_path):
        repo = _new_repo(tmp_path, "unmodified-scope")
        (repo / "unmodified.md").write_text(SUB_BULLET_VIOLATION, encoding="utf-8")
        _commit_all(repo)

        result = _cli("--changed-only", "unmodified.md", cwd=repo)

        assert result.stdout == ""
        assert result.returncode == 0

    def test_should_leave_a_tracked_unmodified_file_byte_identical_under_fix(self, tmp_path):
        repo = _new_repo(tmp_path, "unmodified-scope")
        (repo / "unmodified.md").write_text(SUB_BULLET_VIOLATION, encoding="utf-8")
        _commit_all(repo)

        result = _cli("--fix", "--changed-only", "unmodified.md", cwd=repo)

        assert (repo / "unmodified.md").read_text(encoding="utf-8") == SUB_BULLET_VIOLATION
        assert result.returncode == 0

    def test_should_fix_every_hit_in_a_never_added_file_same_as_a_full_scan(self, tmp_path):
        repo = _new_repo(tmp_path, "untracked-scope")
        subprocess.run(["git", "commit", "-q", "--allow-empty", "-m", "base"], cwd=repo, check=True)
        (repo / "untracked.md").write_text(SUB_BULLET_VIOLATION, encoding="utf-8")

        result = _cli("--fix", "--changed-only", "untracked.md", cwd=repo)

        assert result.returncode == 0
        assert (repo / "untracked.md").read_text(encoding="utf-8") == SUB_BULLET_FIXED

    def test_should_pass_the_plain_check_after_fixing_a_never_added_file(self, tmp_path):
        repo = _new_repo(tmp_path, "untracked-scope")
        subprocess.run(["git", "commit", "-q", "--allow-empty", "-m", "base"], cwd=repo, check=True)
        (repo / "untracked.md").write_text(SUB_BULLET_VIOLATION, encoding="utf-8")
        _cli("--fix", "--changed-only", "untracked.md", cwd=repo)

        result = _cli("--changed-only", "untracked.md", cwd=repo)

        assert result.returncode == 0

    def test_should_report_only_the_untracked_files_hit_when_given_an_unmodified_tracked_file_and_an_untracked_one(self, tmp_path):
        repo = _new_repo(tmp_path, "multi-file-scope")
        (repo / "tracked.md").write_text(SUB_BULLET_VIOLATION, encoding="utf-8")
        _commit_all(repo)
        (repo / "untracked.md").write_text(SUB_BULLET_VIOLATION, encoding="utf-8")

        result = _cli("--changed-only", "tracked.md", "untracked.md", cwd=repo)

        assert result.stdout == "== untracked.md\n2:sub-bullet\n"

    def test_should_exit_1_when_only_the_untracked_file_has_an_in_scope_violation(self, tmp_path):
        repo = _new_repo(tmp_path, "multi-file-scope")
        (repo / "tracked.md").write_text(SUB_BULLET_VIOLATION, encoding="utf-8")
        _commit_all(repo)
        (repo / "untracked.md").write_text(SUB_BULLET_VIOLATION, encoding="utf-8")

        result = _cli("--changed-only", "tracked.md", "untracked.md", cwd=repo)

        assert result.returncode == 1


class TestFailureScenarios:
    NOT_A_WORK_TREE = (
        "check-bullet-gap.py: get-changed-lines.sh failed for plain.md: "
        "get-changed-lines.sh: not inside a git work tree\n"
    )

    def test_should_exit_2_when_changed_lines_lookup_fails_outside_a_git_work_tree_in_check_mode(self, tmp_path):
        (tmp_path / "plain.md").write_text(SUB_BULLET_VIOLATION, encoding="utf-8")

        result = _cli("--changed-only", "plain.md", cwd=tmp_path)

        assert result.returncode == 2

    def test_should_name_the_checker_and_the_file_on_stderr_when_changed_lines_lookup_fails_in_check_mode(self, tmp_path):
        (tmp_path / "plain.md").write_text(SUB_BULLET_VIOLATION, encoding="utf-8")

        result = _cli("--changed-only", "plain.md", cwd=tmp_path)

        assert result.stderr == self.NOT_A_WORK_TREE

    def test_should_exit_2_when_changed_lines_lookup_fails_outside_a_git_work_tree_in_fix_mode(self, tmp_path):
        (tmp_path / "plain.md").write_text(SUB_BULLET_VIOLATION, encoding="utf-8")

        result = _cli("--fix", "--changed-only", "plain.md", cwd=tmp_path)

        assert result.returncode == 2

    def test_should_name_the_checker_and_the_file_on_stderr_when_changed_lines_lookup_fails_in_fix_mode(self, tmp_path):
        (tmp_path / "plain.md").write_text(SUB_BULLET_VIOLATION, encoding="utf-8")

        result = _cli("--fix", "--changed-only", "plain.md", cwd=tmp_path)

        assert result.stderr == self.NOT_A_WORK_TREE

    def test_should_never_insert_into_the_file_when_changed_lines_lookup_fails(self, tmp_path):
        path = tmp_path / "plain.md"
        path.write_text(SUB_BULLET_VIOLATION, encoding="utf-8")

        _cli("--fix", "--changed-only", "plain.md", cwd=tmp_path)

        assert path.read_text(encoding="utf-8") == SUB_BULLET_VIOLATION

    def test_should_exit_2_when_the_input_is_not_valid_utf8(self, tmp_path):
        path = tmp_path / "latin1.md"
        path.write_bytes(b"- caf\xe9 item\n- next\n")

        result = _cli("--fix", str(path))

        assert result.returncode == 2

    def test_should_print_nothing_on_stdout_when_the_input_is_not_valid_utf8(self, tmp_path):
        path = tmp_path / "latin1.md"
        path.write_bytes(b"- caf\xe9 item\n- next\n")

        result = _cli("--fix", str(path))

        assert result.stdout == ""

    def test_should_print_one_stderr_line_naming_the_checker_and_file_with_no_traceback_when_the_input_is_not_valid_utf8(self, tmp_path):
        path = tmp_path / "latin1.md"
        path.write_bytes(b"- caf\xe9 item\n- next\n")

        result = _cli("--fix", str(path))

        assert result.stderr == f"check-bullet-gap.py: cannot read {path}: not valid UTF-8\n"

    def test_should_leave_the_file_byte_identical_when_the_input_is_not_valid_utf8(self, tmp_path):
        path = tmp_path / "latin1.md"
        path.write_bytes(b"- caf\xe9 item\n- next\n")

        _cli("--fix", str(path))

        assert path.read_bytes() == b"- caf\xe9 item\n- next\n"

    def test_should_exit_2_when_the_input_path_does_not_exist(self, tmp_path):
        result = _cli("--fix", str(tmp_path / "missing.md"))

        assert result.returncode == 2

    def test_should_print_nothing_on_stdout_when_the_input_path_does_not_exist(self, tmp_path):
        result = _cli("--fix", str(tmp_path / "missing.md"))

        assert result.stdout == ""

    def test_should_start_the_stderr_line_with_the_checker_name_and_the_missing_path_when_the_input_path_does_not_exist(self, tmp_path):
        path = tmp_path / "missing.md"

        result = _cli("--fix", str(path))

        assert result.stderr.startswith(f"check-bullet-gap.py: cannot read {path}: ")
