#!/usr/bin/env python3
"""check-hard-wrap.py - flag prose paragraphs hard-wrapped across physical lines.

Rule (doc-standards, "Density"): "In standalone markdown docs, keep each prose
paragraph on a single physical line - never hard-wrap mid-paragraph; rely on
the editor's soft-wrap."

Nothing else enforced this. check-density.sh only flags lines OVER the cap, so
hard-wrapping is not merely unchecked - it actively DEFEATS that check: a
60-word paragraph broken into three 20-word lines passes every line while
costing the reader the same 60 words.

DETECTION ONLY - do not add a --fix pass.

check-bullet-gap.py has one, so the absence here reads like an omission. It is
not. The mechanical fix for a hard wrap is joining the lines, and a join
produces exactly the over-cap lines check-density.sh exists to reject: joining
references/rename-list.md's 147 lines down to 131 turns a clean density run
into four hits (370, 289, 292 and 257 chars against a 256-char cap).

A --fix whose output fails a sibling checker is a broken tool. The rule's own
remedy is "over the cap, split on a sentence boundary - never drop info to
fit", and choosing that boundary is an authorial decision, not a transform. So
unwrapping is join-THEN-split, and it has to satisfy both checkers at once.

AI-consumed output (compact, parseable - mirrors check-density.sh):
  == <filename>          header, printed once per file that has hits
  <line>:continues-prose    the line continues a prose line above it
  <line>:continues-bullet   the line continues a bullet above it

Both reasons are violations. They are counted separately so the unwrap diff
stays auditable, not because one is tolerated.

Usage:
  check-hard-wrap.py [--changed-only] <file> [<file>...]

--changed-only scopes every reported hit to the lines get-changed-lines.sh
reports as changed vs HEAD for that same file, so a fixer's convergence
loop never re-reports a violation that predates the session's own edits.
The scope check is the CONTINUATION line's own number (the line already
printed), never the line it continues - see find_hits()'s docstring.

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

BULLET = re.compile(r"^(\s*)([-*+]|\d+\.)\s")
FENCE = re.compile(r"^\s*(```|~~~)")
FRONTMATTER = re.compile(r"^---\s*$")
TABLE_ROW = re.compile(r"^\s*\|")
BLOCKQUOTE = re.compile(r"^\s*>")
SETEXT_UNDERLINE = re.compile(r"^\s*(=+|-+)\s*$")
ATX_HEADING = re.compile(r"^\s*#")
HORIZONTAL_RULE = re.compile(r"^\s*(\*{3,}|-{3,}|_{3,})\s*$")
LINK_REF_DEF = re.compile(r"^\s*\[[^\]]+\]:\s")
HTML_TAG_ONLY = re.compile(r"^\s*</?[a-zA-Z][^>]*>\s*$")
LINK_ONLY = re.compile(r"^\s*([>*+-]|\d+\.)?\s*\[[^\]]+\]\([^)]+\)\s*\.?\s*$")


def is_setext_underline(line, previous):
    """True when `line` underlines `previous` into a setext heading.

    Context-dependent, so it cannot join the classifier above: the very same
    `-----` is a heading underline after a title and a horizontal rule after a
    blank line. Getting this wrong is destructive rather than merely noisy -
    the report says "joinable", and joining an underline into its title
    silently deletes the heading.
    """
    return bool(SETEXT_UNDERLINE.match(line)) and bool(previous.strip())


def is_continuable_prose(line):
    """True when this line is body prose a paragraph could be wrapped across.

    This is the inverse of check-density.sh's skip-set: a line that script
    declines to MEASURE is a line this script must decline to JOIN, so the two
    never disagree about what counts as a paragraph.
    """
    if not line.strip():
        return False
    if FENCE.match(line):
        return False
    # Each of these carries its own per-line marker, so consecutive ones are
    # structure the author wrote deliberately, not an unmarked wrap.
    if TABLE_ROW.match(line):
        return False
    if BLOCKQUOTE.match(line):
        return False
    if ATX_HEADING.match(line):
        return False
    if HORIZONTAL_RULE.match(line):
        return False
    if LINK_REF_DEF.match(line):
        return False
    if HTML_TAG_ONLY.match(line):
        return False
    if LINK_ONLY.match(line):
        return False
    return True


def find_hits(lines):
    """(line_number, reason) for every line continuing the line above it."""
    hits = []
    in_fence = False
    # Frontmatter only exists as a leading block, so the opening --- must be
    # line 0; a bare --- anywhere else is a horizontal rule, not a delimiter.
    in_frontmatter = bool(lines) and bool(FRONTMATTER.match(lines[0]))

    for i, line in enumerate(lines):
        if in_frontmatter:
            if i > 0 and FRONTMATTER.match(line):
                in_frontmatter = False
            continue

        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue

        if i == 0:
            continue

        # A bullet OPENS a block, so it is never a continuation of the line
        # above it. A bullet flush against preceding prose is the bullet-gap
        # concern check-bullet-gap.py owns, not a hard wrap.
        if BULLET.match(line):
            continue

        previous = lines[i - 1]
        if not is_continuable_prose(line):
            continue

        if is_setext_underline(line, previous):
            continue

        # Two trailing spaces and a trailing backslash are markdown's two
        # explicit hard breaks - authored, visible in the render, and destroyed
        # by joining. Only an UNMARKED break is a hard wrap.
        if previous.endswith("  ") or previous.endswith("\\"):
            continue

        if BULLET.match(previous):
            hits.append((i + 1, "continues-bullet"))
        elif is_continuable_prose(previous):
            hits.append((i + 1, "continues-prose"))

    return hits


class ChangedLinesError(Exception):
    """get-changed-lines.sh failed to determine scope for one file."""


def get_changed_line_numbers(path):
    """The set of line numbers get-changed-lines.sh reports as changed for
    `path` vs HEAD. Never reimplements its git/awk logic - shells out to
    the one shared helper every doc-standards checker's --changed-only
    scopes itself against, so they can never disagree on what "changed"
    means. Raises ChangedLinesError on a non-zero exit rather than
    treating failure as clean or as whole-file-in-scope."""
    result = subprocess.run(
        [str(CHANGED_LINES_SCRIPT), str(path)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise ChangedLinesError(path)
    return {int(line) for line in result.stdout.splitlines() if line.strip()}


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
            "usage: check-hard-wrap.py [--changed-only] <file> [<file>...]",
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
