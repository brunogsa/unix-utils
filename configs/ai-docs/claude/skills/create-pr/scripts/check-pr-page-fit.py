#!/usr/bin/env python3
# check-pr-page-fit.py - Check that a PR body's visible text
# fits on one screen.
#
# Usage:
#   check-pr-page-fit.py <file> [page-lines] [wrap-width]
#
#   <file>       Markdown file to measure
#                (e.g. pr_<slug>_pr<N>.ideal.md).
#
#   page-lines   Optional. Rendered lines the whole body may
#                occupy. Default: 64, the sum of the
#                per-section budgets in create-pr's
#                references/pr-page-budget.md.
#
#   wrap-width   Optional. Chars per rendered line before
#                wrapping. Default: 95 - GitHub's ~860px
#                description column at 14px/1.5 body type.
#
# stdin: none
# stdout: a verdict line, then a breakdown per heading -
#   top-level sections worst-first, each subsection indented
#   under its parent and included in its total.
#
# exit: 0 fits one page; 1 bad usage or file not found
#   (message on stderr); 2 within 20% of the budget; 3 over
#   the budget.

import importlib.util
import math
import re
import sys
from pathlib import Path
from typing import NoReturn

SCRIPT_DIR = Path(__file__).resolve().parent

# The fence rule is shared repo-wide: same marker, a run at
# least as long as the opener, and no info string closes it.
#
# Loaded by path because the hyphenated name blocks an import.
PARSE_FENCES = SCRIPT_DIR.parents[2] / "scripts" / "parse-fences.py"
_spec = importlib.util.spec_from_file_location("parse_fences", PARSE_FENCES)
try:
    if _spec is None or _spec.loader is None:
        raise ImportError("no import spec")
    parse_fences = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(parse_fences)
except Exception as error:
    print(f"error: cannot load {PARSE_FENCES}: {error}", file=sys.stderr)
    sys.exit(1)

DEFAULT_PAGE_LINES = "64"
DEFAULT_WRAP_WIDTH = "95"
MIN_WRAP_WIDTH = 20
WARN_PERCENT = 80

EXIT_FITS = 0
EXIT_USAGE = 1
EXIT_CLOSE = 2
EXIT_OVER = 3

PREAMBLE = "(before first heading)"

# Sorts a top-level section worst-first by subtracting its
# count from a ceiling no real body reaches.
SORT_CEILING = 999999999

# A body with no heading at all keeps this as its shallowest
# level, so every row of its breakdown prints unindented.
NO_HEADING_LEVEL = 99

BREAKDOWN_HEADER = "  lines  section (subsections roll up into their parent)"

BLANK = re.compile(r"^[ \t]*$")
FRONTMATTER_DELIMITER = re.compile(r"^---[ \t]*$")
HTML_COMMENT_OPENER = re.compile(r"^[ \t]*<!--")
LINK_REF_DEFINITION = re.compile(r"^[ \t]*\[[^\]]+\]:[ \t]")
EMPTY_ANCHOR = re.compile(r"^[ \t]*<a[ \t][^>]*></a>[ \t]*$")
EXPANDED_DETAILS = re.compile(r"<details[ \t]+open")
DETAILS_CLOSER_LINE = re.compile(r"^[ \t]*</details>")
CLOSED_FENCE = (False, "", 0)
HEADING = re.compile(r"^#+[ \t]")
HEADING_MARKER = re.compile(r"^#+[ \t]*")

# Wrapping is decided by what GitHub RENDERS, not by what the
# source spells, so the width drops the invisible markup:
#
# - HTML tags - <summary><strong>x</strong></summary> shows as
#   `x`.
#
# - Link targets - [types.ts](https://...) shows as `types.ts`.
# - Emphasis markers - **x**, _x_, and `x` all show as `x`.
INVISIBLE_MARKUP = (
    (re.compile(r"<[^>]*>"), ""),
    (re.compile(r"\]\([^)]*\)"), "]"),
    (re.compile(r"[*_`]"), ""),
)


def print_usage(stream):
    """Print the header block above, stopping at its first
    non-comment line so editing the header never desyncs it."""
    source_lines = Path(__file__).read_text(encoding="utf-8").splitlines()
    for line in source_lines[1:]:
        if not line.startswith("#"):
            break
        print(re.sub(r"^# ?", "", line), file=stream)


def fail_usage(message, *, show_usage=False) -> NoReturn:
    print(f"error: {message}", file=sys.stderr)
    if show_usage:
        print_usage(sys.stderr)
    sys.exit(EXIT_USAGE)


def get_visible_width(line):
    for pattern, replacement in INVISIBLE_MARKUP:
        line = pattern.sub(replacement, line)
    return len(line)


