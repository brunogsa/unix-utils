"""Measures duplicated code and duplicated tests with jscpd.

jscpd's --similarity pairs functions by structure: names and
literals are normalized away, so two functions differing only in
them score 1.0. A verbatim block inside two different
functions is a token clone with no similarity, also
scored 1.0: it flags an exact copy, not equal functions.
It leaves test files out by name, so every file is staged under
a neutral name before the scan.
Source files are compared with source files and test files with
test files, which keeps the two findings apart.
A touched file is compared with the repo's files of its kind,
committed or not, and a pair is flagged when it overlaps a
touched line.
"""

import json
import shutil
import tempfile
from pathlib import Path

from quality_metrics.declaration import is_excluded_path, is_test_file
from quality_metrics.functions import measurement
from quality_metrics.repo_paths import repo_relative
from quality_metrics.tools import run_tool

CODE_METRIC = "code_duplication"
TEST_METRIC = "test_duplication"

SIMILARITY_LIMIT = 0.82

# A duplicate is flagged from MIN_LINES lines, in both jscpd
# detectors.
#
# An exact token clone is flagged from --min-lines identical
# lines, and only when it also reaches jscpd's 50-token default.
#
# A similar function pair (--similarity) is flagged only when
# each function has --min-lines + 1 lines.
#
# So jscpd scans at MIN_LINES - 1, and an exact clone, which
# carries no similarity, is kept only when it spans MIN_LINES
# identical lines.
MIN_LINES = 4

# Tests repeat their arrange steps on purpose, so a test
# duplicate is flagged only from 8 lines up.
TEST_MIN_LINES = 8

# --similarity does not read the languages the declaration marks
# token_only_duplication, so only exact token clones are found
# there. The 50-token default would hide a clone of 4 short
# lines, so --min-tokens 1 lets the line minimum alone decide.
JSCPD_TOKEN_ONLY_MIN_TOKENS = "1"

# jscpd gives an exact clone no similarity: it is a full match.
EXACT_CLONE_SIMILARITY = 1.0

REPORT_NAME = "jscpd-report.json"


def measure(target, metrics, declaration):
    """One flagged record per duplicated pair touching the
    target."""
    repo_path = repo_relative(Path.cwd(), target.repo_path or target.path)
    suffix = Path(repo_path).suffix
    is_test = is_test_file(repo_path)
    metric = TEST_METRIC if is_test else CODE_METRIC
    if metric not in metrics:
        return []
    min_lines = TEST_MIN_LINES if is_test else MIN_LINES
    extensions = declaration.languages[target.language].extensions
    peers = _scannable_peers(repo_path, is_test, extensions, declaration)
    with tempfile.TemporaryDirectory() as scan_dir:
        names = _stage_corpus(
            target, repo_path, suffix, peers, Path(scan_dir)
        )
        is_token_only = declaration.languages[
            target.language
        ].is_token_only_duplication
        clones = _scan_both_kinds(
            Path(scan_dir), is_token_only, min_lines
        )
    return _flagged_records(target, metric, repo_path, names, clones)


def _stage_corpus(target, repo_path, suffix, peers, scan_dir):
    """Copy the target and its peers into `scan_dir`; map staged
    to real names.

    Each file keeps its own extension, so jscpd reads it as the
    language that extension belongs to.
    """
    names = {f"c0{suffix}": repo_path}
    shutil.copyfile(target.path, scan_dir / f"c0{suffix}")
    for index, peer in enumerate(peers, start=1):
        staged = f"c{index}{Path(peer).suffix}"
        shutil.copyfile(peer, scan_dir / staged)
        names[staged] = peer
    return names


def _scannable_peers(repo_path, is_test, extensions, declaration):
    """Peers of the target that the declaration does not
    exclude."""
    return [
        peer for peer in _peers_of(repo_path, is_test, extensions)
        if not is_excluded_path(declaration, peer)
    ]


def _peers_of(repo_path, is_test, extensions):
    """Repo files, committed or not, in the target's language
    and kind."""
    listed = run_tool(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"]
    ).split("\0")
    return [
        path for path in listed
        if path and path != repo_path and Path(path).suffix in extensions
        and is_test_file(path) == is_test and Path(path).is_file()
    ]


def _scan_both_kinds(scan_dir, is_token_only, min_lines):
    """Similar pairs of `min_lines` lines plus exact clones of
    as many."""
    clones = _scan(scan_dir, is_token_only, min_lines - 1)
    return [
        clone for clone in clones
        if "similarity" in clone
        or _longest_identical_run(scan_dir, clone) >= min_lines
    ]


def _longest_identical_run(scan_dir, clone):
    """Most consecutive identical lines the two sides of a clone
    share."""
    first, second = clone["firstFile"], clone["secondFile"]
    first_lines = (scan_dir / Path(first["name"]).name).read_text().splitlines()
    second_lines = (scan_dir / Path(second["name"]).name).read_text().splitlines()
    longest = run = 0
    for offset in range(first["end"] - first["start"] + 1):
        first_index = first["start"] - 1 + offset
        second_index = second["start"] - 1 + offset
        is_same = (
            first_index < len(first_lines) and second_index < len(second_lines)
            and first_lines[first_index].strip() == second_lines[second_index].strip()
        )
        run = run + 1 if is_same else 0
        longest = max(longest, run)
    return longest


def _scan(scan_dir, is_token_only, min_lines):
    token_options = (
        ["--min-tokens", JSCPD_TOKEN_ONLY_MIN_TOKENS]
        if is_token_only else []
    )
    with tempfile.TemporaryDirectory() as report_dir:
        # jscpd reads .jscpd.json from its cwd, so it runs in
        # the empty report dir: the repo's own config must not
        # apply.
        run_tool([
            "jscpd", f"--similarity={SIMILARITY_LIMIT}",
            "--min-lines", str(min_lines), *token_options,
            "--reporters", "json", "--output", report_dir,
            "--no-gitignore", "--no-tips", "--silent", str(scan_dir),
        ], cwd=report_dir)
        report = json.loads((Path(report_dir) / REPORT_NAME).read_text())
    return report["duplicates"]


def _flagged_records(target, metric, repo_path, names, clones):
    records = []
    for clone in clones:
        touched_sides = _touched_sides(target, clone)
        if not touched_sides:
            continue
        target_side, other_side = touched_sides[0]
        similarity = clone.get("similarity", EXACT_CLONE_SIMILARITY)
        record = measurement(target, metric, similarity, SIMILARITY_LIMIT)
        records.append({
            **record,
            "file": repo_path,
            "line": target_side["start"],
            "flagged_at_limit": True,
            "other_file": names[other_side["name"]],
            "other_line": other_side["start"],
        })
    return records


def _touched_sides(target, clone):
    """Each (target side, other side) pair on a touched line."""
    return [
        (target_side, other_side)
        for target_side, other_side in _sides(clone)
        if target.touches(target_side["start"], target_side["end"])
    ]


def _sides(clone):
    """Each (target-file side, other side) pair the clone
    offers.

    A clone inside the target file offers both orders, so the
    caller can keep the side that sits on a touched line.
    """
    first, second = clone["firstFile"], clone["secondFile"]
    pairs = []
    if Path(first["name"]).stem == "c0":
        pairs.append((first, second))
    if Path(second["name"]).stem == "c0":
        pairs.append((second, first))
    return pairs
