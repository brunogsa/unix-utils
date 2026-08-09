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
--fix applies it directly, bottom-to-top (highest line number first) so one
pass repairs every hit without a hit's own insertion shifting the line
numbers of hits still queued above it.

Usage:
  check-bullet-gap.py [--fix] [--max-chars N] [--max-words N] <file> [<file>...]

Exit codes:
  0  clean
  1  violations found (or, with --fix, violations remained after fixing)
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


def find_hits(lines, max_chars, max_words):
    """Bullet-gap hits in an already-split line list - the shared scan
    both check() and fix() run, so fixing can never drift from checking."""
    gap_chars = max_chars * GAP_RATIO
    gap_words = max_words * GAP_RATIO

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

    return hits


def check(path, max_chars, max_words):
    with open(path, encoding="utf-8") as fh:
        lines = fh.read().splitlines()

    hits = find_hits(lines, max_chars, max_words)

    if hits:
        print(f"== {path}")
        for line_no, detail in hits:
            print(f"{line_no}:{detail}")

    return len(hits)


def fix(path, max_chars, max_words):
    """Insert a blank line after every hit, bottom-to-top in one pass.

    Bottom-to-top means an earlier (higher-line-number) insertion never
    shifts the still-queued line numbers of hits below it, so a single
    pass over the original hit list is always enough - no re-scan loop
    needed between insertions.
    """
    with open(path, encoding="utf-8") as fh:
        raw = fh.read()
    trailing_newline = raw.endswith("\n")
    lines = raw.splitlines()

    hits = find_hits(lines, max_chars, max_words)
    if not hits:
        return 0

    for line_no, _detail in sorted(hits, reverse=True):
        lines.insert(line_no, "")

    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + ("\n" if trailing_newline else ""))

    # Defensive re-check: the insertion above is designed to always resolve
    # every hit in one pass (see the docstring), so this should stay 0 -
    # but a real remainder here is a correctness bug worth surfacing loudly
    # rather than reporting a false "clean".
    return len(find_hits(lines, max_chars, max_words))


def main(argv):
    max_chars, max_words = MAX_CHARS, MAX_WORDS
    fix_mode = False
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
        elif arg == "--fix":
            fix_mode = True
            i += 1
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
            "usage: check-bullet-gap.py [--fix] [--max-chars N] [--max-words N] <file>...",
            file=sys.stderr,
        )
        return 2

    total = 0
    for path in files:
        try:
            if fix_mode:
                total += fix(path, max_chars, max_words)
            else:
                total += check(path, max_chars, max_words)
        except OSError as err:
            print(f"cannot read {path}: {err}", file=sys.stderr)
            return 2

    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
