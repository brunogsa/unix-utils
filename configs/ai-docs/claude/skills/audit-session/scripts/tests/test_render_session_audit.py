#!/usr/bin/env python3
"""Tests for render-session-audit.py: the deterministic HTML renderer that
fills the committed assets/audit-template.html from cost.json +
timeline.json + narrative.json.

Fixtures: hand-built dicts shaped like the real producers' output —
cost.json mirrors claude-usage-report.py's build_payload() (see its
TestSessionMode suite), timeline.json mirrors
extract-session-timeline.py's build_timeline_payload(). No fixture reads
real ~/.claude data; every test passes in-memory payloads directly to
render_audit_html()/write_audit_html().

Usage:
  pytest scripts/tests/test_render_session_audit.py
"""

import importlib.util
import os
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).parent.parent


def _load_module(filename, module_name):
    """Import a dash-named script (not a valid module name) by file path."""
    spec = importlib.util.spec_from_file_location(module_name, SCRIPTS / filename)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {filename} from {SCRIPTS}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


rsa = _load_module("render-session-audit.py", "render_session_audit")


def _cost_fixture(**overrides):
    """A trimmed but realistically-shaped cost.json — the fields the
    renderer actually reads, matching claude-usage-report.py's
    build_payload() key names (main_cost/subagent_cost/total)."""
    base = {
        "generated_at": "2026-08-10T14:32:07-03:00",
        "day": None,
        "coverage": "complete",
        "total": 12.47,
        "main_cost": 9.03,
        "subagent_cost": 3.44,
    }
    base.update(overrides)
    return base


def _timeline_fixture(**overrides):
    """A trimmed but realistically-shaped timeline.json, matching
    extract-session-timeline.py's build_timeline_payload() key names."""
    base = {
        "sid": "sess-abc123",
        "local_day": "2026-08-10",
        "time_partition": {
            "wall_clock_seconds": 3600.0,
            "buckets": {
                "main_api": {"seconds": 1200.0, "pct": 33.0},
                "tool_exec": {"seconds": 900.0, "pct": 25.0},
                "agent_occupied": {"seconds": 600.0, "pct": 17.0},
                "human_idle": {"seconds": 900.0, "pct": 25.0},
            },
            "agent_hours_vs_wall_clock_occupied": {
                "agent_hours_seconds": 1800.0,
                "wall_clock_occupied_seconds": 600.0,
            },
        },
        "turns": [{"index": 0, "duration_seconds": 120.0, "measure": "turn_duration"}],
        "turn_ranking": {"too_early_to_rank": False, "ranked_turn_indices": [0]},
        "tasks": {"note": None, "tasks": []},
        "commits": {
            "items": [
                {"source": "main", "timestamp": "2026-08-10T14:20:00Z",
                 "command": 'git commit -m "fix(render): guard against None"',
                 "turn_index": 0},
            ],
            "note": ("a commit made by a hook, or folded into an existing "
                     "commit by `git commit --amend`, leaves no new tool "
                     "call and so may be missing from this list"),
        },
        "agent_runs": [],
        "timeline": [],
    }
    base.update(overrides)
    return base


def _ranked_item(label, value):
    return {"label": label, "value": value}


def _section_digest(section, headline, ranked=None, findings=None, incomplete=None):
    """One shard's digest — the fixed contract render-session-audit.py
    consumes: {section, headline, ranked[], findings[], incomplete?}."""
    digest = {
        "section": section,
        "headline": headline,
        "ranked": ranked or [],
        "findings": findings or [],
    }
    if incomplete is not None:
        digest["incomplete"] = incomplete
    return digest


def _narrative_fixture(sections=None):
    if sections is None:
        sections = [
            _section_digest("time", "Engaged time was 45 minutes of 1 hour wall clock.",
                             ranked=[_ranked_item("turn 0", 120.0)],
                             findings=["Most time went to tool-exec."]),
            _section_digest("money", "Session cost $12.47 total.",
                             ranked=[_ranked_item("main", 9.03), _ranked_item("subagent", 3.44)],
                             findings=["Subagent spend was 28% of total."]),
            _section_digest("work", "One commit landed.",
                             ranked=[_ranked_item("fix(render): guard against None", 1.0)],
                             findings=["The fix guards a None input."]),
            _section_digest("status", "Session is complete.",
                             ranked=[], findings=["No open follow-ups."]),
        ]
    return {"sections": sections}


