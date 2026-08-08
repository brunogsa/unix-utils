#!/usr/bin/env python3
"""Recover compaction-proof feedback from a Claude Code session transcript.

Mode A of the improve-from-user skill used to
"review the conversation history" — i.e. Claude's in-context memory. Compaction
thins that memory to a summary, so verbatim user corrections from earlier in the
session are gone by the time the skill runs.

They are NOT gone from disk. Claude Code appends every message to a JSONL
transcript under ~/.claude/projects/<cwd-slug>/<session-id>.jsonl, and compaction
never rewrites that file — it only inserts a `compact_boundary` marker and keeps
appending. The originals survive above each boundary. Verified: one session held
13 compactions in a single file with all 14 pre-first-boundary user turns intact.

This script reads that file and emits three things:
  1. [Learning] markers  — pre-digested learnings Claude wrote at correction time
                            (the write-ahead log; immune to compaction by design)
  2. verbatim user turns  — each with a one-line note of what Claude did next
  3. compaction boundaries — marked inline so you see where memory was thinned

Scope: a multi-session sweep, not a single file. Every transcript whose mtime
falls in the --since window AND holds >= 2 real user turns qualifies; the
running session's own transcript is always excluded, even when it qualifies.

Usage:
  extract-session-feedback.py [--since DAYS] [--project-dirs DIR [DIR ...]]

Examples:
  extract-session-feedback.py                       # last 7 days, default read scope
  extract-session-feedback.py --since 30            # last 30 days
  extract-session-feedback.py --project-dirs ~/.claude/projects/-Users-me-some-repo
"""

import argparse
import datetime
import glob
import json
import os
import re
import subprocess
import sys
import time
from typing import NoReturn

USER_TURN_CHAR_CAP = 6000  # verbatim, but guard against a giant paste bloating output
NEXT_TEXT_HEAD = 200        # chars of the following assistant text to show as context

# A real marker is a STANDALONE line `[Learning] said="…" | rule="…"` (the CLAUDE.md
# rule mandates its own line). Anchor to line-start plus the `said=` payload field so
# prose that merely mentions or quotes "[Learning]" mid-sentence isn't misread as an
# emitted marker. Optional leading list bullet / backtick tolerates markdown rendering.
LEARNING_RE = re.compile(r"^\s*[-*]?\s*`?\[Learning\]\s+said=")


def die(msg, code=2) -> NoReturn:
    print(f"extract-session-feedback: {msg}", file=sys.stderr)
    sys.exit(code)


def is_real_user_prose(d):
    """A genuine user prose turn — not a tool result, meta, slash command, or summary."""
    if d.get("type") != "user" or d.get("isMeta") or d.get("isCompactSummary"):
        return False
    content = d.get("message", {}).get("content")
    if not isinstance(content, str):
        return False  # tool_result turns carry a list, not a string
    stripped = content.strip()
    if not stripped:
        return False
    for prefix in ("<command-", "<local-command-", "<system-reminder"):
        if stripped.startswith(prefix):
            return False
    return True


def assistant_parts(d):
    """Return (text, [tool names], [learning-marker lines]) for an assistant message."""
    content = d.get("message", {}).get("content")
    texts, tools, learnings = [], [], []
    if isinstance(content, str):
        blocks = [{"type": "text", "text": content}]
    elif isinstance(content, list):
        blocks = content
    else:
        blocks = []
    for b in blocks:
        if not isinstance(b, dict):
            continue
        if b.get("type") == "text":
            t = b.get("text", "")
            texts.append(t)
            for line in t.splitlines():
                if LEARNING_RE.search(line):
                    learnings.append(line.strip())
        elif b.get("type") == "tool_use":
            tools.append(b.get("name", "?"))
    return "\n".join(texts).strip(), tools, learnings


def one_line(text, cap):
    collapsed = " ".join(text.split())
    return collapsed[:cap] + ("…" if len(collapsed) > cap else "")


def _real_user_turn_texts(path):
    """Yield each real user prose turn's stripped text content from path.

    Shared by count_real_user_turns and survey() so the JSONL-parse loop and
    the is_real_user_prose filter live in exactly one place. A malformed
    trailing line (a live-appending transcript's partial write) is skipped,
    matching the pre-existing behavior this sweep preserves.
    """
    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            raw = raw.strip()
            if not raw:
                continue
            try:
                d = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if is_real_user_prose(d):
                yield d["message"]["content"].strip()


