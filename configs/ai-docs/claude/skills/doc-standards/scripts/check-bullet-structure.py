#!/usr/bin/env python3
"""check-bullet-structure.py - flag list items whose nesting misleads the reader.

Rules:
  dangling-colon  a list item ending in ":" whose next list item sits at the
                  same or a shallower indent, so the colon introduces nothing.
  staircase       3+ list items chained as single children, each one level
                  deeper than the last - sibling sentences pushed down a level.

Output (mirrors check-bullet-gap.py):
  == <filename>                 header, per file with hits
  <line>:dangling-colon         the colon-ended item
  <line>:staircase:<A>-<B>      the chain's head, and its first-last line span

Report-only, no --fix: nesting the items after a colon versus ending it with a
period, or flattening a chain versus keeping one level, is an authorial call.

--changed-only keeps a hit when ANY line it spans changed vs HEAD, per
get-changed-lines.sh - the colon line or the item after it, any chain level.

Usage:
  check-bullet-structure.py [--changed-only] <file> [<file>...]

Exit codes:
  0  clean
  1  violations found
  2  usage error, get-changed-lines.sh failed, or check-bullet-gap.py
     could not be loaded (one stderr line names it and the directory)
"""

import importlib.util
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent

# Loaded by path because the hyphenated name blocks an import.
#
# Sharing check-bullet-gap.py's list parsing keeps the two
# checkers from disagreeing on what a list item is.
_spec = importlib.util.spec_from_file_location(
    "check_bullet_gap", SCRIPT_DIR / "check-bullet-gap.py"
)

# A load failure exits 2: the hook reads exit 1 as findings.

# Nothing imports this script, so exiting at import is safe.
try:
    if _spec is None or _spec.loader is None:
        raise ImportError("no import spec")
    bullet_gap = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(bullet_gap)
except Exception as error:
    print(
        f"check-bullet-structure.py: cannot load check-bullet-gap.py "
        f"from {SCRIPT_DIR}: {error}",
        file=sys.stderr,
    )
    sys.exit(2)

USAGE = "usage: check-bullet-structure.py [--changed-only] <file>..."

INLINE_CODE = re.compile(r"`[^`]*`")
CODE_SPAN_STAND_IN = "code"
TRAILING_EMPHASIS = re.compile(r"[*_\s]+$")


class ListItem:
    def __init__(self, line_no, indent, parent):
        self.line_no = line_no
        self.indent = indent
        self.parent = parent
        self.children = []


def indent_width(line):
    return len(line) - len(line.lstrip())


def build_list_items(lines, kinds):
    """Every list item outside code and frontmatter, linked to its parent.

    Blank lines never break a parent/child link. A non-list line closes
    every open item at or deeper than its own indent, so a deeper
    continuation paragraph or fence keeps its item open, while a heading
    or paragraph at the margin ends the list.
    """
    items = []
    open_items = []

    for i, line in enumerate(lines):
        is_markdown = kinds[i] in ("text", "fence")
        if not is_markdown or not line.strip():
            continue

        indent = indent_width(line)
        while open_items and open_items[-1].indent >= indent:
            open_items.pop()

        if kinds[i] != "text" or bullet_gap.indent_of(line) is None:
            continue

        parent = open_items[-1] if open_items else None
        item = ListItem(i + 1, indent, parent)
        if parent:
            parent.children.append(item)
        items.append(item)
        open_items.append(item)

    return items


def ends_with_colon(line):
    """True when the item's own text ends in ":".

    Each inline code span becomes one opaque word, so a colon inside it
    never counts, and a "Label: <code span>" item ends in the span.
    A closing bold marker after the colon hides nothing."""
    text = INLINE_CODE.sub(CODE_SPAN_STAND_IN, line)
    text = TRAILING_EMPHASIS.sub("", text)
    return text.endswith(":")


def next_non_blank_index(lines, start):
    for j in range(start, len(lines)):
        if lines[j].strip():
            return j
    return None


def find_dangling_colons(lines, kinds, items):
    hits = []
    for item in items:
        if not ends_with_colon(lines[item.line_no - 1]):
            continue

        j = next_non_blank_index(lines, item.line_no)
        if j is None or kinds[j] != "text":
            continue

        next_indent = bullet_gap.indent_of(lines[j])
        is_sibling_or_shallower = next_indent is not None and next_indent <= item.indent
        if is_sibling_or_shallower:
            hits.append((item.line_no, "dangling-colon", {item.line_no, j + 1}))
    return hits


def has_single_child(item):
    return len(item.children) == 1


def find_staircases(items):
    """One hit per chain, at its head: the topmost item whose single child
    also has a single child. Its parent, when it has one, has siblings."""
    hits = []
    for item in items:
        starts_chain = has_single_child(item) and has_single_child(item.children[0])
        continues_parent_chain = item.parent is not None and has_single_child(item.parent)
        if not starts_chain or continues_parent_chain:
            continue

        chain = [item]
        while has_single_child(chain[-1]):
            chain.append(chain[-1].children[0])

        head, last = chain[0].line_no, chain[-1].line_no
        hits.append((head, f"staircase:{head}-{last}", {n.line_no for n in chain}))
    return hits


def find_hits(lines):
    """(line, detail, scope_lines) per violation, in line order."""
    kinds = bullet_gap.classify_lines(lines)
    items = build_list_items(lines, kinds)
    hits = find_dangling_colons(lines, kinds, items) + find_staircases(items)
    return sorted(hits, key=lambda hit: hit[0])


def check(path, changed_only):
    with open(path, encoding="utf-8") as fh:
        lines = fh.read().splitlines()

    hits = find_hits(lines)
    if changed_only:
        changed = bullet_gap.get_changed_line_set(path)
        hits = [hit for hit in hits if hit[2] & changed]

    if hits:
        print(f"== {path}")
        for line_no, detail, _scope in hits:
            print(f"{line_no}:{detail}")

    return len(hits)


def main(argv):
    changed_only = False
    files = []

    for i, arg in enumerate(argv):
        if arg in ("-h", "--help"):
            print(USAGE)
            return 0
        if arg == "--changed-only":
            changed_only = True
        elif arg == "--":
            files.extend(argv[i + 1:])
            break
        elif arg.startswith("-"):
            print(f"unknown opt: {arg}", file=sys.stderr)
            return 2
        else:
            files.append(arg)

    if not files:
        print(USAGE, file=sys.stderr)
        return 2

    total = 0
    for path in files:
        try:
            total += check(path, changed_only)
        except OSError as err:
            print(f"cannot read {path}: {err}", file=sys.stderr)
            return 2
        except RuntimeError as err:
            print(str(err), file=sys.stderr)
            return 2

    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
