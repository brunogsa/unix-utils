#!/usr/bin/env python3
"""fix-density.py - deterministically repair the mechanically-fixable subset
of doc-standards density violations: gap-missing bullets and over-cap lines
with a safe sentence-boundary split.

Never reimplements check-bullet-gap.py's or check-density.sh's skip logic
(frontmatter/fenced-code/mermaid/table/HTML-only/link-only lines) - it shells
out to both and only acts on the lines they report as violations, so the two
checkers stay the single source of truth for what counts as "prose" here.

A split bullet's second half is emitted as its own indented sub-bullet,
never as a bare continuation line. A continuation line joins the parent's
rendered bullet, so it would shorten the physical line and turn the check
green while leaving the reader exactly as much to read.

Splitting is conservative: a line is split only at a recognized boundary
(". ", " — ", " -- ", "; ") whose remainder doesn't already start with a
markdown structural token (a bullet/heading/table/blockquote/ordered-list
marker) - re-marking an already-marked remainder would double its marker
or nest it under the wrong parent - and whose first half doesn't strand an
unclosed "(", "[", or an odd number of "`" code-span delimiters, which
would break a bracket pair or a code span across the two resulting lines.
When no such boundary exists on a line, the line is left fully untouched
and reported as residue - never deleted, truncated, or reworded.

Runs check-bullet-gap.py --fix and one split pass to convergence (a pass
that changes nothing), capped at MAX_ITERATIONS passes per file, so a split
that leaves one half still over cap gets a further pass at splitting that
half again on the next iteration.

Usage:
  fix-density.py [--max-chars N] [--max-words N] <file> [<file>...]

Exit codes:
  0  fully clean (or fully resolved by fixing)
  1  residue remains - printed as <line>:<chars>:<words>, one per line
  2  usage error
"""

import re
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
BULLET_GAP_SCRIPT = SCRIPT_DIR / "check-bullet-gap.py"
DENSITY_SCRIPT = SCRIPT_DIR / "check-density.sh"

MAX_CHARS = 256
MAX_WORDS = 32
MAX_ITERATIONS = 10

BOUNDARY = re.compile(r"\. | — | -- |; ")
STRUCTURAL_TOKEN = re.compile(r"^(?:[-*+#|>]|\d+\.)")
BULLET_MARKER = re.compile(r"^([ \t]*)([-*+] |\d+\. )")
URL = re.compile(r"\(https?://[^)]*\)")
DATA_URI = re.compile(r"[(<]data:[^)>]*[)>]")

DENSITY_HIT = re.compile(r"^(\d+):(\d+):(\d+)$")


def measure(text):
    """Chars and words as check-density.sh counts them, after the same strips."""
    s = URL.sub("", text)
    s = DATA_URI.sub("", s)
    s = s.replace("[", "").replace("]", "")
    return len(s), len(s.split())


def is_first_half_balanced(first_half):
    """False when `first_half` would strand an unclosed "(", "[", or an
    odd number of "`" code-span delimiters on this line of the split -
    splitting there would break a bracket pair or a code span across the
    two resulting lines. Checked on the raw first half, before measure()'s
    strips - those strips are about display length, not split safety."""
    if first_half.count("(") > first_half.count(")"):
        return False
    if first_half.count("[") > first_half.count("]"):
        return False
    return first_half.count("`") % 2 == 0


def continuation_prefix(line):
    """The prefix `line`'s second half carries so it renders as its own
    element rather than joining the first half's. A bullet's second half
    nests one level under it, aligned past the parent's own marker; any
    other line carries the parent's indent alone."""
    marker = BULLET_MARKER.match(line)
    if marker:
        return marker.group(1) + " " * len(marker.group(2)) + "- "
    return line[: len(line) - len(line.lstrip(" \t"))]


