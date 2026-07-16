#!/usr/bin/env python3
# claude-usage-report - Estimate Claude Code token spend from local transcripts.
#
# Usage:
#   claude-usage-report.py [--days N] [--top N] [--json]
#
# Examples:
#   claude-usage-report.py                # last 7 days, human-readable
#   claude-usage-report.py --days 30      # last 30 days
#   claude-usage-report.py --json         # machine-readable aggregates
#
# Reads every transcript under ~/.claude/projects modified in the window and
# prices each API message at Anthropic LIST prices (PRICES below).
# Answers: where did the spend go — main loop vs subagents, model family,
# day, subagent type, and the costliest sessions.

import argparse
import json
import os
import sys
import time
from collections import defaultdict

TRANSCRIPTS_ROOT = os.path.expanduser("~/.claude/projects")

# Anthropic LIST prices, $/MTok — verified 2026-07-16 against the claude-api skill.
# A stale table skews dollars, not shares — re-verify the numbers when models change.
# family: (input, output, cache_read); cache write = input x1.25 (5m TTL) / x2 (1h TTL).
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


def message_cost(model, usage):
    """Dollar cost of one API message at list prices, split by cache-write TTL."""
    p = PRICES[price_family(model)]
    input_tokens = usage.get("input_tokens", 0) or 0
    output_tokens = usage.get("output_tokens", 0) or 0
    cache_read = usage.get("cache_read_input_tokens", 0) or 0
    breakdown = usage.get("cache_creation") or {}
    write_5m = breakdown.get("ephemeral_5m_input_tokens", 0) or 0
    write_1h = breakdown.get("ephemeral_1h_input_tokens", 0) or 0
    if not breakdown:
        # Older records lack the TTL breakdown; Claude Code uses the 1h cache.
        write_1h = usage.get("cache_creation_input_tokens", 0) or 0
    return (
        input_tokens * p[0]
        + output_tokens * p[1]
        + cache_read * p[2]
        + write_5m * p[0] * 1.25
        + write_1h * p[0] * 2.0
    ) / 1e6


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


def scan_transcript(path):
    """Total cost, per-family cost, per-day cost, and first user prompt of one transcript."""
    total = 0.0
    first_prompt = None
    cost_by_day = defaultdict(float)
    cost_by_family = defaultdict(float)
    for record in iter_records(path):
        message = record.get("message") or {}
        if first_prompt is None and message.get("role") == "user":
            content = message.get("content")
            if isinstance(content, str):
                first_prompt = content[:150]
            elif isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        first_prompt = item["text"][:150]
                        break
        usage = message.get("usage")
        model = message.get("model") or ""
        if not usage or model == "<synthetic>":
            continue
        cost = message_cost(model, usage)
        total += cost
        cost_by_family[price_family(model)] += cost
        cost_by_day[(record.get("timestamp") or "")[:10]] += cost
    return total, cost_by_family, cost_by_day, first_prompt or ""


def match_spawn_type(prompt, session_spawns):
    for spawn_type, prompt_prefix in session_spawns:
        if prompt_prefix and prompt.startswith(prompt_prefix[:100]):
            return spawn_type
    return "UNMATCHED"


def aggregate(main_files, subagent_files):
    spawns = collect_agent_spawns(main_files)
    result = {
        "main_cost": 0.0,
        "subagent_cost": 0.0,
        "by_family": defaultdict(float),
        "by_day": defaultdict(lambda: {"main": 0.0, "sub": 0.0}),
        "by_subagent_type": defaultdict(lambda: {"cost": 0.0, "runs": 0}),
        "sessions": [],
        "subagents_per_session": defaultdict(lambda: {"cost": 0.0, "runs": 0}),
    }
    for path in subagent_files:
        total, by_family, by_day, prompt = scan_transcript(path)
        result["subagent_cost"] += total
        for family, cost in by_family.items():
            result["by_family"][family] += cost
        for day, cost in by_day.items():
            result["by_day"][day]["sub"] += cost
        parent = path.split("/subagents/")[0] + ".jsonl"
        result["subagents_per_session"][parent]["cost"] += total
        result["subagents_per_session"][parent]["runs"] += 1
        spawn_type = match_spawn_type(prompt, spawns.get(parent, []))
        result["by_subagent_type"][spawn_type]["cost"] += total
        result["by_subagent_type"][spawn_type]["runs"] += 1
    for path in main_files:
        total, by_family, by_day, _ = scan_transcript(path)
        result["main_cost"] += total
        for family, cost in by_family.items():
            result["by_family"][family] += cost
        for day, cost in by_day.items():
            result["by_day"][day]["main"] += cost
        result["sessions"].append({"path": path, "cost": total})
    return result