def count_real_user_turns(path):
    """Count path's real user prose turns (see is_real_user_prose)."""
    return sum(1 for _ in _real_user_turn_texts(path))


def qualifying_transcripts(project_dirs, since_days, exclude_path):
    """Top-level *.jsonl transcripts across project_dirs that qualify for the sweep.

    A transcript qualifies when its mtime falls within the last since_days
    days AND it holds >= 2 real user turns (Finding 2/3: this filter is what
    keeps a routine sweep tractable). exclude_path — the running session's
    own transcript — is dropped even when it otherwise qualifies (D7).

    Only top-level files are considered, not nested <session>/subagents/*.jsonl
    files, which carry no user prose (derived design constraint). Returned in
    mtime order (oldest first) so callers group output in session order.
    """
    cutoff = time.time() - since_days * 86400
    exclude_abs = os.path.abspath(exclude_path) if exclude_path else None

    candidates = []
    for project_dir in project_dirs:
        for path in glob.glob(os.path.join(project_dir, "*.jsonl")):
            if exclude_abs and os.path.abspath(path) == exclude_abs:
                continue
            if os.path.getmtime(path) < cutoff:
                continue
            if count_real_user_turns(path) < 2:
                continue
            candidates.append(path)

    candidates.sort(key=os.path.getmtime)
    return candidates


def survey(qualifying):
    """Corpus survey for qualifying: file count, real user turns, estimated tokens.

    Estimated tokens is user_chars / 4 (D "escalation threshold ~80k
    estimated tokens" — the same rough conversion the plan's fan-out
    threshold is built on). Printed before any session content (D12) so an
    oversized sweep is visible before a single message body is read.
    """
    file_count = len(qualifying)
    turn_count = 0
    char_count = 0
    for path in qualifying:
        for text in _real_user_turn_texts(path):
            turn_count += 1
            char_count += len(text)
    return {
        "file_count": file_count,
        "turn_count": turn_count,
        "estimated_tokens": char_count // 4,
    }


