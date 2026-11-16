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


def _plan(tmp_path):
    plan = tmp_path / "plan_fixture.md"
    plan.write_text(PLAN_BODY, encoding="utf-8")
    return plan


def _listed(repo, plan, base):
    completed = _run(repo, plan, base)
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)


class TestUnplannedTests:
    def test_lists_added_tests_matching_no_planned_title_by_path_line_and_title(
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

    def test_names_the_gate_from_the_adding_commit_trailer_else_gate_unknown(
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

    def test_skips_base_ref_tests_and_tests_matching_a_planned_title_of_another_task(
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
