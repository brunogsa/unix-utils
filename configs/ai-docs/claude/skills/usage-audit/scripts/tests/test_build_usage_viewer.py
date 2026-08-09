#!/usr/bin/env python3
"""Smoke tests for build-usage-viewer.py's trim_sessions() and load_days().

Fixtures: none on disk for trim_sessions() — inputs are small literal dicts
small enough to verify by eye against SESSION_FIELDS/DAY_FIELDS. load_days()
tests write 2-3 tiny snapshot JSON files into a
tempfile.TemporaryDirectory() and point the module's SNAPSHOTS_DIR at it via
mock.patch.object; this file never reads the committed
usage-history/snapshots/.

Usage:
  python3 scripts/tests/test_build_usage_viewer.py
"""

import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).parent.parent


def _load_module(filename, module_name):
    """Import a dash-named script (not a valid module name) by file path."""
    spec = importlib.util.spec_from_file_location(module_name, SCRIPTS / filename)
    # spec_from_file_location returns None for a path no importer claims, and
    # a spec built without a loader; both mean the script under test is gone.
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {filename} from {SCRIPTS}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cur = _load_module("build-usage-viewer.py", "build_usage_viewer")


class TestTrimSessions(unittest.TestCase):
    """trim_sessions() reduces the top sessions list to only the fields the
    viewer page renders, keeping the inlined HTML payload small."""

    def test_keeps_only_the_fields_the_viewer_page_renders(self):
        session = {
            "title": "Fix billing dedup", "cost": 12.5, "duration_hours": 1.2,
            "compactions": 2, "user_messages": 9, "interruptions": 0,
            "skills": ["usage-audit"], "path": "/Users/x/.claude/projects/p/abcdef1234567890.jsonl",
            "tokens": {"input": 1000, "output": 500},
        }
        trimmed = cur.trim_sessions([session])
        self.assertEqual(
            set(trimmed[0]) - {"id"}, set(cur.SESSION_FIELDS) & set(session),
            msg="trim_sessions must drop any session field the viewer page "
                "does not render (e.g. the full transcript path, raw "
                "token dict), keeping only SESSION_FIELDS plus id")

    def test_derives_a_short_id_from_the_transcript_filename_when_title_is_blank(self):
        session = {
            "title": "", "cost": 1.0, "duration_hours": 0.1, "compactions": 0,
            "user_messages": 1, "interruptions": 0, "skills": [],
            "path": "/Users/x/.claude/projects/p/abcdef1234567890.jsonl",
        }
        trimmed = cur.trim_sessions([session])
        self.assertEqual(
            trimmed[0]["id"], "abcdef12",
            msg="with a blank title, the row's id must be the first 8 "
                "characters of the transcript's own filename, so a "
                "blank-titled session still reads as distinguishable "
                "from its neighbors")

    def test_keeps_only_the_first_n_sessions_by_the_configured_cap(self):
        sessions = [{"title": f"session-{i}", "path": f"/p/session-{i}.jsonl"}
                    for i in range(cur.TOP_SESSIONS + 3)]
        trimmed = cur.trim_sessions(sessions)
        self.assertEqual(
            len(trimmed), cur.TOP_SESSIONS,
            msg=f"trim_sessions must cap the rendered list at TOP_SESSIONS "
                f"({cur.TOP_SESSIONS}) even when given more sessions than that")


