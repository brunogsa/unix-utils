"""Blackbox CLI tests for learn-ledger.py.

Each test pipes a JSON array of feedback items into the
`unseen` or `add` subcommand and reads stdout, stderr, the
exit code and the ledger file.

Every ledger is a fixture under pytest's tmp_path, reached
through LEARN_LEDGER, so the real
~/.claude/state/learn-ledger.jsonl is never touched.

Usage:
  ./run-tests.py <this file>
"""

import importlib.util
import io
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "learn-ledger.py"

ITEM_A = {"origin": "lateral-marker", "verbatim": "never mock the database in integration tests"}
ITEM_B = {"origin": "lateral-marker", "verbatim": "prefer fakes over bare mocks"}


def _run_ledger(ledger, stdin_text, *args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        input=stdin_text,
        capture_output=True,
        text=True,

        # The inherited environment carries coverage's
        # subprocess hook, so only LEARN_LEDGER is added.
        env={**os.environ, "LEARN_LEDGER": str(ledger)},
    )


def _items(*items):
    return json.dumps(list(items))


def _verbatims(result):
    return [item["verbatim"] for item in json.loads(result.stdout)]


def _ledger_lines(ledger):
    if not ledger.exists():
        return []
    return ledger.read_text(encoding="utf-8").splitlines()


