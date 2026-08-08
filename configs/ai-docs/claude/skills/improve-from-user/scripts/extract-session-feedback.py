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

"""

import argparse
import os
import re
import sys
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


def main():
    ap = argparse.ArgumentParser(add_help=True, description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.parse_args()

    raise NotImplementedError(
        "Task 3 replaces single-file selection with the multi-session sweep"
    )


def emit(path, turns, learnings, boundaries):
    out = sys.stdout
    mtime = ""
    try:
        import datetime
        mtime = datetime.datetime.fromtimestamp(os.path.getmtime(path)).isoformat(timespec="seconds")
    except Exception:
        pass

    out.write("# Session feedback extract (recovered from disk — survives compaction)\n")
    out.write(f"# transcript : {path}\n")
    out.write(f"# modified   : {mtime}\n")
    out.write(f"# summary    : {len(turns)} user turns · "
              f"{len(learnings)} [Learning] markers · {len(boundaries)} compaction boundaries\n")
    if boundaries:
        out.write("# NOTE: this session compacted — the turns below are the ORIGINAL verbatim text,\n")
        out.write("#       not the summary your in-context memory now holds. Trust these over memory.\n")
    out.write("\n")

    out.write("## [Learning] markers — pre-digested, emitted at correction time\n\n")
    if learnings:
        for lineno, m in learnings:
            out.write(f"- [line {lineno}] {m}\n")
    else:
        out.write("(none — no [Learning] markers were emitted this session; "
                  "rely on the verbatim turns below)\n")
    out.write("\n")

    out.write("## Verbatim user turns + what Claude did next\n\n")
    if not turns:
        out.write("(no user prose turns found — check the transcript path in the header)\n")
    for t in turns:
        header = f"### turn @ {t['ts'] or '?'}  [line {t['line']}]"
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


if __name__ == "__main__":
    main()