class TestSessionAuditRendererHappy(unittest.TestCase):
    def test_should_render_a_single_self_contained_audit_session_html_file_from_cost_json_timeline_json_and_narrative_json(self):
        """The renderer must write exactly one file named
        audit_session-<sid>.html, and that file's own bytes must never
        reference an external network resource (no http(s):// URL, no
        <script src=, no <link> to a remote stylesheet) -- a page opened
        over file:// must render standalone."""
        cost = _cost_fixture()
        timeline = _timeline_fixture()
        narrative = _narrative_fixture()

        with tempfile.TemporaryDirectory() as tmp:
            out_path = rsa.write_audit_html(cost, timeline, narrative, out_dir=tmp)

            self.assertEqual(os.path.basename(out_path), "audit_session-sess-abc123.html")
            self.assertTrue(os.path.isfile(out_path))
            self.assertEqual(
                len(os.listdir(tmp)), 1,
                msg="the renderer must write exactly one file")

            with open(out_path) as fh:
                html_text = fh.read()

        self.assertNotIn("http://", html_text)
        self.assertNotIn("https://", html_text)
        self.assertNotIn("<script", html_text,
                          msg="the page must carry no script tag at all, "
                              "let alone one fetching a remote resource")
        self.assertNotIn('<link', html_text,
                          msg="the page must not reference an external stylesheet")


class TestSessionAuditRendererRanking(unittest.TestCase):
    def test_should_rank_each_sections_items_by_cost_or_time_and_print_how_many_were_not_shown_beyond_the_top_n(self):
        """A shard's ranked[] is not guaranteed pre-sorted -- the renderer
        must sort by value itself, show only the top 5, and print a
        "plus N more, not shown" line for the rest (D9), so a reader never
        mistakes a truncated list for the complete one."""
        cost = _cost_fixture()
        timeline = _timeline_fixture()
        # 8 items, deliberately out of order, so a renderer that trusted
        # on-disk order (rather than sorting) would show the wrong top 5.
        unsorted_ranked = [
            _ranked_item("turn 3", 40.0),
            _ranked_item("turn 7", 900.0),
            _ranked_item("turn 1", 10.0),
            _ranked_item("turn 6", 500.0),
            _ranked_item("turn 0", 700.0),
            _ranked_item("turn 5", 300.0),
            _ranked_item("turn 4", 200.0),
            _ranked_item("turn 2", 20.0),
        ]
        narrative = _narrative_fixture(sections=[
            _section_digest("time", "Engaged time was 45 minutes.", ranked=unsorted_ranked),
            _section_digest("money", "Session cost $12.47 total.", ranked=[]),
            _section_digest("work", "One commit landed.", ranked=[]),
            _section_digest("status", "Session is complete.", ranked=[]),
        ])

        html_text = rsa.render_audit_html(cost, timeline, narrative)

        top_5_labels = ["turn 7", "turn 0", "turn 6", "turn 5", "turn 4"]
        positions = [html_text.index(label) for label in top_5_labels]
        self.assertEqual(
            positions, sorted(positions),
            msg="the top 5 items by value (descending) must appear in that "
                "order: turn 7 (900), turn 0 (700), turn 6 (500), "
                "turn 5 (300), turn 4 (200)")
        for dropped_label in ("turn 3", "turn 1", "turn 2"):
            self.assertNotIn(
                dropped_label, html_text,
                msg=f"{dropped_label} ranks below the top 5 and must not "
                    "appear as its own row")
        self.assertIn(
            "plus 3 more, not shown", html_text,
            msg="the 3 dropped items (turn 3, turn 1, turn 2) must be "
                "counted in a not-shown line, never silently omitted")


class TestSessionAuditRendererEscaping(unittest.TestCase):
    def test_should_html_escape_user_and_assistant_text_quoted_in_the_timeline_so_an_unescaped_angle_bracket_cannot_break_the_page(self):
        """A commit `command` can embed a user- or assistant-authored commit
        message verbatim from the transcript. Real markup in that string
        must never reach the page unescaped -- the threat model's
        transcript-derived-text-into-static-HTML mitigation (AC2)."""
        cost = _cost_fixture()
        raw_payload = '<script>alert(1)</script>'
        timeline = _timeline_fixture(commits={
            "items": [
                {"source": "main", "timestamp": "2026-08-10T14:20:00Z",
                 "command": f'git commit -m "{raw_payload}"',
                 "turn_index": 0},
            ],
            "note": None,
        })
        narrative = _narrative_fixture()

        html_text = rsa.render_audit_html(cost, timeline, narrative)

        self.assertNotIn(
            raw_payload, html_text,
            msg="the raw, unescaped <script> tag must never appear in the "
                "output bytes")
        self.assertIn(
            "&lt;script&gt;alert(1)&lt;/script&gt;", html_text,
            msg="the escaped form must be present, proving the value was "
                "rendered (not silently dropped) and escaped")


