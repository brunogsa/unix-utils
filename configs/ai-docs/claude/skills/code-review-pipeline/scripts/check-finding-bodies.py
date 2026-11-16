#!/usr/bin/env python3
# check-finding-bodies.py - Check that every finding body in
# a verdict file or a findings JSON array follows the review
# comment layout and its length budget.
#
# A finding whose heading carries the [test-sdd] tag is
# skipped: test-sdd findings follow test-sdd's own schema.
#
# The parsing and the per-body checks live in the sibling
# finding_bodies package; this file is the CLI.
#
# Usage:
#   check-finding-bodies.py <verdict.md> [<verdict.md> ...]
#   check-finding-bodies.py --findings-json <findings.json>
#
# stdout: "<path>: <finding N|line L>: <reason>" per verdict
#         violation; "<json path>: finding I (<path>:<line>):
#         <reason>" per JSON violation, I counted from 1.
#
# stderr: a usage message, or why a file could not be used.
#
# exit: 0 when every finding passes, 1 on any violation,
#       2 on a usage error, an unreadable file, invalid JSON,
#       a non-array, or an element without a body or path

import argparse
import json
import sys
from typing import NoReturn

from finding_bodies.checks import check_finding, check_json_body
from finding_bodies.parsing import parse_findings

MISPLACED_HEADING_REASON = "numbered finding heading must be '### N.'"

# Heading lens tag of a test-sdd finding, which follows
# test-sdd's own schema, so the review comment layout is
# not applied to it.
TEST_SDD_LENS_TAG = "test-sdd"

JSON_STRING_FIELDS = ("body", "path")


def _build_parser():
    parser = argparse.ArgumentParser(
        prog="check-finding-bodies.py",
        description="Check verdict finding bodies against the review comment layout.",
    )
    parser.add_argument("paths", nargs="*", metavar="verdict.md")
    parser.add_argument(
        "--findings-json", metavar="findings.json",
        help="check the 'body' of each element of a JSON array of findings",
    )
    return parser


def _exit_unusable(path, why) -> NoReturn:
    print(f"check-finding-bodies.py: cannot use {path}: {why}", file=sys.stderr)
    sys.exit(2)


def _read_all(paths):
    texts = {}
    for path in paths:
        try:
            with open(path, encoding="utf-8") as handle:
                texts[path] = handle.read()
        except (OSError, UnicodeDecodeError) as error:
            print(f"check-finding-bodies.py: cannot read {path}: {error}", file=sys.stderr)
            sys.exit(2)
    return texts


def _require_string_fields(json_path, index, finding):
    for field in JSON_STRING_FIELDS:
        is_present = isinstance(finding, dict) and isinstance(finding.get(field), str)
        if not is_present:
            _exit_unusable(json_path, f"finding {index} has no string '{field}' field")


def _load_json_findings(json_path):
    """Return the findings array, exiting 2 when the file cannot
    be read or any element lacks a string body or path."""
    text = _read_all([json_path])[json_path]
    try:
        findings = json.loads(text)
    except json.JSONDecodeError as error:
        _exit_unusable(json_path, f"invalid JSON: {error}")
    if not isinstance(findings, list):
        _exit_unusable(json_path, "must hold a JSON array of findings")
    for index, finding in enumerate(findings, start=1):
        _require_string_fields(json_path, index, finding)
    return findings


def _verdict_report_lines(path, text):
    """Return one output line per violation of one verdict."""
    findings, misplaced_heading_lines = parse_findings(text)
    lines = [
        f"{path}: line {line_number}: {MISPLACED_HEADING_REASON}"
        for line_number in misplaced_heading_lines
    ]
    checked = [f for f in findings if TEST_SDD_LENS_TAG not in f.heading_tokens]
    for finding in checked:
        lines += [
            f"{path}: finding {finding.number}: {reason}"
            for reason in check_finding(finding)
        ]
    return lines


def _report_verdicts(paths):
    report_lines = []
    for path, text in _read_all(paths).items():
        report_lines += _verdict_report_lines(path, text)
    for line in report_lines:
        print(line)
    return bool(report_lines)


def _report_json_findings(json_path):
    has_violation = False
    for index, finding in enumerate(_load_json_findings(json_path), start=1):
        location = f"{finding['path']}:{finding.get('line')}"
        for reason in check_json_body(finding["body"], finding["path"]):
            print(f"{json_path}: finding {index} ({location}): {reason}")
            has_violation = True
    return has_violation


def main():
    parser = _build_parser()
    args = parser.parse_args()
    has_one_mode = bool(args.paths) != bool(args.findings_json)
    if not has_one_mode:
        parser.error("pass verdict.md paths or --findings-json, exactly one of the two")
    if args.findings_json:
        has_violation = _report_json_findings(args.findings_json)
    else:
        has_violation = _report_verdicts(args.paths)
    sys.exit(1 if has_violation else 0)


if __name__ == "__main__":
    main()
