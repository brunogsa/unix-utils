"""Blackbox CLI tests for get-unplanned-tests.py.

Fixtures: each test builds a throwaway git repo under tmp_path with a
base commit, then a branch commit that adds test declarations, and a
plan whose `## Test Design` section names the planned titles. Nothing
reads or writes the live repo.

Usage:
  pytest configs/ai-docs/claude/scripts/tests/get-unplanned-tests.test.py
"""

import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "get-unplanned-tests.py"

GIT_IDENTITY_ENV = {
    "GIT_AUTHOR_NAME": "Fixture Author",
    "GIT_AUTHOR_EMAIL": "fixture@example.com",
    "GIT_COMMITTER_NAME": "Fixture Author",
    "GIT_COMMITTER_EMAIL": "fixture@example.com",
}

GATE_TRAILER = "Gate: changed-line coverage"

PLAN_BODY = """# Plan

## Test Design

```ts
describe("csv import", () => {
  // Happy cases
  it("parses a quoted field");
  it("sums a column");
});

describe("csv export", () => {
  // Happy cases
  it("handles a trailing newline");
});
```

## Tasks
"""


def _git(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
        env={**os.environ, **GIT_IDENTITY_ENV},
    ).stdout.strip()


def _write(repo, relative_path, content):
    path = repo / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _it_lines_at(first_line, *titles):
    """Return file content whose i-th title's it() line sits at
    first_line + 2*i, padded with comment filler above."""
    lines = ["// filler"] * (first_line - 1)
    for index, title in enumerate(titles):
        if index:
            lines.append("// filler")
        lines.append(f'it("{title}", () => {{}});')
    return "\n".join(lines) + "\n"


def _commit(repo, subject, trailer=None):
    message = subject if trailer is None else f"{subject}\n\n{trailer}"
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)


def _init_repo(repo, base_files=None):
    """Commit a baseline (the plan outside the repo stays untracked)
    and return the base SHA the branch diffs against."""
    _git(repo, "init", "-q")
    _write(repo, "README.md", "fixture\n")
    for relative_path, content in (base_files or {}).items():
        _write(repo, relative_path, content)
    _commit(repo, "chore: baseline")
    return _git(repo, "rev-parse", "HEAD")


def _run(repo, plan, base):
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(plan), "--base", base],
        capture_output=True,
        text=True,
        cwd=repo,
    )


def _plan(tmp_path, body=PLAN_BODY):
    plan = tmp_path / "plan_fixture.md"
    plan.write_text(body, encoding="utf-8")
    return plan


def _listed(repo, plan, base):
    completed = _run(repo, plan, base)
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)


