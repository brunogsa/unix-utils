#!/usr/bin/env python3
"""Billing-correctness and snapshot-mechanics tests for claude-usage-report.py.

Fixtures: none on disk — every transcript is a handful of hand-readable
records built in code via _assistant_record()/_write_transcript() below, each
one small enough that the expected dollar figure can be verified by hand
against MODEL_PRICES / SONNET_5_INTRO_PRICES / FAST_MODE_PRICES.

The billing-correctness tests force TZ=America/Sao_Paulo (UTC-3, no DST) for
their whole class so local-day bucketing is deterministic on any machine —
Sao Paulo is also the real-world timezone the local-day bug was measured
against. Every filesystem path used (transcripts root, snapshots dir) is a
tempfile.TemporaryDirectory(); this file never reads or writes
~/.claude/projects or the committed usage-history/snapshots/.

Usage:
  python3 scripts/tests/test_claude_usage_report.py
"""

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import date, datetime, timedelta, timezone
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


cur = _load_module("claude-usage-report.py", "claude_usage_report")


def _iso(epoch):
    """Epoch seconds -> UTC ISO-8601 string, the shape parse_ts() expects."""
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def _advisor_iteration(*, input_tokens, output_tokens, model="claude-opus-5"):
    """One usage.iterations entry for an /advisor turn's second model —
    the only place Claude Code reports that model's tokens."""
    return {
        "type": "advisor_message",
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_read_input_tokens": 0,
        "cache_creation_input_tokens": 0,
        "cache_creation": {"ephemeral_5m_input_tokens": 0, "ephemeral_1h_input_tokens": 0},
    }


def _assistant_record(message_id, request_id, epoch, *, input_tokens, output_tokens,
                       cache_read_tokens=0, model="claude-sonnet-5", speed=None,
                       advisor_iterations=None):
    """One transcript line for a single content-block of an assistant
    response, shaped like a real Claude Code transcript record."""
    usage = {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_read_input_tokens": cache_read_tokens,
        "cache_creation_input_tokens": 0,
        "cache_creation": {"ephemeral_5m_input_tokens": 0, "ephemeral_1h_input_tokens": 0},
    }
    if speed is not None:
        usage["speed"] = speed
    if advisor_iterations is not None:
        # Real records carry the main model's own turn as a "message"
        # iteration alongside; only the advisor entries are extra spend.
        usage["iterations"] = [{"type": "message"}] + advisor_iterations
    return {
        "type": "assistant",
        "timestamp": _iso(epoch),
        "requestId": request_id,
        "message": {
            "id": message_id,
            "role": "assistant",
            "model": model,
            "content": [{"type": "text", "text": "..."}],
            "usage": usage,
        },
    }


def _write_transcript(dir_path, filename, records):
    """Write one record per line to dir_path/filename; returns the path."""
    path = os.path.join(dir_path, filename)
    with open(path, "w") as fh:
        for record in records:
            fh.write(json.dumps(record) + "\n")
    return path


class TestPricingRates(unittest.TestCase):
    """Pure unit tests of message_rates() — the branch that picks which price
    tuple a message bills at, given its model, day, and usage.speed.
    """

    def test_sonnet_5_bills_at_the_introductory_rate_on_the_last_day_of_its_intro_window(self):
        rates = cur.message_rates("claude-sonnet-5", cur.SONNET_5_INTRO_LAST_DAY, speed=None)
        self.assertEqual(
            rates, cur.SONNET_5_INTRO_PRICES,
            "Sonnet 5 on the last day of its intro window must still bill "
            "at the promotional $2/$10 rate, not the standard $3/$15 rate")

    def test_sonnet_5_bills_at_the_standard_rate_the_day_after_its_intro_window_closes(self):
        day_after_intro = (date.fromisoformat(cur.SONNET_5_INTRO_LAST_DAY)
                            + timedelta(days=1)).isoformat()
        rates = cur.message_rates("claude-sonnet-5", day_after_intro, speed=None)
        self.assertEqual(
            rates, cur.MODEL_PRICES["claude-sonnet-5"],
            "Sonnet 5 the day after its intro window closes must bill at "
            "the standard $3/$15 rate, not the $2/$10 promotional rate")

    def test_fast_mode_opus_bills_at_double_the_standard_rate(self):
        rates = cur.message_rates("claude-opus-5", "2026-07-20", speed="fast")
        self.assertEqual(
            rates, cur.FAST_MODE_PRICES,
            "Opus 5 with usage.speed == 'fast' must bill at the doubled "
            "fast-mode rate ($10/$50), keyed off usage.speed alone since "
            "nothing in the token counts reveals fast mode")
        self.assertNotEqual(
            rates, cur.MODEL_PRICES["claude-opus-5"],
            "the fast-mode rate must differ from Opus 5's standard list rate")

    def test_standard_speed_opus_bills_at_the_undoubled_list_rate(self):
        rates = cur.message_rates("claude-opus-5", "2026-07-20", speed="standard")
        self.assertEqual(
            rates, cur.MODEL_PRICES["claude-opus-5"],
            "Opus 5 with usage.speed == 'standard' must NOT bill at the "
            "doubled fast-mode rate")


