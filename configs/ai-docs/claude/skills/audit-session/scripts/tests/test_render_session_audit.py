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
            _section_digest("recommendations", "Two concrete follow-ups would cut spend.",
                             ranked=[], findings=[
                                 "Cache hit rate is healthy; no action needed there.",
                                 "Subagent spend is 28% of total; consider fewer opus shards.",
                             ]),
        ]
    return {"sections": sections}


class TestFormatDurationHours(unittest.TestCase):
    def test_should_format_a_duration_under_a_minute_as_a_bare_seconds_count(self):
        """Below the 60s threshold there is no minutes/hours component worth
        showing -- print the bare seconds count, e.g. "38s"."""
        self.assertEqual(rsa._format_duration_hours(38.0), "38s")

    def test_should_format_a_duration_of_at_least_a_minute_but_under_an_hour_as_minutes_only_no_seconds(self):
        """Once a duration reaches a full minute, per the spec's formatter
        table a bare seconds count must never be shown again -- render
        minutes only, e.g. "42m", dropping the remainder seconds."""
        self.assertEqual(rsa._format_duration_hours(2520.0), "42m")

    def test_should_format_a_duration_of_at_least_an_hour_as_hours_and_minutes_no_seconds(self):
        """At an hour or beyond, render hours + minutes with no seconds
        component at all -- 46,065 total seconds is 12h 47m 45s, and the
        trailing 45s must be dropped, not rounded into the minutes."""
        self.assertEqual(rsa._format_duration_hours(46065.0), "12h 47m")


class TestHumanizeTokenCount(unittest.TestCase):
    def test_should_humanize_a_large_token_count_in_millions_with_two_decimal_places(self):
        """The spec's own example: 58,293,049 raw tokens must read as
        "58.29M", never as the raw digit count a human cannot parse at a
        glance."""
        self.assertEqual(rsa._humanize_token_count(58293049), "58.29M")

    def test_should_humanize_a_token_count_in_the_low_millions_keeping_the_trailing_zero(self):
        """The spec's other example, 1,300,000 tokens as "1.30M" -- the
        trailing zero must survive the formatting, not collapse to "1.3M"."""
        self.assertEqual(rsa._humanize_token_count(1300000), "1.30M")

    def test_should_leave_a_token_count_under_one_million_as_a_plain_comma_grouped_integer(self):
        """Below a million, a human can still read the raw count at a
        glance -- only comma-group it, do not invent a K suffix the spec
        never asked for."""
        self.assertEqual(rsa._humanize_token_count(58292), "58,292")


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
            _section_digest("recommendations", "Two concrete follow-ups would cut spend.", ranked=[]),
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


class TestSessionAuditRendererRecommendations(unittest.TestCase):
    def test_should_render_the_recommendations_section_content_from_the_narrative_digest(self):
        """S5 Recommendations is a 5th narrative shard like the other 4 --
        its digest's title, headline, and findings must actually appear on
        the page, not just be validated as present/absent."""
        cost = _cost_fixture()
        timeline = _timeline_fixture()
        narrative = _narrative_fixture(sections=[
            _section_digest("time", "Engaged time was 45 minutes.", ranked=[_ranked_item("turn 0", 120.0)]),
            _section_digest("money", "Session cost $12.47 total.", ranked=[_ranked_item("main", 9.03)]),
            _section_digest("work", "One commit landed.", ranked=[_ranked_item("commit", 1.0)]),
            _section_digest("status", "Session is complete.", ranked=[]),
            _section_digest(
                "recommendations", "Two concrete follow-ups would cut spend.",
                ranked=[],
                findings=["Subagent spend is 28% of total; consider fewer opus shards."]),
        ])

        html_text = rsa.render_audit_html(cost, timeline, narrative)

        self.assertIn("Recommendations", html_text,
                       msg="the Recommendations section title must appear on the page")
        self.assertIn("Two concrete follow-ups would cut spend.", html_text,
                       msg="the recommendations shard's headline must appear on the page")
        self.assertIn("Subagent spend is 28% of total; consider fewer opus shards.", html_text,
                       msg="the recommendations shard's findings must appear on the page")


