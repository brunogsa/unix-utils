#!/usr/bin/env python3
# claude-usage-report - Estimate Claude Code token spend from local transcripts.
#
# Usage:
#   claude-usage-report.py --backfill              # write a snapshot per missing closed day
#   claude-usage-report.py --backfill --rebuild    # also redo days already snapshotted
#   claude-usage-report.py --day YYYY-MM-DD        # one calendar day
#   claude-usage-report.py [--days N] [--top N]    # ad-hoc rolling window (never snapshots)
#   claude-usage-report.py --json                  # machine-readable aggregates
#   claude-usage-report.py --session SID --json    # one session id (never snapshots)
#
# Reads every transcript under ~/.claude/projects and prices each API response at
# Anthropic LIST prices (MODEL_PRICES below). Answers: where did the spend go —
# main loop vs subagents, model family, day, subagent type, skill (both
# whole-session and marginal/non-overlapping), and the costliest sessions.
#
# "Response", not "record": one API response is written as one transcript record
# PER CONTENT BLOCK, each stamped with the same message.usage, so summing records
# bills a response once per block it emitted. See billing_id() — this went
# unnoticed long enough to inflate every snapshot written before 2026-07-27.
# Every snapshot now carries a ccusage token cross-check so it cannot recur
# silently; see the reconcile_tokens() block for why tokens and not dollars.
#
# The committed record is one snapshot per CLOSED LOCAL CALENDAR DAY. That unit
# is what makes the history comparable, and each property below was a live bug
# in the previous rolling-window design:
#   - Immutable: a day's aggregate never changes once the day is over, so a
#     backfilled day equals a day captured live. Windows captured mid-day did
#     not — 2026-07-24 read $49 when sampled at 21:49 that day vs $413 once closed.
#   - Non-overlapping: window snapshots double-counted. The 7-day 2026-07-25
#     snapshot fully contained both the 2026-07-19 and 2026-07-23 snapshots, so
#     every "before -> after" delta between them compared a set to its superset.
#   - Self-dividing: cost_per_day is just the day's total, so the old divisor bug
#     (total / nominal window_days, while cost spanned window_days + 1 buckets)
#     cannot recur. It had inflated the 2026-07-19 snapshot 2x.
#   - LOCAL, not UTC: bucketing on the raw UTC timestamp prefix misfiled 44.2%
#     of priced records (12,693 sampled) for a UTC-3 user who works evenings.

import argparse
import bisect
import glob
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import time
from collections import defaultdict
from datetime import date, datetime, timedelta

TRANSCRIPTS_ROOT = os.path.expanduser("~/.claude/projects")
# realpath resolves the ~/.claude symlink so snapshots land in the repo checkout.
HISTORY_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "usage-history"))


