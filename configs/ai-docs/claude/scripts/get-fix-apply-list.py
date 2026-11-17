#!/usr/bin/env python3
# get-fix-apply-list.py - list the verdict entries the fix step
#   applies.
#
# Usage:
#   get-fix-apply-list.py <verdict-path>
#
# verdict-path: a merged verdict_quality-gate_*.md.
#
# stdin: none.
#
# stdout: the number of each in-scope entry the judge did not
#   skip, one per line in file order, empty when none.
#
# exit: 0 success, 1 unreadable verdict file
import argparse
import importlib.util
import re
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent

PARSE_FENCES_PATH = SCRIPTS_DIR / "parse-fences.py"

ENTRY_START = re.compile(r"^### (?P<number>\d+)\. (?P<heading>.*)$")
BRACKET_TAG = re.compile(r"\[([^\]]*)\]")

RENDERED_SECTION = re.compile(r"^## (?:Open violations|Gate input violations)\b")
FINDINGS_SECTION = re.compile(r"^## Findings\s*$")

JUDGED_FINDING_TAGS = {"metrics", "refactor", "auto-review"}
EXCLUDED_TAGS = {"Done", "QUESTION"}

SKIPPED_ANNOTATION = re.compile(r"^SKIPPED \(")


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


def main():
    parser = argparse.ArgumentParser(
        description="Print the numbers of the verdict entries the fix "
        "step applies."
    )
    parser.add_argument("verdict", help="path to a merged verdict_quality-gate_*.md")
    arguments = parser.parse_args()
    entries = list_in_scope_entries(read_verdict(arguments.verdict))
    for entry in entries:
        if not has_skipped_line(entry):
            print(entry["number"])


if __name__ == "__main__":
    main()
