#!/usr/bin/env python3
# claude-usage-report - Estimate Claude Code token spend from local transcripts.
#
# Usage:
#   claude-usage-report.py [--days N] [--top N] [--json] [--snapshot]
#
# Examples:
#   claude-usage-report.py                # last 7 days, human-readable
#   claude-usage-report.py --days 30      # last 30 days
#   claude-usage-report.py --json         # machine-readable aggregates
#   claude-usage-report.py --snapshot     # also persist to ../usage-history/snapshots/
#
# Reads every transcript under ~/.claude/projects modified in the window and
# prices each API message at Anthropic LIST prices (PRICES below).
# Answers: where did the spend go — main loop vs subagents, model family,
# day, subagent type, skill, and the costliest sessions.

import argparse
import json
import os
import re
import sys
import time
from collections import defaultdict
from datetime import datetime

TRANSCRIPTS_ROOT = os.path.expanduser("~/.claude/projects")
# realpath resolves the ~/.claude symlink so snapshots land in the repo checkout.
HISTORY_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "usage-history"))

TOKEN_KINDS = ("input", "output", "cache_read", "cache_write_5m", "cache_write_1h")
# The literal record Claude Code writes when the user presses Escape mid-turn.
INTERRUPT_SENTINEL = "[Request interrupted by user"
# Slash-command invocations land in user records as <command-name>/x</command-name>;
# plugin skills can carry a colon (plugin:skill).
COMMAND_NAME_RE = re.compile(r"<command-name>/?([\w:-]+)</command-name>")
# Built-in commands are told apart structurally: the record after theirs
# carries <local-command-stdout>. These built-ins emit no stdout record,
# so the structural filter can't catch them — exclude by name.
BUILTIN_SILENT_COMMANDS = {"clear", "compact", "login", "logout"}

# Anthropic LIST prices, $/MTok — verified 2026-07-23 against the claude-api skill.
# A stale table skews dollars, not shares — re-verify the numbers when models change.
# family: (input, output, cache_read); cache write = input x1.25 (5m TTL) / x2 (1h TTL).
# Sonnet 5 has an intro rate ($2.00/$10.00) through 2026-08-31; this table uses
# the flat post-intro $3.00/$15.00 bucket, so sonnet dollars run slightly high
# until that date.
PRICES = {
    "fable": (10.0, 50.0, 1.00),
    "opus": (5.0, 25.0, 0.50),
    "sonnet": (3.0, 15.0, 0.30),
    "haiku": (1.0, 5.0, 0.10),
}


def price_family(model):
    m = (model or "").lower()
    if "fable" in m or "mythos" in m:
        return "fable"
    for family in ("opus", "sonnet", "haiku"):
        if family in m:
            return family
    return "sonnet"


def cache_writes(usage):
    """(5m, 1h) cache-write token counts of one usage record."""
    breakdown = usage.get("cache_creation") or {}
    write_5m = breakdown.get("ephemeral_5m_input_tokens", 0) or 0
    write_1h = breakdown.get("ephemeral_1h_input_tokens", 0) or 0
    if not breakdown:
        # Older records lack the TTL breakdown; Claude Code uses the 1h cache.
        write_1h = usage.get("cache_creation_input_tokens", 0) or 0
    return write_5m, write_1h


def message_cost(model, usage):
    """Dollar cost of one API message at list prices, split by cache-write TTL."""
    p = PRICES[price_family(model)]
    input_tokens = usage.get("input_tokens", 0) or 0
    output_tokens = usage.get("output_tokens", 0) or 0
    cache_read = usage.get("cache_read_input_tokens", 0) or 0
    write_5m, write_1h = cache_writes(usage)
    return (
        input_tokens * p[0]
        + output_tokens * p[1]
        + cache_read * p[2]
        + write_5m * p[0] * 1.25
        + write_1h * p[0] * 2.0
    ) / 1e6