class TestSessionAuditRendererReconciledPercentages(unittest.TestCase):
    def test_should_render_the_reconciled_wall_clock_percentages_from_the_timeline_payload_without_re_deriving_them(self):
        """extract-session-timeline.py's _percentages_summing_to_100() already
        reconciles every bucket's pct via largest-remainder rounding so the
        buckets sum to exactly 100. A renderer that recomputed
        seconds/wall_clock_seconds itself could print a different, naively-
        rounded number for the same bucket -- two disagreeing answers for
        one figure. The supplied pct must appear verbatim."""
        cost = _cost_fixture()
        # 1200 / 3600 naively rounds to 33.3%, but the reconciled pct
        # supplied here is deliberately 41.0% -- a value no naive
        # recomputation from these seconds would ever produce. If the
        # renderer printed anything else, it would prove it re-derived
        # the percentage instead of trusting the supplied one.
        timeline = _timeline_fixture(time_partition={
            "wall_clock_seconds": 3600.0,
            "buckets": {
                "main_api": {"seconds": 1200.0, "pct": 41.0},
                "tool_exec": {"seconds": 900.0, "pct": 25.0},
                "agent_occupied": {"seconds": 600.0, "pct": 17.0},
                "human_idle": {"seconds": 900.0, "pct": 17.0},
            },
            "agent_hours_vs_wall_clock_occupied": {
                "agent_hours_seconds": 1800.0,
                "wall_clock_occupied_seconds": 600.0,
            },
        })
        narrative = _narrative_fixture()

        html_text = rsa.render_audit_html(cost, timeline, narrative)

        self.assertIn(
            "(41.0%)", html_text,
            msg="the supplied, already-reconciled pct must appear "
                "verbatim, not a value re-derived from seconds/wall_clock")
        self.assertNotIn(
            "(33.3%)", html_text,
            msg="33.3% is what a naive seconds/wall_clock recomputation "
                "would produce for this bucket -- its presence would prove "
                "the renderer re-derived the percentage instead of trusting "
                "the supplied one")


class TestSessionAuditRendererPageBudget(unittest.TestCase):
    def test_should_fit_within_the_four_page_budget_for_the_largest_measured_fixture_session(self):
        """A realistically large session -- a long multi-hour batch with
        many commits and every narrative section near its top-N cap --
        must still render under FOUR_PAGE_BYTE_BUDGET, so the audit page
        stays a quick read rather than silently ballooning with every
        commit or finding a long session accumulates."""
        cost = _cost_fixture()
        # 50 commits, each with a realistic conventional-commit subject --
        # the largest commit count observed in a single long batch session.
        commit_items = [
            {"source": "main", "timestamp": f"2026-08-10T{9 + (i % 8):02d}:{i % 60:02d}:00Z",
             "command": f'git commit -m "fix(module-{i}): resolve edge case in handler {i}"',
             "turn_index": i}
            for i in range(50)
        ]
        timeline = _timeline_fixture(commits={"items": commit_items, "note": None})
        narrative = _narrative_fixture(sections=[
            _section_digest(
                "time", "Engaged time was 6 hours 12 minutes of 8 hours wall clock.",
                ranked=[_ranked_item(f"turn {i}", 1000.0 - i) for i in range(20)],
                findings=[f"Finding {i} about time usage in this long session." for i in range(10)]),
            _section_digest(
                "money", "Session cost $184.32 total across 50 commits.",
                ranked=[_ranked_item(f"model {i}", 20.0 - i) for i in range(20)],
                findings=[f"Finding {i} about cost distribution across models." for i in range(10)]),
            _section_digest(
                "work", "50 commits landed across 12 skills and 30 files.",
                ranked=[_ranked_item(commit_items[i]["command"], 50.0 - i) for i in range(20)],
                findings=[f"Finding {i} summarizing a cluster of related commits." for i in range(10)]),
            _section_digest(
                "status", "Session is complete with 2 follow-ups queued.",
                ranked=[_ranked_item(f"task {i}", 5.0 - i * 0.1) for i in range(20)],
                findings=[f"Finding {i} about remaining follow-up work." for i in range(10)]),
        ])

        html_text = rsa.render_audit_html(cost, timeline, narrative)

        self.assertLessEqual(
            len(html_text.encode("utf-8")), rsa.FOUR_PAGE_BYTE_BUDGET,
            msg="the largest realistic session's audit page must still "
                "fit the four-page budget")