class TestHappyPath:
    def test_should_exit_0_when_unseen_runs_after_an_add(self, tmp_path):
        ledger = tmp_path / "ledger.jsonl"
        _run_ledger(ledger, _items(ITEM_A), "add", "--verdict", "applied")

        result = _run_ledger(ledger, _items(ITEM_A, ITEM_B), "unseen")

        assert result.returncode == 0

    def test_should_drop_an_item_that_was_added_with_a_verdict_and_keep_the_other(self, tmp_path):
        ledger = tmp_path / "ledger.jsonl"
        _run_ledger(ledger, _items(ITEM_A), "add", "--verdict", "applied")

        result = _run_ledger(ledger, _items(ITEM_A, ITEM_B), "unseen")

        assert _verbatims(result) == ["prefer fakes over bare mocks"]

    def test_should_report_one_dropped_item_on_stderr_when_one_item_was_already_handled(self, tmp_path):
        ledger = tmp_path / "ledger.jsonl"
        _run_ledger(ledger, _items(ITEM_A), "add", "--verdict", "applied")

        result = _run_ledger(ledger, _items(ITEM_A, ITEM_B), "unseen")

        assert result.stderr.strip() == "learn-ledger: dropped 1 already-handled item(s)"

    def test_should_write_a_record_with_exactly_key_origin_verdict_and_ts_when_an_item_is_added(self, tmp_path):
        ledger = tmp_path / "ledger.jsonl"

        _run_ledger(ledger, _items(ITEM_A), "add", "--verdict", "rejected")

        record = json.loads(_ledger_lines(ledger)[0])
        assert sorted(record) == ["key", "origin", "ts", "verdict"]

    def test_should_write_a_64_hex_character_key_when_an_item_is_added(self, tmp_path):
        ledger = tmp_path / "ledger.jsonl"

        _run_ledger(ledger, _items(ITEM_A), "add", "--verdict", "rejected")

        record = json.loads(_ledger_lines(ledger)[0])
        assert re.fullmatch(r"[0-9a-f]{64}", record["key"])

    def test_should_record_the_item_origin_and_the_given_verdict_when_an_item_is_added(self, tmp_path):
        ledger = tmp_path / "ledger.jsonl"

        _run_ledger(ledger, _items(ITEM_A), "add", "--verdict", "rejected")

        record = json.loads(_ledger_lines(ledger)[0])
        assert (record["origin"], record["verdict"]) == ("lateral-marker", "rejected")

    def test_should_stamp_the_record_with_a_utc_timestamp_when_an_item_is_added(self, tmp_path, monkeypatch):
        ledger = tmp_path / "ledger.jsonl"
        spec = importlib.util.spec_from_file_location("learn_ledger", SCRIPT)
        if spec is None or spec.loader is None:
            raise ImportError(f"cannot load {SCRIPT}")
        script = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(script)

        class FrozenDatetime(datetime):
            @classmethod
            def now(cls, tz=None):
                return datetime(2026, 3, 14, 9, 26, 53, tzinfo=tz)

        monkeypatch.setattr(script, "datetime", FrozenDatetime)
        monkeypatch.setenv("LEARN_LEDGER", str(ledger))
        monkeypatch.setattr(sys, "stdin", io.StringIO(_items(ITEM_A)))
        monkeypatch.setattr(sys, "argv", ["learn-ledger.py", "add", "--verdict", "rejected"])

        script.main()

        record = json.loads(_ledger_lines(ledger)[0])
        assert record["ts"] == "2026-03-14T09:26:53Z"

    def test_should_append_only_the_new_item_when_a_second_add_repeats_a_handled_one(self, tmp_path):
        ledger = tmp_path / "ledger.jsonl"
        _run_ledger(ledger, _items(ITEM_A), "add", "--verdict", "applied")

        _run_ledger(ledger, _items(ITEM_A, ITEM_B), "add", "--verdict", "dropped")

        assert len(_ledger_lines(ledger)) == 2

    def test_should_append_nothing_when_an_add_repeats_only_handled_items(self, tmp_path):
        ledger = tmp_path / "ledger.jsonl"
        _run_ledger(ledger, _items(ITEM_A), "add", "--verdict", "applied")
        _run_ledger(ledger, _items(ITEM_A, ITEM_B), "add", "--verdict", "dropped")

        _run_ledger(ledger, _items(ITEM_A, ITEM_B), "add", "--verdict", "dropped")

        assert len(_ledger_lines(ledger)) == 2

    def test_should_pass_extra_item_fields_through_unchanged_when_unseen_returns_them(self, tmp_path):
        ledger = tmp_path / "ledger.jsonl"
        rich = {"origin": "lateral-marker", "verbatim": "keep it simple", "session": "abc-123", "line": 17}

        result = _run_ledger(ledger, _items(rich), "unseen")

        assert json.loads(result.stdout) == [rich]

    def test_should_keep_input_order_among_the_unseen_items_when_one_item_was_handled(self, tmp_path):
        ledger = tmp_path / "ledger.jsonl"
        third = {"origin": "o", "verbatim": "third"}
        first = {"origin": "o", "verbatim": "first"}
        second = {"origin": "o", "verbatim": "second"}
        _run_ledger(ledger, _items(first), "add", "--verdict", "applied")

        result = _run_ledger(ledger, _items(third, first, second, ITEM_A), "unseen")

        assert _verbatims(result) == [
            "third",
            "second",
            "never mock the database in integration tests",
        ]


