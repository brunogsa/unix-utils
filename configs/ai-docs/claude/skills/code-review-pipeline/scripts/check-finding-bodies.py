#!/usr/bin/env python3
# check-finding-bodies.py - Check that every finding body in
# a verdict file or a findings JSON array follows the review
# comment layout and its length budget.
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
import re
import sys
from typing import NoReturn

FINDING_HEADING = re.compile(r"^### (\d+)\. ((?:\[[^\]]*\])*)\s*(?:`([^`:]*))?")
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

# The reviewer's private rule files: the PR author cannot open
# them, so a body citing one asks for trust instead of stating
# the principle.
INTERNAL_RULE_SOURCE = re.compile(
    r"\b[a-z]+-standards\b"
    r"|\b(?:CLAUDE|AGENTS)\.md\b"
    r"|\b(?:review-principles|review-checklists|common-preamble)\b"
    r"|~/\.claude/",
    re.IGNORECASE,
)


class Finding:
    """One numbered finding; `lines` holds (text, is_fenced) pairs,
    with fence delimiter lines counted as fenced."""

    def __init__(self, number, heading_tokens, path):
        self.number = number
        self.heading_tokens = heading_tokens
        self.path = path
        self.lines = []


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
                current = Finding(int(heading.group(1)), tokens, heading.group(3) or "")
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


def _check_citations(prose, path):
    """Flag each distinct internal rule source the prose names, unless
    the finding is about that very file (its path contains the name)."""
    path_lower = path.lower()
    cited = {}
    for line in prose:
        for match in INTERNAL_RULE_SOURCE.finditer(line):
            token = match.group(0)
            is_finding_own_file = token.lower() in path_lower
            if not is_finding_own_file:
                cited.setdefault(token.lower(), token)
    return [
        f'body cites internal rule source "{token}";'
        " state the principle and why it matters for this code instead"
        for token in cited.values()
    ]


def _split_body(body_lines):
    """Return (body, prose, tag body index, tag) for (text,
    is_fenced) pairs."""
    body = [line for line, _ in body_lines]
    prose = [line for line, is_fenced in body_lines if not is_fenced]
    tag_body_index, tag = _find_tag(body_lines)
    return body, prose, tag_body_index, tag


def check_finding(finding):
    """Return every layout, budget and citation violation of one finding."""
    body, prose, tag_body_index, tag = _split_body(_reviewer_lines(finding))
    return (
        _check_tag_position(body, tag_body_index, tag)
        + _check_ordinal(finding.heading_tokens, tag)
        + _check_sections(prose, tag)
        + _check_budget(prose, tag)
        + _check_citations(prose, finding.path)
    )


def _fence_body_text(text):
    """Pair each line of a standalone body with whether it sits in
    a code block, fence delimiter lines counted as fenced."""
    pairs = []
    is_in_fence = False
    for line in text.splitlines():
        is_delimiter = bool(FENCE_DELIMITER.match(line))
        if is_delimiter:
            is_in_fence = not is_in_fence
        pairs.append((line, is_in_fence or is_delimiter))
    return pairs


def check_json_body(text, path):
    """Return every violation of one JSON finding body; the heading
    checks are skipped because a JSON finding has no heading."""
    body, prose, tag_body_index, tag = _split_body(_fence_body_text(text))
    return (
        _check_tag_position(body, tag_body_index, tag)
        + _check_sections(prose, tag)
        + _check_budget(prose, tag)
        + _check_citations(prose, path)
    )


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


def _load_json_findings(json_path):
    """Return the findings array, exiting 2 when the file cannot be
    read or any element lacks a string body or path."""
    text = _read_all([json_path])[json_path]
    try:
        findings = json.loads(text)
    except json.JSONDecodeError as error:
        _exit_unusable(json_path, f"invalid JSON: {error}")
    if not isinstance(findings, list):
        _exit_unusable(json_path, "must hold a JSON array of findings")
    for index, finding in enumerate(findings, start=1):
        for field in ("body", "path"):
            is_present = isinstance(finding, dict) and isinstance(finding.get(field), str)
            if not is_present:
                _exit_unusable(json_path, f"finding {index} has no string '{field}' field")
    return findings


def _report_verdicts(paths):
    has_violation = False
    for path, text in _read_all(paths).items():
        findings, misplaced_heading_lines = parse_findings(text)
        for line_number in misplaced_heading_lines:
            print(f"{path}: line {line_number}: {MISPLACED_HEADING_REASON}")
            has_violation = True
        for finding in findings:
            for reason in check_finding(finding):
                print(f"{path}: finding {finding.number}: {reason}")
                has_violation = True
    return has_violation


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
