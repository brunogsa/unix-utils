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

--changed-only scopes both modes to the lines changed-lines.sh reports as
changed vs HEAD for that file. A hit whose reported line isn't in that set is
entirely invisible - not printed, not counted toward the exit code, and not
inserted-into by --fix - so a caller looping "until exit 0" never spins on a
pre-existing violation outside its own edits. Scope is recomputed fresh on
every call (no caching), and an untracked file's whole content already
counts as changed, so --changed-only there matches a full scan.

Usage:
  check-bullet-gap.py [--fix] [--changed-only] [--max-chars N] [--max-words N] <file> [<file>...]

Exit codes:
  0  clean
  1  violations found (or, with --fix, violations remained after fixing)
  2  usage error, or changed-lines.sh itself failed (not a git work tree,
     missing file)
"""

import re
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
CHANGED_LINES_SCRIPT = SCRIPT_DIR / "changed-lines.sh"

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


def get_changed_line_set(path):
    """Line numbers `path` changed vs HEAD, per changed-lines.sh's own
    contract (docstring at the top of that script): every line for an
    untracked file, only `git diff -U0 HEAD`'s added lines for a tracked
    and modified one, empty for a tracked and unmodified one.

    Shells out rather than reimplementing the git/awk logic locally, and is
    called fresh on every invocation - no caching - so a caller re-running
    --fix in a convergence loop always scopes against the file's current
    diff, not a stale one from an earlier pass.

    Raises RuntimeError, naming `path`, when changed-lines.sh itself exits
    non-zero (not a git work tree, missing file) - the caller must treat
    that as a hard failure, never as "clean" or "whole file in scope"."""
    result = subprocess.run(
        [str(CHANGED_LINES_SCRIPT), str(path)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"changed-lines.sh failed for {path}: {result.stderr.strip()}"
        )
    return {int(line) for line in result.stdout.split()}


def in_scope_hits(hits, path, changed_only):
    """`hits` filtered to changed-lines.sh's changed-line set for `path`,
    or `hits` unchanged when --changed-only wasn't requested."""
    if not changed_only:
        return hits
    changed = get_changed_line_set(path)
    return [hit for hit in hits if hit[0] in changed]


def check(path, max_chars, max_words, changed_only):
    with open(path, encoding="utf-8") as fh:
        lines = fh.read().splitlines()

    hits = in_scope_hits(find_hits(lines, max_chars, max_words), path, changed_only)

    if hits:
        print(f"== {path}")
        for line_no, detail in hits:
            print(f"{line_no}:{detail}")

    return len(hits)


def fix(path, max_chars, max_words, changed_only):
    """Insert a blank line after every in-scope hit, bottom-to-top in one
    pass.

    Bottom-to-top means an earlier (higher-line-number) insertion never
    shifts the still-queued line numbers of hits below it, so a single
    pass over the original hit list is always enough - no re-scan loop
    needed between insertions. An out-of-scope hit is never inserted-into
    at all, so it survives untouched for a later, in-scope pass.
    """
    with open(path, encoding="utf-8") as fh:
        raw = fh.read()
    trailing_newline = raw.endswith("\n")
    lines = raw.splitlines()

    hits = in_scope_hits(find_hits(lines, max_chars, max_words), path, changed_only)
    if not hits:
        return 0

    for line_no, _detail in sorted(hits, reverse=True):
        lines.insert(line_no, "")

    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + ("\n" if trailing_newline else ""))

    # Defensive re-check: the insertion above is designed to always resolve
    # every in-scope hit in one pass (see the docstring), so this should
    # stay 0 - but a real remainder here is a correctness bug worth
    # surfacing loudly rather than reporting a false "clean". Scope is
    # recomputed against the file just written, per get_changed_line_set's
    # own fresh-per-call contract.
    remaining = find_hits(lines, max_chars, max_words)
    return len(in_scope_hits(remaining, path, changed_only))


def main(argv):
    max_chars, max_words = MAX_CHARS, MAX_WORDS
    fix_mode = False
    changed_only = False
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
        elif arg == "--changed-only":
            changed_only = True
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
            "usage: check-bullet-gap.py [--fix] [--changed-only] "
            "[--max-chars N] [--max-words N] <file>...",
            file=sys.stderr,
        )
        return 2

    total = 0
    for path in files:
        try:
            if fix_mode:
                total += fix(path, max_chars, max_words, changed_only)
            else:
                total += check(path, max_chars, max_words, changed_only)
        except OSError as err:
            print(f"cannot read {path}: {err}", file=sys.stderr)
            return 2
        except RuntimeError as err:
            print(str(err), file=sys.stderr)
            return 2

    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