class TestUnplannedTests:
    def test_should_list_added_tests_matching_no_planned_title_by_path_line_and_title(
        self, tmp_path
    ):
        repo = tmp_path / "repo"
        repo.mkdir()
        base = _init_repo(repo)
        _write(
            repo,
            "tests/parse.test.ts",
            _it_lines_at(38, "parses a quoted field")
            + _it_lines_at(1, "rejects an empty row"),
        )
        _write(
            repo,
            "tests/format.test.ts",
            _it_lines_at(12, "formats zero"),
        )
        _commit(repo, "feat: add csv tests")

        listed = _listed(repo, _plan(tmp_path), base)

        found = {(row["path"], row["line"], row["title"]) for row in listed}
        assert found == {
            ("tests/parse.test.ts", 39, "rejects an empty row"),
            ("tests/format.test.ts", 12, "formats zero"),
        }

    def test_should_name_the_gate_from_the_adding_commits_trailer_else_gate_unknown(
        self, tmp_path
    ):
        repo = tmp_path / "repo"
        repo.mkdir()
        base = _init_repo(repo)
        _write(
            repo,
            "tests/parse.test.ts",
            _it_lines_at(40, "rejects an empty row"),
        )
        _commit(repo, "test: reject empty rows", GATE_TRAILER)
        _write(
            repo,
            "tests/format.test.ts",
            _it_lines_at(12, "formats zero"),
        )
        _commit(repo, "test: format zero")

        listed = _listed(repo, _plan(tmp_path), base)

        gate_by_title = {row["title"]: row["gate"] for row in listed}
        assert gate_by_title == {
            "rejects an empty row": "changed-line coverage",
            "formats zero": "gate unknown",
        }

    def test_should_skip_base_ref_tests_and_tests_matching_a_planned_title_outside_the_narrowed_tasks(
        self, tmp_path
    ):
        repo = tmp_path / "repo"
        repo.mkdir()
        base = _init_repo(
            repo,
            {"tests/legacy.test.ts": _it_lines_at(3, "keeps legacy rows")},
        )
        _write(
            repo,
            "tests/legacy.test.ts",
            _it_lines_at(3, "keeps legacy rows")
            + _it_lines_at(1, "rejects an empty row"),
        )
        _write(
            repo,
            "tests/export.test.ts",
            _it_lines_at(7, "handles a trailing newline"),
        )
        _commit(repo, "test: more csv tests")

        listed = _listed(repo, _plan(tmp_path), base)

        assert [row["title"] for row in listed] == ["rejects an empty row"]

    def test_should_emit_nothing_when_every_added_test_matches_a_planned_title(
        self, tmp_path
    ):
        repo = tmp_path / "repo"
        repo.mkdir()
        base = _init_repo(repo)
        _write(
            repo,
            "tests/parse.test.ts",
            _it_lines_at(5, "parses a quoted field", "sums a column"),
        )
        _write(
            repo,
            "tests/export.test.ts",
            _it_lines_at(9, "handles a trailing newline"),
        )
        _commit(repo, "test: csv tests the plan names", GATE_TRAILER)

        completed = _run(repo, _plan(tmp_path), base)

        assert completed.returncode == 0, completed.stderr
        assert json.loads(completed.stdout) == []

    def test_should_ignore_it_calls_inside_string_literals_of_a_python_test_file(
        self, tmp_path
    ):
        repo = tmp_path / "repo"
        repo.mkdir()
        base = _init_repo(repo)
        _write(
            repo,
            "tests/test_fixtures.py",
            "FIXTURE = 'it(\"rejects an empty row\", () => {});'\n"
            "\n"
            "def test_should_reject_an_empty_row():\n"
            "    assert FIXTURE\n",
        )
        _commit(repo, "test: python fixture holding js text")

        listed = _listed(repo, _plan(tmp_path), base)

        assert [row["title"] for row in listed] == [
            "test_should_reject_an_empty_row"
        ]

    def test_should_match_a_planned_title_with_an_apostrophe_to_a_python_name_without_it(
        self, tmp_path
    ):
        repo = tmp_path / "repo"
        repo.mkdir()
        base = _init_repo(repo)
        _write(
            repo,
            "tests/test_gate.py",
            "def test_should_name_the_gate_from_the_adding_commits_trailer():\n"
            "    pass\n",
        )
        _commit(repo, "test: gate naming")
        plan = _plan(
            tmp_path,
            """# Plan

## Test Design

```ts
describe("gate", () => {
  // Happy cases
  it("should name the gate from the adding commit's trailer");
});
```

## Tasks
""",
        )

        listed = _listed(repo, plan, base)

        assert listed == []

    def test_should_not_list_a_test_the_base_branch_deleted_after_the_fork(
        self, tmp_path
    ):
        repo = tmp_path / "repo"
        repo.mkdir()
        _init_repo(
            repo,
            {"tests/legacy.test.ts": _it_lines_at(3, "keeps legacy rows")},
        )
        _git(repo, "branch", "feature")
        _git(repo, "rm", "-q", "tests/legacy.test.ts")
        _commit(repo, "test: base drops the legacy test")
        base = _git(repo, "rev-parse", "HEAD")
        _git(repo, "checkout", "-q", "feature")
        _write(repo, "README.md", "fixture, edited on the branch\n")
        _commit(repo, "docs: edit readme")

        listed = _listed(repo, _plan(tmp_path), base)

        assert listed == []

    def test_should_not_list_tests_of_a_renamed_test_file_that_gains_no_new_test(
        self, tmp_path
    ):
        repo = tmp_path / "repo"
        repo.mkdir()
        base = _init_repo(
            repo,
            {"tests/legacy.test.ts": _it_lines_at(3, "keeps legacy rows")},
        )
        _git(repo, "mv", "tests/legacy.test.ts", "tests/archive.test.ts")
        _commit(repo, "refactor: rename the legacy test file")

        listed = _listed(repo, _plan(tmp_path), base)

        assert listed == []

    def test_should_list_an_unplanned_test_when_git_is_configured_to_omit_diff_path_prefixes(
        self, tmp_path
    ):
        repo = tmp_path / "repo"
        repo.mkdir()
        base = _init_repo(repo)
        _git(repo, "config", "diff.noprefix", "true")
        _write(
            repo,
            "tests/parse.test.ts",
            _it_lines_at(4, "rejects an empty row"),
        )
        _commit(repo, "test: reject empty rows")

        listed = _listed(repo, _plan(tmp_path), base)

        assert [(row["path"], row["line"]) for row in listed] == [
            ("tests/parse.test.ts", 4)
        ]

    def test_should_list_an_unplanned_test_in_a_file_whose_directory_name_holds_a_space(
        self, tmp_path
    ):
        repo = tmp_path / "repo"
        repo.mkdir()
        base = _init_repo(repo)
        _write(
            repo,
            "my dir/parse.test.ts",
            _it_lines_at(4, "rejects an empty row"),
        )
        _commit(repo, "test: reject empty rows")

        listed = _listed(repo, _plan(tmp_path), base)

        assert [(row["path"], row["line"]) for row in listed] == [
            ("my dir/parse.test.ts", 4)
        ]

    def test_should_not_list_an_existing_test_whose_declaration_line_was_edited(
        self, tmp_path
    ):
        repo = tmp_path / "repo"
        repo.mkdir()
        base = _init_repo(
            repo,
            {
                "tests/test_rows.py": "def test_should_reject_an_empty_row(self):\n"
                "    pass\n"
            },
        )
        _write(
            repo,
            "tests/test_rows.py",
            "def test_should_reject_an_empty_row(self, tmp_path):\n"
            "    pass\n",
        )
        _commit(repo, "test: give the row test a temp directory")

        listed = _listed(repo, _plan(tmp_path), base)

        assert listed == []

    def test_should_name_the_gate_of_the_commit_that_added_a_test_not_a_later_edit(
        self, tmp_path
    ):
        repo = tmp_path / "repo"
        repo.mkdir()
        base = _init_repo(repo)
        _write(
            repo,
            "tests/parse.test.ts",
            'it("rejects an empty row", () => {});\n',
        )
        _commit(repo, "test: reject empty rows", GATE_TRAILER)
        _write(
            repo,
            "tests/parse.test.ts",
            'it("rejects an empty row", () => { run(); });\n',
        )
        _commit(repo, "test: run the parser", "Gate: metrics")

        listed = _listed(repo, _plan(tmp_path), base)

        assert [(row["title"], row["gate"]) for row in listed] == [
            ("rejects an empty row", "changed-line coverage")
        ]

    def test_should_not_list_a_regex_test_method_call_as_a_test_declaration(
        self, tmp_path
    ):
        repo = tmp_path / "repo"
        repo.mkdir()
        base = _init_repo(repo)
        _write(
            repo,
            "src/matcher.js",
            'const startsWithA = /^a/.test("abc");\n',
        )
        _commit(repo, "feat: match a leading letter")

        listed = _listed(repo, _plan(tmp_path), base)

        assert listed == []

    def test_should_list_tests_declared_through_only_skip_and_each_modifiers(
        self, tmp_path
    ):
        repo = tmp_path / "repo"
        repo.mkdir()
        base = _init_repo(repo)
        _write(
            repo,
            "tests/modifiers.test.js",
            'it.only("focuses a row", () => {});\n'
            'test.skip("skips a row", () => {});\n'
            'it.each([1])("each %s", () => {});\n',
        )
        _commit(repo, "test: add modifier forms")

        listed = _listed(repo, _plan(tmp_path), base)

        assert {row["title"] for row in listed} == {
            "focuses a row",
            "skips a row",
            "each %s",
        }