@unittest.skipUnless(hasattr(time, "tzset"), "requires POSIX tzset (macOS/Linux)")
class TestBillingCorrectness(unittest.TestCase):
    """Regression coverage for the two billing bugs described in this
    script's module docstring, plus the day-attribution and subagent-rollup
    invariants those bugs depend on.
    """

    _original_tz = None

    @classmethod
    def setUpClass(cls):
        cls._original_tz = os.environ.get("TZ")
        os.environ["TZ"] = "America/Sao_Paulo"
        time.tzset()

    @classmethod
    def tearDownClass(cls):
        if cls._original_tz is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = cls._original_tz
        time.tzset()

    def test_a_response_written_as_three_content_block_records_bills_exactly_once(self):
        """A response Claude Code writes as N transcript records — one per
        content block, each stamped with the identical message.usage — must
        bill exactly once, not once per block. Regression for the bug fixed
        2026-07-27: summing every record inflated a day 3.4x."""
        day = "2026-07-20"
        since, until = cur.day_bounds(day)
        epoch = since + 3600
        # All three blocks share one epoch: real transcripts can stamp
        # sub-second blocks identically, and a shared epoch isolates the
        # dedup gate from the separate anchor-day mechanism under test
        # elsewhere, which also blocks a same-key repeat but only when the
        # repeat's epoch differs from the earliest one seen for that key.
        records = [
            _assistant_record("msg_dedup", "req_dedup", epoch,
                               input_tokens=1000, output_tokens=500, cache_read_tokens=200)
            for _ in range(3)
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_transcript(tmp, "session.jsonl", records)
            result = cur.aggregate([path], [], since, until)

        price_in, price_out, price_cache = cur.SONNET_5_INTRO_PRICES
        expected_once = (1000 * price_in + 500 * price_out + 200 * price_cache) / 1e6
        self.assertAlmostEqual(
            result["main_cost"], expected_once, places=6,
            msg="a 3-block response with identical usage on each block must "
                "bill once, not 3 times")
        self.assertEqual(
            result["api_calls"]["main"], 1,
            msg="3 content-block records of one response must count as 1 "
                "API call, not 3")

    def test_a_response_with_growing_output_tokens_bills_the_peak_not_the_anchor_or_the_sum(self):
        """output_tokens is written cumulatively as a response streams, so a
        response whose blocks report output_tokens 100, then 400, then 900
        must bill the peak (900) — not the earliest block's partial 100, and
        not the naive sum 1400. Regression for the bug fixed 2026-08-08."""
        day = "2026-07-20"
        since, until = cur.day_bounds(day)
        epoch = since + 3600
        records = [
            _assistant_record("msg_peak", "req_peak", epoch + i,
                               input_tokens=1000, output_tokens=out, cache_read_tokens=0)
            for i, out in enumerate([100, 400, 900])
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_transcript(tmp, "session.jsonl", records)
            result = cur.aggregate([path], [], since, until)

        price_in, price_out, _ = cur.SONNET_5_INTRO_PRICES
        expected = (1000 * price_in + 900 * price_out) / 1e6
        self.assertAlmostEqual(
            result["main_cost"], expected, places=6,
            msg="the response must bill its peak output_tokens (900), not "
                "the anchor block's 100 (under-bills) and not the sum 1400 "
                "(over-bills)")

    def test_a_response_straddling_local_midnight_bills_once_to_the_earlier_local_day(self):
        """A response whose content-block records straddle local midnight
        must bill entirely to the local day of its earliest record, and must
        not also be counted when the following day is scanned separately."""
        day1, day2 = "2026-07-16", "2026-07-17"
        boundary = cur.day_bounds(day2)[0]
        records = [
            _assistant_record("msg_straddle", "req_straddle", boundary - 1,
                               input_tokens=1000, output_tokens=100, cache_read_tokens=0),
            _assistant_record("msg_straddle", "req_straddle", boundary + 1,
                               input_tokens=1000, output_tokens=900, cache_read_tokens=0),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_transcript(tmp, "session.jsonl", records)
            since1, until1 = cur.day_bounds(day1)
            day1_result = cur.aggregate([path], [], since1, until1)
            since2, until2 = cur.day_bounds(day2)
            day2_result = cur.aggregate([path], [], since2, until2)

        price_in, price_out, _ = cur.SONNET_5_INTRO_PRICES
        expected_day1_cost = (1000 * price_in + 900 * price_out) / 1e6
        self.assertAlmostEqual(
            day1_result["main_cost"], expected_day1_cost, places=6,
            msg="a response anchored just before local midnight must bill "
                "fully to that earlier day, using its peak output tokens")
        self.assertEqual(
            day2_result["main_cost"], 0.0,
            msg="the same response's later block must not be re-billed "
                "when the next day is scanned on its own")
        self.assertEqual(
            day2_result["api_calls"]["main"], 0,
            msg="the next day's scan must not count the straddling "
                "response as an API call at all")

    def test_local_day_converts_a_utc_evening_timestamp_to_the_previous_local_calendar_day(self):
        """A record whose UTC calendar date and local calendar date differ
        must convert to the LOCAL date. Bucketing by the raw UTC date
        historically misfiled 44.2% of records for a UTC-3 user."""
        # 2026-07-21T01:00:00Z is 2026-07-20T22:00:00 local at UTC-3 (this
        # test class's forced TZ): UTC day is the 21st, local day the 20th.
        epoch = cur.parse_ts("2026-07-21T01:00:00Z")
        self.assertEqual(
            cur.local_day(epoch), "2026-07-20",
            msg="a record timestamped 2026-07-21T01:00:00Z must bucket to "
                "local day 2026-07-20 (UTC-3), not the UTC date 2026-07-21")

    def test_aggregate_files_a_cross_utc_midnight_record_under_its_local_day_not_its_utc_day(self):
        """The same UTC/local divergence, proven end to end through
        aggregate()'s by_day rollup rather than just the local_day() helper."""
        epoch = cur.parse_ts("2026-07-21T01:00:00Z")
        local_day, utc_day = "2026-07-20", "2026-07-21"
        since, until = cur.day_bounds(local_day)
        record = _assistant_record("msg_localday", "req_localday", epoch,
                                    input_tokens=1000, output_tokens=1, cache_read_tokens=0)
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_transcript(tmp, "session.jsonl", [record])
            result = cur.aggregate([path], [], since, until)

        self.assertIn(
            local_day, result["by_day"],
            msg="aggregate's by_day must key this record under its local "
                "day 2026-07-20")
        self.assertNotIn(
            utc_day, result["by_day"],
            msg="aggregate's by_day must not also file this record under "
                "its UTC day 2026-07-21")

    def test_a_subagent_nested_two_levels_deep_rolls_up_to_the_top_level_session_once(self):
        """A subagent transcript nested under .../subagents/... at any depth
        — including a subagent's own subagent — rolls its cost up to the
        top-level parent session, via path.split("/subagents/")[0], and is
        counted exactly once in that parent's subagent tally."""
        day = "2026-07-20"
        since, until = cur.day_bounds(day)
        epoch = since + 3600
        with tempfile.TemporaryDirectory() as tmp:
            parent_path = os.path.join(tmp, "parent-session.jsonl")
            one_level_path = os.path.join(tmp, "parent-session", "subagents", "child.jsonl")
            two_level_path = os.path.join(
                tmp, "parent-session", "subagents", "child", "subagents", "grandchild.jsonl")
            os.makedirs(os.path.dirname(one_level_path), exist_ok=True)
            os.makedirs(os.path.dirname(two_level_path), exist_ok=True)

            _write_transcript(tmp, "parent-session.jsonl", [
                _assistant_record("msg_parent", "req_parent", epoch,
                                   input_tokens=1000, output_tokens=100, cache_read_tokens=0),
            ])
            _write_transcript(os.path.dirname(one_level_path), "child.jsonl", [
                _assistant_record("msg_child", "req_child", epoch,
                                   input_tokens=1000, output_tokens=200, cache_read_tokens=0),
            ])
            _write_transcript(os.path.dirname(two_level_path), "grandchild.jsonl", [
                _assistant_record("msg_grandchild", "req_grandchild", epoch,
                                   input_tokens=1000, output_tokens=300, cache_read_tokens=0),
            ])

            result = cur.aggregate([parent_path], [one_level_path, two_level_path], since, until)

        price_in, price_out, _ = cur.SONNET_5_INTRO_PRICES
        expected_subagent_cost = (
            (1000 * price_in + 200 * price_out) + (1000 * price_in + 300 * price_out)
        ) / 1e6
        self.assertAlmostEqual(
            result["subagent_cost"], expected_subagent_cost, places=6,
            msg="a subagent nested 2 levels deep must roll its cost into "
                "subagent_cost the same as a 1-level-deep one")
        self.assertIn(
            parent_path, result["subagents_per_session"],
            msg="both the 1-level and 2-level nested subagents must roll "
                "up under the same top-level parent session key")
        self.assertEqual(
            result["subagents_per_session"][parent_path]["runs"], 2,
            msg="the parent's subagent run count must be 2 (one per "
                "nested subagent), not merged into 1 or double-counted")

    def test_an_advisor_turn_bills_its_second_model_on_top_of_the_main_one(self):
        """An /advisor turn bills a second model whose tokens appear ONLY in
        usage.iterations — the top-level usage fields sum the "message"
        iterations alone. Regression for the bug fixed 2026-08-09, where
        those tokens were structurally invisible to the aggregator."""
        day = "2026-07-20"
        since, until = cur.day_bounds(day)
        epoch = since + 3600
        record = _assistant_record(
            "msg_advisor", "req_advisor", epoch,
            input_tokens=1000, output_tokens=100,
            advisor_iterations=[_advisor_iteration(input_tokens=50000, output_tokens=800)])
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_transcript(tmp, "session.jsonl", [record])
            result = cur.aggregate([path], [], since, until)

        main_in, main_out, _ = cur.SONNET_5_INTRO_PRICES
        advisor_in, advisor_out, _ = cur.MODEL_PRICES["claude-opus-5"]
        expected = (
            1000 * main_in + 100 * main_out + 50000 * advisor_in + 800 * advisor_out
        ) / 1e6
        self.assertAlmostEqual(
            result["main_cost"], expected, places=6,
            msg="the advisor iteration's tokens must bill at the ADVISOR's "
                "own model rate on top of the main model's turn")
        self.assertEqual(
            result["tokens"]["input"], 51000,
            msg="the advisor iteration's 50,000 input tokens must be added "
                "to the main turn's 1,000, not silently dropped")

    def test_advisor_tokens_on_a_non_anchor_block_still_bill_and_bill_only_once(self):
        """A subagent transcript never carries its advisor iterations on the
        ANCHOR block record — measured 2026-07-19: 0 of 13 on the anchor. The
        dedup gate skips every non-anchor record, so reading the iterations
        off the record being priced dropped every subagent advisor call."""
        day = "2026-07-20"
        since, until = cur.day_bounds(day)
        epoch = since + 3600
        iterations = [_advisor_iteration(input_tokens=50000, output_tokens=800)]
        records = [
            # The anchor carries none, exactly as a real subagent's does.
            _assistant_record("msg_late", "req_late", epoch,
                               input_tokens=1000, output_tokens=100),
            _assistant_record("msg_late", "req_late", epoch + 1,
                               input_tokens=1000, output_tokens=100,
                               advisor_iterations=iterations),
            _assistant_record("msg_late", "req_late", epoch + 2,
                               input_tokens=1000, output_tokens=100,
                               advisor_iterations=iterations),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            subagent_dir = os.path.join(tmp, "parent-session", "subagents")
            os.makedirs(subagent_dir, exist_ok=True)
            _write_transcript(tmp, "parent-session.jsonl", [
                _assistant_record("msg_parent", "req_parent", epoch,
                                   input_tokens=10, output_tokens=10),
            ])
            path = _write_transcript(subagent_dir, "child.jsonl", records)
            result = cur.aggregate(
                [os.path.join(tmp, "parent-session.jsonl")], [path], since, until)

        advisor_in, advisor_out, _ = cur.MODEL_PRICES["claude-opus-5"]
        main_in, main_out, _ = cur.SONNET_5_INTRO_PRICES
        expected_subagent = (
            1000 * main_in + 100 * main_out + 50000 * advisor_in + 800 * advisor_out
        ) / 1e6
        self.assertAlmostEqual(
            result["subagent_cost"], expected_subagent, places=6,
            msg="advisor iterations living only on non-anchor blocks must "
                "still bill (once), not be skipped with those blocks")


class TestSnapshotMechanics(unittest.TestCase):
    """Refusal, backfill idempotency, retention coverage, and the ccusage
    cross-check's graceful degradation. Every test isolates TRANSCRIPTS_ROOT
    and SNAPSHOTS_DIR to a tempfile.TemporaryDirectory() via mock.patch.object
    and clears the module's ccusage cache first, so no test depends on or
    mutates real state.
    """

    def test_refuses_to_snapshot_the_current_open_day(self):
        """--day for today (not yet closed) must exit non-zero and must not
        write a snapshot — a day is only immutable once it has ended."""
        today = date.today().isoformat()
        with tempfile.TemporaryDirectory() as tmp:
            transcripts_root = os.path.join(tmp, "projects")
            os.makedirs(transcripts_root)
            snapshots_dir = os.path.join(tmp, "snapshots")
            with mock.patch.object(cur, "TRANSCRIPTS_ROOT", transcripts_root), \
                 mock.patch.object(cur, "SNAPSHOTS_DIR", snapshots_dir), \
                 mock.patch.object(sys, "argv", ["claude-usage-report.py", "--day", today]):
                with self.assertRaises(SystemExit) as ctx:
                    cur.main()
            self.assertFalse(
                os.path.exists(os.path.join(snapshots_dir, f"{today}.json")),
                msg="refusing to snapshot the open day must not leave a "
                    "snapshot file behind")
        self.assertEqual(
            ctx.exception.code, 1,
            msg="requesting a snapshot of today (still open) must exit "
                "with a non-zero status")

    def test_backfill_skips_a_day_that_already_has_a_snapshot(self):
        """--backfill without --rebuild must leave a day's existing
        snapshot file untouched."""
        day = "2026-07-20"
        cur._ccusage_days.clear()
        with tempfile.TemporaryDirectory() as tmp:
            transcripts_root = os.path.join(tmp, "projects")
            os.makedirs(transcripts_root)
            snapshots_dir = os.path.join(tmp, "snapshots")
            os.makedirs(snapshots_dir)
            existing_path = os.path.join(snapshots_dir, f"{day}.json")
            with open(existing_path, "w") as fh:
                json.dump({"day": day, "sentinel": "pre-existing"}, fh)

            args = argparse.Namespace(since=day, until=day, rebuild=False, top=8)
            with mock.patch.object(cur, "TRANSCRIPTS_ROOT", transcripts_root), \
                 mock.patch.object(cur, "SNAPSHOTS_DIR", snapshots_dir), \
                 mock.patch.object(cur.shutil, "which", return_value=None):
                cur.run_backfill(args, last_closed_day="2026-07-25")

            with open(existing_path) as fh:
                after = json.load(fh)
        self.assertEqual(
            after.get("sentinel"), "pre-existing",
            msg="a day that already has a committed snapshot must be left "
                "untouched without --rebuild")

    def test_backfill_with_rebuild_overwrites_a_days_existing_snapshot(self):
        """--backfill --rebuild must re-measure and overwrite a day's
        existing snapshot file rather than skipping it — the escape hatch
        for when an aggregation fix leaves old snapshots wrong."""
        day = "2026-07-20"
        cur._ccusage_days.clear()
        with tempfile.TemporaryDirectory() as tmp:
            transcripts_root = os.path.join(tmp, "projects")
            os.makedirs(transcripts_root)
            snapshots_dir = os.path.join(tmp, "snapshots")
            os.makedirs(snapshots_dir)
            existing_path = os.path.join(snapshots_dir, f"{day}.json")
            with open(existing_path, "w") as fh:
                json.dump({"day": day, "sentinel": "pre-existing"}, fh)

            args = argparse.Namespace(since=day, until=day, rebuild=True, top=8)
            with mock.patch.object(cur, "TRANSCRIPTS_ROOT", transcripts_root), \
                 mock.patch.object(cur, "SNAPSHOTS_DIR", snapshots_dir), \
                 mock.patch.object(cur.shutil, "which", return_value=None):
                cur.run_backfill(args, last_closed_day="2026-07-25")

            with open(existing_path) as fh:
                after = json.load(fh)
        self.assertNotIn(
            "sentinel", after,
            msg="--rebuild must overwrite an existing snapshot with "
                "freshly computed data, not leave the old file untouched")
        self.assertEqual(after["day"], day)

    def test_a_day_before_the_retention_floor_writes_unretained_coverage(self):
        """A day whose transcripts have already been pruned past Claude
        Code's retention floor must record coverage: "unretained", not
        "complete" — unretained means unmeasurable, not idle."""
        day = "2026-06-01"
        retention_floor = "2026-07-01"
        cur._ccusage_days.clear()
        with tempfile.TemporaryDirectory() as tmp:
            transcripts_root = os.path.join(tmp, "projects")
            os.makedirs(transcripts_root)
            snapshots_dir = os.path.join(tmp, "snapshots")
            with mock.patch.object(cur, "TRANSCRIPTS_ROOT", transcripts_root), \
                 mock.patch.object(cur, "SNAPSHOTS_DIR", snapshots_dir), \
                 mock.patch.object(cur.shutil, "which", return_value=None):
                path, _, _ = cur.snapshot_day(day, top_n=8, retention_floor=retention_floor)
            with open(path) as fh:
                payload = json.load(fh)
        self.assertEqual(
            payload["coverage"], "unretained",
            msg="a day older than the retention floor must be marked "
                "unretained, not complete")

    def test_a_day_at_the_retention_floor_writes_complete_coverage(self):
        """The boundary day (day == retention_floor) is still within the
        retained range and must record coverage: "complete"."""
        day = "2026-07-01"
        retention_floor = "2026-07-01"
        cur._ccusage_days.clear()
        with tempfile.TemporaryDirectory() as tmp:
            transcripts_root = os.path.join(tmp, "projects")
            os.makedirs(transcripts_root)
            snapshots_dir = os.path.join(tmp, "snapshots")
            with mock.patch.object(cur, "TRANSCRIPTS_ROOT", transcripts_root), \
                 mock.patch.object(cur, "SNAPSHOTS_DIR", snapshots_dir), \
                 mock.patch.object(cur.shutil, "which", return_value=None):
                path, _, _ = cur.snapshot_day(day, top_n=8, retention_floor=retention_floor)
            with open(path) as fh:
                payload = json.load(fh)
        self.assertEqual(
            payload["coverage"], "complete",
            msg="a day exactly at the retention floor must be marked "
                "complete, not unretained")

    def test_reconciliation_degrades_to_unavailable_when_ccusage_is_not_installed(self):
        """When the ccusage binary is absent, the token cross-check must
        degrade to status "unavailable" rather than crash or silently
        report "ok"."""
        cur._ccusage_days.clear()
        empty_tokens = {"tokens": dict.fromkeys(cur.TOKEN_KINDS, 0)}
        with mock.patch.object(cur.shutil, "which", return_value=None):
            status = cur.reconcile_tokens(empty_tokens, "2026-07-20")
        self.assertEqual(
            status["status"], "unavailable",
            msg="reconcile_tokens must report unavailable, not crash or "
                "claim ok, when ccusage cannot run at all")

    def test_reconciliation_degrades_to_unavailable_when_ccusage_returns_an_unrecognized_schema(self):
        """A ccusage output whose schema this script doesn't recognize (e.g.
        a future version renaming or dropping a field) must degrade to
        status "unavailable" instead of crashing the snapshot run — the
        exact failure mode a ccusage 20.x schema change hit in production."""
        cur._ccusage_days.clear()
        empty_tokens = {"tokens": dict.fromkeys(cur.TOKEN_KINDS, 0)}
        fake_result = subprocess.CompletedProcess(
            args=["ccusage"], returncode=0,
            stdout=json.dumps({"unexpected_top_level_key": []}), stderr="")
        with mock.patch.object(cur.shutil, "which", return_value="/usr/bin/ccusage"), \
             mock.patch.object(cur.subprocess, "run", return_value=fake_result):
            status = cur.reconcile_tokens(empty_tokens, "2026-07-21")
        self.assertEqual(
            status["status"], "unavailable",
            msg="an unrecognized ccusage schema must degrade to "
                "unavailable, not raise an exception or report ok")


if __name__ == "__main__":
    unittest.main(verbosity=2)
