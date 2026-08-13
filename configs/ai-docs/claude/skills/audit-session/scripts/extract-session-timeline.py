#!/usr/bin/env python3
# extract-session-timeline - Build timeline.json: the time-and-work-done
# extractor for one Claude Code session.
#
# Usage:
#   extract-session-timeline.py <sid>
#
# stdin: none. stdout: the timeline.json payload (pretty-printed JSON) — a
# chronological event feed, the D5 wall-clock time partition (main-API /
# tool-exec / agent-occupied / unattributed / human-idle, reconciled to 100%
# after rounding), the agent-hours-vs-wall-clock-occupied pair, the session's
# task-store listing, and every git-commit tool call found across the main
# and subagent transcripts. Exit 1, naming every project directory searched,
# when `sid` matches no transcript anywhere under ~/.claude/projects.
#
# WHY REUSE CLAUDE-USAGE-REPORT.PY'S HELPERS: parse_ts/local_day/iter_records/
# find_session_transcripts/project_directories/is_human_message already parse
# the same transcript shape correctly (torn final lines, ISO timestamps,
# local-day bucketing, sid resolution across every project directory) — this
# script must never re-derive what that one already got right. Imported by
# file path via importlib because the filename's dash makes it an invalid
# module name for a plain `import`, the same precedent build-usage-viewer.py
# uses for config-change-ledger.py and delivered-work-ledger.py.

import argparse
import bisect
import importlib.util
import json
import os
import re
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
TASKS_ROOT = os.path.expanduser("~/.claude/tasks")

# Tool names whose wall-clock span is a subagent run, not a plain tool call —
# same check claude-usage-report.py's collect_agent_spawns() uses to find a
# spawn, so the two scripts agree on what counts as "an agent ran".
AGENT_TOOL_NAMES = ("Task", "Agent")

# Requires a trailing whitespace-or-end after "commit" so "commit-tree" /
# "commit-graph" (real git plumbing subcommands) don't false-match "commit".
GIT_COMMIT_RE = re.compile(r"\bgit\s+commit(?:\s|$)")

COMMIT_NOTE = ("a commit made by a hook, or folded into an existing commit by "
               "`git commit --amend`, leaves no new tool call and so may be "
               "missing from this list")


