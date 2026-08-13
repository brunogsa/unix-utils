#!/usr/bin/env python3
"""Tests for extract-session-timeline.py: the time-and-work-done extractor
that builds timeline.json for one Claude Code session.

Fixtures: none on disk — every transcript is a handful of hand-readable
records built in code via _human_record()/_tool_use_record()/
_tool_result_record()/_turn_duration_record()/_write_transcript() below, each
small enough that expected durations/percentages can be verified by hand.
Every filesystem path used (transcripts root, tasks root) is a
tempfile.TemporaryDirectory(); this file never reads or writes
~/.claude/projects or ~/.claude/tasks.

Usage:
  pytest scripts/tests/test_session_timeline.py
"""

import contextlib
import importlib.util
import io
import json
import os
import tempfile
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).parent.parent


def _load_module(filename, module_name):
    """Import a dash-named script (not a valid module name) by file path."""
    spec = importlib.util.spec_from_file_location(module_name, SCRIPTS / filename)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {filename} from {SCRIPTS}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sti = _load_module("extract-session-timeline.py", "session_timeline")


def _iso(epoch):
    """Epoch seconds -> UTC ISO-8601 string, the shape parse_ts() expects."""
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def _human_record(epoch, text="do the thing"):
    """One typed human turn, the shape is_human_message() accepts."""
    return {
        "type": "user",
        "timestamp": _iso(epoch),
        "message": {"role": "user", "content": [{"type": "text", "text": text}]},
    }


def _turn_duration_record(end_epoch, duration_ms):
    """A turn_duration system record: the span ends AT end_epoch and started
    duration_ms milliseconds earlier."""
    return {
        "type": "system",
        "subtype": "turn_duration",
        "timestamp": _iso(end_epoch),
        "durationMs": duration_ms,
    }


def _away_summary_record(epoch):
    """A system record Claude Code writes while the human is away — carries a
    timestamp, so it extends the transcript's last_epoch, but is not the
    assistant producing anything."""
    return {
        "type": "system",
        "subtype": "away_summary",
        "timestamp": _iso(epoch),
        "content": "waiting on the operator",
    }


def _assistant_text_record(epoch, text="here is what I found"):
    """A plain assistant reply carrying no tool_use — the assistant producing
    output, which is what ends a turn's engaged span."""
    return {
        "type": "assistant",
        "timestamp": _iso(epoch),
        "message": {"role": "assistant", "content": [{"type": "text", "text": text}]},
    }


def _tool_use_record(epoch, tool_id, name, command=None):
    """One assistant tool_use block, e.g. a Bash call or a Task/Agent spawn."""
    tool_input = {"command": command} if command is not None else {}
    return {
        "type": "assistant",
        "timestamp": _iso(epoch),
        "message": {"role": "assistant", "content": [
            {"type": "tool_use", "id": tool_id, "name": name, "input": tool_input}]},
    }


