#!/usr/bin/env python3
# split-forced-refactors.py - Move forced refactors to a branch.
#
# Purpose: local git only, never pushes.
#
# Usage:
#   split-forced-refactors.py --repo <path> --base <ref>
#     --feature-branch <name> --refactor-branch <name>
#
# stdin: unused
# stdout: one JSON object - outcome ("moved" or "kept"),
#   files, lines, commits, refactor_branch, needs_push
# exit: 0 on moved or kept, 2 on bad usage

import argparse
import json
import subprocess
import sys

FORCED_REFACTOR_GATE = "metrics"
MAX_FILES = 5
MAX_CHANGED_LINES = 100


def run_git(repo, *args):
    result = subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def parse_arguments(argv):
    parser = argparse.ArgumentParser(
        description="Move Gate: metrics refactor commits into their own branch."
    )
    parser.add_argument("--repo", required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--feature-branch", required=True)
    parser.add_argument("--refactor-branch", required=True)
    return parser.parse_args(argv)


def list_forced_refactor_commits(repo, base, feature_branch):
    shas = run_git(
        repo, "rev-list", "--reverse", "--no-merges", f"{base}..{feature_branch}"
    ).splitlines()
    return [sha for sha in shas if is_forced_refactor(repo, sha)]


def is_forced_refactor(repo, sha):
    gate = run_git(
        repo, "log", "-1", "--format=%(trailers:key=Gate,valueonly)", sha
    )
    return gate.strip() == FORCED_REFACTOR_GATE


def sum_changed_files_and_lines(repo, shas):
    paths = set()
    lines = 0
    for sha in shas:
        numstat = run_git(repo, "show", "--numstat", "--format=", sha)
        for row in numstat.splitlines():
            added, deleted, path = row.split("\t", 2)
            paths.add(path)
            lines += count_text_lines(added) + count_text_lines(deleted)
    return len(paths), lines


def count_text_lines(numstat_cell):
    # git prints "-" for a binary file: no countable lines
    return 0 if numstat_cell == "-" else int(numstat_cell)


def move_onto_refactor_branch(repo, base, shas, refactor_branch, feature_branch):
    run_git(repo, "checkout", "-b", refactor_branch, base)
    run_git(repo, "cherry-pick", *shas)
    run_git(repo, "rebase", refactor_branch, feature_branch)


def get_kept_report(shas, files, lines):
    return {
        "outcome": "kept",
        "files": files,
        "lines": lines,
        "commits": shas,
        "refactor_branch": None,
        "needs_push": [],
    }


def get_moved_report_fields(refactor_branch, feature_branch):
    return {
        "outcome": "moved",
        "refactor_branch": refactor_branch,
        "needs_push": [
            {"branch": refactor_branch, "force_with_lease": False},
            {"branch": feature_branch, "force_with_lease": True},
        ],
    }


def main(argv):
    arguments = parse_arguments(argv)
    repo = arguments.repo
    shas = list_forced_refactor_commits(
        repo, arguments.base, arguments.feature_branch
    )
    files, lines = sum_changed_files_and_lines(repo, shas)
    is_over_threshold = files > MAX_FILES or lines > MAX_CHANGED_LINES
    report = get_kept_report(shas, files, lines)
    if is_over_threshold:
        move_onto_refactor_branch(
            repo,
            arguments.base,
            shas,
            arguments.refactor_branch,
            arguments.feature_branch,
        )
        report.update(
            get_moved_report_fields(
                arguments.refactor_branch, arguments.feature_branch
            )
        )
    print(json.dumps(report))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
