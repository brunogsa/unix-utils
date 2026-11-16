"""Split verdict text, or a standalone finding body, into
lines paired with whether each sits inside a code block."""

import re

FINDING_HEADING = re.compile(r"^### (\d+)\. ((?:\[[^\]]*\])*)\s*(?:`([^`:]*))?")
MISPLACED_FINDING_HEADING = re.compile(r"^(?:#{1,2}|#{4,6}) \d+\. ")
FINDING_BOUNDARY = re.compile(r"^(?:#{1,3} |---$)")
FENCE_DELIMITER = re.compile(r"^\s*```")
BRACKET_TOKEN = re.compile(r"\[([^\]]*)\]")


class Finding:
    """One numbered finding; `lines` holds (text, is_fenced)
    pairs, with fence delimiter lines counted as fenced."""

    def __init__(self, number, heading_tokens, path):
        self.number = number
        self.heading_tokens = heading_tokens
        self.path = path
        self.lines = []


def _finding_from_heading(heading):
    tokens = BRACKET_TOKEN.findall(heading.group(2))
    return Finding(int(heading.group(1)), tokens, heading.group(3) or "")


class _VerdictParser:
    """Walks a verdict line by line, tracking the open finding
    and whether the walk is inside a code fence."""

    def __init__(self):
        self.findings = []
        self.misplaced_heading_lines = []
        self.current = None
        self.is_in_fence = False

    def feed(self, line_number, line):
        is_delimiter = bool(FENCE_DELIMITER.match(line))
        is_structure_line = not self.is_in_fence and not is_delimiter
        if is_structure_line and self._read_structure(line_number, line):
            return
        if is_delimiter:
            self.is_in_fence = not self.is_in_fence
        if self.current is not None:
            self.current.lines.append((line, self.is_in_fence or is_delimiter))

    def _read_structure(self, line_number, line):
        """Handle a heading or boundary line outside a fence;
        return True when the line was one of them."""
        if MISPLACED_FINDING_HEADING.match(line):
            self.misplaced_heading_lines.append(line_number)
        heading = FINDING_HEADING.match(line)
        if heading:
            self.current = _finding_from_heading(heading)
            self.findings.append(self.current)
            return True
        if FINDING_BOUNDARY.match(line):
            self.current = None
            return True
        return False


def parse_findings(text):
    """Split a verdict into findings, ignoring headings inside
    code fences.
    Also return the line numbers of numbered findings filed
    under a heading level other than ###."""
    parser = _VerdictParser()
    for line_number, line in enumerate(text.splitlines(), start=1):
        parser.feed(line_number, line)
    return parser.findings, parser.misplaced_heading_lines


def fence_body_text(text):
    """Pair each line of a standalone body with whether it sits
    in a code block, fence delimiter lines counted as fenced."""
    pairs = []
    is_in_fence = False
    for line in text.splitlines():
        is_delimiter = bool(FENCE_DELIMITER.match(line))
        if is_delimiter:
            is_in_fence = not is_in_fence
        pairs.append((line, is_in_fence or is_delimiter))
    return pairs
