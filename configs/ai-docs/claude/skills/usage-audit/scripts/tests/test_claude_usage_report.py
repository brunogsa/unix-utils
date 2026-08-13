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
import contextlib
import importlib.util
import io
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
                       advisor_iterations=None, cwd=None, skills=(),
                       cache_write_5m=0, cache_write_1h=0,
                       cache_creation_total=None):
    """One transcript line for a single content-block of an assistant
    response, shaped like a real Claude Code transcript record.

    `cache_creation_total` defaults to the two TTL buckets' sum, which
    is what a well-formed record carries; pass it explicitly only to
    build the malformed shape where the flat field disagrees."""
    if cache_creation_total is None:
        cache_creation_total = cache_write_5m + cache_write_1h
    usage = {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_read_input_tokens": cache_read_tokens,
        "cache_creation_input_tokens": cache_creation_total,
        "cache_creation": {"ephemeral_5m_input_tokens": cache_write_5m,
                           "ephemeral_1h_input_tokens": cache_write_1h},
    }
    if speed is not None:
        usage["speed"] = speed
    if advisor_iterations is not None:
        # Real records carry the main model's own turn as a "message"
        # iteration alongside; only the advisor entries are extra spend.
        usage["iterations"] = [{"type": "message"}] + advisor_iterations
    record = {
        "type": "assistant",
        "timestamp": _iso(epoch),
        "requestId": request_id,
        "message": {
            "id": message_id,
            "role": "assistant",
            "model": model,
            "content": [{"type": "text", "text": "..."}] + [
                {"type": "tool_use", "name": "Skill", "input": {"skill": name}}
                for name in skills],
            "usage": usage,
        },
    }

    # Omitted rather than defaulted when no
    # caller names a directory, so the
    # no-cwd path stays exercised.
    if cwd is not None:
        record["cwd"] = cwd
    return record