def get_body_start(lines):
    """Index of the first body line, past any YAML frontmatter.

    Bundled reference files carry budget overrides there that
    are not part of the PR body they reproduce."""
    if not lines or not FRONTMATTER_DELIMITER.match(lines[0]):
        return 0
    index = 1
    while index < len(lines) and not FRONTMATTER_DELIMITER.match(lines[index]):
        index += 1
    return index + 1


def get_fence_state(line, fence_state):
    """(in_fence, fence_char, fence_len) after one line.

    Leading whitespace is dropped first, so a fence indented
    under a list item still opens and closes."""
    return parse_fences.toggle_fence(line.lstrip(" \t"), *fence_state)


def is_fence_opener(line):
    is_in_fence, _, _ = get_fence_state(line, CLOSED_FENCE)
    return is_in_fence


def get_index_after_balanced_closer(lines, opener_index):
    """Index just past the </details> that balances the opener.

    A nested block closes first, and the outer text after it is
    still hidden. Counting per line keeps a one-line block
    balanced.

    A tag quoted inside fenced code is sample text, so fence
    lines never move the depth."""
    depth = 0
    fence_state = CLOSED_FENCE
    index = opener_index
    while index < len(lines):
        line = lines[index]
        was_in_fence = fence_state[0]
        fence_state = get_fence_state(line, fence_state)
        is_outside_fence = not was_in_fence and not fence_state[0]
        if is_outside_fence:
            depth += line.count("<details") - line.count("</details>")
        index += 1
        if depth <= 0:
            break
    return index


class PageMeter:
    """Running rendered-line totals for one body, overall and
    per heading.

    What counts as one rendered line:

    - A collapsed <details> block - its summary only.
    - An expanded <details open> block - summary + its text.
    - A ```mermaid fence - 0 lines, it renders as a diagram.
    - Any other fenced code block - its lines + both fences.
    - Images, HTML comments, link-ref definitions - 0 lines.
    - A heading - 1 line.
    - A long line - ceil(chars / width), since it wraps.
    - A blank line - 0 lines, a separator, not content."""

    def __init__(self, lines, wrap_width):
        self.lines = lines
        self.wrap_width = wrap_width
        self.visible_widths = [get_visible_width(line) for line in lines]
        self.total = 0

        # Everything before the first heading still belongs to a
        # section, so a preamble is reported, never absorbed.
        self.count_by_section = {PREAMBLE: 0}
        self.level_by_section = {PREAMBLE: 0}
        self.open_section_by_level = {0: PREAMBLE}
        self.deepest_open_level = 0

    def get_line_cost(self, index):
        if BLANK.match(self.lines[index]):
            return 1
        return max(1, math.ceil(self.visible_widths[index] / self.wrap_width))

    def charge(self, cost):
        """Add a cost to the total and to every heading still
        open above it, so a section includes its subsections."""
        self.total += cost
        for level in range(self.deepest_open_level + 1):
            section = self.open_section_by_level.get(level, "")
            if section:
                self.count_by_section[section] += cost

    def open_heading(self, line):
        """A heading closes every section at or below its depth,
        so report nesting mirrors document nesting."""
        level = len(line) - len(line.lstrip("#"))
        title = HEADING_MARKER.sub("", line)
        for closed_level in range(level, self.deepest_open_level + 1):
            self.open_section_by_level[closed_level] = ""
        self.open_section_by_level[0] = ""
        self.open_section_by_level[level] = title
        self.deepest_open_level = level
        if title not in self.count_by_section:
            self.count_by_section[title] = 0
            self.level_by_section[title] = level
        self.charge(1)

    def charge_collapsed_summary(self, opener_index):
        """Charge the summary the reader sees, at its wrapped
        width - a long summary costs the same collapsed or
        expanded."""
        lines = self.lines
        index = opener_index + 1
        while index < len(lines):
            if "<summary" in lines[index] or "</details>" in lines[index]:
                break
            index += 1
        has_summary = index < len(lines) and "<summary" in lines[index]
        self.charge(self.get_line_cost(index) if has_summary else 1)

    def charge_code_fence(self, opener_index):
        """Charge a fenced block and return the index past it."""
        lines = self.lines
        is_mermaid = "mermaid" in lines[opener_index].lower()
        fence_state = get_fence_state(lines[opener_index], CLOSED_FENCE)
        index = opener_index + 1
        fenced_cost = 0
        while index < len(lines):
            fence_state = get_fence_state(lines[index], fence_state)
            if not fence_state[0]:
                break
            fenced_cost += self.get_line_cost(index)
            index += 1
        if not is_mermaid:
            self.charge(fenced_cost + 2)
        return index + 1

    def is_never_rendered(self, line):
        return bool(
            LINK_REF_DEFINITION.match(line)
            or "![" in line
            or EMPTY_ANCHOR.match(line)
        )

    def measure(self):
        lines = self.lines
        index = get_body_start(lines)
        while index < len(lines):
            line = lines[index]
            if HTML_COMMENT_OPENER.match(line):
                while index < len(lines) and "-->" not in lines[index]:
                    index += 1
                index += 1
            elif self.is_never_rendered(line):
                index += 1
            elif "<details" in line:
                index = self.skip_details_opener(index)
            elif DETAILS_CLOSER_LINE.match(line) or BLANK.match(line):
                index += 1
            elif "<summary" in line:
                self.charge(self.get_line_cost(index))
                index += 1
            elif is_fence_opener(line):
                index = self.charge_code_fence(index)
            elif HEADING.match(line):
                self.open_heading(line)
                index += 1
            else:
                self.charge(self.get_line_cost(index))
                index += 1

    def skip_details_opener(self, opener_index):
        """An expanded block falls through to its inner lines; a
        collapsed one costs its summary and hides the rest."""
        if EXPANDED_DETAILS.search(self.lines[opener_index]):
            return opener_index + 1
        self.charge_collapsed_summary(opener_index)
        return get_index_after_balanced_closer(self.lines, opener_index)

    def get_breakdown_rows(self):
        """(count, indent, title) rows: top-level sections
        worst-first, each child in document order below it."""
        real_levels = [level for level in self.level_by_section.values() if level > 0]
        top_level = min(real_levels + [NO_HEADING_LEVEL])
        keyed_rows = []
        anchor = 0
        for order, (title, count) in enumerate(self.count_by_section.items()):
            if count <= 0:
                continue
            level = self.level_by_section[title]
            if level <= top_level:
                anchor = count
            sort_key = (SORT_CEILING - anchor, order)
            keyed_rows.append((sort_key, count, level - top_level, title))
        keyed_rows.sort()
        return [(count, indent, title) for _, count, indent, title in keyed_rows]