class TestSessionAuditRendererFailure(unittest.TestCase):
    def test_should_render_a_shards_section_as_incomplete_with_its_reason_when_the_sections_digest_carries_incomplete(self):
        """A shard that could not finish its analysis (e.g. it ran out of
        budget partway through) marks its own digest `incomplete` with a
        reason string. The renderer must surface that section as INCOMPLETE
        with the reason visible, never rendering it as if it were a normal,
        silently-blank section."""
        cost = _cost_fixture()
        timeline = _timeline_fixture()
        narrative = _narrative_fixture(sections=[
            _section_digest("time", "Engaged time was 45 minutes.", ranked=[_ranked_item("turn 0", 120.0)]),
            _section_digest("money", "Session cost $12.47 total.", ranked=[_ranked_item("main", 9.03)]),
            _section_digest(
                "work", headline="",
                incomplete="ran out of budget before summarizing commits"),
            _section_digest("status", "Session is complete.", ranked=[]),
        ])

        html_text = rsa.render_audit_html(cost, timeline, narrative)

        self.assertIn(
            "INCOMPLETE", html_text,
            msg="the work section must be visibly marked INCOMPLETE")
        self.assertIn(
            "ran out of budget before summarizing commits", html_text,
            msg="the reason must be visible, not just an INCOMPLETE label "
                "with no explanation")
        self.assertNotIn(
            "One commit landed", html_text,
            msg="an incomplete section's normal headline/ranked/findings "
                "must not render alongside the INCOMPLETE marker")

    def test_should_never_write_into_usage_history_snapshots_regardless_of_its_inputs(self):
        """usage-history/snapshots/ holds the audit pipeline's own inputs
        (cost.json/timeline.json/narrative.json); the renderer must never
        write its output there, even when a malicious or malformed `sid`
        (e.g. containing path-traversal characters) tries to steer the
        output filename outside the requested out_dir."""
        with tempfile.TemporaryDirectory() as tmp_root:
            out_dir = os.path.join(tmp_root, "output")
            os.makedirs(out_dir)
            snapshots_dir = os.path.join(tmp_root, "usage-history", "snapshots")
            os.makedirs(snapshots_dir)

            cost = _cost_fixture()
            timeline = _timeline_fixture(sid="../usage-history/snapshots/pwned")
            narrative = _narrative_fixture()

            out_path = rsa.write_audit_html(cost, timeline, narrative, out_dir=out_dir)

            self.assertEqual(
                os.listdir(snapshots_dir), [],
                msg="a malicious sid must never let the renderer write "
                    "into usage-history/snapshots/")
            written_real_dir = os.path.dirname(os.path.realpath(out_path))
            self.assertEqual(
                written_real_dir, os.path.realpath(out_dir),
                msg="the output file must land inside the requested "
                    "out_dir, never traverse out of it")

    def test_should_refuse_to_render_when_the_narrative_digest_is_missing_a_required_section(self):
        """The orchestrator always fans out to 4 fixed shards (time, money,
        work, status); a narrative.json missing one of them is malformed
        input, and rendering must refuse loudly rather than emit a page
        with that whole section silently absent."""
        cost = _cost_fixture()
        timeline = _timeline_fixture()
        narrative = _narrative_fixture(sections=[
            _section_digest("time", "Engaged time was 45 minutes.", ranked=[_ranked_item("turn 0", 120.0)]),
            _section_digest("money", "Session cost $12.47 total.", ranked=[_ranked_item("main", 9.03)]),
            _section_digest("work", "One commit landed.", ranked=[_ranked_item("commit", 1.0)]),
            # "status" section deliberately omitted.
        ])

        with self.assertRaises(ValueError) as ctx:
            rsa.render_audit_html(cost, timeline, narrative)

        self.assertIn("status", str(ctx.exception),
                       msg="the refusal must name the missing section so "
                           "the caller knows which shard's digest is absent")


if __name__ == "__main__":
    unittest.main()