def parse_ts(iso_timestamp):
    """ISO-8601 timestamp string -> epoch seconds, or None on absent/malformed."""
    if not iso_timestamp:
        return None
    try:
        return datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def find_transcripts(cutoff_epoch):
    """All .jsonl transcripts modified since cutoff, split main vs subagent."""
    main_files, subagent_files = [], []
    for dirpath, _, names in os.walk(TRANSCRIPTS_ROOT):
        for name in names:
            if not name.endswith(".jsonl"):
                continue
            path = os.path.join(dirpath, name)
            try:
                if os.path.getmtime(path) < cutoff_epoch:
                    continue
            except OSError:
                continue
            if "/subagents/" in path:
                subagent_files.append(path)
            else:
                main_files.append(path)
    return main_files, subagent_files


def iter_records(path):
    try:
        with open(path, errors="replace") as fh:
            for line in fh:
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue
    except OSError as err:
        print(f"skipping unreadable {path}: {err}", file=sys.stderr)


def collect_agent_spawns(main_files):
    """session file -> [(subagent_type, prompt prefix)] for subagent attribution."""
    spawns = defaultdict(list)
    for path in main_files:
        for record in iter_records(path):
            content = (record.get("message") or {}).get("content")
            if not isinstance(content, list):
                continue
            for item in content:
                is_spawn = isinstance(item, dict) and item.get("type") == "tool_use" and item.get("name") in ("Task", "Agent")
                if not is_spawn:
                    continue
                spawn_input = item.get("input") or {}
                spawns[path].append((
                    spawn_input.get("subagent_type") or "general-purpose",
                    (spawn_input.get("prompt") or "")[:150],
                ))
    return spawns


def is_human_message(record, content):
    """True when a user record is a typed human turn, not a tool result or harness meta."""
    if record.get("isMeta") or record.get("isCompactSummary"):
        return False
    if isinstance(content, str):
        return True
    if not isinstance(content, list):
        return False
    has_text = any(isinstance(i, dict) and i.get("type") == "text" for i in content)
    has_tool_result = any(isinstance(i, dict) and i.get("type") == "tool_result" for i in content)
    return has_text and not has_tool_result


