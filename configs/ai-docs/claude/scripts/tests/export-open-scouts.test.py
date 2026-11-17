"""Blackbox CLI tests for export-open-scouts.py.

Fixtures: each test writes throwaway task JSON files under
tmp_path and points the script at them with --tasks-root.
Nothing reads ~/.claude/tasks.

Usage:
  ./run-tests.py <this file>
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent.parent / "export-open-scouts.py"

SESSION_ID = "9a8c27c7-aaac-46a0-bb96-30246519abc7"


def _write_task(tasks_root, task_id, subject, status="pending", description=""):
    session_dir = tasks_root / SESSION_ID
    session_dir.mkdir(parents=True, exist_ok=True)
    task = {
        "id": task_id,
        "subject": subject,
        "description": description,
        "status": status,
        "blocks": [],
        "blockedBy": [],
    }
    (session_dir / f"{task_id}.json").write_text(json.dumps(task), encoding="utf-8")


def _scout_subject(task_id, title):
    return f" {task_id}. [#{task_id}][Scout] {title}"


def _run(tasks_root, out_path):
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--tasks-root",
            str(tasks_root),
            SESSION_ID,
            str(out_path),
        ],
        capture_output=True,
        text=True,
    )


def _section_headings(out_path):
    return [
        line
        for line in out_path.read_text(encoding="utf-8").splitlines()
        if line.startswith("## ")
    ]


class TestScoutsExported:
    def test_should_export_only_pending_and_in_progress_scouts_leaving_out_completed_and_deleted_ones(
        self, tmp_path
    ):
        tasks_root = tmp_path / "tasks"
        _write_task(tasks_root, "3", _scout_subject("3", "Stale retry comment"))
        _write_task(
            tasks_root,
            "4",
            _scout_subject("4", "Dead config key"),
            status="in_progress",
        )
        _write_task(
            tasks_root,
            "5",
            _scout_subject("5", "Unused mock"),
            status="completed",
        )
        _write_task(
            tasks_root,
            "6",
            _scout_subject("6", "Lint gap in parser"),
            status="deleted",
        )
        out_path = tmp_path / "open-scouts.md"

        completed = _run(tasks_root, out_path)

        assert completed.returncode == 0, completed.stderr
        assert completed.stdout == "2\n"
        assert _section_headings(out_path) == [
            "## #3 [Scout] Stale retry comment",
            "## #4 [Scout] Dead config key",
        ]

    def test_should_leave_out_an_open_task_whose_subject_is_not_marked_scout(
        self, tmp_path
    ):
        tasks_root = tmp_path / "tasks"
        _write_task(tasks_root, "7", " 7. [#7][Task] Add the scout leg")
        _write_task(tasks_root, "8", _scout_subject("8", "Flaky NSE spec"))
        out_path = tmp_path / "open-scouts.md"

        completed = _run(tasks_root, out_path)

        assert completed.returncode == 0, completed.stderr
        assert completed.stdout == "1\n"
        assert _section_headings(out_path) == ["## #8 [Scout] Flaky NSE spec"]

    def test_should_order_scouts_by_numeric_task_id_so_task_10_follows_task_9(
        self, tmp_path
    ):
        tasks_root = tmp_path / "tasks"
        _write_task(tasks_root, "10", _scout_subject("10", "Tenth scout"))
        _write_task(tasks_root, "9", _scout_subject("9", "Ninth scout"))
        _write_task(tasks_root, "2", _scout_subject("2", "Second scout"))
        out_path = tmp_path / "open-scouts.md"

        completed = _run(tasks_root, out_path)

        assert completed.returncode == 0, completed.stderr
        assert _section_headings(out_path) == [
            "## #2 [Scout] Second scout",
            "## #9 [Scout] Ninth scout",
            "## #10 [Scout] Tenth scout",
        ]

    def test_should_write_each_scout_as_a_section_headed_by_its_id_and_subject_without_the_task_list_prefix_with_its_description_below(
        self, tmp_path
    ):
        tasks_root = tmp_path / "tasks"
        _write_task(
            tasks_root,
            "43",
            " 43. [#43][Scout] Flaky: NSE skip-list spec throws on a random SKU",
            description="Failed once in a 3864-test run. Prior: fix - pin the fixture.",
        )
        out_path = tmp_path / "open-scouts.md"

        completed = _run(tasks_root, out_path)

        assert completed.returncode == 0, completed.stderr
        assert out_path.read_text(encoding="utf-8") == (
            "## #43 [Scout] Flaky: NSE skip-list spec throws on a random SKU\n"
            "\n"
            "Failed once in a 3864-test run. Prior: fix - pin the fixture.\n"
        )


class TestNothingToExport:
    @pytest.mark.parametrize(
        "has_session_dir",
        [True, False],
        ids=["session-with-no-open-scout", "session-with-no-task-directory"],
    )
    def test_should_print_0_and_write_no_file_when_no_open_scout_exists(
        self, tmp_path, has_session_dir
    ):
        tasks_root = tmp_path / "tasks"
        if has_session_dir:
            _write_task(
                tasks_root,
                "5",
                _scout_subject("5", "Unused mock"),
                status="completed",
            )
        out_path = tmp_path / "open-scouts.md"

        completed = _run(tasks_root, out_path)

        assert completed.returncode == 0, completed.stderr
        assert completed.stdout == "0\n"
        assert not out_path.exists()


class TestUnreadableTask:
    def test_should_exit_1_naming_the_malformed_task_file_and_write_no_file(
        self, tmp_path
    ):
        tasks_root = tmp_path / "tasks"
        _write_task(tasks_root, "3", _scout_subject("3", "Stale retry comment"))
        broken = tasks_root / SESSION_ID / "4.json"
        broken.write_text('{"id": "4", "subject": ', encoding="utf-8")
        out_path = tmp_path / "open-scouts.md"

        completed = _run(tasks_root, out_path)

        assert completed.returncode == 1
        assert str(broken) in completed.stderr
        assert completed.stdout == ""
        assert not out_path.exists()
