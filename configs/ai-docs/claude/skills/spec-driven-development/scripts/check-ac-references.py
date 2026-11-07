#!/usr/bin/env python3
"""check-ac-references.py - flag every line of a spec or plan that
cites an acceptance criterion by its `AC-<n>` ID instead of spelling
out the behavior.

Anchors - the places another gate joins on the ID - are exempt:
  - the spec's `### AC-<n>:` and `### Retired: AC-<n>` headings
  - the plan's `- **AC-<n>**` coverage-list headers
  - inside a fence, a trailing `// AC-<n>... T<n>... [on-demand]`
    annotation, or the exact line
    `// AC-<n> - prose, verified by direct-coder diff review, no test`
  - the bullet lines of a `## Task Details` entry's
    `**Testable Acceptance criteria**` field, read with the same rule
    check-ac-task-consistency.py uses to join them

Only the anchor itself is exempt: an ID elsewhere on the same line,
such as one inside an it() title before its annotation, still counts.

Usage:
  check-ac-references.py <doc> [<doc>...]

stdout: one `<file>:<line>: <text>` per line citing an ID
stderr: a diagnostic on a usage error or an unreadable file
exit: 0 no citation; 1 at least one citation; 2 usage error, or a file
      missing, unreadable or not valid UTF-8
"""

import importlib.util
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
USAGE = "usage: check-ac-references.py <doc> [<doc>...]"

AC_ID = re.compile(r"AC-\d+")
SECTION_HEADING = re.compile(r"^## ")
DETAILS_HEADING = re.compile(r"^## Task Details[ \t]*$")
SUMMARY_TASK = re.compile(r"<summary>Task \d+")
AC_FIELD = re.compile(r"\*\*Testable Acceptance criteria\*\*")

# Each pattern matches only the anchor, so the rest of the line
# is still scanned.
LINE_ANCHORS = (
    re.compile(r"^### AC-\d+:"),
    re.compile(r"^### Retired: AC-\d+"),
    re.compile(r"^[ \t]*- \*\*AC-\d+\*\*"),
)

# check-ac-coverage.sh's PROSE_AC_MARKER_RE, the one line it
# accepts as coverage of a prose criterion.
PROSE_MARKER = re.compile(
    r"^[ \t]*// AC-\d+ - prose, verified by direct-coder diff review, no test[ \t]*$"
)

# Every token is anchored by a literal (`AC-`, `T`, `[`), so the
# repeats cannot backtrack catastrophically on a long line.
TRAILING_ANNOTATION = re.compile(
    r"//[ \t]*(?:AC-\d+[ \t]*)+(?:T\d+[ \t]*)*(?:\[on-demand\][ \t]*)?$"
)

# The fence rule is shared repo-wide; loaded by path because the
# hyphenated name blocks an import.
PARSE_FENCES = SCRIPT_DIR.parents[2] / "scripts" / "parse-fences.py"
_spec = importlib.util.spec_from_file_location("parse_fences", PARSE_FENCES)

try:
    if _spec is None or _spec.loader is None:
        raise ImportError("no import spec")
    parse_fences = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(parse_fences)
except Exception as error:
    print(
        f"check-ac-references.py: cannot load {PARSE_FENCES}: {error}",
        file=sys.stderr,
    )
    sys.exit(2)

toggle_fence = parse_fences.toggle_fence


def strip_anchors(text, is_fenced):
    """The line with every anchor removed, leaving only the text
    an ID citation would be prose in."""
    if is_fenced:
        if PROSE_MARKER.match(text):
            return ""
        return TRAILING_ANNOTATION.sub("", text)
    for anchor in LINE_ANCHORS:
        text = anchor.sub("", text, count=1)
    return text


def find_citations(lines):
    """1-based numbers of the lines citing an ID outside an anchor."""
    citations = []
    in_fence = False
    fence_char = ""
    fence_len = 0
    in_details = False
    in_ac_field = False

    for number, text in enumerate(lines, start=1):
        in_fence, fence_char, fence_len = toggle_fence(
            text, in_fence, fence_char, fence_len
        )

        if not in_fence:
            if SECTION_HEADING.match(text):
                in_details = bool(DETAILS_HEADING.match(text))
                in_ac_field = False
            elif in_details and SUMMARY_TASK.search(text):
                in_ac_field = False
            elif in_details and AC_FIELD.search(text):
                # The field's tokens sit on the lines below
                # its marker; the sibling gate never reads the
                # marker line, so an ID there is still prose.
                in_ac_field = True
                if AC_ID.search(text):
                    citations.append(number)
                continue
            elif in_ac_field:
                if not text.strip():
                    in_ac_field = False
                continue

        if AC_ID.search(strip_anchors(text, in_fence)):
            citations.append(number)

    return citations


def read_lines(path):
    try:
        return Path(path).read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        print(f"error: file not found: {path}", file=sys.stderr)
    except (OSError, UnicodeDecodeError) as error:
        print(f"error: cannot read {path}: {error}", file=sys.stderr)
    sys.exit(2)


def main():
    args = sys.argv[1:]
    if args and args[0] in ("-h", "--help"):
        print(USAGE)
        return 0
    if not args:
        print(USAGE, file=sys.stderr)
        return 2

    documents = [(path, read_lines(path)) for path in args]

    found = False
    for path, lines in documents:
        for number in find_citations(lines):
            print(f"{path}:{number}: {lines[number - 1]}")
            found = True

    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