def _load_usage_report():
    path = os.path.normpath(os.path.join(
        SCRIPT_DIR, "..", "..", "usage-audit", "scripts", "claude-usage-report.py"))
    spec = importlib.util.spec_from_file_location("claude_usage_report", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load claude-usage-report.py from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


usage_report = _load_usage_report()


def resolve_session(sid):
    """(main_path, subagent_paths) for sid, or exit(1) naming every searched
    project directory — delegates entirely to find_session_transcripts() /
    project_directories() / exit_session_not_found() so sid resolution AND its
    failure message never drift from claude-usage-report.py's own --session
    behavior."""
    main_path, subagent_paths = usage_report.find_session_transcripts(sid)
    if main_path is None:
        usage_report.exit_session_not_found(sid)
    return main_path, subagent_paths


def _iso_from_epoch(epoch):
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def _extract_raw_events(path, source_label):
    """One streaming pass over `path` via iter_records() — never re-reads the
    file and never holds more than the small subset of fields each record
    kind needs, so a multi-thousand-record transcript stays cheap even though
    every line gets looked at once.

    Returns (events, activity_epochs, away_summary_epochs, commits,
    first_epoch, last_epoch): `events` is a list of (epoch, kind, payload)
    tuples for turn_duration/tool_use/tool_result/human_message records, NOT
    yet sorted (the caller sorts once, so pairing tool_use with tool_result
    is correct regardless of on-disk record order — AC #5). `activity_epochs`
    is the sorted list of moments the assistant was producing something (an
    assistant record, or a tool_result coming back), which is what tells a
    computed turn when the assistant stopped rather than when the human next
    spoke. `away_summary_epochs` is the sorted list of moments Claude Code
    recorded a system/away_summary record — written when it detects the
    human stepped away, so its timestamp is itself evidence the assistant
    had already stopped by then, tighter evidence than activity_epochs alone
    when the assistant's next event lands long after the human returns.
    first_epoch/last_epoch span every record in the file that carries a
    parseable timestamp, whether or not it produced an event.
    """
    events = []
    activity_epochs = []
    away_summary_epochs = []
    commits = []
    first_epoch = None
    last_epoch = None
    for record in usage_report.iter_records(path):
        epoch = usage_report.parse_ts(record.get("timestamp"))
        if epoch is None:
            continue
        if first_epoch is None or epoch < first_epoch:
            first_epoch = epoch
        if last_epoch is None or epoch > last_epoch:
            last_epoch = epoch

        rtype = record.get("type")
        if rtype == "assistant":
            activity_epochs.append(epoch)
        if rtype == "system" and record.get("subtype") == "away_summary":
            away_summary_epochs.append(epoch)
        if rtype == "system" and record.get("subtype") == "turn_duration":
            events.append((epoch, "turn_duration", {"duration_ms": record.get("durationMs") or 0}))
            continue

        message = record.get("message") or {}
        content = message.get("content")
        if rtype == "assistant" and isinstance(content, list):
            for item in content:
                if not (isinstance(item, dict) and item.get("type") == "tool_use" and item.get("id")):
                    continue
                name = item.get("name")
                events.append((epoch, "tool_use", {"id": item["id"], "name": name}))
                if name == "Bash":
                    command = (item.get("input") or {}).get("command", "")
                    if GIT_COMMIT_RE.search(command):
                        commits.append({
                            "source": source_label,
                            "timestamp": record.get("timestamp"),
                            "command": command,
                        })
        elif rtype == "user":
            if usage_report.is_human_message(record, content):
                events.append((epoch, "human_message", {}))
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "tool_result" and item.get("tool_use_id"):
                        events.append((epoch, "tool_result", {"id": item["tool_use_id"]}))
                        activity_epochs.append(epoch)
    events.sort(key=lambda event: event[0])
    activity_epochs.sort()
    away_summary_epochs.sort()
    return events, activity_epochs, away_summary_epochs, commits, first_epoch, last_epoch


def _pair_tool_spans(events):
    """Sorted events -> [(start_epoch, end_epoch, kind)] for each matched
    tool_use/tool_result pair, kind in {"tool-exec", "agent-occupied"}. Reads
    the already-timestamp-sorted list, so a tool_result that lands earlier in
    file order than its tool_use still pairs correctly."""
    open_calls = {}
    spans = []
    for epoch, kind, payload in events:
        if kind == "tool_use":
            open_calls[payload["id"]] = (epoch, payload["name"])
        elif kind == "tool_result":
            opened = open_calls.pop(payload["id"], None)
            if opened is None:
                continue
            start_epoch, name = opened
            bucket_kind = "agent-occupied" if name in AGENT_TOOL_NAMES else "tool-exec"
            spans.append((start_epoch, epoch, bucket_kind))
    return spans


def _merge_intervals(intervals):
    """Union of possibly-overlapping (start, end) pairs into the fewest
    non-overlapping spans, so a bucket never double-counts time two parallel
    calls of the SAME kind both occupied."""
    merged = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def _subtract_intervals(base, remove):
    """base minus every overlapping part of remove. Both arguments must
    already be merged (non-overlapping within themselves)."""
    result = []
    remove = sorted(remove)
    for start, end in base:
        cur_start = start
        for r_start, r_end in remove:
            if r_end <= cur_start or r_start >= end:
                continue
            if r_start > cur_start:
                result.append((cur_start, min(r_start, end)))
            cur_start = max(cur_start, r_end)
            if cur_start >= end:
                break
        if cur_start < end:
            result.append((cur_start, end))
    return result


def _interval_seconds(intervals):
    return sum(end - start for start, end in intervals)


def _window_bounds(first_epoch, last_epoch, *interval_lists):
    """(window_start, window_end) covering first_epoch, last_epoch, and
    every interval's own start/end, or (None, None) when nothing is
    timestamped at all. A turn_duration record's measured duration can
    reach earlier than the transcript's first record (its own end minus a
    long duration) — that is evidence the session began before its first
    record, not a reason to clamp the measured span. Widening the window
    here is what keeps wall_clock_seconds >= every bucket it is later
    divided into, so the percentages can still reconcile to 100 (AC 1)."""
    points = [epoch for epoch in (first_epoch, last_epoch) if epoch is not None]
    for intervals in interval_lists:
        for start, end in intervals:
            points.append(start)
            points.append(end)
    if not points:
        return None, None
    return min(points), max(points)


def _last_activity_in_window(activity_epochs, window_start, window_end):
    """The latest sorted activity epoch inside [window_start, window_end], or
    window_start when the assistant produced nothing in that window at all —
    so an unanswered message yields a zero-length span rather than one
    reaching to whatever record happens to close the window."""
    index = bisect.bisect_right(activity_epochs, window_end) - 1
    if index < 0 or activity_epochs[index] < window_start:
        return window_start
    return activity_epochs[index]


def _first_away_summary_in_window(away_summary_epochs, window_start, window_end):
    """The earliest sorted away_summary epoch inside [window_start,
    window_end], or None when no away_summary record falls there. Written
    when Claude Code detects the human stepped away, so its own timestamp is
    evidence the assistant had already stopped by then — narrower evidence
    than _last_activity_in_window alone when the assistant's next recorded
    event doesn't land until the human returns, possibly hours later."""
    index = bisect.bisect_left(away_summary_epochs, window_start)
    if index < len(away_summary_epochs) and away_summary_epochs[index] <= window_end:
        return away_summary_epochs[index]
    return None


def _has_interior_activity(activity_epochs, span_start, span_end):
    """Whether any activity epoch falls strictly inside (span_start,
    span_end), excluding both endpoints. A computed span's span_end is
    itself DEFINED by its closing activity epoch (from
    _last_activity_in_window) or by an away_summary marker — that endpoint is
    evidence the turn ended there, never evidence of what happened while it
    ran. A span with no epoch strictly between its own bounds carries only a
    completion marker: the transcript has no record of when the underlying
    API call actually began, so its duration is an estimate, not a
    measurement (Scout #33). Only the FIRST activity epoch after span_start
    needs checking — since activity_epochs is sorted, if that one already
    lands on or past span_end, nothing smaller could be interior either."""
    index = bisect.bisect_right(activity_epochs, span_start)
    return index < len(activity_epochs) and activity_epochs[index] < span_end


def _build_turns(human_epochs, turn_duration_events, last_epoch,
                  activity_epochs, away_summary_epochs):
    """One entry per human turn, each carrying the engaged span used for the
    main-API bucket. When an in-window turn_duration record exists it is
    authoritative (measure="turn_duration"); otherwise the span runs from the
    human message to the assistant's last event inside that turn's window
    (measure="computed"), per the plan's "fall back to a computed span, and
    say which measure produced it" requirement.

    A computed span must end where the assistant stopped producing events, NOT
    at the window's end: the window closes at the NEXT human message (or the
    transcript's last record), so a human who steps away overnight would
    otherwise charge every hour of that absence to main-API time.

    An away_summary record inside that window narrows the span further still:
    it fires when the human is detected as away, so a turn holding only ONE
    assistant record — generated when the human comes back and resumes, not
    while it was produced — would otherwise still bill the whole absence to
    main-API even after the last-activity clamp above. This narrowing never
    applies to the turn_duration branch, whose recorded duration stays
    authoritative regardless of what else the window contains."""
    human_epochs = sorted(human_epochs)
    turn_duration_events = sorted(turn_duration_events)
    turns = []
    for index, start in enumerate(human_epochs):
        window_end = (human_epochs[index + 1] if index + 1 < len(human_epochs)
                      else (last_epoch if last_epoch is not None else start))
        match = next((td for td in turn_duration_events if start < td[0] <= window_end + 1e-6), None)
        if match:
            end_epoch, duration_ms = match
            duration_seconds = duration_ms / 1000.0
            turns.append({
                "index": index, "measure": "turn_duration",
                "duration_seconds": duration_seconds,
                "span_start": end_epoch - duration_seconds, "span_end": end_epoch,
            })
        else:
            last_activity = _last_activity_in_window(activity_epochs, start, window_end)
            first_away_summary = _first_away_summary_in_window(away_summary_epochs, start, window_end)
            span_end = (min(last_activity, first_away_summary)
                       if first_away_summary is not None else last_activity)
            turns.append({
                "index": index, "measure": "computed",
                "duration_seconds": max(0.0, span_end - start),
                "span_start": start, "span_end": span_end,
            })
    return turns


def _percentages_summing_to_100(seconds_by_bucket, total_seconds):
    """Round each bucket's share of total_seconds to a whole percent so the
    buckets sum to exactly 100 (the largest-remainder method) whenever
    total_seconds is nonzero.

    A zero-duration or single-record session has no span to take a share
    of at all, so a percentage of it is undefined rather than "100 split
    some way" — this deliberately returns all-zero (summing to 0, not 100)
    for that one case instead of dividing by zero."""
    if not total_seconds:
        return {name: 0.0 for name in seconds_by_bucket}
    raw = {name: (seconds / total_seconds) * 100 for name, seconds in seconds_by_bucket.items()}
    floors = {name: int(value) for name, value in raw.items()}
    remainder = 100 - sum(floors.values())
    order = sorted(raw, key=lambda name: raw[name] - floors[name], reverse=True)
    for name in order[:remainder]:
        floors[name] += 1
    return {name: float(floors[name]) for name in seconds_by_bucket}


def _subagent_run_label(subagent_path):
    """{"agent_type", "model"} for one subagent run.

    agent_type always comes from <subagent>.meta.json's "agentType" when the
    sidecar is present and readable; "unknown" when the sidecar is missing,
    unreadable, or omits the key — nothing else in the transcript names the
    dispatched subagent_type, so it is never guessed.

    model comes from the sidecar's "model" field ONLY when that field is
    present and non-empty. The fallback fires whenever model is absent or
    empty, independent of whether the sidecar itself loaded — sidecars
    exist for every run on a real session but carry "model" for only 12 of
    39, so gating the fallback on "sidecar missing" (the prior behavior)
    left the other 27 stuck on "unknown" even though the transcript names
    the real model. The fallback model is the LAST "model" carried by the
    subagent transcript's own assistant records (present on every priced
    response even without the sidecar; the LAST one, because a mid-run
    model switch means the run finished on that model), normalized via
    _normalize_model_alias() to the sidecar's own short-alias family so the
    model column never mixes raw ids with aliases. "unknown" only when no
    assistant record in the transcript carries a model at all."""
    agent_type = "unknown"
    model = None
    meta_path = os.path.splitext(subagent_path)[0] + ".meta.json"
    if os.path.isfile(meta_path):
        try:
            with open(meta_path) as fh:
                meta = json.load(fh)
            agent_type = meta.get("agentType") or "unknown"
            model = meta.get("model") or None
        except (OSError, json.JSONDecodeError):
            pass
    if not model:
        model = _normalize_model_alias(_last_transcript_model(subagent_path))
    return {"agent_type": agent_type, "model": model}


def _normalize_model_alias(model):
    """model normalized to the .meta.json sidecar's own short-alias family
    ("opus"/"sonnet"/"haiku"), matched by prefix against the full model ids
    Claude Code's transcripts carry (e.g. "claude-sonnet-5",
    "claude-opus-4-7") — the form _last_transcript_model() returns. An id
    whose prefix isn't recognized (a future model family) is returned
    unchanged rather than guessing a tier; "unknown" (no model found at
    all) passes through unchanged for the same reason."""
    if model.startswith("claude-opus-"):
        return "opus"
    if model.startswith("claude-sonnet-"):
        return "sonnet"
    if model.startswith("claude-haiku-"):
        return "haiku"
    return model


def _last_transcript_model(subagent_path):
    """The `model` on the LAST assistant record that carries one, scanning
    subagent_path's own transcript; "unknown" when none do — the fallback
    source for _subagent_run_label() when the .meta.json sidecar's "model"
    field is absent or empty."""
    model = "unknown"
    for record in usage_report.iter_records(subagent_path):
        record_model = (record.get("message") or {}).get("model")
        if record_model:
            model = record_model
    return model


def list_tasks(sid):
    """The session's tasks from ~/.claude/tasks/<sid>/*.json, ordered by file
    mtime, or a "no tasks tracked" note when the directory is empty or
    absent — never raising either way."""
    tasks_dir = os.path.join(TASKS_ROOT, sid)
    if not os.path.isdir(tasks_dir):
        return {"note": "no tasks tracked", "tasks": []}
    paths = sorted(
        (path for path in (os.path.join(tasks_dir, name) for name in os.listdir(tasks_dir))
         if path.endswith(".json") and os.path.isfile(path)),
        key=os.path.getmtime)
    tasks = []
    for path in paths:
        try:
            with open(path) as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError):
            continue
        tasks.append({
            "id": data.get("id"),
            "subject": data.get("subject"),
            "status": data.get("status"),
        })
    if not tasks:
        return {"note": "no tasks tracked", "tasks": []}
    return {"note": None, "tasks": tasks}


