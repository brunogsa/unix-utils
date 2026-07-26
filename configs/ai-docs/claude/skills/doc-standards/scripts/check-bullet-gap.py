#!/usr/bin/env python3
"""check-bullet-gap.py - flag bullets missing the doc-standards blank-line gap.

Rule: "Separate any bullet that has a sub-bullet or exceeds 80% of the density
cap from the next bullet with a blank line."

Both triggers reduce to one shape - a bullet that ends a GROUP sits flush
against the bullet starting the next group:

  sub-bullet   the line is a bullet DEEPER than the bullet on the next line,
               i.e. a nested block ending flush against its parent's sibling.
  over-80pct   the line is a bullet over 80% of the density cap (205 chars /
               26 words) and the next line is a bullet at the SAME or a
               SHALLOWER indent.

A bullet followed by its own DEEPER child never fires: the [Why] behind the
rule asks for a stopping point "between groups", and a parent plus its
sub-bullets is one group. The literal reading would flag every
[Instruction]/[Why] pair, which is the house style, not a defect.

Density is measured exactly as check-density.sh measures it - URLs, data URIs,
and [] brackets stripped first - so the two scripts never disagree about how
long a line is.

AI-consumed output (compact, parseable - mirrors check-density.sh):
  == <filename>                 header, per file with hits
  <line>:sub-bullet             one per violation
  <line>:over-80pct:<N>c/<N>w

The fix is the same for every hit: insert a blank line AFTER the reported line.

Usage:
  check-bullet-gap.py [--max-chars N] [--max-words N] <file> [<file>...]

Exit codes:
  0  clean
  1  violations found
  2  usage error
"""

import re
import sys

# Defaults mirror check-density.sh's caps; this script gates at 80% of them.
MAX_CHARS = 256
MAX_WORDS = 32
GAP_RATIO = 0.8

BULLET = re.compile(r"^(\s*)([-*+]|\d+\.)\s")
FENCE = re.compile(r"^\s*(```|~~~)")
FRONTMATTER = re.compile(r"^---\s*$")
URL = re.compile(r"\(https?://[^)]*\)")
DATA_URI = re.compile(r"[(<]data:[^)>]*[)>]")


def indent_of(line):
    """Indent width of a bullet line, or None when the line is not a bullet."""
    m = BULLET.match(line)
    return len(m.group(1)) if m else None


def measure(line):
    """Chars and words as check-density.sh counts them, after the same strips."""
    s = URL.sub("", line)
    s = DATA_URI.sub("", s)
    s = s.replace("[", "").replace("]", "")
    return len(s), len(s.split())


def check(path, max_chars, max_words):
    gap_chars = max_chars * GAP_RATIO
    gap_words = max_words * GAP_RATIO

    with open(path, encoding="utf-8") as fh:
        lines = fh.read().splitlines()

    hits = []
    in_fence = False
    in_frontmatter = bool(lines) and bool(FRONTMATTER.match(lines[0]))

    for i in range(len(lines) - 1):
        cur = lines[i]

        if in_frontmatter:
            # The opening --- is line 0, so only a LATER --- closes the block.
            if i > 0 and FRONTMATTER.match(cur):
                in_frontmatter = False
            continue

        if FENCE.match(cur):
            in_fence = not in_fence
            continue
        if in_fence:
            continue

        cur_indent = indent_of(cur)
        next_indent = indent_of(lines[i + 1])
        if cur_indent is None or next_indent is None:
            continue

        if cur_indent > next_indent:
            hits.append((i + 1, "sub-bullet"))
            continue

        # A DEEPER next bullet is this bullet's own child - same group, no gap.
        if cur_indent < next_indent:
            continue

        chars, words = measure(cur)
        if chars > gap_chars or words > gap_words:
            hits.append((i + 1, f"over-80pct:{chars}c/{words}w"))

    if hits:
        print(f"== {path}")
        for line_no, detail in hits:
            print(f"{line_no}:{detail}")

    return len(hits)


def main(argv):
    max_chars, max_words = MAX_CHARS, MAX_WORDS
    files = []

    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--max-chars":
            max_chars = int(argv[i + 1])
            i += 2
        elif arg == "--max-words":
            max_words = int(argv[i + 1])
            i += 2
        elif arg == "--":
            files.extend(argv[i + 1:])
            break
        elif arg.startswith("-"):
            print(f"unknown opt: {arg}", file=sys.stderr)
            return 2
        else:
            files.append(arg)
            i += 1

    if not files:
        print(
            "usage: check-bullet-gap.py [--max-chars N] [--max-words N] <file>...",
            file=sys.stderr,
        )
        return 2

    total = 0
    for path in files:
        try:
            total += check(path, max_chars, max_words)
        except OSError as err:
            print(f"cannot read {path}: {err}", file=sys.stderr)
            return 2

    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