class TestCornerCases:
    def test_should_treat_an_item_with_edited_words_as_unseen_again(self, tmp_path):
        ledger = tmp_path / "ledger.jsonl"
        _run_ledger(ledger, _items(ITEM_A), "add", "--verdict", "applied")
        edited = {"origin": "lateral-marker", "verbatim": "never mock the database in unit tests"}

        result = _run_ledger(ledger, _items(edited), "unseen")

        assert _verbatims(result) == ["never mock the database in unit tests"]

    def test_should_still_match_when_only_whitespace_differs_in_the_verbatim(self, tmp_path):
        ledger = tmp_path / "ledger.jsonl"
        _run_ledger(ledger, _items(ITEM_A), "add", "--verdict", "covered")
        spaced = {
            "origin": "lateral-marker",
            "verbatim": "  never   mock the\tdatabase\nin integration tests  ",
        }

        result = _run_ledger(ledger, _items(spaced), "unseen")

        assert json.loads(result.stdout) == []

    def test_should_keep_an_item_unseen_when_another_origin_handled_the_same_verbatim(self, tmp_path):
        ledger = tmp_path / "ledger.jsonl"
        _run_ledger(ledger, _items(ITEM_A), "add", "--verdict", "applied")
        other = {"origin": "user-feedback", "verbatim": "never mock the database in integration tests"}

        result = _run_ledger(ledger, _items(other), "unseen")

        assert _verbatims(result) == ["never mock the database in integration tests"]

    def test_should_exit_0_when_the_ledger_file_is_missing(self, tmp_path):
        ledger = tmp_path / "ledger.jsonl"

        result = _run_ledger(ledger, _items(ITEM_A, ITEM_B), "unseen")

        assert result.returncode == 0

    def test_should_return_every_item_when_the_ledger_file_is_missing(self, tmp_path):
        ledger = tmp_path / "ledger.jsonl"

        result = _run_ledger(ledger, _items(ITEM_A, ITEM_B), "unseen")

        assert len(json.loads(result.stdout)) == 2

    def test_should_report_zero_dropped_when_the_ledger_file_is_missing(self, tmp_path):
        ledger = tmp_path / "ledger.jsonl"

        result = _run_ledger(ledger, _items(ITEM_A, ITEM_B), "unseen")

        assert result.stderr.strip() == "learn-ledger: dropped 0 already-handled item(s)"

    def test_should_create_the_missing_parent_directory_when_an_item_is_added(self, tmp_path):
        ledger = tmp_path / "nested" / "state" / "ledger.jsonl"

        _run_ledger(ledger, _items(ITEM_A), "add", "--verdict", "applied")

        assert len(_ledger_lines(ledger)) == 1

    def test_should_print_an_empty_array_when_unseen_gets_an_empty_input(self, tmp_path):
        ledger = tmp_path / "ledger.jsonl"

        result = _run_ledger(ledger, "[]", "unseen")

        assert json.loads(result.stdout) == []

    def test_should_exit_0_when_unseen_gets_an_empty_input(self, tmp_path):
        ledger = tmp_path / "ledger.jsonl"

        result = _run_ledger(ledger, "[]", "unseen")

        assert result.returncode == 0

    def test_should_exit_0_when_add_gets_an_empty_input(self, tmp_path):
        ledger = tmp_path / "ledger.jsonl"

        result = _run_ledger(ledger, "[]", "add", "--verdict", "applied")

        assert result.returncode == 0

    def test_should_write_nothing_when_add_gets_an_empty_input(self, tmp_path):
        ledger = tmp_path / "ledger.jsonl"

        _run_ledger(ledger, "[]", "add", "--verdict", "applied")

        assert _ledger_lines(ledger) == []

    def test_should_write_a_repeated_item_once_when_one_add_call_repeats_it(self, tmp_path):
        ledger = tmp_path / "ledger.jsonl"

        _run_ledger(ledger, _items(ITEM_A, ITEM_A), "add", "--verdict", "applied")

        assert len(_ledger_lines(ledger)) == 1


