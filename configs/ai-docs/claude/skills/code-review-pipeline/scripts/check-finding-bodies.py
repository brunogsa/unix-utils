#!/usr/bin/env python3
# check-finding-bodies.py - Check that every finding body in
# a verdict file follows the review comment layout and its
# length budget.
#
# Usage:
#   check-finding-bodies.py <verdict.md> [<verdict.md> ...]
#
# stdout: "<path>: finding <N>: <reason>" per violation, or
#   "<path>: line <L>: <reason>" for a misplaced finding heading
# stderr: a usage message, or the path that could not be read
# exit: 0 when every finding passes, 1 on any violation,
#       2 on a usage error or an unreadable file

import argparse
import re
import sys

FINDING_HEADING = re.compile(r"^### (\d+)\. ((?:\[[^\]]*\])*)")
MISPLACED_FINDING_HEADING = re.compile(r"^(?:#{1,2}|#{4,6}) \d+\. ")
MISPLACED_HEADING_REASON = "numbered finding heading must be '### N.'"
FINDING_BOUNDARY = re.compile(r"^(?:#{1,3} |---$)")
FENCE_DELIMITER = re.compile(r"^\s*```")
SEVERITY_TAG_LINE = re.compile(r"^\*\*\[([^\]]+)\]\*\*$")
BRACKET_TOKEN = re.compile(r"\[([^\]]*)\]")

# Lines /address-verdicts appends after review, never part of
# the comment a reviewer wrote.
ANNOTATION_PREFIXES = ("APPLIED (", "SKIPPED (")

ORDINAL_BY_TAG = {
    "MANDATORY": "HIGH",
    "OBRIGATÓRIO": "HIGH",
    "RECOMMENDED": "MEDIUM",
    "RECOMENDADO": "MEDIUM",
    "NITPICK": "LOW",
    "OPTIONAL": "LOW",
    "OPCIONAL": "LOW",
    "QUESTION": "QUESTION",
    "PERGUNTA": "QUESTION",
}
HEADING_ORDINALS = set(ORDINAL_BY_TAG.values())
MANDATORY_TAGS = {"MANDATORY", "OBRIGATÓRIO"}
QUESTION_TAGS = {"QUESTION", "PERGUNTA"}
NITPICK_TAG = "NITPICK"
BLOCKQUOTE_PREFIX = "> "

SUGGESTION_LABELS = ("**Suggestion**", "**Sugestão**")
TRADEOFF_LABELS = ("**Trade-off of not doing it**", "**Trade-off de não fazer**")

CHAR_CAP = 512
MANDATORY_CHAR_CAP = 1024
MANDATORY_LINE_CAP = 16
QUOTED_LINE_MAX = 60


class Finding:
    """One numbered finding; `lines` holds (text, is_fenced) pairs,
    with fence delimiter lines counted as fenced."""

    def __init__(self, number, heading_tokens):
        self.number = number
        self.heading_tokens = heading_tokens
        self.lines = []


def _build_parser():
    parser = argparse.ArgumentParser(
        prog="check-finding-bodies.py",
        description="Check verdict finding bodies against the review comment layout.",
    )
    parser.add_argument("paths", nargs="+", metavar="verdict.md")
    return parser


def parse_findings(text):
    """Split a verdict into findings, ignoring headings inside code
    fences. Also return the line numbers of numbered findings filed
    under a heading level other than ###."""
    findings = []
    misplaced_heading_lines = []
    current = None
    is_in_fence = False
    for line_number, line in enumerate(text.splitlines(), start=1):
        is_delimiter = bool(FENCE_DELIMITER.match(line))
        if not is_in_fence and not is_delimiter:
            if MISPLACED_FINDING_HEADING.match(line):
                misplaced_heading_lines.append(line_number)
            heading = FINDING_HEADING.match(line)
            if heading:
                tokens = BRACKET_TOKEN.findall(heading.group(2))
                current = Finding(int(heading.group(1)), tokens)
                findings.append(current)
                continue
            if FINDING_BOUNDARY.match(line):
                current = None
                continue
        if is_delimiter:
            is_in_fence = not is_in_fence
        if current is not None:
            current.lines.append((line, is_in_fence or is_delimiter))
    return findings, misplaced_heading_lines