def _attach_turn_index(commits, turns):
    """Main-sourced commits get the index of the turn whose engaged span
    contains them — "attributed to ... the turn ... that ran it" (AC #3).
    Subagent-sourced commits are already attributed by their `source` label."""
    for commit in commits:
        if commit["source"] != "main":
            continue
        epoch = usage_report.parse_ts(commit["timestamp"])
        commit["turn_index"] = next(
            (turn["index"] for turn in turns if turn["span_start"] <= epoch <= turn["span_end"]),
            None)
    return commits


def _build_timeline_entries(turns, tool_spans, commits):
    """The chronological feed of turn/tool_call/commit entries the script is
    named for — sorted by timestamp regardless of which section of the
    payload (turns/buckets/commits) each entry also feeds."""
    entries = []
    for turn in turns:
        entries.append({
            "type": "turn", "timestamp": _iso_from_epoch(turn["span_end"]),
            "index": turn["index"], "duration_seconds": round(turn["duration_seconds"], 1),
            "measure": turn["measure"],
        })
    for start, end, kind in tool_spans:
        entries.append({
            "type": "tool_call", "timestamp": _iso_from_epoch(start),
            "kind": kind, "duration_seconds": round(end - start, 1),
        })
    for commit in commits:
        entries.append({
            "type": "commit", "timestamp": commit["timestamp"],
            "source": commit["source"], "command": commit["command"],
        })
    entries.sort(key=lambda entry: entry["timestamp"] or "")
    return entries