def first_text(content):
    """First text payload of a user record: the string itself or its first text block."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                return item.get("text") or ""
    return ""


def iter_text_payloads(content):
    """Every text payload of a record, whether content is a string or a block list."""
    if isinstance(content, str):
        yield content
    elif isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                yield item.get("text") or ""


def scan_transcript(path, cutoff_epoch):
    """Cost, tokens, call/turn counters, skills, and wall-clock bounds of one transcript.

    A file can clear the mtime-based find_transcripts() gate (touched recently)
    while still holding much older records (a long-running/resumed session) —
    skip any record timestamped before cutoff_epoch so those don't leak into
    a nominal N-day window.
    """
    stats = {
        "cost": 0.0,
        "by_family": defaultdict(float),
        "by_day": defaultdict(float),
        "first_prompt": "",
        "title": "",
        "api_calls": 0,
        "tokens": dict.fromkeys(TOKEN_KINDS, 0),
        "thinking_blocks": 0,
        "text_blocks": 0,
        "user_messages": 0,
        "interruptions": 0,
        "compactions": 0,
        "skills": defaultdict(int),
        "first_epoch": None,
        "last_epoch": None,
    }
    # Commands seen but not yet classified as skill vs built-in;
    # settled by the NEXT user record (see the deferral below).
    pending_commands = []
    for record in iter_records(path):
        epoch = parse_ts(record.get("timestamp"))
        if epoch is not None and epoch < cutoff_epoch:
            continue
        if record.get("subtype") == "compact_boundary":
            stats["compactions"] += 1
        # Claude Code writes an auto-generated title as this session
        # progresses; the transcript's last one is the final title.
        if record.get("type") == "ai-title" and record.get("aiTitle"):
            stats["title"] = record["aiTitle"]
        if epoch is not None:
            if stats["first_epoch"] is None or epoch < stats["first_epoch"]:
                stats["first_epoch"] = epoch
            if stats["last_epoch"] is None or epoch > stats["last_epoch"]:
                stats["last_epoch"] = epoch
        message = record.get("message") or {}
        content = message.get("content")
        if message.get("role") == "user":
            # Command-name tags also appear in meta/local-command records,
            # so scan every user record, not just typed human turns.
            #
            # A built-in command's record is immediately followed by a
            # <local-command-stdout> user record; a skill invocation's
            # never is. Defer counting each command until the next user
            # record settles which kind it was.
            texts = list(iter_text_payloads(content))
            is_stdout_record = any("<local-command-stdout>" in t for t in texts)
            if not is_stdout_record:
                for name in pending_commands:
                    stats["skills"][name] += 1
            pending_commands.clear()
            if not is_stdout_record:
                for text in texts:
                    for name in COMMAND_NAME_RE.findall(text):
                        if name not in BUILTIN_SILENT_COMMANDS:
                            pending_commands.append(name)
        if message.get("role") == "user" and is_human_message(record, content):
            text = first_text(content)
            # An Escape press is a correction event, not a typed turn — count it apart.
            if text.startswith(INTERRUPT_SENTINEL):
                stats["interruptions"] += 1
            else:
                stats["user_messages"] += 1
                if not stats["first_prompt"]:
                    stats["first_prompt"] = text[:150]
        if message.get("role") == "assistant" and isinstance(content, list):
            for item in content:
                if not isinstance(item, dict):
                    continue
                # Transcripts persist thinking blocks with EMPTY text (signature only),
                # so block counts are the only locally measurable thinking signal;
                # the thinking tokens themselves hide inside usage.output_tokens.
                if item.get("type") == "thinking":
                    stats["thinking_blocks"] += 1
                elif item.get("type") == "text":
                    stats["text_blocks"] += 1
                elif item.get("type") == "tool_use" and item.get("name") == "Skill":
                    skill = (item.get("input") or {}).get("skill")
                    if skill:
                        stats["skills"][skill] += 1
        usage = message.get("usage")
        model = message.get("model") or ""
        if not usage or model == "<synthetic>":
            continue
        stats["api_calls"] += 1
        write_5m, write_1h = cache_writes(usage)
        stats["tokens"]["input"] += usage.get("input_tokens", 0) or 0
        stats["tokens"]["output"] += usage.get("output_tokens", 0) or 0
        stats["tokens"]["cache_read"] += usage.get("cache_read_input_tokens", 0) or 0
        stats["tokens"]["cache_write_5m"] += write_5m
        stats["tokens"]["cache_write_1h"] += write_1h
        cost = message_cost(model, usage)
        stats["cost"] += cost
        stats["by_family"][price_family(model)] += cost
        stats["by_day"][(record.get("timestamp") or "")[:10]] += cost
    # A command at end-of-file has no follower to disprove it — count it.
    for name in pending_commands:
        stats["skills"][name] += 1
    return stats


def match_spawn_type(prompt, session_spawns):
    for spawn_type, prompt_prefix in session_spawns:
        if prompt_prefix and prompt.startswith(prompt_prefix[:100]):
            return spawn_type
    return "UNMATCHED"


def merge_common(result, stats, side):
    """Fold one transcript's family/day/token/char counters into the aggregate."""
    result["api_calls"][side] += stats["api_calls"]
    result["thinking_blocks"] += stats["thinking_blocks"]
    result["text_blocks"] += stats["text_blocks"]
    for family, cost in stats["by_family"].items():
        result["by_family"][family] += cost
    for day, cost in stats["by_day"].items():
        result["by_day"][day][side] += cost
    for kind in TOKEN_KINDS:
        result["tokens"][kind] += stats["tokens"][kind]


def session_duration(stats):
    """Wall-clock seconds from first to last record (includes idle gaps)."""
    if stats["first_epoch"] is None or stats["last_epoch"] is None:
        return 0.0
    return max(0.0, stats["last_epoch"] - stats["first_epoch"])