def candidate_splits(line, max_chars, max_words):
    """Every safe (first_half, second_half) split of `line`, best first.

    "Safe" rejects a remainder that already starts with a markdown
    structural token - re-marking it as a sub-bullet would double its
    marker or nest it under the wrong parent - and rejects a first half
    that would strand an unclosed "(", "[", or an odd number of "`"
    code-span delimiters, breaking a bracket pair or code span across the
    split. Among the safe candidates, one where both halves land at/under
    the caps sorts first; ties (and the no-candidate-fits-both-caps case)
    break on how evenly the split balances the two halves, in characters.

    Each half is measured exactly as it will be emitted, prefix included,
    so a candidate ranked as fitting both caps still fits once written.
    """
    prefix = continuation_prefix(line)
    marker = BULLET_MARKER.match(line)
    marker_end = marker.end() if marker else 0
    safe = []

    for m in BOUNDARY.finditer(line):
        # An ordered-list marker ends in ". ", which is also a boundary -
        # splitting there would strand "1." as a bullet with no content.
        if m.end() <= marker_end:
            continue
        first = line[: m.end()].rstrip()
        remainder = line[m.end() :].lstrip()
        if not remainder or STRUCTURAL_TOKEN.match(remainder):
            continue
        if not is_first_half_balanced(first):
            continue

        second = prefix + remainder
        first_chars, first_words = measure(first)
        second_chars, second_words = measure(second)
        both_under_cap = (
            first_chars <= max_chars
            and first_words <= max_words
            and second_chars <= max_chars
            and second_words <= max_words
        )
        balance = abs(first_chars - second_chars)
        safe.append((0 if both_under_cap else 1, balance, first, second))

    safe.sort(key=lambda candidate: candidate[:2])
    return [(first, second) for _, _, first, second in safe]


def split_line(line, max_chars, max_words):
    """The single best safe split for `line`, or None when no boundary is safe."""
    candidates = candidate_splits(line, max_chars, max_words)
    return candidates[0] if candidates else None


def get_density_hits(path, max_chars, max_words):
    """Parse check-density.sh's <line>:<chars>:<words> rows for one file."""
    result = subprocess.run(
        [
            str(DENSITY_SCRIPT),
            "--max-chars",
            str(max_chars),
            "--max-words",
            str(max_words),
            str(path),
        ],
        capture_output=True,
        text=True,
    )
    hits = []
    for row in result.stdout.splitlines():
        m = DENSITY_HIT.match(row)
        if m:
            hits.append((int(m.group(1)), int(m.group(2)), int(m.group(3))))
    return hits


def split_pass(path, max_chars, max_words):
    """One bottom-to-top split pass over the file's current density hits.

    Bottom-to-top means an earlier (higher-line-number) insertion never
    shifts the still-queued line numbers of hits below it - the same
    guarantee check-bullet-gap.py's fix() relies on - so a single pass over
    one density-check's hit list is always enough per pass.
    """
    hits = get_density_hits(path, max_chars, max_words)
    if not hits:
        return [], False

    with open(path, encoding="utf-8") as fh:
        raw = fh.read()
    trailing_newline = raw.endswith("\n")
    lines = raw.splitlines()

    changed = False
    residue = []
    for line_no, chars, words in sorted(hits, reverse=True):
        split = split_line(lines[line_no - 1], max_chars, max_words)
        if split is None:
            residue.append((line_no, chars, words))
            continue
        first, second = split
        lines[line_no - 1] = first
        lines.insert(line_no, second)
        changed = True

    if changed:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + ("\n" if trailing_newline else ""))

    return residue, changed


def converge(path, max_chars, max_words):
    """Alternate bullet-gap --fix and a split pass until a pass changes
    nothing, capped at MAX_ITERATIONS - see the module docstring for why a
    single split pass isn't always enough (a freshly split half can still
    be over cap and need its own further split on the next pass)."""
    with open(path, encoding="utf-8") as fh:
        previous_content = fh.read()

    residue = []
    for _ in range(MAX_ITERATIONS):
        subprocess.run(
            [
                sys.executable,
                str(BULLET_GAP_SCRIPT),
                "--fix",
                "--max-chars",
                str(max_chars),
                "--max-words",
                str(max_words),
                str(path),
            ],
            capture_output=True,
            text=True,
        )
        residue, _ = split_pass(path, max_chars, max_words)

        with open(path, encoding="utf-8") as fh:
            current_content = fh.read()
        if current_content == previous_content:
            return residue
        previous_content = current_content

    print(
        f"fix-density.py: did not converge on {path} after {MAX_ITERATIONS} iterations",
        file=sys.stderr,
    )
    return residue


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
            files.extend(argv[i + 1 :])
            break
        elif arg.startswith("-"):
            print(f"unknown opt: {arg}", file=sys.stderr)
            return 2
        else:
            files.append(arg)
            i += 1

    if not files:
        print(
            "usage: fix-density.py [--max-chars N] [--max-words N] <file>...",
            file=sys.stderr,
        )
        return 2

    total_residue = 0
    for path in files:
        try:
            residue = converge(path, max_chars, max_words)
        except OSError as err:
            print(f"cannot read {path}: {err}", file=sys.stderr)
            return 2

        if residue:
            print(f"== {path}")
            for line_no, chars, words in sorted(residue):
                print(f"{line_no}:{chars}:{words}")
        total_residue += len(residue)

    return 1 if total_residue else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