class TestSessionAuditRendererEscaping(unittest.TestCase):
    def test_should_html_escape_user_and_assistant_text_quoted_in_a_narrative_finding_so_an_unescaped_angle_bracket_cannot_break_the_page(self):
        """A narrative shard's `finding` can quote user- or
        assistant-authored text verbatim from the transcript. Real markup
        in that string must never reach the page unescaped -- the threat
        model's transcript-derived-text-into-static-HTML mitigation (AC2).

        Re-targeted from a commit `command` (the original injection point)
        now that the Commits section is deleted (gap 5) and no longer
        renders any commit field at all; a narrative finding is the
        general case this guard protects, since every shard's
        headline/ranked/findings ultimately quotes the transcript."""
        cost = _cost_fixture()
        timeline = _timeline_fixture()
        raw_payload = '<script>alert(1)</script>'
        narrative = _narrative_fixture(sections=[
            _section_digest("time", "Engaged time was 45 minutes.", ranked=[_ranked_item("turn 0", 120.0)]),
            _section_digest("money", "Session cost $12.47 total.", ranked=[_ranked_item("main", 9.03)]),
            _section_digest("work", "One commit landed.", ranked=[_ranked_item("commit", 1.0)],
                             findings=[raw_payload]),
            _section_digest("status", "Session is complete.", ranked=[]),
            _section_digest("recommendations", "Two concrete follow-ups would cut spend.", ranked=[]),
        ])

        html_text = rsa.render_audit_html(cost, timeline, narrative)

        self.assertNotIn(
            raw_payload, html_text,
            msg="the raw, unescaped <script> tag must never appear in the "
                "output bytes")
        self.assertIn(
            "&lt;script&gt;alert(1)&lt;/script&gt;", html_text,
            msg="the escaped form must be present, proving the value was "
                "rendered (not silently dropped) and escaped")


class TestSessionAuditRendererTimeHoursFormatting(unittest.TestCase):
    def test_should_print_every_time_partition_bucket_duration_in_hours_instead_of_a_bare_seconds_count_over_a_minute(self):
        """Gap 4: the old renderer printed every bucket and the wall clock
        as a bare seconds count. Every duration over a minute must go
        through the hours formatter -- no "1200s"/"3600s" left anywhere."""
        cost = _cost_fixture()
        timeline = _timeline_fixture()  # buckets: 1200s, 900s, 600s, 900s; wall clock 3600s
        narrative = _narrative_fixture()

        html_text = rsa.render_audit_html(cost, timeline, narrative)

        self.assertIn("20m", html_text, msg="the 1200s main_api bucket must render as 20m")
        self.assertIn("15m", html_text, msg="the 900s tool_exec/human_idle buckets must render as 15m")
        self.assertIn("10m", html_text, msg="the 600s agent_occupied bucket must render as 10m")
        self.assertIn("1h 0m", html_text, msg="the 3600s wall clock must render as 1h 0m")
        self.assertNotIn("1200s", html_text, msg="no bare-seconds bucket duration may remain")
        self.assertNotIn("3600s", html_text, msg="no bare-seconds wall clock duration may remain")

    def test_should_render_the_agent_hours_vs_wall_clock_occupied_pair_as_two_labelled_bars_in_hours(self):
        """The parallelism ratio (how much agent work ran concurrently vs
        how long the human actually watched it happen) must render as two
        distinct labelled bars, both durations through the hours
        formatter -- never a bare seconds count."""
        cost = _cost_fixture()
        timeline = _timeline_fixture()  # agent_hours_seconds=1800, wall_clock_occupied_seconds=600
        narrative = _narrative_fixture()

        html_text = rsa.render_audit_html(cost, timeline, narrative)

        self.assertIn("30m", html_text, msg="1800s agent hours must render as 30m")
        self.assertEqual(
            html_text.count('class="bar-row"'), 2,
            msg="the agent-hours-vs-wall-clock-occupied pair must render as "
                "exactly two side-by-side labelled bars")
        self.assertNotIn("1800s", html_text, msg="no bare-seconds agent-hours duration may remain")