def _tool_result_record(epoch, tool_id):
    """The user-turn tool_result that closes a tool_use's wall-clock span."""
    return {
        "type": "user",
        "timestamp": _iso(epoch),
        "message": {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": tool_id, "content": "ok"}]},
    }


def _write_transcript(dir_path, filename, records):
    """Write one record per line to dir_path/filename; returns the path."""
    path = os.path.join(dir_path, filename)
    with open(path, "w") as fh:
        for record in records:
            fh.write(json.dumps(record) + "\n")
    return path


def _make_session(tmp, sid, main_records, subagent_files=None):
    """Lay out tmp/<escaped-project>/<sid>.jsonl (+ subagents/*.jsonl) the way
    find_session_transcripts() expects, and return the sid unchanged."""
    project_dir = os.path.join(tmp, "-Users-x-project")
    os.makedirs(project_dir, exist_ok=True)
    _write_transcript(project_dir, f"{sid}.jsonl", main_records)
    if subagent_files:
        subagent_dir = os.path.join(project_dir, sid, "subagents")
        os.makedirs(subagent_dir, exist_ok=True)
        for filename, records in subagent_files.items():
            _write_transcript(subagent_dir, filename, records)
    return sid


class TestSessionTimeline(unittest.TestCase):

    def _build(self, tmp, sid, *, tasks_root=None):
        """build_timeline_payload(sid) with TRANSCRIPTS_ROOT (and optionally
        TASKS_ROOT) mocked to this test's temp directory."""
        patches = [mock.patch.object(sti.usage_report, "TRANSCRIPTS_ROOT", tmp)]
        if tasks_root is not None:
            patches.append(mock.patch.object(sti, "TASKS_ROOT", tasks_root))
        with contextlib.ExitStack() as stack:
            for patch in patches:
                stack.enter_context(patch)
            return sti.build_timeline_payload(sid)

    def _assert_partition_reconciles(self, payload):
        """The D5 partition invariant: the four buckets' seconds sum exactly
        to wall clock, and their rounded percentages sum to exactly 100.
        Excludes a zero-duration session, where there is no span to divide by
        and every bucket comes back 0 — that fixture asserts its own totals."""
        partition = payload["time_partition"]
        buckets = partition["buckets"]
        total_seconds = sum(buckets[name]["seconds"] for name in buckets)
        self.assertEqual(total_seconds, partition["wall_clock_seconds"],
                          msg="the four buckets must be a true partition of wall clock")
        total_pct = sum(buckets[name]["pct"] for name in buckets)
        self.assertEqual(total_pct, 100.0,
                          msg="the rounded percentages must reconcile to exactly 100")

    def test_attributes_engaged_time_to_main_api_tool_exec_and_agent_occupied_buckets_that_partition_wall_clock(self):
        """The core D5 partition: a tool call and a subagent run that both
        fall inside one turn's span must be carved out of main-API time, not
        double-counted on top of it, and the four buckets must sum exactly to
        the session's wall clock."""
        with tempfile.TemporaryDirectory() as tmp:
            sid = _make_session(tmp, "sess-buckets", [
                _human_record(1000),
                _tool_use_record(1010, "tu_bash", "Bash", command="pytest ."),
                _tool_result_record(1030, "tu_bash"),
                _tool_use_record(1040, "tu_task", "Task"),
                _tool_result_record(1090, "tu_task"),
                _turn_duration_record(1100, duration_ms=100_000),
            ])
            payload = self._build(tmp, sid)

        buckets = payload["time_partition"]["buckets"]
        self.assertEqual(payload["time_partition"]["wall_clock_seconds"], 100.0)
        self.assertEqual(buckets["agent_occupied"]["seconds"], 50.0,
                          msg="the Task call's own 1040-1090 span is agent-occupied")
        self.assertEqual(buckets["tool_exec"]["seconds"], 20.0,
                          msg="the Bash call's own 1010-1030 span is tool-exec")
        self.assertEqual(buckets["main_api"]["seconds"], 30.0,
                          msg="the turn's 1000-1100 span minus the 20s tool-exec "
                              "and 50s agent-occupied carved out of it")
        self.assertEqual(buckets["human_idle"]["seconds"], 0.0)
        self._assert_partition_reconciles(payload)


    def test_unions_two_overlapping_bash_calls_into_one_tool_exec_span_instead_of_double_counting_their_overlap(self):
        """Two Bash calls of the SAME kind whose spans overlap (1010-1060 and
        1030-1080) must be merged into their union (1010-1080 = 70s), never
        summed naively (which would double-count the 1030-1060 overlap and
        push the partition's total past wall clock)."""
        with tempfile.TemporaryDirectory() as tmp:
            sid = _make_session(tmp, "sess-bash-overlap", [
                _human_record(1000),
                _tool_use_record(1010, "tu_bash1", "Bash", command="pytest ."),
                _tool_result_record(1060, "tu_bash1"),
                _tool_use_record(1030, "tu_bash2", "Bash", command="pytest ."),
                _tool_result_record(1080, "tu_bash2"),
                _turn_duration_record(1100, duration_ms=100_000),
            ])
            payload = self._build(tmp, sid)

        buckets = payload["time_partition"]["buckets"]
        self.assertEqual(buckets["tool_exec"]["seconds"], 70.0,
                          msg="the overlapping 1010-1060 and 1030-1080 spans "
                              "must union to 70s, not sum to 100s")
        self._assert_partition_reconciles(payload)

    def test_carves_a_concurrent_bash_call_entirely_out_of_tool_exec_when_it_falls_inside_a_subagent_run(self):
        """A Bash call (1020-1080) running concurrently INSIDE a Task span
        (1010-1090) is agent-occupied time, not tool-exec — cross-kind
        overlap must subtract fully, leaving tool_exec at 0, not the Bash
        call's own 60s."""
        with tempfile.TemporaryDirectory() as tmp:
            sid = _make_session(tmp, "sess-crosskind-overlap", [
                _human_record(1000),
                _tool_use_record(1010, "tu_task", "Task"),
                _tool_use_record(1020, "tu_bash", "Bash", command="pytest ."),
                _tool_result_record(1080, "tu_bash"),
                _tool_result_record(1090, "tu_task"),
                _turn_duration_record(1100, duration_ms=100_000),
            ])
            payload = self._build(tmp, sid)

        buckets = payload["time_partition"]["buckets"]
        self.assertEqual(buckets["tool_exec"]["seconds"], 0.0,
                          msg="the Bash call's 1020-1080 span sits entirely "
                              "inside the Task's 1010-1090 span")
        self.assertEqual(buckets["agent_occupied"]["seconds"], 80.0)
        self._assert_partition_reconciles(payload)

    def test_labels_both_task_and_agent_tool_use_names_as_agent_occupied_time(self):
        """AGENT_TOOL_NAMES must recognize both "Task" and "Agent" as a
        subagent run occupying wall clock, not just one of the two names."""
        for agent_tool_name in ("Task", "Agent"):
            with self.subTest(agent_tool_name=agent_tool_name):
                with tempfile.TemporaryDirectory() as tmp:
                    sid = _make_session(tmp, f"sess-agentname-{agent_tool_name.lower()}", [
                        _human_record(1000),
                        _tool_use_record(1010, "tu_agent", agent_tool_name),
                        _tool_result_record(1090, "tu_agent"),
                        _turn_duration_record(1100, duration_ms=100_000),
                    ])
                    payload = self._build(tmp, sid)
                buckets = payload["time_partition"]["buckets"]
                self.assertEqual(buckets["agent_occupied"]["seconds"], 80.0,
                                  msg=f'a "{agent_tool_name}" tool_use/tool_result '
                                      f"span must be agent-occupied")

    def test_reports_the_agent_hours_vs_wall_clock_occupied_pair_explicitly(self):
        """Two 60s subagent runs whose main-side Task spans overlap
        (1010-1070 and 1040-1100, unioning to 90s of wall-clock-occupied
        time) must still report their own 60+60=120s of agent_hours_seconds
        independently — nothing else in the payload pins this pair, so a
        deleted or zeroed key would otherwise ship silently."""
        with tempfile.TemporaryDirectory() as tmp:
            sid = _make_session(tmp, "sess-agent-hours", [
                _human_record(1000),
                _tool_use_record(1010, "tu_task1", "Task"),
                _tool_result_record(1070, "tu_task1"),
                _tool_use_record(1040, "tu_task2", "Task"),
                _tool_result_record(1100, "tu_task2"),
                _turn_duration_record(1110, duration_ms=110_000),
            ], subagent_files={
                "agent-a.jsonl": [
                    _tool_use_record(2000, "tu_a", "Bash", command="ls"),
                    _tool_result_record(2060, "tu_a"),
                ],
                "agent-b.jsonl": [
                    _tool_use_record(3000, "tu_b", "Bash", command="ls"),
                    _tool_result_record(3060, "tu_b"),
                ],
            })
            payload = self._build(tmp, sid)

        self.assertEqual(
            payload["time_partition"]["agent_hours_vs_wall_clock_occupied"],
            {"agent_hours_seconds": 120.0, "wall_clock_occupied_seconds": 90.0})

    def test_widens_wall_clock_to_cover_a_turn_duration_span_that_starts_before_the_transcripts_first_record(self):
        """A turn_duration record's measured duration can exceed the elapsed
        time since the session's first record (e.g. a slow first turn) —
        span_start = end - duration then lands before first_epoch. That is
        evidence the session began earlier than its first record shows, so
        wall clock must widen to cover it rather than clamping engaged time,
        or the four shares stop reconciling to 100% (AC 1)."""
        with tempfile.TemporaryDirectory() as tmp:
            sid = _make_session(tmp, "sess-overrun", [
                _human_record(1000),
                _turn_duration_record(1010, duration_ms=100_000),
            ])
            payload = self._build(tmp, sid)

        buckets = payload["time_partition"]["buckets"]
        self.assertEqual(payload["time_partition"]["wall_clock_seconds"], 100.0,
                          msg="wall clock must widen to the turn's 910-1010 span, "
                              "not stay at the 1000-1010 record range")
        self.assertEqual(buckets["main_api"]["seconds"], 100.0)
        self._assert_partition_reconciles(payload)

    def test_reconciles_every_wall_clock_percentage_to_100_after_rounding(self):
        """A 6-second wall clock split 2/1/2/1 across the four buckets forces
        two of them (16.667%, 33.333%) to round unevenly — the largest-
        remainder method must still land the four shares on exactly 100."""
        with tempfile.TemporaryDirectory() as tmp:
            sid = _make_session(tmp, "sess-pct", [
                _human_record(0),
                _tool_use_record(1, "tu_bash", "Bash", command="pytest ."),
                _tool_result_record(2, "tu_bash"),
                _tool_use_record(3, "tu_task", "Task"),
                _tool_result_record(5, "tu_task"),
                _turn_duration_record(5, duration_ms=5_000),
                _human_record(6),
            ])
            payload = self._build(tmp, sid)

        buckets = payload["time_partition"]["buckets"]
        self.assertEqual(buckets["main_api"]["pct"], 33.0)
        self.assertEqual(buckets["tool_exec"]["pct"], 17.0)
        self.assertEqual(buckets["agent_occupied"]["pct"], 33.0)
        self.assertEqual(buckets["human_idle"]["pct"], 17.0)
        self._assert_partition_reconciles(payload)

    def test_guards_every_duration_percentage_against_division_by_zero_for_a_zero_duration_or_single_record_session(self):
        """A session with only one record ever written has no span to divide
        by — every bucket must come back as 0, never raise ZeroDivisionError."""
        with tempfile.TemporaryDirectory() as tmp:
            sid = _make_session(tmp, "sess-single", [
                _human_record(1000),
            ])
            payload = self._build(tmp, sid)

        self.assertEqual(payload["time_partition"]["wall_clock_seconds"], 0.0)
        for name, bucket in payload["time_partition"]["buckets"].items():
            self.assertEqual(bucket["seconds"], 0.0, msg=f"{name} seconds")
            self.assertEqual(bucket["pct"], 0.0, msg=f"{name} pct")


    def test_builds_a_chronological_timeline_of_turn_duration_spans_tool_calls_and_git_commits_for_a_session(self):
        """The payload's `timeline` feed must merge all three event kinds
        into one timestamp-ordered list, whatever order each kind's own
        section (turns/buckets/commits) happens to build them in."""
        with tempfile.TemporaryDirectory() as tmp:
            sid = _make_session(tmp, "sess-chrono", [
                _human_record(1000),
                _tool_use_record(1005, "tu_commit", "Bash", command="git commit -m 'feat'"),
                _tool_result_record(1007, "tu_commit"),
                _turn_duration_record(1010, duration_ms=10_000),
                _human_record(2000),
                _tool_use_record(2002, "tu_task", "Task"),
                _tool_result_record(2010, "tu_task"),
                _turn_duration_record(2015, duration_ms=15_000),
            ])
            payload = self._build(tmp, sid)

        timeline = payload["timeline"]
        timestamps = [entry["timestamp"] for entry in timeline]
        self.assertEqual(timestamps, sorted(timestamps),
                          msg="the timeline must be sorted chronologically")
        types = [entry["type"] for entry in timeline]
        self.assertEqual(types.count("turn"), 2)
        self.assertEqual(types.count("tool_call"), 2)
        self.assertEqual(types.count("commit"), 1)
        commit_entry = next(entry for entry in timeline if entry["type"] == "commit")
        self.assertIn("git commit", commit_entry["command"])
        self.assertEqual(commit_entry["source"], "main")

    def test_sorts_records_by_timestamp_before_computing_any_span_even_when_the_transcript_holds_out_of_order_entries(self):
        """The tool_result line is written to the file BEFORE its tool_use
        line, even though it happened later in real time — pairing must
        still succeed once records are sorted by timestamp, not file order."""
        with tempfile.TemporaryDirectory() as tmp:
            sid = _make_session(tmp, "sess-outoforder", [
                _human_record(1000),
                _tool_result_record(1030, "tu_bash"),
                _tool_use_record(1010, "tu_bash", "Bash", command="pytest ."),
                _turn_duration_record(1040, duration_ms=40_000),
            ])
            payload = self._build(tmp, sid)

        self.assertEqual(payload["time_partition"]["buckets"]["tool_exec"]["seconds"], 20.0,
                          msg="the 1010-1030 span must be recovered despite the "
                              "tool_result line preceding its tool_use line on disk")

    def test_falls_back_to_a_computed_span_and_says_which_measure_produced_it_when_turn_duration_records_are_sparse_or_absent(self):
        """No turn_duration record exists at all — the turn's span must fall
        back to the stretch the assistant was actually producing output over
        (0 to its last event at 2), and the payload must say which measure
        produced it. The next human message lands at 5, so a span that ran to
        the next message instead would read 5.0 here."""
        with tempfile.TemporaryDirectory() as tmp:
            sid = _make_session(tmp, "sess-nofallback", [
                _human_record(0),
                _assistant_text_record(2),
                _human_record(5),
            ])
            payload = self._build(tmp, sid)

        first_turn = payload["turns"][0]
        self.assertEqual(first_turn["measure"], "computed")
        self.assertEqual(first_turn["duration_seconds"], 2.0)

    def test_stops_a_computed_turns_span_at_the_assistants_last_event_so_an_overnight_human_absence_is_never_charged_to_main_api(self):
        """The human writes at 0, the assistant answers and finishes at 40,
        then the human is away until 40000. Charging that absence to main-API
        time is what made a real 42-hour session report 97% main-API — the
        turn's engaged span must end at 40, leaving the 11-hour gap in
        human_idle."""
        with tempfile.TemporaryDirectory() as tmp:
            sid = _make_session(tmp, "sess-overnight-gap", [
                _human_record(0),
                _tool_use_record(10, "tu_bash", "Bash", command="pytest ."),
                _tool_result_record(30, "tu_bash"),
                _assistant_text_record(40),
                _human_record(40000),
                _tool_use_record(40010, "tu_bash2", "Bash", command="git status"),
                _tool_result_record(40030, "tu_bash2"),
            ])
            payload = self._build(tmp, sid)

        buckets = payload["time_partition"]["buckets"]
        self.assertEqual(payload["turns"][0]["duration_seconds"], 40.0,
                          msg="the turn ends at the assistant's last event (40), "
                              "not at the next human message (40000)")
        self.assertEqual(buckets["main_api"]["seconds"], 30.0,
                          msg="turn 0's 0-40 span and turn 1's 40000-40030 span, "
                              "each minus the 20s Bash call carved out of it")
        self.assertEqual(buckets["human_idle"]["seconds"], 39960.0,
                          msg="the 40-to-40000 absence belongs to human_idle")
        self._assert_partition_reconciles(payload)

    def test_collapses_a_computed_turns_span_to_zero_when_the_human_message_drew_no_assistant_activity_at_all(self):
        """The human writes at 0 and gets no answer before writing again an
        hour later — there is no engaged time to attribute, so the turn's span
        must collapse rather than swallow the whole hour."""
        with tempfile.TemporaryDirectory() as tmp:
            sid = _make_session(tmp, "sess-unanswered-turn", [
                _human_record(0),
                _human_record(3600),
                _assistant_text_record(3610),
            ])
            payload = self._build(tmp, sid)

        buckets = payload["time_partition"]["buckets"]
        self.assertEqual(payload["turns"][0]["duration_seconds"], 0.0,
                          msg="no assistant event followed the message at 0")
        self.assertEqual(buckets["main_api"]["seconds"], 10.0,
                          msg="only the answered second turn's 3600-3610 span "
                              "is main-API time")
        self.assertEqual(buckets["human_idle"]["seconds"], 3600.0)
        self._assert_partition_reconciles(payload)

    def test_stops_the_final_computed_turns_span_at_its_last_activity_rather_than_at_the_transcripts_last_record(self):
        """The final turn takes its window end from the transcript's last
        record instead of a next human message, and that last record can be an
        away-summary written two hours after the assistant stopped — the same
        activity-based end must apply there, not a silent pass-through of the
        old behavior."""
        with tempfile.TemporaryDirectory() as tmp:
            sid = _make_session(tmp, "sess-final-turn", [
                _human_record(0),
                _assistant_text_record(20),
                _away_summary_record(7200),
            ])
            payload = self._build(tmp, sid)

        buckets = payload["time_partition"]["buckets"]
        self.assertEqual(payload["turns"][0]["duration_seconds"], 20.0,
                          msg="the final turn ends at the assistant's last event "
                              "(20), not at the away-summary record (7200)")
        self.assertEqual(payload["time_partition"]["wall_clock_seconds"], 7200.0,
                          msg="wall clock still spans every timestamped record")
        self.assertEqual(buckets["main_api"]["seconds"], 20.0)
        self.assertEqual(buckets["human_idle"]["seconds"], 7180.0)
        self._assert_partition_reconciles(payload)

    def test_keeps_a_turn_duration_measured_span_at_its_recorded_duration_even_when_no_assistant_event_falls_inside_it(self):
        """A recorded turn_duration is authoritative: its span stays
        end-minus-duration wide whatever the transcript's own records show, so
        narrowing computed spans to observed activity must not leak into this
        branch and shrink a measured 100s turn that has no assistant record of
        its own."""
        with tempfile.TemporaryDirectory() as tmp:
            sid = _make_session(tmp, "sess-measured-then-away", [
                _human_record(0),
                _turn_duration_record(100, duration_ms=100_000),
                _human_record(40000),
                _assistant_text_record(40010),
            ])
            payload = self._build(tmp, sid)

        buckets = payload["time_partition"]["buckets"]
        first_turn = payload["turns"][0]
        self.assertEqual(first_turn["measure"], "turn_duration")
        self.assertEqual(first_turn["duration_seconds"], 100.0,
                          msg="the recorded duration stands on its own, with no "
                              "assistant record inside the 0-100 span")
        self.assertEqual(buckets["main_api"]["seconds"], 110.0,
                          msg="the measured 100s turn plus the computed "
                              "40000-40010 turn")
        self._assert_partition_reconciles(payload)

    def test_emits_a_too_early_to_rank_note_instead_of_a_ranked_timeline_when_the_session_has_only_one_turn(self):
        """A single-turn session has nothing to rank against — the payload
        must say so explicitly rather than emit a degenerate one-item ranking."""
        with tempfile.TemporaryDirectory() as tmp:
            sid = _make_session(tmp, "sess-oneturn", [
                _human_record(1000),
                _turn_duration_record(1010, duration_ms=10_000),
            ])
            payload = self._build(tmp, sid)

        self.assertTrue(payload["turn_ranking"]["too_early_to_rank"])
        self.assertEqual(payload["turn_ranking"]["note"],
                          "only 1 turn(s) recorded; nothing to rank yet",
                          msg="key presence alone doesn't pin the note's actual "
                              "text — an empty note must fail this")
        self.assertNotIn("ranked_turn_indices", payload["turn_ranking"])


    def test_lists_completed_and_pending_tasks_from_the_sessions_task_store_ordered_by_file_mtime(self):
        """Ordered by file mtime, not filename — b.json's mtime is set
        earlier than a.json's, and the task list must reflect that, not
        alphabetical order."""
        with tempfile.TemporaryDirectory() as transcripts_tmp, \
             tempfile.TemporaryDirectory() as tasks_tmp:
            sid = _make_session(transcripts_tmp, "sess-tasks", [_human_record(1000)])
            tasks_dir = os.path.join(tasks_tmp, sid)
            os.makedirs(tasks_dir)
            path_b = os.path.join(tasks_dir, "b.json")
            path_a = os.path.join(tasks_dir, "a.json")
            with open(path_b, "w") as fh:
                json.dump({"id": "b", "subject": "first done", "status": "completed"}, fh)
            with open(path_a, "w") as fh:
                json.dump({"id": "a", "subject": "second, still open", "status": "pending"}, fh)
            now = time.time()
            os.utime(path_b, (now - 100, now - 100))
            os.utime(path_a, (now - 10, now - 10))

            payload = self._build(transcripts_tmp, sid, tasks_root=tasks_tmp)

        task_ids = [task["id"] for task in payload["tasks"]["tasks"]]
        self.assertEqual(task_ids, ["b", "a"],
                          msg="tasks must be ordered by file mtime, oldest first")

    def test_reports_no_tasks_tracked_never_fail_when_the_sessions_task_store_directory_is_empty(self):
        """Covers both trigger shapes of the same outcome: a task-store
        directory that was never created, and one that exists but is empty —
        neither may raise, and both must report the same note."""
        with tempfile.TemporaryDirectory() as transcripts_tmp, \
             tempfile.TemporaryDirectory() as tasks_tmp:
            sid = _make_session(transcripts_tmp, "sess-notasks", [_human_record(1000)])

            absent_payload = self._build(transcripts_tmp, sid, tasks_root=tasks_tmp)
            self.assertEqual(absent_payload["tasks"], {"note": "no tasks tracked", "tasks": []},
                              msg="a task-store directory that was never created")

            os.makedirs(os.path.join(tasks_tmp, sid))
            empty_payload = self._build(transcripts_tmp, sid, tasks_root=tasks_tmp)
            self.assertEqual(empty_payload["tasks"], {"note": "no tasks tracked", "tasks": []},
                              msg="a task-store directory that exists but holds no task files")


    def test_parses_only_git_commit_tool_calls_from_the_main_and_subagent_transcripts_and_says_the_commit_list_may_be_incomplete(self):
        """A plain `git status` call must not be mistaken for a commit; a
        `git commit` call in a subagent transcript must be attributed to
        that subagent, not folded into main's list; the payload must say the
        list may be incomplete (D10 — hook/amend commits leave no tool call)."""
        with tempfile.TemporaryDirectory() as tmp:
            sid = _make_session(tmp, "sess-commits", [
                _human_record(1000),
                _tool_use_record(1005, "tu_status", "Bash", command="git status"),
                _tool_result_record(1006, "tu_status"),
                _tool_use_record(1010, "tu_commit", "Bash", command="git commit -m 'feat'"),
                _tool_result_record(1012, "tu_commit"),
                _turn_duration_record(1020, duration_ms=20_000),
            ], subagent_files={"agent-sub.jsonl": [
                _tool_use_record(1013, "tu_sub_commit", "Bash", command="git commit -m 'sub change'"),
                _tool_result_record(1014, "tu_sub_commit"),
            ]})
            payload = self._build(tmp, sid)

        commits = payload["commits"]
        self.assertEqual(len(commits["items"]), 2,
                          msg="the `git status` call must not be counted as a commit")
        sources = {item["source"] for item in commits["items"]}
        self.assertEqual(sources, {"main", "agent-sub"})
        main_commit = next(item for item in commits["items"] if item["source"] == "main")
        self.assertEqual(main_commit["turn_index"], 0)
        self.assertIn("hook", commits["note"])
        self.assertIn("amend", commits["note"])

    def test_attributes_a_main_commit_to_the_second_turn_when_its_the_only_turn_containing_it(self):
        """A single-turn fixture can't prove turn attribution — index 0
        would be the only index that exists whether or not the code reads
        span containment at all. Two turns, with the sole commit landing
        only inside the SECOND turn's span, is what actually pins it."""
        with tempfile.TemporaryDirectory() as tmp:
            sid = _make_session(tmp, "sess-turnindex", [
                _human_record(1000),
                _turn_duration_record(1100, duration_ms=100_000),
                _human_record(2000),
                _tool_use_record(2010, "tu_commit", "Bash", command="git commit -m 'feat'"),
                _tool_result_record(2011, "tu_commit"),
                _tool_use_record(1500, "tu_gap_commit", "Bash", command="git commit -m 'gap'"),
                _tool_result_record(1501, "tu_gap_commit"),
                _turn_duration_record(2100, duration_ms=100_000),
            ])
            payload = self._build(tmp, sid)

        commits_by_timestamp = {item["timestamp"]: item for item in payload["commits"]["items"]}
        turn1_commit = commits_by_timestamp[_iso(2010)]
        self.assertEqual(turn1_commit["turn_index"], 1,
                          msg="the commit at 2010 falls inside turn 1's 2000-2100 "
                              "span, not turn 0's 1000-1100 span")
        gap_commit = commits_by_timestamp[_iso(1500)]
        self.assertIsNone(gap_commit["turn_index"],
                           msg="a commit at 1500 falls in the gap between turn 0's "
                               "1000-1100 span and turn 1's 2000-2100 span — no "
                               "turn's span contains it")

    def test_labels_a_subagent_runs_agent_type_and_model_as_unknown_without_inventing_a_tier_when_its_meta_json_sidecar_is_missing(self):
        """agent-nometa.jsonl has no agent-nometa.meta.json sidecar on disk —
        the run must still be reported, labeled unknown rather than guessed."""
        with tempfile.TemporaryDirectory() as tmp:
            sid = _make_session(tmp, "sess-nometa", [
                _human_record(1000),
                _turn_duration_record(1010, duration_ms=10_000),
            ], subagent_files={"agent-nometa.jsonl": [
                _tool_use_record(1001, "tu_inner", "Bash", command="ls"),
                _tool_result_record(1006, "tu_inner"),
            ]})
            payload = self._build(tmp, sid)

        run = payload["agent_runs"][0]
        self.assertEqual(run["agent_type"], "unknown")
        self.assertEqual(run["model"], "unknown")
        self.assertEqual(run["duration_seconds"], 5.0,
                          msg="timing still comes from the subagent's own first/last "
                              "record, independent of the missing sidecar")

    def test_renders_every_duration_in_the_users_local_timezone_by_reusing_parse_ts_and_local_day_never_re_deriving_them(self):
        """A UTC timestamp just after midnight must fall on the PREVIOUS
        local day at UTC-3 — the exact behavior local_day() implements —
        proving this script reused it rather than re-deriving its own."""
        old_tz = os.environ.get("TZ")
        os.environ["TZ"] = "America/Sao_Paulo"
        time.tzset()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                sid = _make_session(tmp, "sess-tz", [
                    _human_record(1000),
                    _turn_duration_record(1010, duration_ms=10_000),
                ])
                payload = self._build(tmp, sid)
        finally:
            if old_tz is None:
                os.environ.pop("TZ", None)
            else:
                os.environ["TZ"] = old_tz
            time.tzset()

        expected_day = sti.usage_report.local_day(1000)
        self.assertEqual(payload["local_day"], expected_day)


    def test_resolves_a_sid_against_a_later_project_directory_when_it_is_not_in_the_first_one_searched(self):
        """The failure-path test only proves every directory gets NAMED when
        none of them match. This is the success-path counterpart: the
        transcript lives ONLY in the second of two project directories, so
        resolution must not stop after checking the first one."""
        with tempfile.TemporaryDirectory() as tmp:
            dir_a = os.path.join(tmp, "-Users-x-project-a")
            dir_b = os.path.join(tmp, "-Users-x-project-b")
            os.makedirs(dir_a)
            os.makedirs(dir_b)
            _write_transcript(dir_a, "other-session.jsonl", [_human_record(1000)])
            sid = "sess-only-in-dir-b"
            _write_transcript(dir_b, f"{sid}.jsonl", [
                _human_record(1000),
                _turn_duration_record(1010, duration_ms=10_000),
            ])
            with mock.patch.object(sti.usage_report, "TRANSCRIPTS_ROOT", tmp):
                payload = sti.build_timeline_payload(sid)

        self.assertEqual(payload["sid"], sid,
                          msg="the payload must build from dir_b's transcript "
                              "even though dir_a was searched first and had "
                              "no match")

    def test_exits_non_zero_naming_every_project_directory_searched_when_the_given_session_id_matches_no_transcript(self):
        """An unknown session id must fail loudly and name every directory
        that was searched, so the reader can tell a typo'd sid from a
        transcript that was pruned or never existed."""
        with tempfile.TemporaryDirectory() as tmp:
            dir_a = os.path.join(tmp, "-Users-x-project-a")
            dir_b = os.path.join(tmp, "-Users-x-project-b")
            os.makedirs(dir_a)
            os.makedirs(dir_b)
            _write_transcript(dir_a, "other-session.jsonl", [_human_record(1000)])
            stderr_buf = io.StringIO()
            with mock.patch.object(sti.usage_report, "TRANSCRIPTS_ROOT", tmp), \
                 contextlib.redirect_stderr(stderr_buf):
                with self.assertRaises(SystemExit) as ctx:
                    sti.build_timeline_payload("nonexistent-sid")
            stderr_text = stderr_buf.getvalue()

        self.assertNotEqual(ctx.exception.code, 0,
                             msg="a session id matching no transcript must exit non-zero")
        self.assertIn(dir_a, stderr_text,
                       msg="every searched project directory must be named, "
                           "including ones that held unrelated sessions")
        self.assertIn(dir_b, stderr_text,
                       msg="every searched project directory must be named, "
                           "including one that held nothing at all")

    def test_skips_a_torn_final_line_without_failing_when_the_transcript_is_still_being_written(self):
        """The last line is a truncated, mid-write JSON fragment (no closing
        brace) — the run must still succeed using every valid line before it."""
        with tempfile.TemporaryDirectory() as tmp:
            sid = _make_session(tmp, "sess-torn", [
                _human_record(1000),
                _turn_duration_record(1010, duration_ms=10_000),
            ])
            project_dir = os.path.join(tmp, "-Users-x-project")
            path = os.path.join(project_dir, f"{sid}.jsonl")
            with open(path, "a") as fh:
                fh.write('{"type": "assistant", "timestamp": "2026-0')  # torn, no trailing newline

            payload = self._build(tmp, sid)

        self.assertEqual(len(payload["turns"]), 1)
        self.assertEqual(payload["turns"][0]["duration_seconds"], 10.0)

    def test_streams_a_multi_thousand_record_transcript_without_loading_it_fully_into_memory(self):
        """5,000 filler records plus the one real turn — wrapping the
        transcript's file handle to forbid read()/readlines() proves the
        parse path only ever iterates it line-by-line, never materializes
        the whole file."""
        class _ForbidWholeFileRead:
            """Delegates iteration to the real handle; raises on any call
            that would load the whole remaining file into memory at once."""

            def __init__(self, fh):
                self._fh = fh

            def __iter__(self):
                return iter(self._fh)

            def __enter__(self):
                return self

            def __exit__(self, *exc_info):
                return self._fh.__exit__(*exc_info)

            def read(self, *args, **kwargs):
                raise AssertionError("must not call read() — that loads the whole file into memory")

            def readlines(self, *args, **kwargs):
                raise AssertionError("must not call readlines() — that loads the whole file into memory")

        with tempfile.TemporaryDirectory() as tmp:
            filler = [{"type": "assistant", "timestamp": _iso(500 + i),
                       "message": {"role": "assistant", "content": [{"type": "text", "text": "..."}]}}
                      for i in range(5000)]
            sid = _make_session(tmp, "sess-huge", [
                _human_record(0),
                *filler,
                _turn_duration_record(1010, duration_ms=10_000),
            ])
            transcript_path = os.path.join(tmp, "-Users-x-project", f"{sid}.jsonl")
            real_open = open

            def guarded_open(path, *args, **kwargs):
                fh = real_open(path, *args, **kwargs)
                if os.path.abspath(path) == os.path.abspath(transcript_path):
                    return _ForbidWholeFileRead(fh)
                return fh

            with mock.patch("builtins.open", side_effect=guarded_open):
                payload = self._build(tmp, sid)

        self.assertEqual(payload["turns"][0]["duration_seconds"], 10.0)


if __name__ == "__main__":
    unittest.main()