def _reviewer_lines(finding):
    """Body lines minus the annotations added after review."""
    return [
        (line, is_fenced) for line, is_fenced in finding.lines
        if is_fenced or not line.startswith(ANNOTATION_PREFIXES)
    ]


def _find_tag(body_lines):
    """Return (body index, tag) of the first known severity tag
    line outside a code block, or (None, None)."""
    for index, (line, is_fenced) in enumerate(body_lines):
        match = None if is_fenced else SEVERITY_TAG_LINE.match(line)
        if match and match.group(1) in ORDINAL_BY_TAG:
            return index, match.group(1)
    return None, None


def _first_index(prose, labels):
    return next((i for i, line in enumerate(prose) if line in labels), None)


def _check_tag_position(body, tag_line_index, tag):
    tag_names = ", ".join(ORDINAL_BY_TAG)
    if tag is None:
        return [f"body must open with a severity tag line **[TAG]**, TAG one of {tag_names}; none found"]
    opening = [line for line in body[:tag_line_index] if line.strip()]
    is_nitpick_prefix = (
        tag == NITPICK_TAG
        and len(opening) == 1
        and opening[0].startswith(BLOCKQUOTE_PREFIX)
    )
    if not opening or is_nitpick_prefix:
        return []
    first = opening[0][:QUOTED_LINE_MAX]
    return [f'body must open with the severity tag line **[{tag}]**; got "{first}"']


def _check_ordinal(heading_tokens, tag):
    ordinals = [token for token in heading_tokens if token in HEADING_ORDINALS]
    expected = ORDINAL_BY_TAG.get(tag)
    if not ordinals:
        needed = f"[{expected}]" if expected else "[HIGH], [MEDIUM], [LOW] or [QUESTION]"
        return [f"heading has no ordinal; it needs {needed}"]
    if expected and ordinals[0] != expected:
        return [f"heading ordinal [{ordinals[0]}] must be [{expected}] to match the tag [{tag}]"]
    return []


def _check_sections(prose, tag):
    suggestion_index = _first_index(prose, SUGGESTION_LABELS)
    tradeoff_index = _first_index(prose, TRADEOFF_LABELS)
    reasons = []
    if suggestion_index is None and tag not in QUESTION_TAGS:
        reasons.append(f"missing a {' / '.join(SUGGESTION_LABELS)} line")
    if tradeoff_index is None:
        reasons.append(f"missing a {' / '.join(TRADEOFF_LABELS)} line")
    is_misordered = (
        suggestion_index is not None
        and tradeoff_index is not None
        and tradeoff_index < suggestion_index
    )
    if is_misordered:
        reasons.append("the trade-off line must come after the suggestion line")
    return reasons


def _check_budget(prose, tag):
    is_mandatory = tag in MANDATORY_TAGS
    char_cap = MANDATORY_CHAR_CAP if is_mandatory else CHAR_CAP
    char_count = len("\n".join(prose).strip())
    reasons = []
    if char_count > char_cap:
        reasons.append(
            f"body is {char_count} chars, over the {char_cap}-char cap (code blocks excluded)"
        )
    line_count = sum(1 for line in prose if line.strip())
    if is_mandatory and line_count > MANDATORY_LINE_CAP:
        reasons.append(
            f"body is {line_count} non-blank lines, over the {MANDATORY_LINE_CAP}-line cap"
            " (code blocks excluded)"
        )
    return reasons


def check_finding(finding):
    """Return every layout and budget violation of one finding."""
    body_lines = _reviewer_lines(finding)
    body = [line for line, _ in body_lines]
    prose = [line for line, is_fenced in body_lines if not is_fenced]
    tag_body_index, tag = _find_tag(body_lines)
    return (
        _check_tag_position(body, tag_body_index, tag)
        + _check_ordinal(finding.heading_tokens, tag)
        + _check_sections(prose, tag)
        + _check_budget(prose, tag)
    )


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


def main():
    args = _build_parser().parse_args()
    has_violation = False
    for path, text in _read_all(args.paths).items():
        findings, misplaced_heading_lines = parse_findings(text)
        for line_number in misplaced_heading_lines:
            print(f"{path}: line {line_number}: {MISPLACED_HEADING_REASON}")
            has_violation = True
        for finding in findings:
            for reason in check_finding(finding):
                print(f"{path}: finding {finding.number}: {reason}")
                has_violation = True
    sys.exit(1 if has_violation else 0)


if __name__ == "__main__":
    main()