def aggregate(main_files, subagent_files, cutoff_epoch):
    spawns = collect_agent_spawns(main_files)
    result = {
        "main_cost": 0.0,
        "subagent_cost": 0.0,
        "by_family": defaultdict(float),
        "by_day": defaultdict(lambda: {"main": 0.0, "sub": 0.0}),
        "by_subagent_type": defaultdict(lambda: {"cost": 0.0, "runs": 0}),
        "by_skill": defaultdict(lambda: {
            "cost": 0.0, "invocations": 0, "sessions": 0,
            "compactions": 0, "interruptions": 0,
            "tokens": dict.fromkeys(TOKEN_KINDS, 0),
        }),
        "sessions": [],
        "subagents_per_session": defaultdict(lambda: {
            "cost": 0.0, "runs": 0, "tokens": dict.fromkeys(TOKEN_KINDS, 0),
        }),
        "api_calls": {"main": 0, "sub": 0},
        "tokens": dict.fromkeys(TOKEN_KINDS, 0),
        "thinking_blocks": 0,
        "text_blocks": 0,
        "user_messages": 0,
        "interruptions": 0,
        "compactions": 0,
        "session_seconds": 0.0,
    }
    for path in subagent_files:
        stats = scan_transcript(path, cutoff_epoch)
        result["subagent_cost"] += stats["cost"]
        merge_common(result, stats, "sub")
        parent = path.split("/subagents/")[0] + ".jsonl"
        result["subagents_per_session"][parent]["cost"] += stats["cost"]
        result["subagents_per_session"][parent]["runs"] += 1
        for kind in TOKEN_KINDS:
            result["subagents_per_session"][parent]["tokens"][kind] += stats["tokens"][kind]
        spawn_type = match_spawn_type(stats["first_prompt"], spawns.get(parent, []))
        result["by_subagent_type"][spawn_type]["cost"] += stats["cost"]
        result["by_subagent_type"][spawn_type]["runs"] += 1
    for path in main_files:
        stats = scan_transcript(path, cutoff_epoch)
        result["main_cost"] += stats["cost"]
        merge_common(result, stats, "main")
        duration = session_duration(stats)
        # Human turns and compactions only make sense in main sessions;
        # a subagent's "user" records are its spawn prompt and tool results.
        result["user_messages"] += stats["user_messages"]
        result["interruptions"] += stats["interruptions"]
        result["compactions"] += stats["compactions"]
        result["session_seconds"] += duration
        # A session counts under EVERY skill it invoked, so by_skill rows
        # overlap and don't sum to the total — they isolate, not partition.
        session_subagents = result["subagents_per_session"].get(
            path, {"cost": 0.0, "tokens": dict.fromkeys(TOKEN_KINDS, 0)})
        for skill, invocation_count in stats["skills"].items():
            entry = result["by_skill"][skill]
            entry["cost"] += stats["cost"] + session_subagents["cost"]
            entry["invocations"] += invocation_count
            entry["sessions"] += 1
            entry["compactions"] += stats["compactions"]
            entry["interruptions"] += stats["interruptions"]
            for kind in TOKEN_KINDS:
                entry["tokens"][kind] += stats["tokens"][kind] + session_subagents["tokens"][kind]
        priced_input = (stats["tokens"]["cache_read"] + stats["tokens"]["input"]
                        + stats["tokens"]["cache_write_5m"] + stats["tokens"]["cache_write_1h"])
        result["sessions"].append({
            "path": path,
            "title": stats["title"],
            "cost": stats["cost"],
            "api_calls": stats["api_calls"],
            "duration_s": duration,
            "compactions": stats["compactions"],
            "user_messages": stats["user_messages"],
            "interruptions": stats["interruptions"],
            "tokens": dict(stats["tokens"]),
            "cache_hit_rate": stats["tokens"]["cache_read"] / priced_input if priced_input else 0.0,
            "skills": dict(sorted(stats["skills"].items())),
        })
    return result


def derived_metrics(result):
    """Ratios and KPI-level rollups computed from the raw aggregate."""
    tokens = result["tokens"]
    priced_input = (tokens["cache_read"] + tokens["input"]
                    + tokens["cache_write_5m"] + tokens["cache_write_1h"])
    assistant_blocks = result["thinking_blocks"] + result["text_blocks"]
    grand = result["main_cost"] + result["subagent_cost"]
    return {
        "cache_hit_rate": tokens["cache_read"] / priced_input if priced_input else 0.0,
        "thinking_block_share": result["thinking_blocks"] / assistant_blocks if assistant_blocks else 0.0,
        "session_count": len(result["sessions"]),
        "session_hours": result["session_seconds"] / 3600,
        "api_calls": result["api_calls"]["main"] + result["api_calls"]["sub"],
        "cost_per_user_message": grand / result["user_messages"] if result["user_messages"] else 0.0,
    }


