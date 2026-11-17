#!/usr/bin/env python3
# check-metrics-judge-coverage.py - check that a metrics judge
#   ruled every raw metrics record exactly once.
#
# Usage:
#   check-metrics-judge-coverage.py --report <report.json> \
#     [--exceptions <claims.json>] --judge <judge.md>
#   check-metrics-judge-coverage.py --help
#
# stdin: none.
#
# stdout: one "<key>: <reason>" line per record cited by no
#   `[metrics]` finding's `**Record**:` line and no
#   `## Dismissed records` line, cited more than once, or
#   cited but absent from the report.
#
#   Also one line per malformed dismissal line; nothing when
#   every record is ruled once.
#
# exit: 0 every record ruled once, 1 at least one line printed,
#   2 an unreadable judge file, report or exceptions file
import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import NoReturn

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

from quality_metrics import record_keys
from quality_metrics.report import partition_claims

PARSE_FENCES_PATH = SCRIPTS_DIR / "parse-fences.py"

SECTION_HEADING = re.compile(r"^## ")
DISMISSAL_SECTION = re.compile(r"^## Dismissed records\s*$")
FINDING_HEADING = re.compile(r"^### \d+\. (?P<heading>.*)$")
BRACKET_TAG = re.compile(r"\[([^\]]*)\]")
RECORD_LINE = re.compile(r"^\*\*Record\*\*: (?P<keys>.+)$")
CITED_KEY = re.compile(r"`([^`]+)`")
DISMISSAL_LINE = re.compile(r"^- `(?P<key>[^`]+)`:(?P<reason>.*)$")

METRICS_TAG = "metrics"


def fail(message) -> NoReturn:
    print(f"check-metrics-judge-coverage: {message}", file=sys.stderr)
    sys.exit(2)


def read_text(path, description):
    try:
        return Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        fail(f"cannot read {description} {path}: {error}")


def load_json(path, description):
    try:
        return json.loads(read_text(path, description))
    except json.JSONDecodeError as error:
        fail(f"{description} {path} is not JSON: {error}")


def load_report(path):
    loaded = load_json(path, "report")
    if not isinstance(loaded, dict) or "violations" not in loaded:
        fail(f"report {path} lacks the key violations")
    return loaded


def load_exceptions(path):
    if path is None:
        return []
    loaded = load_json(path, "exceptions file")
    if not isinstance(loaded, list):
        fail(f"exceptions file {path} must hold a JSON list")
    return loaded


def load_toggle_fence():
    spec = importlib.util.spec_from_file_location("parse_fences", PARSE_FENCES_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {PARSE_FENCES_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.toggle_fence


def iter_lines_outside_fences(text):
    toggle_fence = load_toggle_fence()
    fence_state = (False, "", 0)
    for line in text.splitlines():
        previous_state = fence_state
        fence_state = toggle_fence(line, *fence_state)
        if not (previous_state[0] or fence_state[0]):
            yield line


def required_keys(report, exceptions):
    """Every key the judge must rule on, in report order."""
    _, open_violations = partition_claims(report["violations"], exceptions)
    keys = record_keys.keys_by_section(
        [violation for violation, _ in open_violations], report
    )
    return [key for section in record_keys.RULED_SECTIONS for key in keys[section]]


def read_citations(judge_text):
    """(finding keys, dismissal keys, problem lines) from the
    judge file, each key list holding one entry per citation."""
    finding_keys = []
    dismissal_keys = []
    problems = []
    is_dismissal_section = False
    is_metrics_finding = False
    for line in iter_lines_outside_fences(judge_text):
        if SECTION_HEADING.match(line):
            is_dismissal_section = bool(DISMISSAL_SECTION.match(line))
            is_metrics_finding = False
            continue
        if is_dismissal_section:
            _read_dismissal_line(line, dismissal_keys, problems)
            continue
        heading = FINDING_HEADING.match(line)
        if heading:
            is_metrics_finding = METRICS_TAG in BRACKET_TAG.findall(heading["heading"])
            continue
        record = RECORD_LINE.match(line)
        if record and is_metrics_finding:
            finding_keys += CITED_KEY.findall(record["keys"])
    return finding_keys, dismissal_keys, problems


def _read_dismissal_line(line, dismissal_keys, problems):
    if not line.strip():
        return
    dismissal = DISMISSAL_LINE.match(line)
    if not dismissal:
        problems.append(f"malformed dismissal line: {line}")
        return
    dismissal_keys.append(dismissal["key"])
    if not dismissal["reason"].strip():
        problems.append(f"{dismissal['key']}: dismissal gives no reason")


def list_problems(keys, finding_keys, dismissal_keys):
    problems = []
    for key in keys:
        findings = finding_keys.count(key)
        dismissals = dismissal_keys.count(key)
        if findings + dismissals == 0:
            problems.append(f"{key}: no finding and no dismissal")
        elif findings + dismissals > 1:
            problems.append(
                f"{key}: cited {findings + dismissals} times "
                f"({_count(findings, 'finding')}, {_count(dismissals, 'dismissal')})"
            )
    known = set(keys)
    unknown = dict.fromkeys(key for key in finding_keys + dismissal_keys if key not in known)
    problems += [f"{key}: not a record in the report" for key in unknown]
    return problems


def _count(number, noun):
    return f"{number} {noun}" if number == 1 else f"{number} {noun}s"


def main():
    parser = argparse.ArgumentParser(
        description="Check that a metrics judge file rules every raw "
        "metrics record exactly once, by a finding or a dismissal.",
    )
    parser.add_argument("--report", required=True, type=Path, help="measure report JSON")
    parser.add_argument("--exceptions", type=Path, help="JSON list of split-diff exception claims")
    parser.add_argument("--judge", required=True, type=Path, help="metrics-judge_*.md file")
    arguments = parser.parse_args()

    report = load_report(arguments.report)
    exceptions = load_exceptions(arguments.exceptions)
    judge_text = read_text(arguments.judge, "judge file")

    finding_keys, dismissal_keys, problems = read_citations(judge_text)
    problems = list_problems(
        required_keys(report, exceptions), finding_keys, dismissal_keys
    ) + problems
    for problem in problems:
        print(problem)
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