class TestSessionAuditRendererCommitsRemoved(unittest.TestCase):
    def test_should_not_render_a_commits_section_even_when_the_timeline_carries_commit_items(self):
        """Gap 5: the Commits section is a wall of raw git-log text that
        the user said means nothing -- "Work done" already carries the
        1-line-per-change changelog. The renderer must never emit a
        Commits heading or the raw commit command text, even when
        timeline.json still carries commits.items (the extractor keeps
        emitting them; only this renderer's use of them stops)."""
        cost = _cost_fixture()
        timeline = _timeline_fixture()  # commits.items carries a real commit command
        narrative = _narrative_fixture()

        html_text = rsa.render_audit_html(cost, timeline, narrative)

        self.assertNotIn("Commits", html_text,
                          msg="no Commits heading may appear anywhere on the page")
        self.assertNotIn(
            'git commit -m "fix(render): guard against None"', html_text,
            msg="the raw commit command text must not reach the page")


class TestSessionAuditRendererHighlights(unittest.TestCase):
    def test_should_render_a_highlights_kpi_strip_with_every_tile_rendered_when_its_source_data_is_present(self):
        """Gap 7 (Highlights): a deterministic KPI card strip, not LLM
        prose. Each tile is gated on its own source key -- this test
        supplies every optional key so every one of the 9 tiles renders,
        proving both the two computed tiles (cost/hour, main-vs-subagent
        split) and the simple pass-through tiles all fire."""
        cost = _cost_fixture(
            total=16.80,
            cache_hit_rate=0.80,
            api_calls={"main": 41, "sub": 17},
            compactions=9,
            kpis={"session_hours": 4.0, "user_messages": 26, "interruptions": 3},
        )
        timeline = _timeline_fixture()  # wall_clock_seconds=3600.0
        narrative = _narrative_fixture()

        html_text = rsa.render_audit_html(cost, timeline, narrative)

        self.assertIn("Highlights", html_text, msg="the Highlights section title must appear")
        self.assertIn("$16.80", html_text, msg="Total cost tile: total verbatim as dollars")
        self.assertIn("1h 0m", html_text, msg="Wall clock tile: 3600s through the hours formatter")
        self.assertIn("$4.20", html_text, msg="Cost / hour tile: 16.80 / 4.0 session_hours")
        self.assertIn("72%", html_text,
                       msg="Main vs subagent tile: main_cost 9.03 of 12.47 combined is 72%")
        for tile_label in ("Cache hit rate", "API calls", "User messages",
                            "Compactions", "Interruptions"):
            self.assertIn(f'<span class="kpi-label">{tile_label}</span>', html_text,
                           msg=f"the {tile_label} tile must render when its source key is present")

    def test_should_render_the_cache_hit_rate_tile_as_a_percent_of_a_0_to_1_fraction_not_the_raw_fraction_value(self):
        """claude-usage-report.py always emits cache_hit_rate as a 0-1
        fraction (`round(derived["cache_hit_rate"], 3)`), confirmed across
        every usage-history snapshot (e.g. 0.927, 0.952, 0.864) -- never
        already scaled to 0-100. A tile that prints the raw fraction with
        a trailing '%' would show a session with 92.7% cache hits as
        '1%', silently inverting the number gap 2 exists to surface."""
        cost = _cost_fixture(cache_hit_rate=0.927)
        timeline = _timeline_fixture()
        narrative = _narrative_fixture()

        html_text = rsa.render_audit_html(cost, timeline, narrative)

        self.assertIn("93%", html_text,
                       msg="0.927 must render as 93% (fraction times 100, rounded)")
        self.assertNotIn("1%", html_text,
                          msg="the raw fraction must never be printed with a bare percent sign")

    def test_should_skip_a_highlights_tile_whose_source_cost_json_key_is_absent_rather_than_printing_none(self):
        """`_cost_fixture()` carries only total/main_cost/subagent_cost --
        the 6 tiles whose source keys it omits (cost/hour, cache hit rate,
        API calls, user messages, compactions, interruptions) must not
        render at all, and never as a literal "None"."""
        cost = _cost_fixture()  # only total, main_cost, subagent_cost
        timeline = _timeline_fixture()
        narrative = _narrative_fixture()

        html_text = rsa.render_audit_html(cost, timeline, narrative)

        self.assertIn("$12.47", html_text, msg="Total cost tile still renders: total is present")
        self.assertIn("1h 0m", html_text, msg="Wall clock tile still renders: timeline always carries it")
        self.assertNotIn("$None", html_text,
                          msg="a missing dollar-value source key must skip its tile, "
                              "never render the literal None inside a $ tile")
        for missing_tile_label in ("Cost / hour", "Cache hit rate", "API calls",
                                     "User messages", "Compactions", "Interruptions"):
            self.assertNotIn(f'<span class="kpi-label">{missing_tile_label}</span>', html_text,
                              msg=f"the {missing_tile_label} tile must not render "
                                  "when its source key is absent")


