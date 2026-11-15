"""Measures duplicated code and duplicated tests with jscpd.

jscpd's --similarity pairs functions by structure: names and literals
are normalized away, so two functions differing only in them score
1.0. It leaves test files out by name, so every file is staged under
a neutral name before the scan. Source files are compared with source
files and test files with test files, which keeps the two findings
apart. A touched file is compared with the repo's files of its kind,
committed or not, and a pair is flagged when it overlaps a
touched line.
"""

import json
import shutil
import tempfile
from pathlib import Path

from quality_metrics.collection import repo_relative
from quality_metrics.declaration import is_test_file
from quality_metrics.functions import measurement
from quality_metrics.tools import run_tool

CODE_METRIC = "code_duplication"
TEST_METRIC = "test_duplication"

SIMILARITY_LIMIT = 0.82

# jscpd keeps a pair longer than --min-lines, so 3 keeps a pair
# of 4 or more lines.
JSCPD_MIN_LINES = "3"

# --similarity does not read Bash, HTML or CSS, so only exact
# token clones are found there. jscpd's default token minimum
# would hide a clone of 4 short lines, so the line minimum alone
# decides.
TOKEN_ONLY_SUFFIXES = (".sh", ".bash", ".html", ".htm", ".css", ".scss")
JSCPD_TOKEN_ONLY_MIN_TOKENS = "1"

# jscpd gives an exact clone no similarity: it is a full match.
EXACT_CLONE_SIMILARITY = 1.0

REPORT_NAME = "jscpd-report.json"


def measure(target, metrics):
    """One flagged record per duplicated pair touching the target."""
    repo_path = repo_relative(Path.cwd(), target.repo_path or target.path)
    metric = TEST_METRIC if is_test_file(repo_path) else CODE_METRIC
    if metric not in metrics:
        return []
    with tempfile.TemporaryDirectory() as scan_dir:
        names = _stage_corpus(target, repo_path, Path(scan_dir))
        clones = _scan(Path(scan_dir), Path(repo_path).suffix)
    return _flagged_records(target, metric, names, clones)


def _stage_corpus(target, repo_path, scan_dir):
    """Copy the target and its peers into `scan_dir`; map staged to real names."""
    suffix = Path(repo_path).suffix
    names = {f"c0{suffix}": repo_path}
    shutil.copyfile(target.path, scan_dir / f"c0{suffix}")
    for index, peer in enumerate(_peers_of(repo_path), start=1):
        staged = f"c{index}{suffix}"
        shutil.copyfile(peer, scan_dir / staged)
        names[staged] = peer
    return names


def _peers_of(repo_path):
    """Repo files, committed or not, of the target's extension and kind."""
    suffix = Path(repo_path).suffix
    is_test = is_test_file(repo_path)
    listed = run_tool(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"]
    ).split("\0")
    return [
        path for path in listed
        if path and path != repo_path and Path(path).suffix == suffix
        and is_test_file(path) == is_test and Path(path).is_file()
    ]


def _scan(scan_dir, suffix):
    # jscpd reads .jscpd.json from its cwd, so it runs in the
    # empty report dir: the repo's own config must not apply.
    token_options = (
        ["--min-tokens", JSCPD_TOKEN_ONLY_MIN_TOKENS]
        if suffix in TOKEN_ONLY_SUFFIXES else []
    )
    with tempfile.TemporaryDirectory() as report_dir:
        run_tool([
            "jscpd", f"--similarity={SIMILARITY_LIMIT}",
            "--min-lines", JSCPD_MIN_LINES, *token_options,
            "--reporters", "json", "--output", report_dir,
            "--no-gitignore", "--no-tips", "--silent", str(scan_dir),
        ], cwd=report_dir)
        report = json.loads((Path(report_dir) / REPORT_NAME).read_text())
    return report["duplicates"]


def _flagged_records(target, metric, names, clones):
    records = []
    for clone in clones:
        touched_sides = [
            (target_side, other_side)
            for target_side, other_side in _sides(clone)
            if target.touches(target_side["start"], target_side["end"])
        ]
        if not touched_sides:
            continue
        target_side, other_side = touched_sides[0]
        similarity = clone.get("similarity", EXACT_CLONE_SIMILARITY)
        record = measurement(target, metric, similarity, SIMILARITY_LIMIT)
        records.append({
            **record,
            "file": names[target_side["name"]],
            "line": target_side["start"],
            "flagged_at_limit": True,
            "other_file": names[other_side["name"]],
            "other_line": other_side["start"],
        })
    return records


def _sides(clone):
    """Each (target-file side, other side) pair the clone offers.

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