def _load_personal_env():
    """The ledger's PERSONAL_ENV tuple, imported by file path.

    Its filename has dashes, so it is not importable as a
    module name and needs the spec dance below.

    Failing loudly beats defaulting: a silent fallback list
    would drift from the ledger's, and the two would then
    disagree about which spend has a PR denominator at all.
    """
    path = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                        "delivered-work-ledger.py")
    spec = importlib.util.spec_from_file_location("delivered_work_ledger", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load PERSONAL_ENV from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.PERSONAL_ENV


TOKEN_KINDS = ("input", "output", "cache_read", "cache_write_5m", "cache_write_1h")
# Read from the ledger rather than restated here, so the
# spend split and the delivered-work denominator can never
# disagree about which repos count as tooling.
PERSONAL_ENV = _load_personal_env()
REPO_CLASSES = ("work", "tooling")
# The literal record Claude Code writes when the user presses Escape mid-turn.
INTERRUPT_SENTINEL = "[Request interrupted by user"
# Slash-command invocations land in user records as <command-name>/x</command-name>;
# plugin skills can carry a colon (plugin:skill).
COMMAND_NAME_RE = re.compile(r"<command-name>/?([\w:-]+)</command-name>")
# Built-in commands are told apart structurally: the record after theirs
# carries <local-command-stdout>. These built-ins emit no stdout record,
# so the structural filter can't catch them — exclude by name.
BUILTIN_SILENT_COMMANDS = {"clear", "compact", "login", "logout"}
# A/B experiment markers a skill prints into chat (e.g. pr-review's
# review-isolation experiment), landing verbatim in assistant text blocks:
#   [ABTest] experiment=review-isolation arm=A pr=123
#   [ABTest] experiment=review-isolation arm=B pr=124 override=manual
# experiment/arm are opaque tokens — the parser never hardcodes a slug or arm
# name, so any future experiment using this shape parses for free.
AB_MARKER_RE = re.compile(
    r"\[ABTest\] experiment=(\S+) arm=(\S+) pr=(\d+)(?: override=(manual))?")

# Anthropic LIST prices, $/MTok — verified 2026-07-27 against
# platform.claude.com/docs/en/about-claude/pricing.
# (input, output, cache_read); cache write = input x1.25 (5m TTL) / x2 (1h TTL).
#
# Keyed by EXACT model, not by family. Family-level pricing was wrong in two
# directions at once: Sonnet 5 bills below its family during its intro window,
# and Opus bills DOUBLE its family under fast mode. Both are handled below.
#
# The generic family bucket survives only as the fallback for a model released
# after this table was written — a new model prices at its family's rate rather
# than crashing, and shows up in by_family so the omission is visible.
FAMILY_PRICES = {
    "fable": (10.0, 50.0, 1.00),
    "opus": (5.0, 25.0, 0.50),
    "sonnet": (3.0, 15.0, 0.30),
    "haiku": (1.0, 5.0, 0.10),
}
MODEL_PRICES = {
    "claude-fable-5": (10.0, 50.0, 1.00),
    "claude-mythos-5": (10.0, 50.0, 1.00),
    "claude-opus-5": (5.0, 25.0, 0.50),
    "claude-opus-4-8": (5.0, 25.0, 0.50),
    "claude-opus-4-7": (5.0, 25.0, 0.50),
    "claude-opus-4-6": (5.0, 25.0, 0.50),
    "claude-opus-4-5": (5.0, 25.0, 0.50),
    "claude-sonnet-5": (3.0, 15.0, 0.30),
    "claude-sonnet-4-6": (3.0, 15.0, 0.30),
    "claude-sonnet-4-5": (3.0, 15.0, 0.30),
    "claude-haiku-4-5": (1.0, 5.0, 0.10),
}

# Sonnet 5 launched on an introductory rate. It is a real discount on real days
# already in the snapshot series, so pricing those days at the post-intro rate
# overstates them by 50% — the largest single model in this workload.
SONNET_5_INTRO_PRICES = (2.0, 10.0, 0.20)
SONNET_5_INTRO_LAST_DAY = "2026-08-31"

# Fast mode bills Opus 5 / Opus 4.8 at double list. Nothing in the token counts
# reveals it; only usage.speed does, so a fast-mode day would silently read as a
# standard-mode day at half the true cost.
FAST_MODE_PRICES = (10.0, 50.0, 1.00)
FAST_MODE_MODELS = {"claude-opus-5", "claude-opus-4-8"}

# Model ids carry an optional release-date suffix (claude-haiku-4-5-20251001).
MODEL_DATE_SUFFIX_RE = re.compile(r"-\d{8}$")


def model_key(model):
    """Model id stripped of its release-date suffix, for price lookup."""
    return MODEL_DATE_SUFFIX_RE.sub("", (model or "").strip().lower())


def price_family(model):
    m = (model or "").lower()
    if "fable" in m or "mythos" in m:
        return "fable"
    for family in ("opus", "sonnet", "haiku"):
        if family in m:
            return family
    return "sonnet"


def message_rates(model, day, speed):
    """(input, output, cache_read) $/MTok for one message, given its day and speed."""
    key = model_key(model)
    if speed == "fast" and key in FAST_MODE_MODELS:
        return FAST_MODE_PRICES
    if key == "claude-sonnet-5" and day and day <= SONNET_5_INTRO_LAST_DAY:
        return SONNET_5_INTRO_PRICES
    return MODEL_PRICES.get(key) or FAMILY_PRICES[price_family(model)]


def billing_id(record, message):
    """The key identifying ONE billed API response, or None when unidentifiable.

    `uuid` cannot serve here: it is unique per transcript LINE, and one response
    writes one line per content block. `message.id` is the API's own response id,
    and `requestId` disambiguates the retry case where a response is re-delivered
    under a fresh request. A record missing either is counted rather than dropped
    — over-counting a rare malformed record beats silently deleting real spend.
    """
    message_id = message.get("id")
    request_id = record.get("requestId")
    if not message_id or not request_id:
        return None
    return (message_id, request_id)


def cache_writes(usage):
    """(5m, 1h) cache-write token counts of one usage record.

    The `cache_creation` breakdown is authoritative, not the flat
    `cache_creation_input_tokens` beside it, which a minority of
    records zero out while the breakdown keeps the real figure.

    Those records carry every flat field at 0 and an `iterations`
    entry of type `message` holding the true usage, so trusting the
    flat total drops their cache writes entirely.

    Reading the breakdown instead reconciles cache_write to 0.0000%
    against ccusage on all 28 retained days (measured 2026-08-09).
    Trusting the flat total left 4 of them drifting up to 2.5%, in
    BOTH directions — the sign varies because some records zero the
    total while others carry one the breakdown no longer matches.

    The split also decides price, not just the count: the two TTLs
    bill at 1.25x and 2x input.
    """
    breakdown = usage.get("cache_creation") or {}
    write_5m = breakdown.get("ephemeral_5m_input_tokens", 0) or 0
    write_1h = breakdown.get("ephemeral_1h_input_tokens", 0) or 0
    if write_5m or write_1h:
        return write_5m, write_1h
    # No breakdown at all — older records predate the field, and
    # Claude Code writes to the 1h cache.
    return 0, usage.get("cache_creation_input_tokens", 0) or 0


def message_cost(model, usage, day=None):
    """Dollar cost of one API message at list prices, split by cache-write TTL."""
    p = message_rates(model, day, usage.get("speed"))
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


def repo_class(cwd):
    """Which half of the ledger a record's working directory belongs to.

    Everything outside the five personal-env repos counts as work, mirroring
    delivered-work-ledger.py's find_repos(), which discovers work repos as
    exactly that complement. Matching its rule is what lets work spend divide
    by the merged-PR count that same ledger produces.

    A missing cwd counts as work too: it can only under-report the tooling
    side, and a third "unknown" class would need a denominator nothing emits.
    """
    for part in (cwd or "").split("/"):
        if part in PERSONAL_ENV:
            return "tooling"
    return "work"


def parse_ts(iso_timestamp):
    """ISO-8601 timestamp string -> epoch seconds, or None on absent/malformed."""
    if not iso_timestamp:
        return None
    try:
        return datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def local_day(epoch):
    """Epoch seconds -> 'YYYY-MM-DD' in the machine's LOCAL timezone.

    Transcripts timestamp in UTC ('...Z'), so slicing the raw string buckets by
    UTC day. For any user not on UTC that misfiles the tail of each local
    evening into the next day — measured at 44.2% of priced records at UTC-3.
    """
    return datetime.fromtimestamp(epoch).strftime("%Y-%m-%d")


def day_bounds(day):
    """A 'YYYY-MM-DD' local day -> (start_epoch inclusive, end_epoch exclusive)."""
    start = datetime.strptime(day, "%Y-%m-%d")
    return start.timestamp(), (start + timedelta(days=1)).timestamp()


def find_transcripts(since_epoch):
    """All .jsonl transcripts that COULD hold records at/after since_epoch.

    mtime is a file's LAST write, so a file older than since_epoch cannot hold a
    record after it — a sound lower bound. There is deliberately no upper bound:
    a file written today may still carry records from weeks ago (resumed or
    long-running sessions), so the window's far end is enforced per record in
    scan_transcript() instead. Skipping recent files here would silently drop
    exactly the old records a backfill exists to recover.
    """
    main_files, subagent_files = [], []
    for dirpath, _, names in os.walk(TRANSCRIPTS_ROOT):
        for name in names:
            if not name.endswith(".jsonl"):
                continue
            path = os.path.join(dirpath, name)
            try:
                if os.path.getmtime(path) < since_epoch:
                    continue
            except OSError:
                continue
            if "/subagents/" in path:
                subagent_files.append(path)
            else:
                main_files.append(path)
    return main_files, subagent_files


def project_directories():
    """Every ~/.claude/projects/*/ directory, sorted for stable --session error output."""
    return sorted(entry.path for entry in os.scandir(TRANSCRIPTS_ROOT) if entry.is_dir())


def find_session_transcripts(sid):
    """(main_path, subagent_paths) for one session id, searched across every
    project directory rather than only the caller's cwd project — a --session
    audit commonly targets a past run made from a different working directory
    than the one auditing it now. main_path is None when no project directory
    holds "<sid>.jsonl"; subagent_paths is [] in that case.
    """
    for project_dir in project_directories():
        main_path = os.path.join(project_dir, f"{sid}.jsonl")
        if os.path.isfile(main_path):
            subagent_glob = os.path.join(project_dir, sid, "subagents", "*.jsonl")
            return main_path, sorted(glob.glob(subagent_glob))
    return None, []


def exit_session_not_found(sid):
    """Exit 1 naming every project directory searched — the one failure path
    for a sid that matches no transcript. Shared with
    extract-session-timeline.py, which imports this module rather than
    re-deriving the message: two copies would let the two entry points drift
    into reporting the same failure differently."""
    print(f"session {sid!r} not found. Searched project directories:", file=sys.stderr)
    for project_dir in project_directories():
        print(f"  {project_dir}", file=sys.stderr)
    sys.exit(1)


def oldest_retained_day():
    """Local day of the oldest transcript still on disk, or None when there are none.

    Claude Code prunes transcripts on `cleanupPeriodDays` (default 30), so days
    before this are unmeasurable rather than idle — the difference a $0 snapshot
    would otherwise erase. Feeds the `coverage` field in build_payload().
    """
    oldest = None
    for dirpath, _, names in os.walk(TRANSCRIPTS_ROOT):
        for name in names:
            if not name.endswith(".jsonl"):
                continue
            try:
                mtime = os.path.getmtime(os.path.join(dirpath, name))
            except OSError:
                continue
            if oldest is None or mtime < oldest:
                oldest = mtime
    return local_day(oldest) if oldest is not None else None


def day_coverage(day, retention_floor):
    """How much of `day` the transcripts on disk can still account for.

    The floor day is "partial", never "complete": the prune cuts through it at
    an hour, not at midnight, so its earlier sessions are already gone while the
    ones that ran past the cut survive. Calling it complete is what let
    2026-07-09 be measured at 68% of its real spend and read as a counting bug.
    """
    if not retention_floor or day < retention_floor:
        return "unretained"
    return "partial" if day == retention_floor else "complete"


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
    """session file -> [(subagent_type, prompt prefix, record_index)] for subagent attribution.

    record_index is this record's position in the SAME iter_records(path) sequence
    scan_transcript() enumerates below, so a spawn's index lines up with the
    skill-invocation and message-cost positions scan_transcript records for that
    file — that alignment is what lets by_skill_marginal place a subagent into
    the skill span it was spawned in.
    """
    spawns = defaultdict(list)
    for path in main_files:
        for record_index, record in enumerate(iter_records(path)):
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
                    record_index,
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


def scan_transcript(path, since_epoch, until_epoch, seen_messages):
    """Cost, tokens, call/turn counters, skills, and wall-clock bounds of one transcript.

    Both bounds are enforced per record, not per file. A file can clear the
    mtime-based find_transcripts() gate while holding records far outside the
    window on either side (a long-running or resumed session), so `since_epoch`
    keeps older records out and `until_epoch` (exclusive) keeps newer ones out.
    The upper bound is what makes a past day recoverable at all.

    `seen_messages` is the caller's billing-key set, shared across every file of
    one run. Duplicates were measured as intra-file only, but a resumed or forked
    session copies its parent's records verbatim into a new file, so a per-file
    set would let that whole prefix bill twice.

    That set is per-DAY, so it cannot see a response whose blocks straddle local
    midnight — the `anchor_epoch` pre-pass below is what stops both days billing
    one. It costs a second parse of each file, paid only on a full --rebuild.
    """
    stats = {
        "cost": 0.0,
        "by_family": defaultdict(float),
        "by_model": defaultdict(float),
        "by_day": defaultdict(float),

        # Per RECORD, not per session: a
        # session that cd's between work and
        # this config splits across both halves,
        # not rounded to whichever it started in.
        "by_repo_class": defaultdict(float),
        "touches_by_repo_class": defaultdict(
            lambda: {"user_messages": 0, "interruptions": 0}),
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
        # [(record_index, skill_name)], one entry per invocation, in file order —
        # by_skill_marginal's span split (aggregate()) uses these as span boundaries.
        "skill_events": [],
        # [(record_index, cost)] for every priced API message — the per-message
        # cost by_skill_marginal sums into whichever skill's span it falls in.
        "message_costs": [],
        # One dict per distinct (experiment, arm, pr) [ABTest] marker found in
        # this session — see ab_seen below for how repeats within a session
        # collapse to a single trial.
        "ab_trials": [],
        "first_epoch": None,
        "last_epoch": None,
    }
    # Commands seen but not yet classified as skill vs built-in, as
    # (record_index, name); settled by the NEXT user record (see the deferral below).
    pending_commands = []
    # (experiment, arm, pr) -> override-seen bool. A session can print the same
    # marker more than once (e.g. reprinted after a retry); dedupe to one trial
    # per distinct tuple, OR-ing the override flag across repeats.
    ab_seen = {}
    # Earliest record epoch per billing key, over the WHOLE file — built before
    # the window filter because its inputs must include records the window drops.
    # See the anchor check in the pricing block for why.
    anchor_epoch = {}
    # Highest output_tokens and cache_read_input_tokens
    # per billing key, same whole-file scope and for the
    # same reason as the anchor above.
    #
    # Both GROW across a response's blocks, so the anchor
    # record holds only a partial figure for each — see
    # the peak lookup in the pricing block.
    peak_output = {}
    peak_cache_read = {}

    # An /advisor turn's second model per billing key,
    # hoisted for the same reason as peak_output.
    #
    # The pricing block only ever sees the ANCHOR record,
    # and a subagent transcript never puts these on it.
    advisor_entries = {}
    for record in iter_records(path):
        message = record.get("message")
        # This pass sees records the window filter drops, so it meets shapes the
        # main loop never reaches — a non-dict `message` is skipped, not fatal.
        if not isinstance(message, dict):
            continue
        epoch = parse_ts(record.get("timestamp"))
        key = billing_id(record, message)
        if epoch is not None and key is not None:
            anchor_epoch[key] = min(anchor_epoch.get(key, epoch), epoch)
        if key is not None:
            usage = message.get("usage") or {}
            out = usage.get("output_tokens", 0) or 0
            peak_output[key] = max(peak_output.get(key, 0), out)
            read = usage.get("cache_read_input_tokens", 0) or 0
            peak_cache_read[key] = max(peak_cache_read.get(key, 0), read)
            if key not in advisor_entries:
                found = [
                    iteration
                    for iteration in usage.get("iterations") or []
                    if iteration.get("type") == "advisor_message"
                ]
                if found:
                    advisor_entries[key] = found
    for record_index, record in enumerate(iter_records(path)):
        epoch = parse_ts(record.get("timestamp"))
        # An unplaceable record is dropped rather than kept: with one scan per
        # day, a record that matches no window would otherwise match EVERY
        # window and be counted once per backfilled day.
        if epoch is None or not (since_epoch <= epoch < until_epoch):
            continue
        if record.get("subtype") == "compact_boundary":
            stats["compactions"] += 1
        # Claude Code writes an auto-generated title as this session
        # progresses; the transcript's last one is the final title.
        if record.get("type") == "ai-title" and record.get("aiTitle"):
            stats["title"] = record["aiTitle"]
        # Every surviving record is timestamped and inside the window, so these
        # bounds measure the session's wall-clock WITHIN the window — a session
        # spanning midnight contributes its own slice to each day it touches.
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
                for pending_index, name in pending_commands:
                    stats["skills"][name] += 1
                    stats["skill_events"].append((pending_index, name))
            pending_commands.clear()
            if not is_stdout_record:
                for text in texts:
                    for name in COMMAND_NAME_RE.findall(text):
                        if name not in BUILTIN_SILENT_COMMANDS:
                            pending_commands.append((record_index, name))
        if message.get("role") == "user" and is_human_message(record, content):
            text = first_text(content)
            touches = stats["touches_by_repo_class"][repo_class(record.get("cwd"))]
            # An Escape press is a correction event, not a typed turn — count it apart.
            if text.startswith(INTERRUPT_SENTINEL):
                stats["interruptions"] += 1
                touches["interruptions"] += 1
            else:
                stats["user_messages"] += 1
                touches["user_messages"] += 1
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
                    for experiment, arm, pr, override in AB_MARKER_RE.findall(item.get("text") or ""):
                        key = (experiment, arm, pr)
                        ab_seen[key] = ab_seen.get(key, False) or bool(override)
                elif item.get("type") == "tool_use" and item.get("name") == "Skill":
                    skill = (item.get("input") or {}).get("skill")
                    if skill:
                        stats["skills"][skill] += 1
                        stats["skill_events"].append((record_index, skill))
        usage = message.get("usage")
        model = message.get("model") or ""
        if not usage or model == "<synthetic>":
            continue
        # ONE API response becomes N transcript records — one per content block —
        # and Claude Code stamps the same request-side `message.usage` figures on
        # every one. Summing records bills each response once per block it emitted.
        #
        # Measured on 2026-07-20: 6,989 priced records carried 3,345 distinct
        # billing keys, inflating output tokens 3.64x and the day's dollars 2.97x
        # against ccusage. Worse than a constant bias, the multiplier IS the
        # blocks-per-response count, which rises with thinking and tool-call
        # density — so it correlates with the very levers this report measures
        # and does not cancel out of a day-over-day delta.
        billing_key = billing_id(record, message)
        if billing_key is not None:
            if billing_key in seen_messages:
                continue
            # Those N records are written over a real interval, so they can
            # straddle local midnight: msg_011Cd6t8KHRgiEBkBq9N9AYs wrote block 1
            # at 2026-07-16 23:59:59 and blocks 2-4 within the next 1.5s. The
            # dedup set above is per-day, so each side saw an unseen key and both
            # billed the response in full. Charging it to the day of its EARLIEST
            # record makes exactly one day claim it, whichever days are scanned.
            if anchor_epoch.get(billing_key, epoch) != epoch:
                continue
            seen_messages.add(billing_key)
            # `output_tokens` and `cache_read_input_tokens`
            # are both written CUMULATIVELY as a response
            # streams, so the anchor record holds a partial
            # count and only the final block the total.
            #
            # Keeping the anchor's value under-bills the two
            # priciest buckets by a factor that tracks the
            # blocks-per-response count.
            #
            # So the error grows with exactly the thinking
            # and tool-call density these reports measure.
            #
            # Measured on 2026-08-06: 385 of 1,490 responses
            # grew output_tokens, and the peak summed to
            # 1,163,896 against the anchor's 691,710 —
            # matching ccusage to the single token.
            #
            # cache_read grows on fewer responses but each
            # carries more: 12 of 640 on 2026-08-07, and 17
            # of 1,968 on 2026-07-12.
            #
            # The anchor left those two days 1.4% and 1.0%
            # under ccusage; the peak matches exactly, which
            # is what makes them citable at all.
            usage = dict(
                usage,
                output_tokens=peak_output.get(billing_key, 0),
                cache_read_input_tokens=peak_cache_read.get(billing_key, 0),
            )
        stats["api_calls"] += 1
        day = local_day(epoch)
        write_5m, write_1h = cache_writes(usage)
        stats["tokens"]["input"] += usage.get("input_tokens", 0) or 0
        stats["tokens"]["output"] += usage.get("output_tokens", 0) or 0
        stats["tokens"]["cache_read"] += usage.get("cache_read_input_tokens", 0) or 0
        stats["tokens"]["cache_write_5m"] += write_5m
        stats["tokens"]["cache_write_1h"] += write_1h
        cost = message_cost(model, usage, day)
        stats["cost"] += cost
        stats["message_costs"].append((record_index, cost))
        stats["by_family"][price_family(model)] += cost
        stats["by_model"][model_key(model)] += cost
        stats["by_day"][day] += cost
        stats["by_repo_class"][repo_class(record.get("cwd"))] += cost

        # An /advisor turn bills a SECOND model beside the main
        # one, and Claude Code reports it only inside
        # `usage.iterations`. The top-level usage fields sum the
        # `"message"` iterations alone.
        #
        # So an advisor call's tokens are structurally absent
        # from every field read above. This was the whole
        # residual ccusage drift: a day that never invoked
        # /advisor reconciles at 0.000%, so it read as noise.
        #
        # Measured on 2026-07-19: the top-level fields carry
        # 8,363 input tokens against ccusage's 3,137,652, and
        # the advisor iterations hold the missing 3,115,470.
        #
        # Priced under the advisor's OWN model, a tier above the
        # session's main one here. Billed inside the dedup gate
        # because these entries repeat across a response's block
        # records: 1,555 copies of 436 real calls.
        #
        # Read from the pre-pass, not from this record: a
        # subagent transcript never carries them on the anchor.
        #
        # On 2026-07-19 all 13 subagent advisor calls sat on a
        # later block, so reading `usage` here billed the main
        # sessions' 1,541,451 input tokens and none of the
        # subagents' 1,574,019.
        #
        # Taking whichever record carries them first is safe: of
        # 436 keys, 216 appear on several records and none
        # disagreed on list length or on any entry.
        for iteration in advisor_entries.get(billing_key, ()):
            advisor_model = iteration.get("model") or ""
            advisor_5m, advisor_1h = cache_writes(iteration)
            advisor_cost = message_cost(advisor_model, iteration, day)

            # Counted as its own call so that any cost-per-call
            # ratio stays true once its dollars are included.
            stats["api_calls"] += 1
            stats["tokens"]["input"] += iteration.get("input_tokens", 0) or 0
            stats["tokens"]["output"] += iteration.get("output_tokens", 0) or 0
            stats["tokens"]["cache_read"] += iteration.get("cache_read_input_tokens", 0) or 0
            stats["tokens"]["cache_write_5m"] += advisor_5m
            stats["tokens"]["cache_write_1h"] += advisor_1h
            stats["cost"] += advisor_cost
            stats["message_costs"].append((record_index, advisor_cost))
            stats["by_family"][price_family(advisor_model)] += advisor_cost
            stats["by_model"][model_key(advisor_model)] += advisor_cost
            stats["by_day"][day] += advisor_cost
            stats["by_repo_class"][repo_class(record.get("cwd"))] += advisor_cost
    # A command at end-of-file has no follower to disprove it — count it.
    for pending_index, name in pending_commands:
        stats["skills"][name] += 1
        stats["skill_events"].append((pending_index, name))
    stats["ab_trials"] = [
        {"experiment": experiment, "arm": arm, "pr": pr, "override": override}
        for (experiment, arm, pr), override in ab_seen.items()
    ]
    return stats


def match_spawn(prompt, session_spawns):
    """(subagent_type, spawn record_index) for the Task/Agent call that started this
    subagent transcript, matched by prompt prefix. Feeds both by_subagent_type
    (type only) and by_skill_marginal (record_index, to place the subagent's cost
    into the skill span it was spawned in). ("UNMATCHED", None) if no call matches.
    """
    for spawn_type, prompt_prefix, record_index in session_spawns:
        if prompt_prefix and prompt.startswith(prompt_prefix[:100]):
            return spawn_type, record_index
    return "UNMATCHED", None


def span_owner(sorted_events, event_indices, position):
    """The skill owning `position` (a record_index) under by_skill_marginal's span
    rule: a skill's span runs from its invocation event up to the next invocation
    event (of any skill). None if `position` precedes every event in the session —
    that cost is excluded from all skills, same rule as pre-invocation messages.

    `sorted_events` is stats["skill_events"] sorted by index; `event_indices` is
    its parallel list of just the indices, passed separately so callers doing this
    per-message/per-subagent inside one session build it once via bisect, not per call.
    """
    i = bisect.bisect_right(event_indices, position) - 1
    return sorted_events[i][1] if i >= 0 else None


def merge_common(result, stats, side):
    """Fold one transcript's family/day/token/char counters into the aggregate."""
    result["api_calls"][side] += stats["api_calls"]
    result["thinking_blocks"] += stats["thinking_blocks"]
    result["text_blocks"] += stats["text_blocks"]
    for family, cost in stats["by_family"].items():
        result["by_family"][family] += cost
    for model, cost in stats["by_model"].items():
        result["by_model"][model] += cost
    for day, cost in stats["by_day"].items():
        result["by_day"][day][side] += cost

    # A subagent inherits the cwd it was spawned
    # from, so its spend lands under the parent's
    # repo — delegating work never moves cost out
    # of the half that has to answer for it.
    for cls, cost in stats["by_repo_class"].items():
        result["by_repo_class"][cls]["cost"] += cost

        # Kept as its own running total rather than
        # left to be inferred, because the day-level
        # subagent share cannot be split back out per
        # half once the two are summed together.
        if side == "sub":
            result["by_repo_class"][cls]["subagent_cost"] += cost
    for kind in TOKEN_KINDS:
        result["tokens"][kind] += stats["tokens"][kind]


def new_marginal_counters():
    """Zeroed by_skill_marginal counters, for a row or for one of its halves."""
    return {"dedicated_sessions": 0, "dedicated_cost": 0.0,
            "mixed_sessions": 0, "mixed_cost_estimate": 0.0}


def session_repo_class(stats):
    """The single half a whole session counts under.

    Skill rows are per session, so splitting them per record would need a
    denominator no session-level counter has. Across 328 transcripts over 14
    days not one spanned both halves, so charging the whole session to its
    costliest half costs nothing measurable and keeps the split summing back
    to the row it refines.

    Ties break toward work, matching repo_class()'s own bias: over-reporting
    the work half can only make the KPI it feeds read worse, never better.
    """
    by_class = stats["by_repo_class"]
    if not by_class:
        return "work"
    return max(by_class.items(), key=lambda kv: (kv[1], kv[0]))[0]


def session_duration(stats):
    """Wall-clock seconds from first to last record (includes idle gaps)."""
    if stats["first_epoch"] is None or stats["last_epoch"] is None:
        return 0.0
    return max(0.0, stats["last_epoch"] - stats["first_epoch"])


def aggregate(main_files, subagent_files, since_epoch, until_epoch):
    spawns = collect_agent_spawns(main_files)
    result = {
        "main_cost": 0.0,
        "subagent_cost": 0.0,
        "by_family": defaultdict(float),
        # Per exact model, so a snapshot can be reconciled against ccusage's
        # modelBreakdowns without re-deriving which family each model belongs to.
        "by_model": defaultdict(float),
        "by_day": defaultdict(lambda: {"main": 0.0, "sub": 0.0}),

        # Work vs tooling spend, plus the human
        # touches spent on each.
        #
        # Only the work half has a merged-PR
        # denominator, so dividing TOTAL spend by
        # PRs measured which repo the day was
        # spent in more than how well it went.
        "by_repo_class": defaultdict(lambda: {
            "cost": 0.0, "subagent_cost": 0.0,
            "user_messages": 0, "interruptions": 0}),
        "by_subagent_type": defaultdict(lambda: {"cost": 0.0, "runs": 0}),
        "by_skill": defaultdict(lambda: {
            "cost": 0.0, "invocations": 0, "sessions": 0,
            "compactions": 0, "interruptions": 0,
            "tokens": dict.fromkeys(TOKEN_KINDS, 0),

            # The same overlapping figures, refined to
            # the half each session ran in.
            #
            # A skill that only ever fires while tuning
            # this config must not read as a cost of
            # shipping, and the row alone cannot say.
            "by_repo_class": defaultdict(lambda: {
                "cost": 0.0, "invocations": 0, "sessions": 0}),
        }),
        # Marginal counterpart to by_skill: partitions each session's cost across
        # the skills it invoked instead of letting rows overlap — see the
        # dedicated/mixed split in the main_files loop below.
        "by_skill_marginal": defaultdict(lambda: dict(
            new_marginal_counters(),
            by_repo_class=defaultdict(new_marginal_counters))),
        # [ABTest] marker rollup: ab_tests[experiment][arm] holds that arm's
        # trials/sessions/cost/tokens/overrides; ab_contaminated[experiment]
        # counts sessions that carried 2+ arms of the SAME experiment, whose
        # cost is excluded from every arm rather than misattributed to one.
        "ab_tests": defaultdict(lambda: defaultdict(lambda: {
            "trials": 0, "sessions": 0, "cost": 0.0,
            "tokens": dict.fromkeys(TOKEN_KINDS, 0), "overrides": 0,
        })),
        "ab_contaminated": defaultdict(int),
        "sessions": [],
        "subagents_per_session": defaultdict(lambda: {
            "cost": 0.0, "runs": 0, "tokens": dict.fromkeys(TOKEN_KINDS, 0),
            # [(spawn record_index or None, cost)], one entry per subagent run —
            # by_skill_marginal uses spawn_index to place each subagent's cost
            # into the skill span it was spawned in.
            "by_spawn": [],
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
    # One billing-key set for the whole run: a response is billed once no matter
    # how many files or how many content blocks it appears across.
    seen_messages = set()
    for path in subagent_files:
        stats = scan_transcript(path, since_epoch, until_epoch, seen_messages)
        # find_transcripts() only lower-bounds by mtime (see its docstring), so
        # subagent_files can hold a run whose transcript wasn't touched again
        # until well after this window. Gating on api_calls also drops a run
        # that produced no priced response at all, so "runs" counts invocations
        # that did work rather than every file passing the mtime filter.
        if stats["api_calls"] == 0:
            continue
        result["subagent_cost"] += stats["cost"]
        merge_common(result, stats, "sub")
        parent = path.split("/subagents/")[0] + ".jsonl"
        result["subagents_per_session"][parent]["cost"] += stats["cost"]
        result["subagents_per_session"][parent]["runs"] += 1
        for kind in TOKEN_KINDS:
            result["subagents_per_session"][parent]["tokens"][kind] += stats["tokens"][kind]
        spawn_type, spawn_index = match_spawn(stats["first_prompt"], spawns.get(parent, []))
        result["by_subagent_type"][spawn_type]["cost"] += stats["cost"]
        result["by_subagent_type"][spawn_type]["runs"] += 1
        result["subagents_per_session"][parent]["by_spawn"].append((spawn_index, stats["cost"]))
    for path in main_files:
        stats = scan_transcript(path, since_epoch, until_epoch, seen_messages)
        # Same mtime-only-lower-bound gap as subagent_files above: main_files
        # can include a session last touched after this window closed. Without
        # a guard, result["sessions"] gained one entry per FILE regardless of
        # whether it had any record inside the window, so session_count read as
        # "sessions from this day forward" instead of "sessions active on this
        # day" — it grew for every day still-open sessions would later touch,
        # which is why older days showed inflated, monotonically higher counts.
        #
        # api_calls is the stricter gate: a prompt can be queued and its
        # attachments resolved while the session ends before any API response
        # comes back. Such a file carries a "user" record and no usage at all,
        # so counting it inflates user_messages — a KPI meant to fall — and
        # deflates cost_per_user_message, which divides by it. On 2026-07-19
        # that was 186 of 284 files and roughly 187 of 425 user_messages.
        if stats["api_calls"] == 0:
            continue
        result["main_cost"] += stats["cost"]
        merge_common(result, stats, "main")
        duration = session_duration(stats)

        # Human turns belong to main sessions
        # only: a subagent's "user" records are
        # its spawn prompt and tool results, so
        # counting them inflates every divisor.
        result["user_messages"] += stats["user_messages"]
        result["interruptions"] += stats["interruptions"]
        for cls, touches in stats["touches_by_repo_class"].items():
            result["by_repo_class"][cls]["user_messages"] += touches["user_messages"]
            result["by_repo_class"][cls]["interruptions"] += touches["interruptions"]
        result["compactions"] += stats["compactions"]
        result["session_seconds"] += duration
        # A session counts under EVERY skill it invoked, so by_skill rows
        # overlap and don't sum to the total — they isolate, not partition.
        session_subagents = result["subagents_per_session"].get(
            path, {"cost": 0.0, "tokens": dict.fromkeys(TOKEN_KINDS, 0), "by_spawn": []})
        session_class = session_repo_class(stats)
        for skill, invocation_count in stats["skills"].items():
            entry = result["by_skill"][skill]
            entry["cost"] += stats["cost"] + session_subagents["cost"]
            entry["invocations"] += invocation_count
            entry["sessions"] += 1
            entry["compactions"] += stats["compactions"]
            entry["interruptions"] += stats["interruptions"]
            for kind in TOKEN_KINDS:
                entry["tokens"][kind] += stats["tokens"][kind] + session_subagents["tokens"][kind]
            half = entry["by_repo_class"][session_class]
            half["cost"] += stats["cost"] + session_subagents["cost"]
            half["invocations"] += invocation_count
            half["sessions"] += 1
        # by_skill_marginal: a session with exactly one distinct skill is
        # "dedicated" to it — its whole cost (session + subagents) is a clean,
        # non-overlapping signal. A session with 2+ distinct skills is "mixed" —
        # split its cost by invocation span instead of double-counting it under
        # every skill: each skill owns everything from its invocation event up
        # to the next invocation (of any skill); cost before the first
        # invocation is excluded from all skills, same as an unattributed setup
        # cost. A session with zero skills invoked has nothing to attribute.
        distinct_skills = list(stats["skills"].keys())
        if len(distinct_skills) == 1:
            marginal = result["by_skill_marginal"][distinct_skills[0]]
            dedicated_cost = stats["cost"] + session_subagents["cost"]
            marginal["dedicated_sessions"] += 1
            marginal["dedicated_cost"] += dedicated_cost
            half = marginal["by_repo_class"][session_class]
            half["dedicated_sessions"] += 1
            half["dedicated_cost"] += dedicated_cost
        elif len(distinct_skills) >= 2:
            events = sorted(stats["skill_events"], key=lambda e: e[0])
            event_indices = [e[0] for e in events]
            mixed_cost_by_skill = defaultdict(float)
            for record_index, cost in stats["message_costs"]:
                owner = span_owner(events, event_indices, record_index)
                if owner is not None:
                    mixed_cost_by_skill[owner] += cost
            for spawn_index, sub_cost in session_subagents["by_spawn"]:
                if spawn_index is None:
                    # Can't tell which Task/Agent call spawned this subagent, so
                    # its span is undeterminable — split like messages: proportional
                    # to each skill's message-cost share already assigned above.
                    total_assigned = sum(mixed_cost_by_skill.values())
                    for skill in distinct_skills:
                        share = (mixed_cost_by_skill[skill] / total_assigned if total_assigned
                                 else 1 / len(distinct_skills))
                        mixed_cost_by_skill[skill] += sub_cost * share
                    continue
                owner = span_owner(events, event_indices, spawn_index)
                if owner is not None:
                    mixed_cost_by_skill[owner] += sub_cost
                # else: spawned before the first skill invocation — excluded,
                # same as pre-invocation messages.
            for skill in distinct_skills:
                marginal = result["by_skill_marginal"][skill]
                skill_cost = mixed_cost_by_skill.get(skill, 0.0)
                marginal["mixed_sessions"] += 1
                marginal["mixed_cost_estimate"] += skill_cost
                half = marginal["by_repo_class"][session_class]
                half["mixed_sessions"] += 1
                half["mixed_cost_estimate"] += skill_cost
        # [ABTest] markers: this session's full cost (+ its subagents')
        # attributes to each arm it carries, per experiment — a session with
        # unrelated experiments A and B contributes its whole cost to both.
        # A session carrying 2+ arms of the SAME experiment can't be trusted
        # to pick one, so it's tallied as contaminated instead of split.
        trials_by_experiment = defaultdict(list)
        for trial in stats["ab_trials"]:
            trials_by_experiment[trial["experiment"]].append(trial)
        for experiment, trials in trials_by_experiment.items():
            arms_in_session = {trial["arm"] for trial in trials}
            if len(arms_in_session) > 1:
                result["ab_contaminated"][experiment] += 1
                continue
            arm_stats = result["ab_tests"][experiment][trials[0]["arm"]]
            arm_stats["trials"] += len(trials)
            arm_stats["sessions"] += 1
            arm_stats["cost"] += stats["cost"] + session_subagents["cost"]
            arm_stats["overrides"] += sum(1 for trial in trials if trial["override"])
            for kind in TOKEN_KINDS:
                arm_stats["tokens"][kind] += stats["tokens"][kind] + session_subagents["tokens"][kind]
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

    # Exact model, not just family: Sonnet 5 bills under its family during its
    # intro window and fast-mode Opus bills double, so the family row alone can
    # no longer be reconciled against a bill or against ccusage.
    print("\n== BY MODEL ==")
    for model, cost in sorted(result["by_model"].items(), key=lambda kv: -kv[1]):
        print(f"{model}\t${cost:.2f}")

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

    print("\n== BY SKILL (MARGINAL: non-overlapping, sums toward the total) ==")
    print("caveat: dedicated_cost is exact (session had only this skill); "
          "mixed_cost_est is a span-based approximation, not exact.")
    ranked_marginal = sorted(
        result["by_skill_marginal"].items(),
        key=lambda kv: -(kv[1]["dedicated_cost"] + kv[1]["mixed_cost_estimate"]))
    for skill, stats in ranked_marginal:
        total = stats["dedicated_cost"] + stats["mixed_cost_estimate"]
        print(f"{skill}\ttotal=${total:.2f}\t"
              f"dedicated=${stats['dedicated_cost']:.2f} (n={stats['dedicated_sessions']})\t"
              f"mixed_est=${stats['mixed_cost_estimate']:.2f} (n={stats['mixed_sessions']})")

    if result["ab_tests"] or result["ab_contaminated"]:
        print("\n== AB TESTS ([ABTest] markers found in chat transcripts) ==")
        experiments = sorted(set(result["ab_tests"]) | set(result["ab_contaminated"]))
        for experiment in experiments:
            print(f"{experiment}:")
            arms = result["ab_tests"].get(experiment, {})
            for arm, stats in sorted(arms.items()):
                total_tokens = sum(stats["tokens"].values())
                avg = stats["cost"] / max(stats["trials"], 1)
                print(f"\tarm={arm}\ttrials={stats['trials']}\tsessions={stats['sessions']}\t"
                      f"cost=${stats['cost']:.2f}\tavg=${avg:.2f}/trial\t"
                      f"tokens={total_tokens:,}\toverrides={stats['overrides']}")
            contaminated = result["ab_contaminated"].get(experiment, 0)
            if contaminated:
                print(f"\tcontaminated_sessions={contaminated} "
                      f"(session carried 2+ arms; cost excluded from every arm)")

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


def skill_halves(row, per_half):
    """One skill row's counters split per half, both halves always present.

    Emitting the empty half rather than omitting it keeps every consumer on
    one shape, so reading a skill that never ran in a half needs no guard.
    """
    return {cls: per_half(row["by_repo_class"][cls]) for cls in REPO_CLASSES}


def build_payload(result, top_n, day=None, coverage="complete", reconciliation=None):
    """The machine-readable aggregate — shared by --json and --snapshot.

    `day` set marks a single closed local calendar day (the committed snapshot
    unit); left None it is an ad-hoc rolling window, which never gets snapshotted.
    `coverage` is "complete" when transcripts for the period are still on disk,
    "partial" on the retention-floor day itself, whose earlier sessions are gone
    while its later ones survive, and "unretained" once the whole day was pruned
    — an unretained day reads $0 but means "unmeasurable", not "idle", so no
    reader mistakes deleted history for a day off.
    `reconciliation` is the ccusage token cross-check, present on snapshots only —
    an ad-hoc window has no day for ccusage to be asked about.
    """
    grand = result["main_cost"] + result["subagent_cost"]
    derived = derived_metrics(result)
    ranked_sessions = sorted(result["sessions"], key=lambda s: -s["cost"])[:top_n]
    # Divide by the days actually observed, never a nominal window length. The
    # old code divided by --days N while the cost spanned N+1 buckets (the cutoff
    # lands mid-day, making the oldest bucket partial), which had inflated the
    # 2026-07-19 snapshot's headline KPI 2x ($571.22 reported vs $285.61 true).
    observed_days = len(result["by_day"]) or 1
    payload = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "day": day,
        "coverage": coverage,
        "observed_days": observed_days,
        "kpis": {
            "cost_per_day": round(grand / observed_days, 2),
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
        "by_model": {k: round(v, 2) for k, v in
                     sorted(result["by_model"].items(), key=lambda kv: -kv[1])},
        "by_day": {day: {k: round(v, 2) for k, v in split.items()}
                   for day, split in sorted(result["by_day"].items())},

        # Every class emitted even at zero, so a
        # day with no tooling spend reads apart
        # from one never split at all.
        "by_repo_class": {
            cls: {"cost": round(result["by_repo_class"][cls]["cost"], 2),
                  "subagent_cost": round(
                      result["by_repo_class"][cls]["subagent_cost"], 2),
                  "user_messages": result["by_repo_class"][cls]["user_messages"],
                  "interruptions": result["by_repo_class"][cls]["interruptions"]}
            for cls in REPO_CLASSES},
        "by_subagent_type": {k: {"cost": round(v["cost"], 2), "runs": v["runs"]}
                             for k, v in result["by_subagent_type"].items()},
        # Rows overlap — a session counts under every skill it invoked.
        "by_skill": {k: {"cost": round(v["cost"], 2), "invocations": v["invocations"],
                         "sessions": v["sessions"], "compactions": v["compactions"],
                         "interruptions": v["interruptions"], "tokens": dict(v["tokens"]),
                         "by_repo_class": skill_halves(v, lambda h: {
                             "cost": round(h["cost"], 2),
                             "invocations": h["invocations"],
                             "sessions": h["sessions"]})}
                     for k, v in sorted(result["by_skill"].items(),
                                        key=lambda kv: -kv[1]["cost"])},
        # Non-overlapping counterpart to by_skill — dedicated_cost is exact,
        # mixed_cost_estimate is a span-based approximation (see render_text).
        "by_skill_marginal": {
            k: {"dedicated_sessions": v["dedicated_sessions"],
                "dedicated_cost": round(v["dedicated_cost"], 2),
                "mixed_sessions": v["mixed_sessions"],
                "mixed_cost_estimate": round(v["mixed_cost_estimate"], 2),
                "by_repo_class": skill_halves(v, lambda h: {
                    "dedicated_sessions": h["dedicated_sessions"],
                    "dedicated_cost": round(h["dedicated_cost"], 2),
                    "mixed_sessions": h["mixed_sessions"],
                    "mixed_cost_estimate": round(h["mixed_cost_estimate"], 2)})}
            for k, v in sorted(result["by_skill_marginal"].items(),
                                key=lambda kv: -(kv[1]["dedicated_cost"] + kv[1]["mixed_cost_estimate"]))
        },
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
    # Snapshots only. Carried IN the snapshot rather than printed once at run
    # time so a day stays auditable years later: a reader can tell a figure that
    # was cross-checked from one written while ccusage was missing or drifting.
    if reconciliation is not None:
        payload["reconciliation"] = reconciliation
    # Only present when at least one [ABTest] marker was found — mirrors
    # render_text's gate so a marker-free window's JSON stays unchanged too.
    if result["ab_tests"] or result["ab_contaminated"]:
        payload["ab_tests"] = {
            experiment: {
                arm: {
                    "trials": v["trials"], "sessions": v["sessions"],
                    "cost": round(v["cost"], 2), "tokens": dict(v["tokens"]),
                    "overrides": v["overrides"],
                }
                for arm, v in sorted(arms.items(), key=lambda kv: -kv[1]["cost"])
            }
            for experiment, arms in result["ab_tests"].items()
        }
        if result["ab_contaminated"]:
            payload["ab_tests_contaminated_sessions"] = dict(result["ab_contaminated"])
    return payload


SNAPSHOTS_DIR = os.path.join(HISTORY_DIR, "snapshots")
SNAPSHOT_DAY_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\.json$")


def write_snapshot(payload, day):
    """Persist one closed day's aggregate, named for the day it MEASURES.

    The old naming used the run date, so a file said when it was captured rather
    than what it covered — and a same-day rerun at a different --days silently
    replaced a different period under an identical name. Keying on the measured
    day makes a rewrite idempotent instead of destructive.
    """
    os.makedirs(SNAPSHOTS_DIR, exist_ok=True)
    path = os.path.join(SNAPSHOTS_DIR, f"{day}.json")
    with open(path, "w") as fh:
        json.dump(payload, fh, indent=2)
        fh.write("\n")
    return path


def keep_richer_snapshot(payload, day, coverage):
    """The existing snapshot's path when it outvalues `payload`, else None.

    A rewrite is idempotent only while the day's transcripts are still on disk.
    Once the prune reaches them the same code path becomes the most destructive
    operation here: `--rebuild` is mandatory after any aggregation fix, and it
    would replace a day measured while its records existed with a $0 reading of
    their absence. Measured on 2026-08-09: rebuilding 2026-06-14 writes $0.00
    over a committed $5.62, and 2026-07-10 drops $507.89 to $507.54.

    Gated on coverage so a genuine correction still lands. The 2026-07-27 dedup
    fix cut 2026-07-20 from $441.44 to $130.16 — a fully retained day measured
    lower is the fix working, not history being lost.
    """
    if coverage == "complete":
        return None
    path = os.path.join(SNAPSHOTS_DIR, f"{day}.json")
    try:
        with open(path) as fh:
            existing = json.load(fh)
    except (OSError, ValueError):
        return None
    return path if existing.get("total", 0.0) > payload["total"] else None


def existing_snapshot_days():
    """Local days already committed under snapshots/."""
    try:
        names = os.listdir(SNAPSHOTS_DIR)
    except OSError:
        return set()
    return {m.group(1) for m in (SNAPSHOT_DAY_RE.match(n) for n in names) if m}


def day_range(first_day, last_day):
    """Every local day from first_day to last_day inclusive, ascending."""
    start = datetime.strptime(first_day, "%Y-%m-%d").date()
    end = datetime.strptime(last_day, "%Y-%m-%d").date()
    return [(start + timedelta(days=offset)).isoformat()
            for offset in range((end - start).days + 1)]


# --- ccusage cross-check -----------------------------------------------------
#
# ccusage (github.com/ryoppippi/ccusage) reads the same transcripts and is the
# nearest thing to an independent second opinion on this script. It is wired in
# as a TOKEN oracle only, and that restriction is the whole design:
#
#   - Its token counts are exact. On 2026-07-20 its input, output and cache-read
#     totals matched this script to the single token once the billing-key dedup
#     landed. That makes it a live regression test for the one bug that had
#     inflated this entire history ~3x, and for any future transcript-shape
#     change that reintroduces it.
#   - Its DOLLARS cannot be trusted. It prices from a LiteLLM snapshot bundled
#     into the npm package, and on 2026-07-27 that snapshot was missing 4 of the
#     5 models in this workload. An unknown model costs $0 with no warning, so
#     `ccusage --offline` priced that same ~$130 day at $0.92. With network it
#     fetches fresher prices but is not reproducible: $148.67 and $122.34 for
#     the same closed day, one hour apart. Backed out of its own per-model
#     totals, its implied input rates were $7.67/MTok for Opus 4.8 and
#     $13.41/MTok for Fable 5, against Anthropic's published $5 and $10.
#
# So dollars stay computed here from the dated Anthropic table at the top, and
# ccusage answers only the question it answers reliably: did you count the same
# tokens? That is also what retires the old manual "re-verify PRICES before
# quoting dollars" step — the check that actually catches regressions now runs
# on every snapshot instead of on whoever remembers.
CCUSAGE_TOKEN_TOLERANCE = 0.005

# day -> ccusage token totals. Primed once per run over the whole backfill range
# because ccusage rescans every transcript on each invocation; 42 single-day
# calls cost 42 full scans.
_ccusage_days = {}


def prime_ccusage(first_day, last_day):
    """Load ccusage's per-day totals for a range. False when it cannot run."""
    if shutil.which("ccusage") is None:
        return False
    try:
        out = subprocess.run(
            ["ccusage", "daily", "--json",
             "--since", first_day.replace("-", ""),
             "--until", last_day.replace("-", "")],
            capture_output=True, text=True, check=True, timeout=900)
        entries = json.loads(out.stdout)["daily"]
        # Staged in a local dict so a mid-loop schema failure leaves the shared
        # cache untouched rather than half-filled with an unusable range.
        parsed = {}
        for entry in entries:
            # ccusage 20.x renamed this key `date` -> `period` and added an
            # `agent` dimension whose non-"all" rows break the same day down per
            # agent. Reading those on top of "all" would double-count the day,
            # so keep only the aggregate row.
            if entry.get("agent", "all") != "all":
                continue
            parsed[entry.get("period") or entry["date"]] = {
                "input": entry.get("inputTokens", 0) or 0,
                "output": entry.get("outputTokens", 0) or 0,
                "cache_read": entry.get("cacheReadTokens", 0) or 0,
                "cache_write": entry.get("cacheCreationTokens", 0) or 0,
                "cost": entry.get("totalCost", 0.0) or 0.0,
            }
    # The entry loop sits inside the try because this is an advisory cross-check:
    # the next schema rename must degrade the affected days to `reconciliation:
    # "unavailable"`, never abort the measurement it only verifies.
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError) as err:
        print(f"ccusage cross-check unavailable: {err}", file=sys.stderr)
        return False
    _ccusage_days.update(parsed)
    # A day ccusage omits is a real zero, not a failed lookup — record it as one
    # so an idle day reconciles "ok" instead of "unavailable".
    empty = {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0, "cost": 0.0}
    for day in day_range(first_day, last_day):
        _ccusage_days.setdefault(day, dict(empty))
    return True


def reconcile_tokens(result, day):
    """This run's token totals for `day` against ccusage's, bucket by bucket."""
    mine = {
        "input": result["tokens"]["input"],
        "output": result["tokens"]["output"],
        "cache_read": result["tokens"]["cache_read"],
        # ccusage reports one flat cache-creation figure; this script splits it
        # by TTL because the two bill at different multiples. Sum to compare.
        "cache_write": result["tokens"]["cache_write_5m"] + result["tokens"]["cache_write_1h"],
    }
    if day not in _ccusage_days and not prime_ccusage(day, day):
        return {"status": "unavailable", "script_tokens": mine}
    reference = _ccusage_days[day]
    buckets = {}
    worst = 0.0
    for kind, count in mine.items():
        other = reference[kind]
        scale = max(count, other)
        drift = 0.0 if not scale else (count - other) / scale
        worst = max(worst, abs(drift))
        buckets[kind] = {"script": count, "ccusage": other,
                         "delta_pct": round(drift * 100, 3)}
    return {
        "status": "ok" if worst <= CCUSAGE_TOKEN_TOLERANCE else "drift",
        "worst_delta_pct": round(worst * 100, 3),
        "tokens": buckets,
        # Recorded for visibility, never compared against: see the note above.
        "ccusage_cost_untrusted": round(reference["cost"], 2),
    }


def snapshot_day(day, top_n):
    """Aggregate one closed local day and commit it.

    Returns (path, total cost, ccusage reconciliation status).

    The retention floor is read HERE, per day, rather than once per run. Claude
    Code prunes transcripts on its own schedule, so a multi-minute rebuild can
    straddle a prune and label every day it scans afterwards from a floor that
    stopped being true partway through.
    """
    since_epoch, until_epoch = day_bounds(day)
    main_files, subagent_files = find_transcripts(since_epoch)
    result = aggregate(main_files, subagent_files, since_epoch, until_epoch)
    coverage = day_coverage(day, oldest_retained_day())

    # A day the prune has reached can only measure LOWER
    # than it truly was, so its ccusage cross-check compares
    # two different corpora and reports the deleted spend as
    # a counting disagreement.
    #
    # Measured on 2026-07-09: the script read 342,450 input
    # tokens against a ccusage figure of 450,102 primed
    # minutes earlier, and re-running ccusage after the
    # prune returned 342,452.
    #
    # Nothing miscounted; the transcripts went away mid-run.
    if coverage == "complete":
        reconciliation = reconcile_tokens(result, day)
    else:
        reconciliation = {"status": coverage,
                          "script_tokens": {
                              "input": result["tokens"]["input"],
                              "output": result["tokens"]["output"],
                              "cache_read": result["tokens"]["cache_read"],
                              "cache_write": result["tokens"]["cache_write_5m"]
                              + result["tokens"]["cache_write_1h"]}}
    payload = build_payload(result, top_n, day=day, coverage=coverage,
                            reconciliation=reconciliation)
    kept = keep_richer_snapshot(payload, day, coverage)
    if kept is not None:
        with open(kept) as fh:
            return kept, json.load(fh)["total"], "preserved"
    return write_snapshot(payload, day), payload["total"], reconciliation["status"]


def run_backfill(args, last_closed_day):
    """Write a snapshot for every closed day in range that has none yet.

    Each day runs the SAME single-day path a live capture uses, rather than one
    pass bucketed across days. A 30-day rebuild costs a couple of minutes that
    way, but a backfilled day and a live-captured day come out byte-identical by
    construction — a second code path could drift from the first and silently
    split the history into two incomparable halves.
    """
    retention_floor = oldest_retained_day()
    first_day = args.since or retention_floor or last_closed_day
    last_day = min(args.until or last_closed_day, last_closed_day)
    if first_day > last_day:
        print(f"nothing to backfill: {first_day} is after the last closed day {last_day}.")
        return
    committed = existing_snapshot_days()
    # --rebuild re-measures days that already have a snapshot. Normally skipping
    # them is right — a closed day is immutable, so recomputing it is wasted
    # work. But when the AGGREGATION changes, every existing file is wrong and
    # skipping them is exactly the failure: the 2026-07-27 dedup fix left 42
    # committed days overstated ~3x with no supported way to correct them short
    # of deleting the series by hand.
    missing = [d for d in day_range(first_day, last_day)
               if args.rebuild or d not in committed]
    if not missing:
        print(f"up to date: every day {first_day}..{last_day} already has a snapshot.")
        return
    verb = "rebuilding" if args.rebuild else "backfilling"
    print(f"{verb} {len(missing)} day(s) in {first_day}..{last_day} "
          f"(transcripts retained from {retention_floor or 'unknown'})")
    # One ccusage call for the whole range: it rescans every transcript per
    # invocation, so priming per day would multiply the backfill's cost by the
    # number of days. A failure here is non-fatal — each day then records
    # "unavailable" and the snapshot is still written.
    prime_ccusage(first_day, last_day)
    drifted, preserved = [], []
    for day in missing:
        path, total, status = snapshot_day(day, args.top)
        print(f"  {day}  ${total:>9,.2f}  ccusage:{status:<12} {os.path.basename(path)}")
        if status == "drift":
            drifted.append(day)
        elif status == "preserved":
            preserved.append(day)

    # Named individually rather than counted: a preserved
    # day is one this run could no longer measure, so the
    # reader needs which days now rest on an older run.
    if preserved:
        print(f"\nKEPT the committed snapshot on {len(preserved)} day(s): "
              f"{', '.join(preserved)}\n"
              f"  Their transcripts have been pruned, so re-measuring would "
              f"only have lowered a figure taken while the records existed.")

    # Surfaced at the end because a per-day line scrolls past on a 40-day run,
    # and a token disagreement means the aggregation itself is wrong — the one
    # failure mode that silently poisons every comparison built on these files.
    if drifted:
        print(f"\nTOKEN DRIFT vs ccusage on {len(drifted)} day(s): {', '.join(drifted)}\n"
              f"  Counting disagrees with an independent reader. Treat these days' "
              f"figures as unverified until the cause is found.", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(
        description="Estimate Claude Code token spend from ~/.claude/projects transcripts "
                    "(list prices; shares matter more than absolute dollars).")
    parser.add_argument("--backfill", action="store_true",
                        help="write a snapshot for every closed day that lacks one (default audit step)")
    parser.add_argument("--day", help="aggregate one local calendar day (YYYY-MM-DD) and snapshot it")
    parser.add_argument("--rebuild", action="store_true",
                        help="with --backfill, also re-measure days that already have a "
                             "snapshot (use after an aggregation or pricing fix)")
    parser.add_argument("--since", help="earliest day to backfill (default: oldest retained transcript)")
    parser.add_argument("--until", help="latest day to backfill (default: yesterday)")
    parser.add_argument("--days", type=int, default=7,
                        help="ad-hoc rolling-window report, in days (default: 7); never snapshots")
    parser.add_argument("--top", type=int, default=8, help="how many top sessions to show (default: 8)")
    parser.add_argument("--json", action="store_true", help="emit machine-readable aggregates")
    parser.add_argument("--session", metavar="SID",
                        help="aggregate one session id (its main transcript plus its "
                             "subagent runs), found under any ~/.claude/projects/*/ "
                             "directory; always emits JSON; never snapshots")
    args = parser.parse_args()

    if not os.path.isdir(TRANSCRIPTS_ROOT):
        print(f"transcripts dir not found: {TRANSCRIPTS_ROOT}", file=sys.stderr)
        sys.exit(1)

    # Yesterday, not today: a day is only immutable once it has ended. Sampling
    # 2026-07-24 at 21:49 that day read $49; the closed day was $413.
    last_closed_day = (date.today() - timedelta(days=1)).isoformat()

    if args.backfill:
        run_backfill(args, last_closed_day)
        return

    if args.day:
        if args.day > last_closed_day:
            print(f"refusing to snapshot {args.day}: the day has not closed "
                  f"(last closed day is {last_closed_day}).", file=sys.stderr)
            sys.exit(1)
        path, total, status = snapshot_day(args.day, args.top)
        print(f"{args.day}  ${total:,.2f}  ccusage:{status}  ->  {path}")
        return

    if args.session:
        # One session's own transcripts, not a date window — the far bound is
        # unbounded (float("inf")) so a session spanning multiple calendar days
        # is captured whole. Never touches snapshot_day()/run_backfill(): a
        # mid-session read is inherently partial and must not be mistaken for
        # the immutable closed-day record those two produce.
        main_path, subagent_files = find_session_transcripts(args.session)
        if main_path is None:
            exit_session_not_found(args.session)
        result = aggregate([main_path], subagent_files, 0, float("inf"))
        print(json.dumps(build_payload(result, args.top), indent=2))
        return

    # Ad-hoc window: a human-readable read of recent activity. It deliberately
    # cannot snapshot — an overlapping, variable-length window is exactly the
    # unit the per-day record replaced.
    since_epoch = time.time() - args.days * 86400
    main_files, subagent_files = find_transcripts(since_epoch)
    if not main_files and not subagent_files:
        print(f"No transcripts modified in the last {args.days} days.")
        return

    result = aggregate(main_files, subagent_files, since_epoch, time.time())
    if args.json:
        print(json.dumps(build_payload(result, args.top), indent=2))
    else:
        print(f"window: last {args.days} days · files: {len(main_files)} main + "
              f"{len(subagent_files)} subagent\n")
        render_text(result, args.top)


if __name__ == "__main__":
    main()