class TestSessionAuditRendererMoneyMainVsSubagent(unittest.TestCase):
    def test_should_render_a_main_vs_subagent_stacked_bar_with_dollar_and_percent_labels_in_the_money_panel(self):
        """Gap 3: main-vs-subagent distribution was invisible. One
        horizontal stacked bar, two segments, each labelled with its
        dollar amount and percent of the combined main+subagent spend."""
        cost = _cost_fixture()  # main_cost=9.03, subagent_cost=3.44
        timeline = _timeline_fixture()
        narrative = _narrative_fixture()

        html_text = rsa.render_audit_html(cost, timeline, narrative)

        self.assertIn("$9.03", html_text, msg="the main-session dollar amount must be labelled")
        self.assertIn("$3.44", html_text, msg="the subagent dollar amount must be labelled")
        self.assertIn("72%", html_text, msg="main session's percent of combined spend (9.03/12.47)")
        self.assertIn("28%", html_text, msg="subagent's percent of combined spend (3.44/12.47)")


class TestSessionAuditRendererModelDistribution(unittest.TestCase):
    def test_should_render_model_distribution_bars_from_by_model_when_present(self):
        """Gap 2: model distribution was invisible. Horizontal bar rows
        from `by_model`, each labelled with the exact model name, its
        dollar amount, and its percent of the by_model total."""
        cost = _cost_fixture(by_model={"claude-opus-5": 30.36, "claude-sonnet-5": 17.20})
        timeline = _timeline_fixture()
        narrative = _narrative_fixture()

        html_text = rsa.render_audit_html(cost, timeline, narrative)

        self.assertIn("claude-opus-5", html_text, msg="the exact model name must be labelled")
        self.assertIn("$30.36", html_text, msg="the model's dollar amount must be labelled")
        self.assertIn("claude-sonnet-5", html_text)
        self.assertIn("$17.20", html_text)

    def test_should_fall_back_to_by_family_bars_when_by_model_is_absent(self):
        """When cost.json only carries family-level totals (by_model
        absent), the model-distribution bars must fall back to by_family
        rather than rendering nothing."""
        cost = _cost_fixture(by_family={"opus": 30.36, "sonnet": 17.20})
        timeline = _timeline_fixture()
        narrative = _narrative_fixture()

        html_text = rsa.render_audit_html(cost, timeline, narrative)

        self.assertIn("opus", html_text, msg="the family name must be labelled when by_model is absent")
        self.assertIn("$30.36", html_text)
        self.assertIn("sonnet", html_text)
        self.assertIn("$17.20", html_text)


class TestSessionAuditRendererTokenBreakdown(unittest.TestCase):
    def test_should_scale_each_token_breakdown_bar_to_the_max_token_value_so_cache_read_does_not_collapse_the_other_rows_to_invisible(self):
        """Gap 1: cache_read dwarfs every other token count, so a renderer
        that scaled bar widths to the SUM of all token counts would shrink
        every other row to an invisible sliver. Scaling to the MAX value
        instead keeps the largest row at a full 100% bar and the rest
        proportionate to it, per the spec: "scale each bar to the max token
        value, not the sum, or every other row collapses to invisible"."""
        cost = _cost_fixture(tokens={
            "input": 1300000,
            "output": 200000,
            "cache_read": 58290000,
            "cache_write_5m": 500000,
            "cache_write_1h": 100000,
        })
        timeline = _timeline_fixture()
        narrative = _narrative_fixture()

        html_text = rsa.render_audit_html(cost, timeline, narrative)

        self.assertIn(
            "width:100.0%", html_text,
            msg="the max-value row (cache_read) must fill its bar completely")
        self.assertNotIn(
            "width:96.5%", html_text,
            msg="a renderer that scaled to the SUM instead of the MAX would shrink "
                "cache_read's own bar to ~96.5% of the track instead of a full 100%")
        self.assertIn(
            "cache write is input", html_text,
            msg="the pricing note must explain the cache-write cost multipliers "
                "(input x1.25 for 5m TTL / input x2 for 1h TTL)")
        self.assertIn(
            "58.29M", html_text,
            msg="the cache_read count must be humanized (58.29M), not printed as "
                "the raw digit count a human cannot parse at a glance")
        self.assertNotIn("58290000", html_text)