def render_text(result, top_n):
    grand = result["main_cost"] + result["subagent_cost"]
    if grand == 0:
        print("No priced messages found in the window.")
        return
    main_pct = result["main_cost"] / grand * 100
    print(f"TOTAL (list prices): ${grand:.2f}  "
          f"main=${result['main_cost']:.2f} ({main_pct:.0f}%)  "
          f"sub=${result['subagent_cost']:.2f} ({100 - main_pct:.0f}%)")

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

    print(f"\n== TOP {top_n} MAIN SESSIONS (own cost, + their subagents) ==")
    ranked_sessions = sorted(result["sessions"], key=lambda s: -s["cost"])[:top_n]
    for session in ranked_sessions:
        subs = result["subagents_per_session"].get(session["path"], {"cost": 0.0, "runs": 0})
        short_name = session["path"].replace(TRANSCRIPTS_ROOT + "/", "")
        print(f"${session['cost']:.2f}\t(+${subs['cost']:.2f} sub, n={subs['runs']})\t{short_name}")


def render_json(result, top_n):
    grand = result["main_cost"] + result["subagent_cost"]
    ranked_sessions = sorted(result["sessions"], key=lambda s: -s["cost"])[:top_n]
    print(json.dumps({
        "total": round(grand, 2),
        "main_cost": round(result["main_cost"], 2),
        "subagent_cost": round(result["subagent_cost"], 2),
        "by_family": {k: round(v, 2) for k, v in result["by_family"].items()},
        "by_day": {day: {k: round(v, 2) for k, v in split.items()}
                   for day, split in sorted(result["by_day"].items())},
        "by_subagent_type": {k: {"cost": round(v["cost"], 2), "runs": v["runs"]}
                             for k, v in result["by_subagent_type"].items()},
        "top_sessions": [{
            "path": s["path"],
            "cost": round(s["cost"], 2),
            "subagent_cost": round(result["subagents_per_session"].get(s["path"], {"cost": 0.0})["cost"], 2),
        } for s in ranked_sessions],
    }, indent=2))


def main():
    parser = argparse.ArgumentParser(
        description="Estimate Claude Code token spend from ~/.claude/projects transcripts "
                    "(list prices; shares matter more than absolute dollars).")
    parser.add_argument("--days", type=int, default=7, help="lookback window in days (default: 7)")
    parser.add_argument("--top", type=int, default=8, help="how many top sessions to show (default: 8)")
    parser.add_argument("--json", action="store_true", help="emit machine-readable aggregates")
    args = parser.parse_args()

    if not os.path.isdir(TRANSCRIPTS_ROOT):
        print(f"transcripts dir not found: {TRANSCRIPTS_ROOT}", file=sys.stderr)
        sys.exit(1)

    cutoff = time.time() - args.days * 86400
    main_files, subagent_files = find_transcripts(cutoff)
    if not main_files and not subagent_files:
        print(f"No transcripts modified in the last {args.days} days.")
        return

    result = aggregate(main_files, subagent_files)
    if args.json:
        render_json(result, args.top)
    else:
        print(f"window: last {args.days} days · files: {len(main_files)} main + {len(subagent_files)} subagent\n")
        render_text(result, args.top)


if __name__ == "__main__":
    main()
