#!/usr/bin/env python3
"""check-lazy-continuation.py - flag prose a list item silently swallows.

Markdown's lazy-continuation rule attaches an unindented line to the
paragraph above it. When that paragraph belongs to a list item, prose the
author indented for an OUTER item gets absorbed by an INNER one, and the
rendered text says something the source does not.

The signature is a disagreement, not a style preference: a non-blank,
non-marker line whose indent is STRICTLY LESS than the enclosing list
item's content indent was plainly written for a shallower container, yet
the parser hands it to the deeper one anyway.

  1. Push the branch.
     - On a stacked run, the override replaces this step.   <- content at 5
     Use `git push -u origin HEAD`.                         <- indent 3, absorbed

The reader sees "the stacked override pushes with git push", the exact
inverse of what the pointer bullet means.

An ordinary multi-line bullet continues at EXACTLY the content indent, so
`indent < content_indent` is false and nothing fires. That negative case is
house style across this corpus; a checker that flagged it would be switched
off the day it landed.

DETECTION ONLY - do not add a --fix pass.

Three different edits resolve a hit, and they do not render the same: indent
the prose to the item it belongs to, blank-line it into a block of its own,
or move the marker below the prose. Which one is right depends on which
container the author meant, and that is an authorial decision, not a
transform.

Conservatively scoped: only a paragraph opened by a list-marker line is
tracked. A paragraph that starts AFTER a blank line inside an item can be
absorbed the same way, but telling one apart from an indented code block, a
table, or a nested block quote needs a full container stack - so those are
missed rather than guessed at, because a false positive here costs the whole
check's credibility and a miss costs one finding.

AI-consumed output (compact, parseable - mirrors check-density.sh):
  == <filename>                          header, once per file with hits
  <line>:lazy-continuation:<N>-under-<M>  line indent N, item content indent M

Only the FIRST line of an absorbed run is reported: the run is one defect
with one fix, and per-line rows would read as a cluster of separate ones.

Usage:
  check-lazy-continuation.py [--changed-only] <file> [<file>...]

--changed-only scopes every reported hit to the lines get-changed-lines.sh
reports as changed vs HEAD for that same file, so a fixer's convergence loop
never re-reports a violation that predates the session's own edits.

Exit codes:
  0  clean
  1  violations found
  2  usage error, or (with --changed-only) get-changed-lines.sh failed
"""

import re
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
CHANGED_LINES_SCRIPT = SCRIPT_DIR / "get-changed-lines.sh"

# `\s+|$` so a bare `-` counts as a marker line too: the rule excludes marker
# lines by definition, and the corpus carries four of them.
LIST_MARKER = re.compile(r"^(\s*)([-*+]|\d+\.)(\s+|$)")
FENCE = re.compile(r"^\s*(```|~~~)")
FRONTMATTER = re.compile(r"^---\s*$")

# Blocks CommonMark lets interrupt a paragraph. A line starting one of these
# CLOSES the list instead of being absorbed by it, so author and parser agree
# and there is nothing to report.
ATX_HEADING = re.compile(r"^\s*#")
BLOCKQUOTE = re.compile(r"^\s*>")
THEMATIC_BREAK = re.compile(r"^\s*((\*\s*){3,}|(-\s*){3,}|(_\s*){3,})$")
# Any `<`-led line is treated as an HTML block, though CommonMark only lets
# some kinds interrupt a paragraph. Over-matching here can only lose a
# finding; under-matching would invent one.
HTML_BLOCK = re.compile(r"^\s*<")

PARAGRAPH_INTERRUPTERS = (ATX_HEADING, BLOCKQUOTE, THEMATIC_BREAK, HTML_BLOCK)


class ChangedLinesError(Exception):
    """get-changed-lines.sh exited non-zero for the named path."""


def content_indent_of(marker_match):
    """Column where a list item's content begins, per CommonMark.

    One to four spaces after the marker set the column directly. An empty
    item, or a run of five or more spaces (which opens an indented code
    block rather than content), puts it one column past the marker instead -
    without that branch a `-     text` line reports a content indent of six
    where the parser uses two, and every following line looks absorbed.
    """
    indent, marker, spaces = marker_match.group(1, 2, 3)
    marker_end = len(indent) + len(marker)
    if 1 <= len(spaces) <= 4:
        return marker_end + len(spaces)
    return marker_end + 1


def indent_of(line):
    return len(line) - len(line.lstrip())


def find_hits(lines):
    """Absorbed-prose hits as [(line_number, reason)], one per absorbed run.

    `paragraph_indent` holds the content indent of the list item whose
    paragraph is currently open, or None when no such paragraph is. Lowering
    it to the hit's own indent after reporting is what collapses a run of
    absorbed lines into the single defect it is.
    """
    hits = []
    in_fence = False
    in_frontmatter = bool(lines) and bool(FRONTMATTER.match(lines[0]))
    paragraph_indent = None

    for index, line in enumerate(lines):
        if in_frontmatter:
            # The opening --- is line 0, so only a LATER --- closes the block.
            if index > 0 and FRONTMATTER.match(line):
                in_frontmatter = False
            continue

        if FENCE.match(line):
            in_fence = not in_fence
            paragraph_indent = None
            continue
        if in_fence:
            continue

        if not line.strip():
            paragraph_indent = None
            continue

        marker_match = LIST_MARKER.match(line)
        if marker_match:
            paragraph_indent = content_indent_of(marker_match)
            continue

        if paragraph_indent is None:
            continue

        if any(pattern.match(line) for pattern in PARAGRAPH_INTERRUPTERS):
            paragraph_indent = None
            continue

        line_indent = indent_of(line)
        if line_indent < paragraph_indent:
            reason = f"lazy-continuation:{line_indent}-under-{paragraph_indent}"
            hits.append((index + 1, reason))
            paragraph_indent = line_indent

    return hits


def get_changed_line_numbers(path):
    """Line numbers `path` changed vs HEAD, per get-changed-lines.sh's own
    contract. Shelling out to the same helper check-bullet-gap.py and
    check-hard-wrap.py use keeps all three from disagreeing about what
    "changed" means. Raises ChangedLinesError on a non-zero exit rather than
    treating failure as clean or as whole-file-in-scope."""
    result = subprocess.run(
        [str(CHANGED_LINES_SCRIPT), str(path)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise ChangedLinesError(path)
    return {int(line) for line in result.stdout.split()}


def check(path, changed_only=False):
    with open(path, encoding="utf-8") as fh:
        lines = fh.read().splitlines()

    hits = find_hits(lines)

    if changed_only:
        changed = get_changed_line_numbers(path)
        hits = [(line_no, reason) for line_no, reason in hits if line_no in changed]

    if hits:
        print(f"== {path}")
        for line_no, reason in hits:
            print(f"{line_no}:{reason}")

    return len(hits)


def main(argv):
    files = []
    changed_only = False

    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--":
            files.extend(argv[i + 1:])
            break
        if arg == "--changed-only":
            changed_only = True
            i += 1
            continue
        if arg.startswith("-"):
            print(f"unknown opt: {arg}", file=sys.stderr)
            return 2
        files.append(arg)
        i += 1

    if not files:
        print(
            "usage: check-lazy-continuation.py [--changed-only] <file> [<file>...]",
            file=sys.stderr,
        )
        return 2

    total = 0
    for path in files:
        try:
            total += check(path, changed_only)
        except OSError as err:
            print(f"cannot read {path}: {err}", file=sys.stderr)
            return 2
        except ChangedLinesError as err:
            print(f"get-changed-lines.sh failed for {err}", file=sys.stderr)
            return 2

    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