class TestSessionAuditRendererThinkingShare(unittest.TestCase):
    def test_should_render_the_thinking_block_share_with_a_note_that_thinking_tokens_are_billed_inside_output_tokens(self):
        """The usage API never splits thinking tokens out of output tokens
        -- thinking is billed inside tokens.output. The renderer must not
        fabricate a thinking-token count; it may only show the truthful
        proxy cost.json carries (thinking_block_share, as a share of
        assistant *blocks*, not tokens), labelled with an explicit honesty
        note so the reader cannot mistake it for a token count.

        claude-usage-report.py always emits thinking_block_share as a 0-1
        fraction (`round(derived["thinking_block_share"], 3)`), the same
        contract as cache_hit_rate -- never pre-scaled to 0-100. 0.425
        must render as "42.5%", not the raw fraction with a bare percent
        sign, or a session that is 42.5% thinking blocks would print as
        "0.425%"."""
        cost = _cost_fixture(thinking_block_share=0.425, thinking_blocks=17, text_blocks=23)
        timeline = _timeline_fixture()
        narrative = _narrative_fixture()

        html_text = rsa.render_audit_html(cost, timeline, narrative)

        self.assertIn("42.5%", html_text, msg="0.425 must render as 42.5% (fraction times 100)")
        self.assertNotIn("0.425%", html_text,
                          msg="the raw fraction must never be printed with a bare percent sign")
        self.assertIn(
            "billed inside", html_text,
            msg="an explicit honesty note must state thinking tokens are billed "
                "inside output tokens, so the reader cannot mistake the block "
                "share for a token count")
        self.assertNotIn(
            "thinking tokens: 17", html_text,
            msg="thinking_blocks/text_blocks must never be presented as if they "
                "were a token count")

    def test_should_skip_the_thinking_share_panel_when_its_source_data_is_absent(self):
        """Graceful degradation: the trimmed default cost fixture carries no
        thinking_block_share at all -- the panel must simply not render,
        never crash or print a literal "None"."""
        cost = _cost_fixture()  # only total, main_cost, subagent_cost
        timeline = _timeline_fixture()
        narrative = _narrative_fixture()

        html_text = rsa.render_audit_html(cost, timeline, narrative)

        self.assertNotIn("billed inside", html_text)
        self.assertNotIn("None%", html_text)


class TestSessionAuditRendererSubagentTypes(unittest.TestCase):
    def test_should_render_the_top_5_subagent_types_ranked_by_cost_with_a_plus_n_more_line_for_the_rest(self):
        """`by_subagent_type` can carry more entries than fit on a card
        grid -- top 5 by cost, sorted descending (never trusting on-disk
        order), plus a "plus N more, not shown" line for the rest, matching
        the renderer's existing top-N-ranked convention (D9)."""
        cost = _cost_fixture(by_subagent_type={
            "tdd-coder": {"cost": 12.00, "runs": 4},
            "explore": {"cost": 8.50, "runs": 6},
            "code-review": {"cost": 5.25, "runs": 2},
            "pr-review": {"cost": 3.10, "runs": 1},
            "general-purpose": {"cost": 2.00, "runs": 1},
            "doc-writer": {"cost": 0.75, "runs": 1},
            "spike": {"cost": 0.20, "runs": 1},
        })
        timeline = _timeline_fixture()
        narrative = _narrative_fixture()

        html_text = rsa.render_audit_html(cost, timeline, narrative)

        self.assertIn("tdd-coder", html_text, msg="the highest-cost subagent type must be shown")
        self.assertIn("$12.00", html_text)
        self.assertIn("4 runs", html_text)
        self.assertIn("general-purpose", html_text, msg="the 5th-ranked subagent type must still be shown")
        self.assertNotIn("doc-writer", html_text, msg="the 6th+ ranked entry must be dropped, not rendered")
        self.assertNotIn("spike", html_text, msg="the 6th+ ranked entry must be dropped, not rendered")
        self.assertIn("plus 2 more, not shown", html_text)

    def test_should_skip_the_subagent_types_panel_when_its_source_data_is_absent(self):
        """Graceful degradation: the trimmed default cost fixture carries
        no by_subagent_type at all -- the panel must simply not render."""
        cost = _cost_fixture()  # only total, main_cost, subagent_cost
        timeline = _timeline_fixture()
        narrative = _narrative_fixture()

        html_text = rsa.render_audit_html(cost, timeline, narrative)

        self.assertNotIn("not shown", html_text)


