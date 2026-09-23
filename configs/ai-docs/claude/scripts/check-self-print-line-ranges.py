#!/usr/bin/env python3
# check-self-print-line-ranges.py - flag shell scripts that
# print part of their own source through a fixed numeric line
# range.
#
# Usage:
#   check-self-print-line-ranges.py [--repo-root <dir>]
#
# stdin: none
# stdout: one "<path>:<line>" per hit, path repo-root-relative
# exit: 0 no hits, 1 at least one hit, 2 usage error or
#   --repo-root not a git repo
import argparse
import re
import shlex
import subprocess
import sys
from pathlib import Path

DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[4]

SCAN_DIR = "configs"

# The two spellings a script uses to name its own file, as
# shlex returns them once any surrounding quotes are gone.
SELF_REFERENCES = {"$0", "${BASH_SOURCE[0]}"}

BASH_SHEBANG = re.compile(r"^#!.*\b(bash|sh)\b")

# sed -n '2,14p', or '15q' with no -n: both stop at a line
# number fixed at edit time.
SED_PRINT_RANGE = re.compile(r"^\d+(,\d+)?p$")
SED_QUIT_AT_LINE = re.compile(r"^\d+q$")

HEAD_COUNT_FLAG = re.compile(r"^(-\d+|-n\d+|--lines=\d+)$")
DIGITS = re.compile(r"^\d+$")

# NR<=14, NR<14, 14>=NR, or the range pattern NR==2,NR==14.
# A lower bound alone (NR > 1) reads to the end of the
# block, so it stays unflagged.
AWK_LINE_CAP = re.compile(
    r"\bF?NR\s*<=?\s*\d+"
    r"|\d+\s*>=?\s*F?NR\b"
    r"|\bF?NR\s*==\s*\d+\s*,\s*F?NR\s*==\s*\d+"
)

# Tokens that end one simple command and start the next.
COMMAND_SEPARATOR = re.compile(r"^[|&;()]+$")
OUTPUT_REDIRECT = re.compile(r"^\d*>>?&?$")

# Words that can open a simple command without being its
# program, as in `usage() { sed ...; }` or `then head ...`.
COMMAND_PREFIXES = {"{", "}", "!", "then", "do", "else", "command"}


def list_tracked_files(repo_root):
    """Return every tracked path under SCAN_DIR, repo-root-relative.
    -z keeps paths with spaces or unicode intact."""
    completed = subprocess.run(
        ["git", "-C", str(repo_root), "ls-files", "-z", "--", SCAN_DIR],
        capture_output=True,
        text=True,
        check=True,
    )
    return sorted(p for p in completed.stdout.split("\0") if p)


def is_shell_script(path):
    """True for a *.sh file, or any file whose first line is a
    bash/sh shebang. A symlink is skipped so a linked script is
    never reported twice."""
    if path.is_symlink() or not path.is_file():
        return False
    if path.suffix == ".sh":
        return True
    with path.open("rb") as handle:
        first_line = handle.readline().decode("utf-8", "replace")
    return bool(BASH_SHEBANG.match(first_line))


def join_continued_lines(text):
    """Yield (first_line_number, logical_line), folding every
    trailing-backslash continuation into the line it started on."""
    pending = []
    start = 0
    for number, line in enumerate(text.splitlines(), start=1):
        if not pending:
            start = number
        if line.endswith("\\"):
            pending.append(line[:-1])
            continue
        pending.append(line)
        yield start, " ".join(pending)
        pending = []
    if pending:
        yield start, " ".join(pending)


def split_simple_commands(line):
    """Return the line's simple commands as lists of words, quotes
    already removed. A line shlex cannot tokenize (a quote opened
    on another line, a here-doc body) returns no commands."""
    lexer = shlex.shlex(line, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    lexer.commenters = ""
    try:
        tokens = list(lexer)
    except ValueError:
        return []

    commands = [[]]
    skip_redirect_target = False
    for token in tokens:
        if skip_redirect_target:
            skip_redirect_target = False
            continue
        if token.startswith("#"):
            break
        if COMMAND_SEPARATOR.match(token):
            commands.append([])
            continue
        if OUTPUT_REDIRECT.match(token):
            skip_redirect_target = True
            continue
        if token == "<":
            continue
        commands[-1].append(token)
    return [words for words in commands if words]


def is_sed_line_slice(args):
    has_quiet_flag = "-n" in args
    for arg in args:
        if has_quiet_flag and SED_PRINT_RANGE.match(arg):
            return True
        if SED_QUIT_AT_LINE.match(arg):
            return True
    return False


def is_head_line_slice(args):
    for index, arg in enumerate(args):
        if HEAD_COUNT_FLAG.match(arg):
            return True
        next_arg = args[index + 1] if index + 1 < len(args) else ""
        if arg == "-n" and DIGITS.match(next_arg):
            return True
    return False


def is_awk_line_slice(args):
    return any(AWK_LINE_CAP.search(arg) for arg in args)


LINE_SLICERS = {
    "sed": is_sed_line_slice,
    "head": is_head_line_slice,
    "awk": is_awk_line_slice,
}


def slices_own_source(words):
    """True when one simple command cuts a fixed line range out of
    the script's own file. The self-reference must be a whole word,
    so an awk program's own $0 (the current record) never counts."""
    while words and words[0] in COMMAND_PREFIXES:
        words = words[1:]
    if not words:
        return False
    command, args = words[0], words[1:]
    is_line_slice = LINE_SLICERS.get(command)
    if is_line_slice is None:
        return False
    reads_itself = any(arg in SELF_REFERENCES for arg in args)
    return reads_itself and is_line_slice(args)


def find_hits(repo_root, relpath):
    text = (repo_root / relpath).read_text(encoding="utf-8", errors="replace")
    hits = []
    for number, line in join_continued_lines(text):
        if line.lstrip().startswith("#"):
            continue
        commands = split_simple_commands(line)
        if any(slices_own_source(words) for words in commands):
            hits.append(f"{relpath}:{number}")
    return hits


def main():
    parser = argparse.ArgumentParser(
        description="Flag shell scripts that print part of their own "
        "source through a fixed numeric line range."
    )
    parser.add_argument("--repo-root", default=str(DEFAULT_REPO_ROOT))
    args = parser.parse_args()

    repo_root = Path(args.repo_root).expanduser().resolve()

    try:
        relpaths = list_tracked_files(repo_root)
    except subprocess.CalledProcessError as error:
        print(
            f"--repo-root must be a git repo; git said: {error.stderr.strip()}",
            file=sys.stderr,
        )
        return 2

    hits = []
    for relpath in relpaths:
        if is_shell_script(repo_root / relpath):
            hits.extend(find_hits(repo_root, relpath))

    for hit in hits:
        print(hit)
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