def parse_transcript(path):
    """Parse one transcript into (turns, learnings, boundaries).

    Restores the event-linking loop the deleted single-file resolve_transcript()
    used to run inline in main() — each assistant burst is attached to the user
    turn it answers. Now scoped per file so the sweep's emit() can call it once
    per qualifying transcript instead of once per process.
    """
    turns = []            # list of dicts: {ts, line, text, tools, next_text, boundaries_after}
    learnings = []         # (line, marker-text)
    boundaries = []        # line numbers of compaction boundaries
    current = None         # the user turn currently collecting its "next action"

    with open(path, encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, 1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                d = json.loads(raw)
            except json.JSONDecodeError:
                continue

            if d.get("type") == "system" and d.get("subtype") == "compact_boundary":
                boundaries.append(lineno)
                if current is not None:
                    current["boundaries_after"].append(lineno)
                continue

            if is_real_user_prose(d):
                current = {
                    "ts": d.get("timestamp", ""),
                    "line": lineno,
                    "text": d["message"]["content"].strip(),
                    "tools": [],
                    "next_text": "",
                    "boundaries_after": [],
                }
                turns.append(current)
                continue

            if d.get("type") == "assistant":
                text, tools, marks = assistant_parts(d)
                for m in marks:
                    learnings.append((lineno, m))
                if current is not None:
                    for t in tools:
                        if t not in current["tools"]:
                            current["tools"].append(t)
                    if not current["next_text"] and text:
                        current["next_text"] = text

    return turns, learnings, boundaries


def _default_project_dirs():
    """Resolve the default read-scope dirs via resolve-repo-targets.py --json.

    CLI composition, not a cross-import: both scripts keep their hyphenated
    filenames (matching every other script in this skill), and Python can't
    cleanly import a hyphenated module name.
    """
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resolve-repo-targets.py")
    result = subprocess.run([sys.executable, script, "--json"], capture_output=True, text=True)
    if result.returncode != 0:
        die(f"resolve-repo-targets.py failed: {result.stderr.strip()}")
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        die("resolve-repo-targets.py did not return valid JSON")
    return data["read_scope_dirs"]


def _running_session_transcript(project_dirs):
    """Resolve the live session's own transcript via $CLAUDE_CODE_SESSION_ID, or None.

    The one piece of session-identity logic that survives from the deleted
    precedence chain — now used only for exclusion, never for selection (D7).
    """
    session_id = os.environ.get("CLAUDE_CODE_SESSION_ID")
    if not session_id:
        return None
    for project_dir in project_dirs:
        path = os.path.join(project_dir, f"{session_id}.jsonl")
        if os.path.isfile(path):
            return path
    return None


def main():
    ap = argparse.ArgumentParser(add_help=True, description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--since", type=int, default=7, metavar="DAYS",
                     help="only consider transcripts modified in the last DAYS days (default: 7)")
    ap.add_argument("--project-dirs", nargs="+", metavar="DIR",
                     help="override the default read-scope directories "
                          "(normally resolved via resolve-repo-targets.py --json)")
    args = ap.parse_args()

    project_dirs = args.project_dirs if args.project_dirs else _default_project_dirs()
    exclude_path = _running_session_transcript(project_dirs)
    qualifying = qualifying_transcripts(project_dirs, args.since, exclude_path)

    if not qualifying:
        print(f"# corpus survey: 0 qualifying sessions in the last {args.since} days "
              "-- nothing to mine")
        return

    stats = survey(qualifying)
    print(f"# corpus survey: {stats['file_count']} files · {stats['turn_count']} real user turns · "
          f"~{stats['estimated_tokens']} estimated tokens")

    emit(qualifying)


def _emit_session(out, path, index, total, turns, learnings, boundaries):
    """Write one session's grouped [Learning] markers + verbatim turns to out.

    Body formatting (truncation, NEXT: line, compaction-boundary notes) is
    unchanged from the pre-sweep single-file emit() — only the surrounding
    per-session header/grouping is new, so a multi-session sweep reads as N
    of these blocks back to back, in session order.
    """
    mtime = ""
    try:
        mtime = datetime.datetime.fromtimestamp(os.path.getmtime(path)).isoformat(timespec="seconds")
    except OSError:
        pass

    out.write(f"## Session {index}/{total}: {path}\n")
    out.write(f"# modified   : {mtime}\n")
    out.write(f"# summary    : {len(turns)} user turns · "
              f"{len(learnings)} [Learning] markers · {len(boundaries)} compaction boundaries\n")
    if boundaries:
        out.write("# NOTE: this session compacted — the turns below are the ORIGINAL verbatim text,\n")
        out.write("#       not the summary your in-context memory now holds. Trust these over memory.\n")
    out.write("\n")

    out.write("### [Learning] markers — pre-digested, emitted at correction time\n\n")
    if learnings:
        for lineno, m in learnings:
            out.write(f"- [line {lineno}] {m}\n")
    else:
        out.write("(none — no [Learning] markers were emitted this session; "
                  "rely on the verbatim turns below)\n")
    out.write("\n")

    out.write("### Verbatim user turns + what Claude did next\n\n")
    if not turns:
        out.write("(no user prose turns found — check the transcript path in the header)\n")
    for t in turns:
        header = f"#### turn @ {t['ts'] or '?'}  [line {t['line']}]"
        out.write(header + "\n")
        body = t["text"]
        if len(body) > USER_TURN_CHAR_CAP:
            body = body[:USER_TURN_CHAR_CAP] + f"\n…[truncated, {len(t['text'])} chars total]"
        out.write("USER:\n")
        out.write(body + "\n")
        tools = f"tools=[{', '.join(t['tools'])}]" if t["tools"] else "tools=[]"
        nxt = one_line(t["next_text"], NEXT_TEXT_HEAD) if t["next_text"] else "(no assistant text)"
        out.write(f"NEXT: {tools} · {nxt}\n")
        for b in t["boundaries_after"]:
            out.write(f"\n--- ⟂ COMPACTION BOUNDARY [line {b}] — "
                      "in-context memory was thinned here; turns above recovered from disk ---\n")
        out.write("\n")


def emit(paths):
    """Emit every qualifying session's feedback, grouped and in session order (D8)."""
    out = sys.stdout
    out.write("# Session feedback extract (recovered from disk — survives compaction)\n\n")
    total = len(paths)
    for index, path in enumerate(paths, 1):
        turns, learnings, boundaries = parse_transcript(path)
        _emit_session(out, path, index, total, turns, learnings, boundaries)


if __name__ == "__main__":
    main()
