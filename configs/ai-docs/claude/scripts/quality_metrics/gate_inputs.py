"""Judges a branch by gate inputs read from the base ref.

A branch that edits the inputs it is measured by could pass its own
gate. So a suppression comment it adds is listed as a violation.

A suppression counts as added when the diff holds more of that token
on its added lines than on its removed ones, so moving or keeping one
is silent.
"""

import sys
from collections import Counter, defaultdict
from pathlib import Path

from quality_metrics.tools import run_tool

# The edit-time hook owns the suppression pattern, so a token it
# blocks is also listed here.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "hooks" / "lib"))
from suppression_patterns import PROSE_SUFFIXES, SUPPRESSION_PATTERN

SUPPRESSION_KIND = "suppression"

HUNK_HEADER = "@@"
FILE_HEADER_PREFIX = "diff --git"
NEW_FILE_HEADER = "+++ b/"
NO_NEW_FILE = "+++ /dev/null"


def find_violations(repo_dir, base_ref, head_ref=None):
    """Every suppression the branch adds.

    `head_ref` None means the working tree, untracked files
    included.
    """
    return added_suppressions(repo_dir, base_ref, head_ref)


def added_suppressions(repo_dir, base_ref, head_ref=None):
    added_by_file, removed_by_file = _suppression_counts_in_diff(
        repo_dir, base_ref, head_ref
    )
    if head_ref is None:
        for path, text in _untracked_texts(repo_dir).items():
            added_by_file[path] += _count_suppressions(text)
    violations = []
    for path, added in added_by_file.items():
        if path.lower().endswith(PROSE_SUFFIXES):
            continue
        net_added = added - removed_by_file[path]
        violations += [
            {"kind": SUPPRESSION_KIND, "file": path, "value": token}
            for token in sorted(net_added.elements())
        ]
    return violations


def _suppression_counts_in_diff(repo_dir, base_ref, head_ref):
    refs = [base_ref] if head_ref is None else [base_ref, head_ref]
    diff_text = run_tool(
        ["git", "-c", "core.quotepath=false", "diff", "--no-ext-diff",
         "--no-color", "--relative", "-U0", *refs],
        cwd=repo_dir,
    )
    added_by_file = defaultdict(Counter)
    removed_by_file = defaultdict(Counter)
    current_path = None
    is_in_hunk = False
    for line in diff_text.splitlines():
        if line.startswith(FILE_HEADER_PREFIX):
            current_path, is_in_hunk = None, False
        elif is_in_hunk and current_path and line[:1] == "+":
            added_by_file[current_path] += _count_suppressions(line[1:])
        elif is_in_hunk and current_path and line[:1] == "-":
            removed_by_file[current_path] += _count_suppressions(line[1:])
        elif line.startswith(HUNK_HEADER):
            is_in_hunk = True
        elif line.startswith(NO_NEW_FILE):
            current_path = None
        elif line.startswith(NEW_FILE_HEADER):
            # A name holding a space gets a trailing tab.
            current_path = line[len(NEW_FILE_HEADER):].split("\t")[0]
    return added_by_file, removed_by_file


def _count_suppressions(text):
    return Counter(SUPPRESSION_PATTERN.findall(text))


def _untracked_texts(repo_dir):
    # NUL-separated output skips git's quoting of unusual names.
    listing = run_tool(
        ["git", "ls-files", "-z", "--others", "--exclude-standard"], cwd=repo_dir
    )
    texts = {}
    for name in filter(None, listing.split("\0")):
        try:
            texts[name] = (Path(repo_dir) / name).read_text()
        except (UnicodeDecodeError, OSError):
            continue
    return texts