class TestSessionAuditRendererMoneyPanelDegradation(unittest.TestCase):
    def test_should_render_the_money_and_highlights_panels_without_crashing_when_cost_json_carries_only_total_main_cost_and_subagent_cost(self):
        """Umbrella graceful-degradation check: `_cost_fixture()`'s default
        shape (total/main_cost/subagent_cost only, no tokens, no by_model,
        no by_subagent_type, no thinking_block_share, no kpis) must render
        the full page -- Highlights strip and every Money sub-panel included
        -- without raising, and without a literal "None" surfacing anywhere
        a skipped panel's absent value would otherwise have printed."""
        cost = _cost_fixture()
        timeline = _timeline_fixture()
        narrative = _narrative_fixture()

        html_text = rsa.render_audit_html(cost, timeline, narrative)  # must not raise

        self.assertIn("Highlights", html_text)
        self.assertIn("$12.47", html_text, msg="the total that IS present must still render")
        self.assertNotIn("$None", html_text)
        self.assertNotIn("None%", html_text)
        self.assertNotIn(">None<", html_text)


class TestSessionAuditRendererInlineSvgNoXmlns(unittest.TestCase):
    def test_should_render_inline_svg_bar_charts_without_the_xmlns_attribute_so_the_self_contained_no_url_guard_still_holds(self):
        """The xmlns attribute is optional for inline SVG under HTML5, and
        the standard value ("http://www.w3.org/2000/svg") would itself trip
        the page's own no-http(s):// self-containment guard. This is a
        regression guard: a future edit to _render_stacked_bar_svg must not
        reintroduce it."""
        cost = _cost_fixture()
        timeline = _timeline_fixture()
        narrative = _narrative_fixture()

        html_text = rsa.render_audit_html(cost, timeline, narrative)

        self.assertIn("<svg", html_text, msg="the page must actually contain an inline svg chart")
        self.assertNotIn("xmlns", html_text)
        self.assertNotIn("http://www.w3.org/2000/svg", html_text)


