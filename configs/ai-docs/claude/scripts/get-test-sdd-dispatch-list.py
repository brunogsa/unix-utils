#!/usr/bin/env python3
# get-test-sdd-dispatch-list.py - list test-sdd findings for
#   tdd-coder.
#
# Usage:
#   get-test-sdd-dispatch-list.py <verdict-path>
#
# verdict-path: a verdict_test-sdd_*.md, or a merged
#   verdict_quality-gate_*.md (only [test-sdd] findings listed).
#
# stdin: none.
#
# stdout: heading line of each finding to dispatch, verbatim,
#   one per line in file order; SKIPPED findings are left out;
#   empty when none qualify.
# exit: 0 success, 1 unreadable verdict file
import argparse
import importlib.util
import re
import sys
from pathlib import Path

UNPLANNED_TESTS_FINDING_TITLE = "Unplanned tests added by the branch"

TEST_SDD_TAG = "test-sdd"

# A heading with none of these tags reads as test-sdd, so a new
# lens goes here as well as in the merge-check regex of
# skills/quality-gate/SKILL.md.
LENS_TAGS = {"auto-review", "refactor", "metrics", TEST_SDD_TAG}

# Optional mark before the severity tag: [Done], or the
# selection mark [AI!], [AI!: <message>] or [AI! <message>].
# Further bracket tags may follow the severity, as in a merged
# verdict: [MEDIUM][refactor][LINTER GAP].
FINDING_HEADING = re.compile(
    r"^### \d+\. (?:\[Done\]|\[AI!(?:[: ][^\]]*)?\])?"
    r"\[[A-Z]+\](?P<tags>(?:\[[^\]]*\])*) (?P<title>.*?)\s*$"
)

BRACKET_TAG = re.compile(r"\[([^\]]*)\]")

# Any finding heading, dispatchable or not: it ends the
# previous finding's body.
FINDING_START = re.compile(r"^### \d+\. ")

# A ruling /address-verdicts wrote into a finding body at
# column 0; the finding is final, so it is never dispatched
# again.
SKIPPED_ANNOTATION = re.compile(r"^SKIPPED \(")


def is_test_sdd_finding(heading):
    tags = set(BRACKET_TAG.findall(heading["tags"]))
    return TEST_SDD_TAG in tags or not tags & LENS_TAGS

PARSE_FENCES_PATH = Path(__file__).with_name("parse-fences.py")


def load_toggle_fence():
    spec = importlib.util.spec_from_file_location("parse_fences", PARSE_FENCES_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {PARSE_FENCES_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.toggle_fence


def read_verdict(path):
    try:
        return Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        print(
            f"get-test-sdd-dispatch-list.py: cannot read {path}: {error}",
            file=sys.stderr,
        )
        sys.exit(1)


def is_dispatchable_heading(line):
    heading = FINDING_HEADING.match(line)
    if heading is None:
        return False
    if heading["title"] == UNPLANNED_TESTS_FINDING_TITLE:
        return False
    return is_test_sdd_finding(heading)


def iter_lines_outside_fences(verdict_text):
    toggle_fence = load_toggle_fence()
    fence_state = (False, "", 0)
    for line in verdict_text.splitlines():
        previous_state = fence_state
        fence_state = toggle_fence(line, *fence_state)
        is_inside_fence = previous_state[0] or fence_state[0]
        if not is_inside_fence:
            yield line


def list_dispatchable_headings(verdict_text):
    findings = []
    current_finding = None
    for line in iter_lines_outside_fences(verdict_text):
        if FINDING_START.match(line) or line.startswith("## "):
            current_finding = None
            if is_dispatchable_heading(line):
                current_finding = {"heading": line, "is_skipped": False}
                findings.append(current_finding)
        elif current_finding and SKIPPED_ANNOTATION.match(line):
            current_finding["is_skipped"] = True
    return [f["heading"] for f in findings if not f["is_skipped"]]


def main():
    parser = argparse.ArgumentParser(
        description="Print the test-sdd finding headings that go to "
        "tdd-coder, leaving out the unplanned-tests finding."
    )
    parser.add_argument(
        "verdict",
        help="path to a verdict_test-sdd_*.md or a merged "
        "verdict_quality-gate_*.md",
    )
    arguments = parser.parse_args()
    for heading in list_dispatchable_headings(read_verdict(arguments.verdict)):
        print(heading)


if __name__ == "__main__":
    main()