def build_timeline_payload(sid):
    main_path, subagent_paths = resolve_session(sid)

    (main_events, main_activity_epochs, main_away_summary_epochs, main_commits,
     first_epoch, last_epoch) = _extract_raw_events(main_path, "main")
    tool_spans = _pair_tool_spans(main_events)
    turn_duration_events = [(epoch, payload["duration_ms"])
                             for epoch, kind, payload in main_events if kind == "turn_duration"]
    human_epochs = [epoch for epoch, kind, _ in main_events if kind == "human_message"]

    turns = _build_turns(human_epochs, turn_duration_events, last_epoch,
                         main_activity_epochs, main_away_summary_epochs)

    # Subagent scan moved ahead of the partition and reused for BOTH
    # agent_runs and agent_occupied_intervals below — never re-read a
    # subagent transcript twice. Scout #32: agent_occupied must measure each
    # subagent's own first/last event epoch, not the main transcript's
    # dispatch tool_use/tool_result pair, which can close in milliseconds
    # while the subagent it spawned keeps running for hours.
    commit_items = list(main_commits)
    agent_hours_seconds = 0.0
    agent_runs = []
    agent_run_intervals = []
    for subagent_path in subagent_paths:
        label = os.path.splitext(os.path.basename(subagent_path))[0]
        (_sub_events, _sub_activity_epochs, _sub_away_summary_epochs, sub_commits,
         sub_first, sub_last) = _extract_raw_events(subagent_path, label)
        commit_items.extend(sub_commits)
        duration = (max(0.0, sub_last - sub_first)
                    if sub_first is not None and sub_last is not None else 0.0)
        agent_hours_seconds += duration
        if sub_first is not None and sub_last is not None:
            agent_run_intervals.append((sub_first, sub_last))
        label_info = _subagent_run_label(subagent_path)
        agent_runs.append({
            "file": label, "agent_type": label_info["agent_type"], "model": label_info["model"],
            "duration_seconds": round(duration, 1),
        })

    tool_exec_intervals = [(s, e) for s, e, kind in tool_spans if kind == "tool-exec"]
    agent_occupied_intervals = agent_run_intervals
    all_turn_intervals = [(turn["span_start"], turn["span_end"]) for turn in turns]

    # Scout #33: a computed turn with no activity record strictly inside its
    # span carries only the record that closed it — a completion marker, not
    # a start marker — so that time is unmeasurable and must not be billed
    # to main_api. A turn_duration-measured span is never split this way
    # (its recorded duration is authoritative regardless of what the
    # transcript shows inside it, per bd3293ec).
    main_api_intervals = []
    unattributed_intervals = []
    for turn in turns:
        span = (turn["span_start"], turn["span_end"])
        if turn["measure"] == "computed" and not _has_interior_activity(
                main_activity_epochs, turn["span_start"], turn["span_end"]):
            unattributed_intervals.append(span)
        else:
            main_api_intervals.append(span)

    agent_merged = _merge_intervals(agent_occupied_intervals)
    tool_merged = _subtract_intervals(_merge_intervals(tool_exec_intervals), agent_merged)
    exclusions = _merge_intervals(agent_occupied_intervals + tool_exec_intervals)
    main_merged = _subtract_intervals(_merge_intervals(main_api_intervals), exclusions)
    unattributed_merged = _subtract_intervals(_merge_intervals(unattributed_intervals), exclusions)

    agent_seconds = _interval_seconds(agent_merged)
    tool_seconds = _interval_seconds(tool_merged)
    main_seconds = _interval_seconds(main_merged)
    unattributed_seconds = _interval_seconds(unattributed_merged)
    window_start, window_end = _window_bounds(
        first_epoch, last_epoch,
        all_turn_intervals, tool_exec_intervals, agent_occupied_intervals)
    wall_clock_seconds = (max(0.0, window_end - window_start)
                          if window_start is not None else 0.0)
    engaged_seconds = agent_seconds + tool_seconds + main_seconds + unattributed_seconds
    human_idle_seconds = max(0.0, wall_clock_seconds - engaged_seconds)

    seconds_by_bucket = {
        "main_api": main_seconds, "tool_exec": tool_seconds,
        "agent_occupied": agent_seconds, "unattributed": unattributed_seconds,
        "human_idle": human_idle_seconds,
    }
    percentages = _percentages_summing_to_100(seconds_by_bucket, wall_clock_seconds)

    commit_items = _attach_turn_index(commit_items, turns)
    commit_items.sort(key=lambda item: item["timestamp"] or "")

    if len(turns) <= 1:
        turn_ranking = {"too_early_to_rank": True,
                        "note": f"only {len(turns)} turn(s) recorded; nothing to rank yet"}
    else:
        ranked = sorted(turns, key=lambda turn: turn["duration_seconds"], reverse=True)
        turn_ranking = {"too_early_to_rank": False,
                        "ranked_turn_indices": [turn["index"] for turn in ranked]}

    timeline_entries = _build_timeline_entries(turns, tool_spans, commit_items)

    return {
        "sid": sid,
        "local_day": usage_report.local_day(first_epoch) if first_epoch is not None else None,
        "time_partition": {
            "wall_clock_seconds": round(wall_clock_seconds, 1),
            "buckets": {
                name: {"seconds": round(seconds_by_bucket[name], 1), "pct": percentages[name]}
                for name in ("main_api", "tool_exec", "agent_occupied", "unattributed", "human_idle")
            },
            "agent_hours_vs_wall_clock_occupied": {
                "agent_hours_seconds": round(agent_hours_seconds, 1),
                "wall_clock_occupied_seconds": round(agent_seconds, 1),
            },
        },
        "turns": [
            {"index": turn["index"], "duration_seconds": round(turn["duration_seconds"], 1),
             "measure": turn["measure"]}
            for turn in turns
        ],
        "turn_ranking": turn_ranking,
        "tasks": list_tasks(sid),
        "commits": {"items": commit_items, "note": COMMIT_NOTE},
        "agent_runs": agent_runs,
        "timeline": timeline_entries,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Build timeline.json: the time-and-work-done extractor "
                    "for one Claude Code session.")
    parser.add_argument("sid", help="session id, searched under every ~/.claude/projects/*/ directory")
    args = parser.parse_args()
    print(json.dumps(build_timeline_payload(args.sid), indent=2))


if __name__ == "__main__":
    main()
