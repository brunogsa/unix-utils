#!/usr/bin/env python3
# get-fix-apply-list.py - list the verdict entries the fix step
#   applies, or validate the judge's rulings on them.
#
# Usage:
#   get-fix-apply-list.py <verdict-path>
#   get-fix-apply-list.py --check <verdict-path>
#
# verdict-path: a merged verdict_quality-gate_*.md.
#
# stdin: none.
#
# stdout: default - the number of each in-scope entry the judge
#   did not skip, one per line in file order, empty when none.
#   --check - one "<N>: <reason>" line per entry whose ruling
#   is malformed, nothing when every ruling is valid.
#
# exit: 0 success, 1 unreadable verdict file or, with --check,
#   at least one bad ruling
import argparse
import importlib.util
import re
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent
PIPELINE_SCRIPTS = SCRIPTS_DIR.parent / "skills/code-review-pipeline/scripts"

PARSE_FENCES_PATH = SCRIPTS_DIR / "parse-fences.py"

ENTRY_START = re.compile(r"^### (?P<number>\d+)\. (?P<heading>.*)$")
BRACKET_TAG = re.compile(r"\[([^\]]*)\]")

RENDERED_SECTION = re.compile(r"^## (?:Open violations|Gate input violations)\b")
FINDINGS_SECTION = re.compile(r"^## Findings\s*$")

JUDGED_FINDING_TAGS = {"metrics", "refactor", "auto-review", "scout"}
EXCLUDED_TAGS = {"Done", "QUESTION"}

SKIPPED_ANNOTATION = re.compile(r"^SKIPPED \(")
SKIPPED_RULING_LINE = "SKIPPED (judge ruled Skip)"
RULING_PREFIX = "**Standards check**"
FIX_RULING = "**Standards check**: Fix"
SKIP_RULING = re.compile(
    r'^\*\*Standards check\*\*: Skip - "(?P<rule>.+)"; '
    r"considered fix: (?P<fix>\S.*)$"
)


def load_toggle_fence():
    spec = importlib.util.spec_from_file_location("parse_fences", PARSE_FENCES_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {PARSE_FENCES_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.toggle_fence


def load_finding_body_checks():
    sys.path.insert(0, str(PIPELINE_SCRIPTS))
    return importlib.import_module("finding_bodies.checks")


def read_verdict(path):
    try:
        return Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        print(
            f"get-fix-apply-list.py: cannot read {path}: {error}",
            file=sys.stderr,
        )
        sys.exit(1)


def iter_lines_outside_fences(verdict_text):
    toggle_fence = load_toggle_fence()
    fence_state = (False, "", 0)
    for line in verdict_text.splitlines():
        previous_state = fence_state
        fence_state = toggle_fence(line, *fence_state)
        is_inside_fence = previous_state[0] or fence_state[0]
        if not is_inside_fence:
            yield line


def is_in_scope(tags, is_rendered_section, is_findings_section):
    if tags & EXCLUDED_TAGS:
        return False
    if is_rendered_section:
        return True
    return is_findings_section and bool(tags & JUDGED_FINDING_TAGS)


def list_in_scope_entries(verdict_text):
    """In-scope entries in file order, each with its number,
    whether it sits in a rendered metrics section, and its
    unfenced body lines."""
    entries = []
    current_entry = None
    is_rendered_section = False
    is_findings_section = False
    for line in iter_lines_outside_fences(verdict_text):
        entry_start = ENTRY_START.match(line)
        if entry_start or line.startswith("## "):
            current_entry = None
            if not entry_start:
                is_rendered_section = bool(RENDERED_SECTION.match(line))
                is_findings_section = bool(FINDINGS_SECTION.match(line))
                continue
            tags = set(BRACKET_TAG.findall(entry_start["heading"]))
            if is_in_scope(tags, is_rendered_section, is_findings_section):
                current_entry = {
                    "number": entry_start["number"],
                    "is_rendered": is_rendered_section,
                    "lines": [],
                }
                entries.append(current_entry)
        elif current_entry:
            current_entry["lines"].append(line)
    return entries


def has_skipped_line(entry):
    return any(SKIPPED_ANNOTATION.match(line) for line in entry["lines"])


def list_ruling_problems(entry, checks):
    ruling_indexes = [
        index
        for index, line in enumerate(entry["lines"])
        if line.startswith(RULING_PREFIX)
    ]
    problems = []
    if len(ruling_indexes) > 1:
        problems.append("more than one **Standards check** line")
    for index in ruling_indexes:
        problems.extend(_list_single_ruling_problems(entry, index, checks))
    if entry["is_rendered"]:
        problems.extend(_list_rendered_entry_length_problems(entry, checks))
    return problems


def _list_single_ruling_problems(entry, index, checks):
    line = entry["lines"][index]
    if line == FIX_RULING:
        return []
    skip = SKIP_RULING.match(line)
    if skip is None or not skip["rule"].strip():
        return [
            'ruling is neither "Fix" nor Skip - "<rule>"; considered fix: <fix>'
        ]
    problems = []
    later_lines = entry["lines"][index + 1 :]
    if SKIPPED_RULING_LINE not in later_lines:
        problems.append(f"Skip has no {SKIPPED_RULING_LINE} line after it")
    if checks.INTERNAL_RULE_SOURCE.search(skip["rule"]):
        problems.append("Skip cites a rule source by name; quote the rule")
    return problems


def _list_rendered_entry_length_problems(entry, checks):
    ruling_lines = [
        line
        for line in entry["lines"]
        if line.startswith(RULING_PREFIX) or SKIPPED_ANNOTATION.match(line)
    ]
    ruling_length = len("\n".join(ruling_lines))
    if ruling_length > checks.CHAR_CAP:
        return [
            f"ruling is {ruling_length} chars, "
            f"over the {checks.CHAR_CAP}-char cap"
        ]
    return []


def main():
    parser = argparse.ArgumentParser(
        description="Print the numbers of the verdict entries the fix "
        "step applies, or validate the judge's rulings with --check."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="print one '<N>: <reason>' line per entry with a bad "
        "ruling and exit 1 when any is bad",
    )
    parser.add_argument("verdict", help="path to a merged verdict_quality-gate_*.md")
    arguments = parser.parse_args()
    entries = list_in_scope_entries(read_verdict(arguments.verdict))
    if arguments.check:
        checks = load_finding_body_checks()
        has_bad_ruling = False
        for entry in entries:
            problems = list_ruling_problems(entry, checks)
            if problems:
                has_bad_ruling = True
                print(f"{entry['number']}: {'; '.join(problems)}")
        sys.exit(1 if has_bad_ruling else 0)
    for entry in entries:
        if not has_skipped_line(entry):
            print(entry["number"])


if __name__ == "__main__":
    main()