def _user_record(epoch, text, *, cwd=None):
    """One typed human turn, the shape is_human_message() accepts."""
    record = {
        "type": "user",
        "timestamp": _iso(epoch),
        "message": {"role": "user", "content": [{"type": "text", "text": text}]},
    }
    if cwd is not None:
        record["cwd"] = cwd
    return record


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

    def test_a_response_with_growing_cache_read_tokens_bills_the_peak_not_the_anchor_or_the_sum(self):
        """cache_read_input_tokens grows across a response's blocks on a
        minority of responses, exactly as output_tokens does, so a response
        whose blocks report 200, then 500, then 1200 cache-read tokens must
        bill the peak (1200) — not the anchor block's 200, and not the sum
        1900. Under-billing here left whole days below ccusage and cost them
        their citable status. Regression for the bug fixed 2026-08-09."""
        day = "2026-07-20"
        since, until = cur.day_bounds(day)
        epoch = since + 3600
        records = [
            _assistant_record("msg_cache", "req_cache", epoch + i,
                               input_tokens=1000, output_tokens=100,
                               cache_read_tokens=read)
            for i, read in enumerate([200, 500, 1200])
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_transcript(tmp, "session.jsonl", records)
            result = cur.aggregate([path], [], since, until)

        price_in, price_out, price_cache_read = cur.SONNET_5_INTRO_PRICES
        expected = (1000 * price_in + 100 * price_out
                    + 1200 * price_cache_read) / 1e6
        self.assertAlmostEqual(
            result["main_cost"], expected, places=6,
            msg="the response must bill its peak cache_read_input_tokens "
                "(1200), not the anchor block's 200 (under-bills) and not "
                "the sum 1900 (over-bills)")

    def test_a_response_whose_flat_cache_creation_field_is_zeroed_still_bills_the_ttl_breakdown(self):
        """A minority of records zero every flat usage field while the
        cache_creation breakdown keeps the real figure, so a response
        reporting 0 in cache_creation_input_tokens but 8000 1h-TTL tokens
        in the breakdown must bill those 8000. Trusting the flat field
        dropped them entirely and left 4 days drifting below ccusage.
        Regression for the bug fixed 2026-08-09."""
        day = "2026-07-23"
        since, until = cur.day_bounds(day)
        record = _assistant_record(
            "msg_zeroed", "req_zeroed", since + 3600,
            input_tokens=0, output_tokens=0,
            cache_write_1h=8000, cache_creation_total=0)
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_transcript(tmp, "session.jsonl", [record])
            result = cur.aggregate([path], [], since, until)

        price_in = cur.SONNET_5_INTRO_PRICES[0]
        self.assertAlmostEqual(
            result["main_cost"], 8000 * price_in * 2 / 1e6, places=6,
            msg="the breakdown's 8000 1h-TTL tokens must bill at 2x input, "
                "not be dropped because the flat field reads 0")
        self.assertEqual(
            result["tokens"]["cache_write_1h"], 8000,
            msg="the 1h bucket must carry the breakdown's own figure")

    def test_a_response_with_no_cache_creation_breakdown_bills_its_flat_total_as_one_hour_tokens(self):
        """Records predating the cache_creation breakdown carry only the
        flat total, and Claude Code writes to the 1h cache, so a record
        with an all-zero breakdown and 5000 flat tokens must still bill
        those 5000 at the 1h rate rather than vanish."""
        day = "2026-07-23"
        since, until = cur.day_bounds(day)
        record = _assistant_record(
            "msg_flatonly", "req_flatonly", since + 3600,
            input_tokens=0, output_tokens=0, cache_creation_total=5000)
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_transcript(tmp, "session.jsonl", [record])
            result = cur.aggregate([path], [], since, until)

        self.assertEqual(
            (result["tokens"]["cache_write_5m"],
             result["tokens"]["cache_write_1h"]), (0, 5000),
            msg="with no breakdown to read, the flat total is the only "
                "figure available and belongs to the 1h bucket")

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


class TestRepoClassSplit(unittest.TestCase):
    """Coverage for splitting a day's spend and human touches into the work
    half and the tooling half. Only the work half has a merged-PR
    denominator — the delivered-work ledger excludes the personal-env repos
    by design — so dividing TOTAL spend by PRs measured which repo the day
    was spent in more than how efficiently it was spent.
    """

    TOOLING_CWD = "/Users/brunoagostini/unix-utils/configs/ai-docs/claude"
    WORK_CWD = "/Users/brunoagostini/workspace/code/isaac/contract-validation"

    def test_spend_in_a_personal_environment_repo_bills_to_the_tooling_half(self):
        day = "2026-07-20"
        since, until = cur.day_bounds(day)
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_transcript(tmp, "session.jsonl", [
                _assistant_record("msg_tool", "req_tool", since + 3600,
                                   input_tokens=1000, output_tokens=500,
                                   cwd=self.TOOLING_CWD),
            ])
            result = cur.aggregate([path], [], since, until)

        self.assertAlmostEqual(
            result["by_repo_class"]["tooling"]["cost"], result["main_cost"], places=6,
            msg="a session run inside unix-utils must bill entirely to the "
                "tooling half, which has no merged-PR denominator")
        self.assertEqual(
            result["by_repo_class"]["work"]["cost"], 0.0,
            msg="no work spend may leak from a session that never left a "
                "personal-environment repo")

    def test_spend_in_a_work_repo_bills_to_the_work_half(self):
        day = "2026-07-20"
        since, until = cur.day_bounds(day)
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_transcript(tmp, "session.jsonl", [
                _assistant_record("msg_work", "req_work", since + 3600,
                                   input_tokens=1000, output_tokens=500,
                                   cwd=self.WORK_CWD),
            ])
            result = cur.aggregate([path], [], since, until)

        self.assertAlmostEqual(
            result["by_repo_class"]["work"]["cost"], result["main_cost"], places=6,
            msg="a repo outside the five personal-environment ones is work "
                "spend, mirroring how the ledger discovers work repos")

    def test_a_session_that_moves_between_a_work_repo_and_a_tooling_repo_splits_across_both(self):
        """Classification is per record, not per session: a session that cd's
        from a work repo into this config must land in both halves, which
        per-session tagging could only round to one of them."""
        day = "2026-07-20"
        since, until = cur.day_bounds(day)
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_transcript(tmp, "session.jsonl", [
                _assistant_record("msg_a", "req_a", since + 3600,
                                   input_tokens=1000, output_tokens=500,
                                   cwd=self.WORK_CWD),
                _assistant_record("msg_b", "req_b", since + 7200,
                                   input_tokens=2000, output_tokens=900,
                                   cwd=self.TOOLING_CWD),
            ])
            result = cur.aggregate([path], [], since, until)

        price_in, price_out, _ = cur.SONNET_5_INTRO_PRICES
        self.assertAlmostEqual(
            result["by_repo_class"]["work"]["cost"],
            (1000 * price_in + 500 * price_out) / 1e6, places=6,
            msg="only the turn taken in the work repo may bill to the work half")
        self.assertAlmostEqual(
            result["by_repo_class"]["tooling"]["cost"],
            (2000 * price_in + 900 * price_out) / 1e6, places=6,
            msg="only the turn taken in this config may bill to the tooling half")

    def test_delegating_to_a_subagent_keeps_its_cost_in_the_parents_repo_half(self):
        """A subagent inherits the working directory it was spawned from, so
        delegating work must not move its cost out of the half that has to
        answer for it."""
        day = "2026-07-20"
        since, until = cur.day_bounds(day)
        epoch = since + 3600
        with tempfile.TemporaryDirectory() as tmp:
            subagent_dir = os.path.join(tmp, "parent-session", "subagents")
            os.makedirs(subagent_dir, exist_ok=True)
            parent_path = _write_transcript(tmp, "parent-session.jsonl", [
                _assistant_record("msg_parent", "req_parent", epoch,
                                   input_tokens=1000, output_tokens=100,
                                   cwd=self.WORK_CWD),
            ])
            child_path = _write_transcript(subagent_dir, "child.jsonl", [
                _assistant_record("msg_child", "req_child", epoch,
                                   input_tokens=4000, output_tokens=800,
                                   cwd=self.WORK_CWD),
            ])
            result = cur.aggregate([parent_path], [child_path], since, until)

        self.assertAlmostEqual(
            result["by_repo_class"]["work"]["cost"],
            result["main_cost"] + result["subagent_cost"], places=6,
            msg="the subagent's spend must join its parent's in the work "
                "half, so delegation cannot hide cost from the PR denominator")

    def test_the_delegated_share_of_a_halfs_spend_is_recorded_separately(self):
        """Whether leaning on subagents helps is asked of the work half and the
        tooling half separately, and a day-level subagent total cannot be split
        back out per half once the two are summed."""
        day = "2026-07-20"
        since, until = cur.day_bounds(day)
        epoch = since + 3600
        with tempfile.TemporaryDirectory() as tmp:
            subagent_dir = os.path.join(tmp, "parent-session", "subagents")
            os.makedirs(subagent_dir, exist_ok=True)
            parent_path = _write_transcript(tmp, "parent-session.jsonl", [
                _assistant_record("msg_parent", "req_parent", epoch,
                                   input_tokens=1000, output_tokens=100,
                                   cwd=self.WORK_CWD),
                _assistant_record("msg_tooling", "req_tooling", epoch + 1,
                                   input_tokens=2000, output_tokens=300,
                                   cwd=self.TOOLING_CWD),
            ])
            child_path = _write_transcript(subagent_dir, "child.jsonl", [
                _assistant_record("msg_child", "req_child", epoch + 2,
                                   input_tokens=4000, output_tokens=800,
                                   cwd=self.WORK_CWD),
            ])
            result = cur.aggregate([parent_path], [child_path], since, until)

        price_in, price_out, _ = cur.SONNET_5_INTRO_PRICES
        self.assertAlmostEqual(
            result["by_repo_class"]["work"]["subagent_cost"],
            (4000 * price_in + 800 * price_out) / 1e6, places=6,
            msg="the delegated run's spend must be readable as the work "
                "half's own subagent share, not only as part of its total")
        self.assertAlmostEqual(
            result["by_repo_class"]["tooling"]["subagent_cost"], 0.0, places=6,
            msg="a half that delegated nothing must read as zero delegated "
                "spend, never inherit the other half's subagent runs")

    def test_an_advisor_turns_second_model_bills_to_the_same_half_as_the_turn_it_rode_on(self):
        """The advisor's tokens live only in usage.iterations and are priced
        at a separate site from the main turn, so that site needs its own
        classification or the advisor's spend silently defaults to work."""
        day = "2026-07-20"
        since, until = cur.day_bounds(day)
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_transcript(tmp, "session.jsonl", [
                _assistant_record(
                    "msg_advisor", "req_advisor", since + 3600,
                    input_tokens=1000, output_tokens=100,
                    advisor_iterations=[
                        _advisor_iteration(input_tokens=50000, output_tokens=800)],
                    cwd=self.TOOLING_CWD),
            ])
            result = cur.aggregate([path], [], since, until)

        self.assertAlmostEqual(
            result["by_repo_class"]["tooling"]["cost"], result["main_cost"], places=6,
            msg="the advisor model's spend must follow the turn's own "
                "directory, not default into the work half")

    def test_typed_turns_and_interruptions_count_against_the_half_they_were_sent_in(self):
        day = "2026-07-20"
        since, until = cur.day_bounds(day)
        epoch = since + 3600
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_transcript(tmp, "session.jsonl", [
                _user_record(epoch, "ship the agreement filter", cwd=self.WORK_CWD),

                # A session whose prompts never got
                # a reply is dropped whole, so the
                # typed turns need one to count.
                _assistant_record("msg_reply", "req_reply", epoch + 1,
                                   input_tokens=1000, output_tokens=100,
                                   cwd=self.WORK_CWD),
                _user_record(epoch + 2, f"{cur.INTERRUPT_SENTINEL}]",
                             cwd=self.WORK_CWD),
                _user_record(epoch + 3, "tighten the density check",
                             cwd=self.TOOLING_CWD),
            ])
            result = cur.aggregate([path], [], since, until)

        self.assertEqual(
            result["by_repo_class"]["work"]["user_messages"], 1,
            msg="the one typed turn sent from the work repo must count there")
        self.assertEqual(
            result["by_repo_class"]["work"]["interruptions"], 1,
            msg="an Escape press is attention spent on work, so it belongs "
                "in the work half's touch count")
        self.assertEqual(
            result["by_repo_class"]["tooling"]["user_messages"], 1,
            msg="the turn sent from this config must count against tooling, "
                "not inflate the numerator of touches per merged PR")

    def test_a_subagents_user_records_never_count_as_touches_in_either_half(self):
        """A subagent's "user" records are its spawn prompt and tool results,
        not the human typing — counting them would inflate the very
        denominator touches-per-merged-PR divides by."""
        day = "2026-07-20"
        since, until = cur.day_bounds(day)
        epoch = since + 3600
        with tempfile.TemporaryDirectory() as tmp:
            subagent_dir = os.path.join(tmp, "parent-session", "subagents")
            os.makedirs(subagent_dir, exist_ok=True)
            parent_path = _write_transcript(tmp, "parent-session.jsonl", [
                _user_record(epoch, "audit the skills", cwd=self.WORK_CWD),
                _assistant_record("msg_parent", "req_parent", epoch + 1,
                                   input_tokens=1000, output_tokens=100,
                                   cwd=self.WORK_CWD),
            ])
            child_path = _write_transcript(subagent_dir, "child.jsonl", [
                _user_record(epoch + 2, "You are auditing the skills directory.",
                             cwd=self.WORK_CWD),
                _assistant_record("msg_child", "req_child", epoch + 3,
                                   input_tokens=4000, output_tokens=800,
                                   cwd=self.WORK_CWD),
            ])
            result = cur.aggregate([parent_path], [child_path], since, until)

        self.assertEqual(
            result["by_repo_class"]["work"]["user_messages"], 1,
            msg="only the human's own turn counts; the subagent's spawn "
                "prompt must not become a second touch")

    def test_the_snapshot_reports_both_halves_even_when_one_had_no_spend(self):
        """A reader has to tell a day with no tooling spend apart from a day
        whose split was never measured at all."""
        day = "2026-07-20"
        since, until = cur.day_bounds(day)
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_transcript(tmp, "session.jsonl", [
                _assistant_record("msg_work", "req_work", since + 3600,
                                   input_tokens=1000, output_tokens=500,
                                   cwd=self.WORK_CWD),
            ])
            result = cur.aggregate([path], [], since, until)
        payload = cur.build_payload(result, 5, day=day)

        self.assertEqual(
            payload["by_repo_class"]["tooling"],
            {"cost": 0.0, "subagent_cost": 0.0,
             "user_messages": 0, "interruptions": 0},
            msg="the untouched half must still be emitted at zero rather "
                "than omitted, so its absence never reads as unmeasured")


class TestSkillsPerRepoClass(unittest.TestCase):
    """A skill's dollars and loads, read separately for work and tooling.

    Averaged over every session alike, a skill that only ever fires while
    tuning this config reads as a cost of shipping. The split is per session
    rather than per record because a skill row counts sessions, and no
    session-level counter could divide one row across two halves.
    """

    TOOLING_CWD = "/Users/brunoagostini/unix-utils/configs/ai-docs/claude"
    WORK_CWD = "/Users/brunoagostini/workspace/code/isaac/contract-validation"

    def test_a_skills_spend_and_loads_land_in_the_half_its_session_ran_in(self):
        day = "2026-07-20"
        since, until = cur.day_bounds(day)
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_transcript(tmp, "session.jsonl", [
                _assistant_record("msg_a", "req_a", since + 3600,
                                   input_tokens=1000, output_tokens=500,
                                   cwd=self.TOOLING_CWD,
                                   skills=["doc-standards", "doc-standards"]),
            ])
            result = cur.aggregate([path], [], since, until)

        half = result["by_skill"]["doc-standards"]["by_repo_class"]["tooling"]
        self.assertAlmostEqual(
            half["cost"], result["main_cost"], places=6,
            msg="a skill loaded only while editing this config must charge "
                "its spend to the tooling half, never to shipped work")
        self.assertEqual(
            (half["invocations"], half["sessions"]), (2, 1),
            msg="both loads and the one session they happened in belong to "
                "that same half, so loads per session divides within a half")

    def test_a_half_a_skill_never_ran_in_reports_zero_rather_than_nothing(self):
        """A reader has to tell a skill that never fired in a half apart from
        one whose split was never measured."""
        day = "2026-07-20"
        since, until = cur.day_bounds(day)
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_transcript(tmp, "session.jsonl", [
                _assistant_record("msg_a", "req_a", since + 3600,
                                   input_tokens=1000, output_tokens=500,
                                   cwd=self.TOOLING_CWD, skills=["brainstorm"]),
            ])
            result = cur.aggregate([path], [], since, until)
        payload = cur.build_payload(result, 5, day=day)

        self.assertEqual(
            payload["by_skill"]["brainstorm"]["by_repo_class"]["work"],
            {"cost": 0.0, "invocations": 0, "sessions": 0},
            msg="the untouched half must still be emitted at zero, so its "
                "absence never reads as unmeasured")

    def test_a_session_split_across_both_halves_charges_its_skills_to_the_costlier_one(self):
        """Deliberate approximation: no session-level counter can divide a
        skill row's sessions, so the whole row follows where the money was."""
        day = "2026-07-20"
        since, until = cur.day_bounds(day)
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_transcript(tmp, "session.jsonl", [
                _assistant_record("msg_tooling", "req_tooling", since + 3600,
                                   input_tokens=1000, output_tokens=100,
                                   cwd=self.TOOLING_CWD, skills=["implement"]),
                _assistant_record("msg_work", "req_work", since + 7200,
                                   input_tokens=9000, output_tokens=2000,
                                   cwd=self.WORK_CWD),
            ])
            result = cur.aggregate([path], [], since, until)

        halves = result["by_skill"]["implement"]["by_repo_class"]
        self.assertEqual(
            halves["work"]["sessions"], 1,
            msg="the half holding most of the session's spend owns the whole "
                "skill row, so the two halves keep summing back to it")
        self.assertEqual(
            halves["tooling"]["sessions"], 0,
            msg="charging the session to both halves would double-count the "
                "one session its loads-per-session figure divides by")

    def test_a_lone_skills_attributed_spend_lands_in_its_sessions_half(self):
        """by_skill rows overlap across skills, so the attributable dollars a
        per-skill average should divide come from the marginal partition."""
        day = "2026-07-20"
        since, until = cur.day_bounds(day)
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_transcript(tmp, "session.jsonl", [
                _assistant_record("msg_a", "req_a", since + 3600,
                                   input_tokens=1000, output_tokens=500,
                                   cwd=self.WORK_CWD, skills=["implement"]),
            ])
            result = cur.aggregate([path], [], since, until)

        halves = result["by_skill_marginal"]["implement"]["by_repo_class"]
        self.assertAlmostEqual(
            halves["work"]["dedicated_cost"], result["main_cost"], places=6,
            msg="a session that invoked one skill attributes its whole cost "
                "to that skill, inside the half the session ran in")
        self.assertEqual(
            halves["tooling"]["dedicated_sessions"], 0,
            msg="no dedicated session may leak into the half it never ran in")

    def test_a_multi_skill_sessions_estimated_split_stays_inside_one_half(self):
        """The mixed branch divides a session across the skills it invoked;
        every slice still belongs to the one half the session ran in."""
        day = "2026-07-20"
        since, until = cur.day_bounds(day)
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_transcript(tmp, "session.jsonl", [
                _assistant_record("msg_a", "req_a", since + 3600,
                                   input_tokens=1000, output_tokens=500,
                                   cwd=self.TOOLING_CWD, skills=["brainstorm"]),
                _assistant_record("msg_b", "req_b", since + 7200,
                                   input_tokens=2000, output_tokens=800,
                                   cwd=self.TOOLING_CWD, skills=["implement"]),
            ])
            result = cur.aggregate([path], [], since, until)

        attributed = sum(
            result["by_skill_marginal"][skill]["by_repo_class"]["tooling"]
                  ["mixed_cost_estimate"]
            for skill in ("brainstorm", "implement"))
        self.assertAlmostEqual(
            attributed, result["by_skill_marginal"]["brainstorm"]["mixed_cost_estimate"]
            + result["by_skill_marginal"]["implement"]["mixed_cost_estimate"], places=6,
            msg="the halves must account for every attributed dollar the "
                "rows do, or a per-half average silently under-reads")
        self.assertEqual(
            result["by_skill_marginal"]["brainstorm"]["by_repo_class"]
                  ["tooling"]["mixed_sessions"], 1,
            msg="the shared session counts once under each skill it invoked, "
                "in the half it ran in")


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
        payload = self._snapshot_against_floor(day="2026-06-01",
                                               retention_floor="2026-07-01")
        self.assertEqual(
            payload["coverage"], "unretained",
            msg="a day older than the retention floor must be marked "
                "unretained, not complete")

    def test_the_retention_floor_day_itself_writes_partial_coverage(self):
        """The prune cuts through the floor day at an hour, not at
        midnight, so its earlier sessions are gone while its later ones
        survive — that day must read "partial", never "complete"."""
        payload = self._snapshot_against_floor(day="2026-07-01",
                                               retention_floor="2026-07-01")
        self.assertEqual(
            payload["coverage"], "partial",
            msg="the retention-floor day is cut through mid-day by the "
                "prune, so calling it complete overstates what its "
                "transcripts can still account for")

    def test_a_day_after_the_retention_floor_writes_complete_coverage(self):
        """A day strictly newer than the floor still has all of its
        transcripts on disk and must record coverage: "complete"."""
        payload = self._snapshot_against_floor(day="2026-07-02",
                                               retention_floor="2026-07-01")
        self.assertEqual(
            payload["coverage"], "complete",
            msg="a day the prune has not reached must be marked complete "
                "so it stays eligible for deltas and reconciliation")

    def test_a_partially_retained_day_reports_no_ccusage_verdict(self):
        """A day the prune has reached is measured against a shrunken
        corpus, so its ccusage cross-check would compare two different
        corpora — it must report the coverage word instead of ok/drift."""
        payload = self._snapshot_against_floor(day="2026-07-01",
                                               retention_floor="2026-07-01")
        self.assertEqual(
            payload["reconciliation"]["status"], "partial",
            msg="reconciling a pruned day against ccusage reports deleted "
                "spend as a counting disagreement, so no ok/drift verdict "
                "may be issued for it")

    def test_rebuilding_a_pruned_day_keeps_the_committed_snapshot(self):
        """--rebuild is mandatory after an aggregation fix, but a day
        whose transcripts are gone can only re-measure LOWER — the older,
        richer measurement must survive the rebuild."""
        day = "2026-06-01"
        cur._ccusage_days.clear()
        with tempfile.TemporaryDirectory() as tmp:
            transcripts_root = os.path.join(tmp, "projects")
            os.makedirs(transcripts_root)
            snapshots_dir = os.path.join(tmp, "snapshots")
            os.makedirs(snapshots_dir)
            committed_path = os.path.join(snapshots_dir, f"{day}.json")
            with open(committed_path, "w") as fh:
                json.dump({"day": day, "total": 5.62, "coverage": "complete"}, fh)

            with mock.patch.object(cur, "TRANSCRIPTS_ROOT", transcripts_root), \
                 mock.patch.object(cur, "SNAPSHOTS_DIR", snapshots_dir), \
                 mock.patch.object(cur, "oldest_retained_day",
                                   return_value="2026-07-01"), \
                 mock.patch.object(cur.shutil, "which", return_value=None):
                _, total, status = cur.snapshot_day(day, top_n=8)

            with open(committed_path) as fh:
                after = json.load(fh)
        self.assertEqual(
            after["total"], 5.62,
            msg="rebuilding a day past the retention floor must not "
                "replace a real measurement with a $0 reading of the "
                "transcripts' absence")
        self.assertEqual(
            (total, status), (5.62, "preserved"),
            msg="the run must report the kept figure and say the day was "
                "preserved, so the reader knows it rests on an older run")

    def test_rebuilding_a_retained_day_overwrites_a_higher_committed_total(self):
        """A fully retained day measuring lower is an aggregation fix
        landing, not history being lost — the 2026-07-27 dedup fix cut
        2026-07-20 from $441.44 to $130.16 and had to be allowed to."""
        day = "2026-07-20"
        cur._ccusage_days.clear()
        with tempfile.TemporaryDirectory() as tmp:
            transcripts_root = os.path.join(tmp, "projects")
            os.makedirs(transcripts_root)
            snapshots_dir = os.path.join(tmp, "snapshots")
            os.makedirs(snapshots_dir)
            committed_path = os.path.join(snapshots_dir, f"{day}.json")
            with open(committed_path, "w") as fh:
                json.dump({"day": day, "total": 441.44, "coverage": "complete"}, fh)

            with mock.patch.object(cur, "TRANSCRIPTS_ROOT", transcripts_root), \
                 mock.patch.object(cur, "SNAPSHOTS_DIR", snapshots_dir), \
                 mock.patch.object(cur, "oldest_retained_day",
                                   return_value="2026-07-01"), \
                 mock.patch.object(cur.shutil, "which", return_value=None):
                cur.snapshot_day(day, top_n=8)

            with open(committed_path) as fh:
                after = json.load(fh)
        self.assertLess(
            after["total"], 441.44,
            msg="a correction on a day whose transcripts are all still on "
                "disk must land, or no aggregation fix could ever reach "
                "the committed series")

    def _snapshot_against_floor(self, *, day, retention_floor):
        """Snapshot `day` over an empty transcripts root, with the
        retention floor pinned, and return the payload written."""
        cur._ccusage_days.clear()
        with tempfile.TemporaryDirectory() as tmp:
            transcripts_root = os.path.join(tmp, "projects")
            os.makedirs(transcripts_root)
            snapshots_dir = os.path.join(tmp, "snapshots")
            with mock.patch.object(cur, "TRANSCRIPTS_ROOT", transcripts_root), \
                 mock.patch.object(cur, "SNAPSHOTS_DIR", snapshots_dir), \
                 mock.patch.object(cur, "oldest_retained_day",
                                   return_value=retention_floor), \
                 mock.patch.object(cur.shutil, "which", return_value=None):
                path, _, _ = cur.snapshot_day(day, top_n=8)
            with open(path) as fh:
                return json.load(fh)

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


class TestSessionMode(unittest.TestCase):
    """--session SID --json: the existing aggregate()/build_payload() pipeline
    run over one session id's own transcripts (its main file plus any
    subagent runs under it), found by searching every ~/.claude/projects/*/
    directory rather than only the caller's cwd project — a --session audit
    commonly targets a past run made from elsewhere. Never touches
    snapshot_day()/run_backfill(): a mid-session read is inherently partial
    and must not be written under usage-history/snapshots/.
    """

    def _run_session_json(self, transcripts_root, sid, *, top=8):
        """Run `--session sid --json` against a mocked TRANSCRIPTS_ROOT and
        return the parsed stdout payload."""
        argv = ["claude-usage-report.py", "--session", sid, "--json", "--top", str(top)]
        buf = io.StringIO()
        with mock.patch.object(cur, "TRANSCRIPTS_ROOT", transcripts_root), \
             mock.patch.object(sys, "argv", argv), \
             contextlib.redirect_stdout(buf):
            cur.main()
        return json.loads(buf.getvalue())

    def test_emits_a_json_payload_for_a_session_id_found_in_the_local_projects_transcript_directory(self):
        """The common case: the session's main transcript lives directly
        under one of the project directories."""
        day = "2026-07-20"
        since, _ = cur.day_bounds(day)
        epoch = since + 3600
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = os.path.join(tmp, "-Users-brunoagostini-work-project")
            os.makedirs(project_dir)
            _write_transcript(project_dir, "sess-abc123.jsonl", [
                _assistant_record("msg_a", "req_a", epoch,
                                   input_tokens=1_000_000, output_tokens=500_000),
            ])
            payload = self._run_session_json(tmp, "sess-abc123")

        price_in, price_out, _ = cur.SONNET_5_INTRO_PRICES
        expected_total = round((1_000_000 * price_in + 500_000 * price_out) / 1e6, 2)
        self.assertEqual(
            payload["total"], expected_total,
            msg="the --session payload must total the one priced response "
                "found under the session's own project directory")

    def test_includes_the_main_vs_subagent_cost_split_for_a_session_that_has_subagent_runs(self):
        """A session that delegated to a subagent must report the two
        halves separately, not just their sum — main_cost and
        subagent_cost using distinct token counts so a swapped key would
        be caught rather than masked by equal totals."""
        day = "2026-07-20"
        since, _ = cur.day_bounds(day)
        epoch = since + 3600
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = os.path.join(tmp, "-Users-brunoagostini-work-project")
            subagent_dir = os.path.join(project_dir, "sess-with-sub", "subagents")
            os.makedirs(subagent_dir)
            _write_transcript(project_dir, "sess-with-sub.jsonl", [
                _assistant_record("msg_main", "req_main", epoch,
                                   input_tokens=1_000_000, output_tokens=500_000),
            ])
            _write_transcript(subagent_dir, "child.jsonl", [
                _assistant_record("msg_child", "req_child", epoch,
                                   input_tokens=500_000, output_tokens=1_000_000),
            ])
            payload = self._run_session_json(tmp, "sess-with-sub")

        price_in, price_out, _ = cur.SONNET_5_INTRO_PRICES
        expected_main = round((1_000_000 * price_in + 500_000 * price_out) / 1e6, 2)
        expected_sub = round((500_000 * price_in + 1_000_000 * price_out) / 1e6, 2)
        self.assertEqual(
            payload["main_cost"], expected_main,
            msg="main_cost must reflect only the session's own main-transcript spend")
        self.assertEqual(
            payload["subagent_cost"], expected_sub,
            msg="subagent_cost must reflect only its subagent runs' spend")

    def test_reports_zero_subagent_cost_never_fails_when_the_session_has_no_subagents_directory(self):
        """A session that never delegated has no subagents/ directory at
        all on disk — that must read as zero cost, not raise."""
        day = "2026-07-20"
        since, _ = cur.day_bounds(day)
        epoch = since + 3600
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = os.path.join(tmp, "-Users-brunoagostini-work-project")
            os.makedirs(project_dir)
            _write_transcript(project_dir, "sess-solo.jsonl", [
                _assistant_record("msg_solo", "req_solo", epoch,
                                   input_tokens=1_000_000, output_tokens=500_000),
            ])
            payload = self._run_session_json(tmp, "sess-solo")

        self.assertEqual(
            payload["subagent_cost"], 0.0,
            msg="a session with no subagents/ directory on disk must report "
                "zero subagent cost, not raise")
        self.assertEqual(payload["total"], payload["main_cost"])

    def test_omits_the_reconciliation_field_in_session_mode_exactly_as_the_existing_ad_hoc_window_omits_it(self):
        """--session never asks ccusage for a cross-check: reconciliation is
        a snapshot-only concept (one closed day to cross-check against),
        and a session may span partial or multiple days."""
        day = "2026-07-20"
        since, _ = cur.day_bounds(day)
        epoch = since + 3600
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = os.path.join(tmp, "-Users-brunoagostini-work-project")
            os.makedirs(project_dir)
            _write_transcript(project_dir, "sess-recon.jsonl", [
                _assistant_record("msg_recon", "req_recon", epoch,
                                   input_tokens=1_000_000, output_tokens=500_000),
            ])
            payload = self._run_session_json(tmp, "sess-recon")

        self.assertNotIn(
            "reconciliation", payload,
            msg="--session mode must never carry a reconciliation field, "
                "the same as the existing ad-hoc rolling window")

    def test_still_returns_correct_totals_when_the_sessions_transcript_spans_a_single_record(self):
        """A one-line transcript (no separate human-turn record at all) is
        the minimal real-world shape and must not trip an off-by-one in the
        per-file scan."""
        day = "2026-07-20"
        since, _ = cur.day_bounds(day)
        epoch = since + 3600
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = os.path.join(tmp, "-Users-brunoagostini-work-project")
            os.makedirs(project_dir)
            _write_transcript(project_dir, "sess-single.jsonl", [
                _assistant_record("msg_single", "req_single", epoch,
                                   input_tokens=200_000, output_tokens=100_000),
            ])
            payload = self._run_session_json(tmp, "sess-single")

        price_in, price_out, _ = cur.SONNET_5_INTRO_PRICES
        expected_total = round((200_000 * price_in + 100_000 * price_out) / 1e6, 2)
        self.assertEqual(payload["total"], expected_total)
        self.assertEqual(payload["api_calls"]["main"], 1)

    def test_dedupes_per_content_block_records_via_billing_id_before_summing_cost(self):
        """A response written as 2 content-block records sharing one
        message.id/requestId must bill once, the same billing_id() dedup
        the ad-hoc window and snapshots already rely on."""
        day = "2026-07-20"
        since, _ = cur.day_bounds(day)
        epoch = since + 3600
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = os.path.join(tmp, "-Users-brunoagostini-work-project")
            os.makedirs(project_dir)
            _write_transcript(project_dir, "sess-dedup.jsonl", [
                _assistant_record("msg_dedup", "req_dedup", epoch,
                                   input_tokens=1_000_000, output_tokens=500_000)
                for _ in range(2)
            ])
            payload = self._run_session_json(tmp, "sess-dedup")

        price_in, price_out, _ = cur.SONNET_5_INTRO_PRICES
        expected_total = round((1_000_000 * price_in + 500_000 * price_out) / 1e6, 2)
        self.assertEqual(
            payload["total"], expected_total,
            msg="two content-block records of the same response must bill "
                "once, not twice")
        self.assertEqual(payload["api_calls"]["main"], 1)

    def test_reuses_local_day_and_parse_ts_for_any_date_bucketed_figures_instead_of_reimplementing_them(self):
        """A response stamped just after UTC midnight, still before local
        midnight in America/Sao_Paulo (UTC-3), must bucket under its LOCAL
        day in by_day — proof --session calls the shared local_day()/
        parse_ts() rather than re-deriving day bucketing from the raw
        UTC timestamp."""
        original_tz = os.environ.get("TZ")
        os.environ["TZ"] = "America/Sao_Paulo"
        time.tzset()
        try:
            epoch = cur.parse_ts("2026-07-21T01:00:00Z")
            with tempfile.TemporaryDirectory() as tmp:
                project_dir = os.path.join(tmp, "-Users-brunoagostini-work-project")
                os.makedirs(project_dir)
                _write_transcript(project_dir, "sess-midnight.jsonl", [
                    _assistant_record("msg_midnight", "req_midnight", epoch,
                                       input_tokens=100_000, output_tokens=50_000),
                ])
                payload = self._run_session_json(tmp, "sess-midnight")
        finally:
            if original_tz is None:
                os.environ.pop("TZ", None)
            else:
                os.environ["TZ"] = original_tz
            time.tzset()

        self.assertIn(
            "2026-07-20", payload["by_day"],
            msg="a response stamped 2026-07-21T01:00:00Z must bucket under "
                "its local day 2026-07-20 in America/Sao_Paulo")
        self.assertNotIn(
            "2026-07-21", payload["by_day"],
            msg="the raw UTC calendar day must never appear as a by_day key")

    def test_exits_non_zero_naming_every_project_directory_searched_when_the_given_session_id_matches_no_transcript(self):
        """An unknown session id must fail loudly and name every directory
        that was searched, so the reader can tell a typo'd sid from a
        transcript that was pruned or never existed."""
        with tempfile.TemporaryDirectory() as tmp:
            dir_a = os.path.join(tmp, "-Users-x-project-a")
            dir_b = os.path.join(tmp, "-Users-x-project-b")
            os.makedirs(dir_a)
            os.makedirs(dir_b)
            _write_transcript(dir_a, "other-session.jsonl", [
                _assistant_record("msg_other", "req_other", time.time(),
                                   input_tokens=1000, output_tokens=500),
            ])
            argv = ["claude-usage-report.py", "--session", "nonexistent-sid", "--json"]
            stderr_buf = io.StringIO()
            with mock.patch.object(cur, "TRANSCRIPTS_ROOT", tmp), \
                 mock.patch.object(sys, "argv", argv), \
                 contextlib.redirect_stderr(stderr_buf):
                with self.assertRaises(SystemExit) as ctx:
                    cur.main()
            stderr_text = stderr_buf.getvalue()

        self.assertNotEqual(
            ctx.exception.code, 0,
            msg="a session id matching no transcript must exit non-zero")
        self.assertIn(dir_a, stderr_text,
                       msg="every searched project directory must be named, "
                           "including ones that held unrelated sessions")
        self.assertIn(dir_b, stderr_text,
                       msg="every searched project directory must be named, "
                           "including one that held nothing at all")

    def test_never_writes_to_usage_history_snapshots_when_run_in_session_mode(self):
        """--session must never create the snapshots directory, and must
        never reach snapshot_day()/run_backfill() at all — a mid-session
        read is inherently partial and must not be mistaken for the
        immutable closed-day record those two produce."""
        day = "2026-07-20"
        since, _ = cur.day_bounds(day)
        epoch = since + 3600
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = os.path.join(tmp, "-Users-brunoagostini-work-project")
            os.makedirs(project_dir)
            _write_transcript(project_dir, "sess-nosnap.jsonl", [
                _assistant_record("msg_nosnap", "req_nosnap", epoch,
                                   input_tokens=1_000_000, output_tokens=500_000),
            ])
            snapshots_dir = os.path.join(tmp, "snapshots")
            argv = ["claude-usage-report.py", "--session", "sess-nosnap", "--json"]
            with mock.patch.object(cur, "TRANSCRIPTS_ROOT", tmp), \
                 mock.patch.object(cur, "SNAPSHOTS_DIR", snapshots_dir), \
                 mock.patch.object(cur, "snapshot_day",
                                   side_effect=AssertionError(
                                       "--session mode must never call snapshot_day()")), \
                 mock.patch.object(cur, "run_backfill",
                                   side_effect=AssertionError(
                                       "--session mode must never call run_backfill()")), \
                 mock.patch.object(sys, "argv", argv), \
                 contextlib.redirect_stdout(io.StringIO()):
                cur.main()

        self.assertFalse(
            os.path.exists(snapshots_dir),
            msg="--session mode must never create the usage-history/snapshots/ directory")

    def test_leaves_the_backfill_and_day_code_paths_producing_identical_output_to_before_the_session_flag_was_added(self):
        """Regression guard: --day's snapshot pipeline (aggregate() ->
        build_payload() -> snapshot_day()) must still produce the exact
        pre-change dollar figure and coverage/reconciliation verdict —
        proven against a hand-computed expected value, not f(X) === f(X),
        so a real drift in the shared pipeline would be caught here."""
        day = "2026-07-20"
        since, _ = cur.day_bounds(day)
        epoch = since + 3600
        cur._ccusage_days.clear()
        with tempfile.TemporaryDirectory() as tmp:
            transcripts_root = os.path.join(tmp, "projects")
            os.makedirs(transcripts_root)
            snapshots_dir = os.path.join(tmp, "snapshots")
            _write_transcript(transcripts_root, "session.jsonl", [
                _assistant_record("msg_regress", "req_regress", epoch,
                                   input_tokens=1_000_000, output_tokens=500_000),
            ])
            with mock.patch.object(cur, "TRANSCRIPTS_ROOT", transcripts_root), \
                 mock.patch.object(cur, "SNAPSHOTS_DIR", snapshots_dir), \
                 mock.patch.object(cur, "oldest_retained_day", return_value="2026-07-01"), \
                 mock.patch.object(cur.shutil, "which", return_value=None):
                path, total, status = cur.snapshot_day(day, top_n=8)
            with open(path) as fh:
                payload = json.load(fh)

        price_in, price_out, _ = cur.SONNET_5_INTRO_PRICES
        expected_total = round((1_000_000 * price_in + 500_000 * price_out) / 1e6, 2)
        self.assertEqual(
            (total, status), (expected_total, "unavailable"),
            msg="--day's snapshot_day() must still return the hand-computed "
                "total and the ccusage-absent status, unchanged by adding --session")
        self.assertEqual(payload["total"], expected_total)
        self.assertEqual(payload["coverage"], "complete")
        self.assertEqual(payload["reconciliation"]["status"], "unavailable")


class TestSpawnAttribution(unittest.TestCase):
    """Pure unit tests of collect_agent_spawns()/match_spawn() -- the
    prompt-matching link between a Task/Agent dispatch record in the main
    transcript and the subagent transcript it spawned. Claude Code records
    no other link (agentId only appears in tool_result prose, unrelated to
    the subagent transcript's own filename), so prompt-prefix matching is
    the only mechanism available, and every case here is about that
    mechanism degrading gracefully instead of silently mis-crediting.
    """

    def _spawn_record(self, epoch, subagent_type, prompt):
        """One assistant record dispatching a Task/Agent subagent -- the
        shape collect_agent_spawns() scans for."""
        return {
            "type": "assistant",
            "timestamp": _iso(epoch),
            "message": {
                "role": "assistant",
                "content": [{
                    "type": "tool_use",
                    "name": "Task",
                    "input": {"subagent_type": subagent_type, "prompt": prompt},
                }],
            },
        }

    def test_collect_agent_spawns_stores_the_full_dispatch_prompt_not_truncated_to_150_characters(self):
        long_prompt = "Investigate the flaky checkout test " + "and confirm the root cause " * 6
        self.assertGreater(len(long_prompt), 150)
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_transcript(tmp, "main.jsonl", [
                self._spawn_record(1_700_000_000, "tdd-coder", long_prompt),
            ])
            spawns = cur.collect_agent_spawns([path])

        stored_prompt = spawns[path][0][1]
        self.assertEqual(
            stored_prompt, long_prompt,
            msg="collect_agent_spawns must keep the dispatched prompt in full so "
                "match_spawn can discriminate collisions past the old 150-char cut")

    def test_match_spawn_treats_a_short_transcript_prompt_as_a_candidate_when_it_prefixes_a_longer_spawn_prompt(self):
        spawn_prompt = "Refactor the pricing module " * 6  # > 150 chars, one dispatch
        transcript_prompt = spawn_prompt[:40]  # shorter than the 100-char floor
        session_spawns = [("refactor", spawn_prompt, 3)]

        spawn_type, record_index = cur.match_spawn(transcript_prompt, session_spawns)

        self.assertEqual(
            (spawn_type, record_index), ("refactor", 3),
            msg="a transcript's captured first_prompt shorter than 100 chars must "
                "still match a spawn it fully prefixes -- candidacy is symmetric, "
                "not just prompt.startswith(spawn_prompt)")

    def test_match_spawn_picks_the_candidate_with_the_longest_common_prefix_when_two_spawns_share_their_first_100_characters(self):
        shared_opening = (
            "You are dispatched to review the checkout service PR for "
            "correctness bugs and reuse or simplification opportunities, "
        )
        self.assertGreaterEqual(len(shared_opening), 100)
        refactor_prompt = shared_opening + "then apply the structure-only cleanup yourself."
        tdd_prompt = shared_opening + "then write the RED test before any fix lands."
        session_spawns = [
            ("refactor", refactor_prompt, 10),
            ("tdd-coder", tdd_prompt, 11),
        ]

        spawn_type, record_index = cur.match_spawn(tdd_prompt, session_spawns)

        self.assertEqual(
            (spawn_type, record_index), ("tdd-coder", 11),
            msg="both spawns share the first 100+ chars, but only tdd_prompt's own "
                "text is an exact match past that point -- the longest common "
                "prefix must break the tie the old 100-char key collided on")

    def test_match_spawn_falls_through_to_the_remaining_weaker_candidate_once_its_exact_match_is_consumed(self):
        shared_opening = (
            "You are dispatched to review the checkout service PR for "
            "correctness bugs and reuse or simplification opportunities, "
        )
        refactor_prompt = shared_opening + "then apply the structure-only cleanup yourself."
        tdd_prompt = shared_opening + "then write the RED test before any fix lands."
        session_spawns = [
            ("refactor", refactor_prompt, 10),
            ("tdd-coder", tdd_prompt, 11),
        ]

        first_match = cur.match_spawn(refactor_prompt, session_spawns)
        second_match = cur.match_spawn(refactor_prompt, session_spawns)

        self.assertEqual(
            first_match, ("refactor", 10),
            msg="the exact match (idx 0) must win over the shared-opening-only "
                "candidate (idx 1) on the first call")
        self.assertEqual(
            second_match, ("tdd-coder", 11),
            msg="idx 0 is already consumed, so a second transcript reusing that "
                "exact prompt must fall through to the remaining shared-opening "
                "candidate rather than re-matching the consumed one or going "
                "UNMATCHED -- consumption must never cause a false UNMATCHED")

    def test_match_spawn_resolves_byte_identical_candidates_to_the_earliest_unconsumed_one(self):
        retried_prompt = "Re-run the export job for the July closing batch, unchanged."
        session_spawns = [
            ("tdd-coder", retried_prompt, 20),
            ("tdd-coder", retried_prompt, 27),
        ]

        first_match = cur.match_spawn(retried_prompt, session_spawns)
        second_match = cur.match_spawn(retried_prompt, session_spawns)

        self.assertEqual(
            first_match, ("tdd-coder", 20),
            msg="two byte-identical retries: the first transcript must claim the "
                "earliest (lowest record_index) unconsumed spawn")
        self.assertEqual(
            second_match, ("tdd-coder", 27),
            msg="once the earliest spawn is consumed, the second identical "
                "transcript must fall through to the remaining one, not UNMATCHED")


if __name__ == "__main__":
    unittest.main(verbosity=2)