def render_text(result, top_n):
    grand = result["main_cost"] + result["subagent_cost"]
    if grand == 0:
        print("No priced messages found in the window.")
        return
    derived = derived_metrics(result)
    main_pct = result["main_cost"] / grand * 100
    print(f"TOTAL (list prices): ${grand:.2f}  "
          f"main=${result['main_cost']:.2f} ({main_pct:.0f}%)  "
          f"sub=${result['subagent_cost']:.2f} ({100 - main_pct:.0f}%)")

    print("\n== SESSION HEALTH (main sessions) ==")
    print(f"sessions={derived['session_count']}  wall-clock={derived['session_hours']:.1f}h  "
          f"api_calls={derived['api_calls']} (main={result['api_calls']['main']}, sub={result['api_calls']['sub']})")
    print(f"compactions={result['compactions']}  user_messages={result['user_messages']}  "
          f"interruptions={result['interruptions']}  "
          f"cost/user_message=${derived['cost_per_user_message']:.2f}")

    tokens = result["tokens"]
    print("\n== TOKENS (window totals) ==")
    for kind in TOKEN_KINDS:
        print(f"{kind}\t{tokens[kind]:,}")
    print(f"cache hit rate: {derived['cache_hit_rate']:.1%}  "
          f"thinking blocks: {result['thinking_blocks']:,} "
          f"({derived['thinking_block_share']:.1%} of assistant blocks; "
          f"thinking tokens hide inside output_tokens)")

    print("\n== BY MODEL FAMILY ==")
    for family, cost in sorted(result["by_family"].items(), key=lambda kv: -kv[1]):
        print(f"{family}\t${cost:.2f}")

    print("\n== BY DAY (main / sub) ==")
    for day in sorted(result["by_day"]):
        split = result["by_day"][day]
        print(f"{day}\tmain=${split['main']:.0f}\tsub=${split['sub']:.0f}"
              f"\ttotal=${split['main'] + split['sub']:.0f}")

    print("\n== BY SUBAGENT TYPE ==")
    ranked_types = sorted(result["by_subagent_type"].items(), key=lambda kv: -kv[1]["cost"])
    for spawn_type, stats in ranked_types:
        avg = stats["cost"] / max(stats["runs"], 1)
        print(f"{spawn_type}\t${stats['cost']:.2f}\tn={stats['runs']}\tavg=${avg:.2f}")

    print("\n== BY SKILL (session own+sub cost/tokens; rows overlap — a session "
          "counts under every skill it invoked, so avg inherits whole-session cost) ==")
    ranked_skills = sorted(result["by_skill"].items(), key=lambda kv: -kv[1]["cost"])
    for skill, stats in ranked_skills:
        avg = stats["cost"] / max(stats["invocations"], 1)
        total_tokens = sum(stats["tokens"].values())
        print(f"{skill}\t${stats['cost']:.2f}\tn={stats['invocations']}\tavg=${avg:.2f}\t"
              f"tokens={total_tokens:,}\tsessions={stats['sessions']}\t"
              f"compactions={stats['compactions']}\tinterruptions={stats['interruptions']}")

    print(f"\n== TOP {top_n} MAIN SESSIONS (own cost, + their subagents) ==")
    ranked_sessions = sorted(result["sessions"], key=lambda s: -s["cost"])[:top_n]
    for session in ranked_sessions:
        subs = result["subagents_per_session"].get(session["path"], {"cost": 0.0, "runs": 0})
        short_name = session["path"].replace(TRANSCRIPTS_ROOT + "/", "")
        title = session["title"] or "(no ai-title recorded)"
        total_tokens = sum(session["tokens"].values())
        print(f"${session['cost']:.2f}\t(+${subs['cost']:.2f} sub, n={subs['runs']})\t"
              f"{session['duration_s'] / 3600:.1f}h\tcompactions={session['compactions']}\t"
              f"user_msgs={session['user_messages']}\t{title}")
        print(f"\ttokens={total_tokens:,} (out={session['tokens']['output']:,})\t"
              f"cache_hit={session['cache_hit_rate']:.1%}\t{short_name}")


