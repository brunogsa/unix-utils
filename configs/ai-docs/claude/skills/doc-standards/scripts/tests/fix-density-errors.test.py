"""Tests for the failures fix-density.py must surface as exit 2
instead of a false clean result: scoping that cannot run, a
file that is not valid UTF-8, and a path that does not exist.
"""

LATIN1_BYTES = b"- caf\xe9 item\n- next\n"


def test_exits_2_naming_the_file_and_inner_script_when_changed_only_runs_outside_a_git_work_tree(fixer):
    plain_dir = fixer.tmp_path / "plain-outside-git"
    plain_dir.mkdir()
    path = fixer.write("plain.md", "# Plain fixture\n\nShort filler paragraph.\n", directory=plain_dir)

    result = fixer.run(path.name, "--changed-only", cwd=plain_dir)

    assert result.returncode == 2, result.stdout
    assert "plain.md" in result.stdout
    assert "check-density.sh" in result.stdout


def test_leaves_the_file_untouched_when_changed_only_scoping_fails(fixer):
    plain_dir = fixer.tmp_path / "plain-outside-git"
    plain_dir.mkdir()
    content = "# Plain fixture\n\nShort filler paragraph.\n"
    path = fixer.write("plain.md", content, directory=plain_dir)

    fixer.run(path.name, "--changed-only", cwd=plain_dir)

    assert path.read_text(encoding="utf-8") == content


def test_exits_2_with_nothing_on_stdout_when_input_is_not_valid_utf8(fixer):
    path = fixer.tmp_path / "latin1.md"
    path.write_bytes(LATIN1_BYTES)

    result = fixer.run_with_separate_streams(path)

    assert result.returncode == 2
    assert result.stdout == ""


def test_prints_one_stderr_line_naming_script_and_file_without_a_traceback_when_input_is_not_valid_utf8(fixer):
    path = fixer.tmp_path / "latin1.md"
    path.write_bytes(LATIN1_BYTES)

    result = fixer.run_with_separate_streams(path)

    expected = f"fix-density.py: cannot read {path}: not valid UTF-8"
    assert result.stderr.rstrip("\n") == expected


def test_leaves_the_file_byte_identical_when_input_is_not_valid_utf8(fixer):
    path = fixer.tmp_path / "latin1.md"
    path.write_bytes(LATIN1_BYTES)

    fixer.run_with_separate_streams(path)

    assert path.read_bytes() == LATIN1_BYTES


def test_exits_2_with_nothing_on_stdout_when_the_input_path_does_not_exist(fixer):
    result = fixer.run_with_separate_streams(fixer.tmp_path / "missing.md")

    assert result.returncode == 2
    assert result.stdout == ""


def test_starts_the_stderr_line_with_the_checker_name_and_the_missing_path(fixer):
    path = fixer.tmp_path / "missing.md"

    result = fixer.run_with_separate_streams(path)

    assert result.stderr.startswith(f"fix-density.py: cannot read {path}: ")