def read_lines(path):
    # newline="" keeps a CRLF body's \r on each line, as awk
    # did: a lone "\r" line is then text, not a blank.
    with open(path, encoding="utf-8", errors="replace", newline="") as body:
        content = body.read()
    if not content:
        return []
    lines = content.split("\n")
    if content.endswith("\n"):
        lines.pop()
    return lines


def print_report(verdict, rows):
    print(verdict)
    print(BREAKDOWN_HEADER)
    for count, indent, title in rows:
        print(f"  {count:4d}  {'  ' * max(indent, 0)}{title}")


def parse_args(argv):
    if argv[:1] in (["-h"], ["--help"]):
        print_usage(sys.stdout)
        sys.exit(EXIT_FITS)
    file_arg = argv[0] if argv else ""
    page_arg = argv[1] if len(argv) > 1 else DEFAULT_PAGE_LINES
    width_arg = argv[2] if len(argv) > 2 else DEFAULT_WRAP_WIDTH
    if not file_arg:
        fail_usage("missing <file> argument", show_usage=True)
    if not Path(file_arg).is_file():
        fail_usage(f"file not found: {file_arg}")
    if not re.fullmatch(r"[0-9]+", page_arg) or int(page_arg) < 1:
        fail_usage(f"page-lines must be a positive integer, got: {page_arg}")
    is_valid_width = re.fullmatch(r"[0-9]+", width_arg)
    if not is_valid_width or int(width_arg) < MIN_WRAP_WIDTH:
        fail_usage(f"wrap-width must be an integer >= {MIN_WRAP_WIDTH}, got: {width_arg}")
    return Path(file_arg), int(page_arg), int(width_arg)


def main(argv):
    path, page_lines, wrap_width = parse_args(argv)
    try:
        lines = read_lines(path)
    except OSError as error:
        fail_usage(f"cannot read {path}: {error}")
    meter = PageMeter(lines, wrap_width)
    meter.measure()
    total = meter.total
    rows = meter.get_breakdown_rows()
    warn_threshold = page_lines * WARN_PERCENT // 100

    # The breakdown prints even on success: a passing total does
    # not mean every section stayed within its own budget.
    if total > page_lines:
        cut = total - page_lines
        verdict = f"OVER: ~{total} rendered lines - a one-page body is {page_lines}. Cut ~{cut}."
        print_report(verdict, rows)
        return EXIT_OVER
    if total > warn_threshold:
        verdict = f"CLOSE: ~{total} rendered lines of the {page_lines} that fit one page."
        print_report(verdict, rows)
        return EXIT_CLOSE
    spare = page_lines - total
    verdict = f"OK: ~{total} rendered lines - fits one page ({page_lines}), {spare} to spare."
    print_report(verdict, rows)
    return EXIT_FITS


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