def build_payload(result, top_n, window_days):
    """The machine-readable aggregate — shared by --json and --snapshot."""
    grand = result["main_cost"] + result["subagent_cost"]
    derived = derived_metrics(result)
    ranked_sessions = sorted(result["sessions"], key=lambda s: -s["cost"])[:top_n]
    return {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "window_days": window_days,
        "kpis": {
            "cost_per_day": round(grand / window_days, 2) if window_days else 0.0,
            "user_messages": result["user_messages"],
            "interruptions": result["interruptions"],
            "session_hours": round(derived["session_hours"], 1),
            "cost_per_user_message": round(derived["cost_per_user_message"], 2),
        },
        "total": round(grand, 2),
        "main_cost": round(result["main_cost"], 2),
        "subagent_cost": round(result["subagent_cost"], 2),
        "api_calls": dict(result["api_calls"]),
        "compactions": result["compactions"],
        "session_count": derived["session_count"],
        "cache_hit_rate": round(derived["cache_hit_rate"], 3),
        "thinking_blocks": result["thinking_blocks"],
        "text_blocks": result["text_blocks"],
        "thinking_block_share": round(derived["thinking_block_share"], 3),
        "tokens": dict(result["tokens"]),
        "by_family": {k: round(v, 2) for k, v in result["by_family"].items()},
        "by_day": {day: {k: round(v, 2) for k, v in split.items()}
                   for day, split in sorted(result["by_day"].items())},
        "by_subagent_type": {k: {"cost": round(v["cost"], 2), "runs": v["runs"]}
                             for k, v in result["by_subagent_type"].items()},
        # Rows overlap — a session counts under every skill it invoked.
        "by_skill": {k: {"cost": round(v["cost"], 2), "invocations": v["invocations"],
                         "sessions": v["sessions"], "compactions": v["compactions"],
                         "interruptions": v["interruptions"], "tokens": dict(v["tokens"])}
                     for k, v in sorted(result["by_skill"].items(),
                                        key=lambda kv: -kv[1]["cost"])},
        "top_sessions": [{
            "path": s["path"],
            "title": s["title"],
            "cost": round(s["cost"], 2),
            "subagent_cost": round(result["subagents_per_session"].get(s["path"], {"cost": 0.0})["cost"], 2),
            "api_calls": s["api_calls"],
            "duration_hours": round(s["duration_s"] / 3600, 1),
            "compactions": s["compactions"],
            "user_messages": s["user_messages"],
            "interruptions": s["interruptions"],
            "tokens": s["tokens"],
            "cache_hit_rate": round(s["cache_hit_rate"], 3),
            "skills": s["skills"],
        } for s in ranked_sessions],
    }


def write_snapshot(payload):
    """Persist the aggregate to the committed usage-history folder; latest same-day run wins."""
    snapshots_dir = os.path.join(HISTORY_DIR, "snapshots")
    os.makedirs(snapshots_dir, exist_ok=True)
    path = os.path.join(snapshots_dir, f"{time.strftime('%Y-%m-%d')}.json")
    with open(path, "w") as fh:
        json.dump(payload, fh, indent=2)
        fh.write("\n")
    print(f"snapshot written: {path}")


def main():
    parser = argparse.ArgumentParser(
        description="Estimate Claude Code token spend from ~/.claude/projects transcripts "
                    "(list prices; shares matter more than absolute dollars).")
    parser.add_argument("--days", type=int, default=7, help="lookback window in days (default: 7)")
    parser.add_argument("--top", type=int, default=8, help="how many top sessions to show (default: 8)")
    parser.add_argument("--json", action="store_true", help="emit machine-readable aggregates")
    parser.add_argument("--snapshot", action="store_true",
                        help="also write the aggregates to usage-history/snapshots/YYYY-MM-DD.json")
    args = parser.parse_args()

    if not os.path.isdir(TRANSCRIPTS_ROOT):
        print(f"transcripts dir not found: {TRANSCRIPTS_ROOT}", file=sys.stderr)
        sys.exit(1)

    cutoff = time.time() - args.days * 86400
    main_files, subagent_files = find_transcripts(cutoff)
    if not main_files and not subagent_files:
        print(f"No transcripts modified in the last {args.days} days.")
        return

    result = aggregate(main_files, subagent_files, cutoff)
    if args.json:
        print(json.dumps(build_payload(result, args.top, args.days), indent=2))
    else:
        print(f"window: last {args.days} days · files: {len(main_files)} main + {len(subagent_files)} subagent\n")
        render_text(result, args.top)
    if args.snapshot:
        write_snapshot(build_payload(result, args.top, args.days))


if __name__ == "__main__":
    main()