class TestSessionAuditRendererPageOrder(unittest.TestCase):
    def test_should_render_the_page_sections_in_the_order_highlights_money_time_work_status_recommendations(self):
        """The spec's new page structure replaces the old double-rendered
        Cost/Time-data/Commits/4-narrative layout with one section per
        topic in a fixed order: Highlights, Money (data panel merged with
        its narrative), Time (data panel merged with its narrative), Work
        done, Status and next steps, Recommendations."""
        cost = _cost_fixture()
        timeline = _timeline_fixture()
        narrative = _narrative_fixture()

        html_text = rsa.render_audit_html(cost, timeline, narrative)

        positions = {
            heading: html_text.index(f">{heading}<")
            for heading in ("Highlights", "Money", "Time", "Work done",
                             "Status and next steps", "Recommendations")
        }
        ordered = sorted(positions, key=lambda heading: positions[heading])
        self.assertEqual(
            ordered,
            ["Highlights", "Money", "Time", "Work done",
             "Status and next steps", "Recommendations"],
            msg=f"sections rendered out of the spec'd page order: {positions}")

    def test_should_merge_the_money_data_panel_into_the_single_money_section_rather_than_a_separate_cost_section(self):
        """The old renderer double-rendered every topic: a bare data "Cost"
        section AND a separate narrative "Money" section. The spec calls
        this out as "a large part of why it reads badly" and asks for one
        merged section per topic -- so there must be exactly one Money
        <h2>, with the main-vs-subagent stacked bar living inside it."""
        cost = _cost_fixture()
        timeline = _timeline_fixture()
        narrative = _narrative_fixture()

        html_text = rsa.render_audit_html(cost, timeline, narrative)

        self.assertNotIn(">Cost<", html_text, msg="the old standalone Cost heading must be gone")
        money_start = html_text.index(">Money<")
        next_h2 = html_text.index("<h2>", money_start + 1)
        money_section = html_text[money_start:next_h2]
        self.assertIn(
            'class="stacked-bar"', money_section,
            msg="the main-vs-subagent stacked bar must live inside the Money section")


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
        """A realistically large session -- a long multi-hour batch, every
        Money data panel populated (tokens, models, subagent types), and
        every narrative section near its top-N cap -- must still render
        under FOUR_PAGE_BYTE_BUDGET, so the audit page stays a quick read
        rather than silently ballooning with every finding a long session
        accumulates.

        Commits no longer render (spec gap 5: the Commits section was
        deleted, "Work done" already carries the changelog), so this
        fixture exercises the new heavy paths instead -- a full cost.json
        with every token/model/subagent key populated -- to still prove
        something about page weight."""
        cost = _cost_fixture(
            cache_hit_rate=0.784,
            api_calls={"main": 210, "sub": 340},
            compactions=6,
            thinking_block_share=0.382,
            thinking_blocks=112,
            text_blocks=181,
            kpis={"session_hours": 8.2, "user_messages": 64, "interruptions": 5},
            tokens={
                "input": 1_300_000,
                "output": 890_000,
                "cache_read": 58_290_000,
                "cache_write_5m": 2_100_000,
                "cache_write_1h": 640_000,
            },
            by_model={f"claude-model-{i}": 20.0 - i for i in range(8)},
            by_subagent_type={
                f"subagent-type-{i}": {"cost": 15.0 - i, "runs": 20 - i}
                for i in range(15)
            },
        )
        timeline = _timeline_fixture()
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
                ranked=[_ranked_item(f"fix(module-{i}): resolve edge case in handler {i}", 50.0 - i)
                        for i in range(20)],
                findings=[f"Finding {i} summarizing a cluster of related commits." for i in range(10)]),
            _section_digest(
                "status", "Session is complete with 2 follow-ups queued.",
                ranked=[_ranked_item(f"task {i}", 5.0 - i * 0.1) for i in range(20)],
                findings=[f"Finding {i} about remaining follow-up work." for i in range(10)]),
            _section_digest(
                "recommendations", "Five concrete follow-ups would cut spend and time.",
                ranked=[_ranked_item(f"recommendation {i}", 5.0 - i * 0.1) for i in range(20)],
                findings=[f"Finding {i} tying a recommendation to a specific number." for i in range(10)]),
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
            _section_digest("recommendations", "Two concrete follow-ups would cut spend.", ranked=[]),
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
        """The orchestrator always produces 5 fixed shards (S1-S4 -- time,
        money, work, status -- dispatched in parallel, then S5
        recommendations dispatched sequentially once their digests merge);
        a narrative.json missing one of them is malformed input, and
        rendering must refuse loudly rather than emit a page with that
        whole section silently absent."""
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

    def test_should_refuse_to_render_when_the_narrative_digest_is_missing_the_recommendations_section(self):
        """A 5th fixed shard (S5 Recommendations) now runs sequentially
        after the other 4 are merged; a narrative.json missing its digest
        is malformed input exactly like a missing time/money/work/status
        digest, and must refuse loudly rather than silently drop the
        Recommendations section."""
        cost = _cost_fixture()
        timeline = _timeline_fixture()
        narrative = _narrative_fixture(sections=[
            _section_digest("time", "Engaged time was 45 minutes.", ranked=[_ranked_item("turn 0", 120.0)]),
            _section_digest("money", "Session cost $12.47 total.", ranked=[_ranked_item("main", 9.03)]),
            _section_digest("work", "One commit landed.", ranked=[_ranked_item("commit", 1.0)]),
            _section_digest("status", "Session is complete.", ranked=[]),
            # "recommendations" section deliberately omitted.
        ])

        with self.assertRaises(ValueError) as ctx:
            rsa.render_audit_html(cost, timeline, narrative)

        self.assertIn("recommendations", str(ctx.exception),
                       msg="the refusal must name the missing section so "
                           "the caller knows which shard's digest is absent")


if __name__ == "__main__":
    unittest.main()