class TestFailureScenarios:
    def test_should_still_filter_records_around_a_malformed_ledger_line(self, tmp_path):
        ledger = tmp_path / "ledger.jsonl"
        _run_ledger(ledger, _items(ITEM_A), "add", "--verdict", "applied")
        with ledger.open("a", encoding="utf-8") as ledger_file:
            ledger_file.write("this is not json\n")
        _run_ledger(ledger, _items(ITEM_B), "add", "--verdict", "applied")

        result = _run_ledger(ledger, _items(ITEM_A, ITEM_B), "unseen")

        assert json.loads(result.stdout) == []

    def test_should_exit_0_when_the_ledger_holds_a_malformed_line(self, tmp_path):
        ledger = tmp_path / "ledger.jsonl"
        _run_ledger(ledger, _items(ITEM_A), "add", "--verdict", "applied")
        with ledger.open("a", encoding="utf-8") as ledger_file:
            ledger_file.write("this is not json\n")

        result = _run_ledger(ledger, _items(ITEM_A), "unseen")

        assert result.returncode == 0

    def test_should_name_the_malformed_line_number_in_the_stderr_warning(self, tmp_path):
        ledger = tmp_path / "ledger.jsonl"
        _run_ledger(ledger, _items(ITEM_A), "add", "--verdict", "applied")
        with ledger.open("a", encoding="utf-8") as ledger_file:
            ledger_file.write("this is not json\n")

        result = _run_ledger(ledger, _items(ITEM_A), "unseen")

        assert "line 2" in result.stderr

    def test_should_exit_2_when_add_gets_a_json_object_instead_of_an_array(self, tmp_path):
        ledger = tmp_path / "ledger.jsonl"

        result = _run_ledger(ledger, '{"origin":"a","verbatim":"b"}', "add", "--verdict", "applied")

        assert result.returncode == 2

    def test_should_exit_2_when_add_gets_unparseable_stdin(self, tmp_path):
        ledger = tmp_path / "ledger.jsonl"

        result = _run_ledger(ledger, "not json at all", "add", "--verdict", "applied")

        assert result.returncode == 2

    def test_should_exit_2_when_unseen_gets_unparseable_stdin(self, tmp_path):
        ledger = tmp_path / "ledger.jsonl"

        result = _run_ledger(ledger, "not json at all", "unseen")

        assert result.returncode == 2

    def test_should_create_no_ledger_file_when_stdin_is_not_a_json_array(self, tmp_path):
        ledger = tmp_path / "ledger.jsonl"
        _run_ledger(ledger, '{"origin":"a","verbatim":"b"}', "add", "--verdict", "applied")
        _run_ledger(ledger, "not json at all", "add", "--verdict", "applied")

        assert _ledger_lines(ledger) == []

    def test_should_exit_2_when_an_item_lacks_origin(self, tmp_path):
        ledger = tmp_path / "ledger.jsonl"

        result = _run_ledger(
            ledger,
            json.dumps([ITEM_A, {"verbatim": "no origin here"}]),
            "add",
            "--verdict",
            "applied",
        )

        assert result.returncode == 2

    def test_should_exit_2_when_an_item_has_a_non_string_verbatim(self, tmp_path):
        ledger = tmp_path / "ledger.jsonl"

        result = _run_ledger(
            ledger,
            json.dumps([ITEM_A, {"origin": "x", "verbatim": 42}]),
            "add",
            "--verdict",
            "applied",
        )

        assert result.returncode == 2

    def test_should_explain_the_problem_on_stderr_when_an_item_is_invalid(self, tmp_path):
        ledger = tmp_path / "ledger.jsonl"

        result = _run_ledger(
            ledger,
            json.dumps([ITEM_A, {"origin": "x", "verbatim": 42}]),
            "add",
            "--verdict",
            "applied",
        )

        assert "learn-ledger:" in result.stderr

    def test_should_write_the_valid_first_item_nowhere_when_a_later_item_is_invalid(self, tmp_path):
        ledger = tmp_path / "ledger.jsonl"

        _run_ledger(
            ledger,
            json.dumps([ITEM_A, {"verbatim": "no origin here"}]),
            "add",
            "--verdict",
            "applied",
        )

        assert _ledger_lines(ledger) == []

    def test_should_exit_2_when_the_verdict_is_unknown(self, tmp_path):
        ledger = tmp_path / "ledger.jsonl"

        result = _run_ledger(ledger, _items(ITEM_A), "add", "--verdict", "maybe")

        assert result.returncode == 2

    def test_should_exit_2_when_the_subcommand_is_unknown(self, tmp_path):
        ledger = tmp_path / "ledger.jsonl"

        result = _run_ledger(ledger, _items(ITEM_A), "forget")

        assert result.returncode == 2