class TestTrimSkills(unittest.TestCase):
    """trim_skills() and trim_marginal_skills() reduce the two per-skill maps
    to what the page's per-skill table and trend chart actually divide."""

    BY_SKILL_ROW = {
        "commit-standards": {
            "cost": 41.30, "invocations": 6, "sessions": 4, "compactions": 2,
            "interruptions": 1, "tokens": {"input": 1200, "output": 900},
            "by_repo_class": {
                "work": {"cost": 30.10, "invocations": 4, "sessions": 3},
                "tooling": {"cost": 11.20, "invocations": 2, "sessions": 1},
            },
        },
    }

    MARGINAL_ROW = {
        "commit-standards": {
            "dedicated_sessions": 2, "dedicated_cost": 18.40,
            "mixed_sessions": 2, "mixed_cost_estimate": 9.75,
            "by_repo_class": {
                "work": {"dedicated_sessions": 1, "dedicated_cost": 12.15,
                         "mixed_sessions": 2, "mixed_cost_estimate": 9.75},
                "tooling": {"dedicated_sessions": 1, "dedicated_cost": 6.25,
                            "mixed_sessions": 0, "mixed_cost_estimate": 0.0},
            },
        },
    }

    def test_keeps_only_the_load_counters_the_per_skill_table_renders(self):
        trimmed = cur.trim_skills(self.BY_SKILL_ROW)["commit-standards"]
        self.assertEqual(
            set(trimmed) - {"by_repo_class"}, set(cur.SKILL_FIELDS),
            msg="by_skill rows overlap, so the page divides the marginal "
                "map's dollars instead — this row must carry only the "
                "loads and sessions it is the exact source for, not its "
                "cost, compactions, or five-counter token dict")

    def test_trims_each_half_of_a_skill_row_the_same_way_as_the_row(self):
        trimmed = cur.trim_skills(self.BY_SKILL_ROW)["commit-standards"]
        self.assertEqual(
            trimmed["by_repo_class"]["work"], {"invocations": 4, "sessions": 3},
            msg="a half carries the same counters as its row, so the work "
                "and tooling columns of the per-skill table read from one "
                "shape rather than two")

    def test_sums_a_marginal_halfs_dedicated_and_mixed_spend_into_one_cost(self):
        trimmed = cur.trim_marginal_skills(self.MARGINAL_ROW)["commit-standards"]
        self.assertEqual(
            trimmed["by_repo_class"]["work"], {"cost": 21.90, "sessions": 3},
            msg="a per-skill average divides cost by sessions, so each half "
                "sums its exact dedicated spend and its estimated mixed "
                "share into the one figure that average needs")

    def test_keeps_the_estimated_share_visible_at_the_marginal_row_level(self):
        trimmed = cur.trim_marginal_skills(self.MARGINAL_ROW)["commit-standards"]
        self.assertEqual(
            {k: v for k, v in trimmed.items() if k != "by_repo_class"},
            {"dedicated_sessions": 2, "dedicated_cost": 18.40,
             "mixed_sessions": 2, "mixed_cost_estimate": 9.75},
            msg="the row keeps its dedicated/mixed split so the day panel "
                "can still show how much of a skill's attributed spend was "
                "measured exactly and how much was estimated")


class TestLoadDays(unittest.TestCase):
    """load_days() reads every usage-history/snapshots/*.json, trims each to
    the fields the viewer renders, and skips what it cannot use."""

    def test_reads_every_snapshot_file_keyed_by_its_own_day_field(self):
        with tempfile.TemporaryDirectory() as tmp:
            for day, cost in (("2026-07-20", 12.5), ("2026-07-21", 8.0)):
                with open(os.path.join(tmp, f"{day}.json"), "w") as fh:
                    json.dump({"day": day, "coverage": "complete", "total": cost}, fh)
            with mock.patch.object(cur, "SNAPSHOTS_DIR", tmp):
                days = cur.load_days()
        self.assertEqual(
            set(days), {"2026-07-20", "2026-07-21"},
            msg="load_days must return one entry per snapshot file, keyed "
                "by that file's own `day` field")

    def test_skips_a_legacy_snapshot_with_no_day_field_instead_of_crashing(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "window.json"), "w") as fh:
                json.dump({"since": "2026-07-01", "until": "2026-07-15", "total": 99.0}, fh)
            with open(os.path.join(tmp, "2026-07-20.json"), "w") as fh:
                json.dump({"day": "2026-07-20", "coverage": "complete", "total": 1.0}, fh)
            with mock.patch.object(cur, "SNAPSHOTS_DIR", tmp):
                days = cur.load_days()
        self.assertEqual(
            set(days), {"2026-07-20"},
            msg="a pre-rewrite window snapshot with no `day` field must be "
                "skipped, not crash load_days or be misplaced on the "
                "per-day axis")

    def test_skips_an_unreadable_snapshot_file_instead_of_crashing(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "2026-07-19.json"), "w") as fh:
                fh.write("{not valid json")
            with open(os.path.join(tmp, "2026-07-20.json"), "w") as fh:
                json.dump({"day": "2026-07-20", "coverage": "complete", "total": 1.0}, fh)
            with mock.patch.object(cur, "SNAPSHOTS_DIR", tmp):
                days = cur.load_days()
        self.assertEqual(
            set(days), {"2026-07-20"},
            msg="a snapshot file that fails to parse as JSON must be "
                "skipped, not crash load_days or take down the whole "
                "viewer build")


if __name__ == "__main__":
    unittest.main(verbosity=2)
