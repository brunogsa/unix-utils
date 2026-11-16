"""Measures function length and file length in non-blank,
non-comment lines.

Code files count lines the way lizard counts NLOC; Bash counts
logical lines, as shellmetrics reads them. HTML and CSS have no
function syntax, so only their file length is measured, with a
plain count that drops blank lines and comment text.
"""

import re

from quality_metrics.functions import (
    BASH,
    measurement,
    run_function_tool,
    touched_functions,
)
from quality_metrics.tools import ToolError, bash_file_lloc

FUNCTION_LINES_LIMIT = 30
FILE_LINES_LIMIT = 300

# HTML and CSS have no function syntax: only file length
# applies.
LANGUAGES_WITHOUT_FUNCTIONS = ("html", "css")

COMMENT_PATTERNS = {
    "html": re.compile(r"<!--.*?-->", re.DOTALL),
    "css": re.compile(r"/\*.*?\*/", re.DOTALL),
}

SCSS_SUFFIX = ".scss"

# SCSS adds `//` line comments. Strings and `url(...)` match
# first and are kept, so a `//` inside them stays code.
SCSS_COMMENT_PATTERN = re.compile(
    r"""("[^"\n]*"|'[^'\n]*'|url\([^)\n]*\))|/\*.*?\*/|//[^\n]*""",
    re.DOTALL,
)

# A lizard `--xml` File item holds Nr., NCSS, CCN, Functions;
# NCSS is the file's non-blank, non-comment line count.
LIZARD_FILE_NCSS = re.compile(
    r'<measure type="File">.*?<item name="[^"]*">\s*'
    r"<value>[^<]*</value>\s*<value>(\d+)</value>",
    re.DOTALL,
)


def measure(target, metrics):
    results = []
    if target.language not in LANGUAGES_WITHOUT_FUNCTIONS:
        results += _function_length_measurements(target)
    results.append(_file_length_measurement(target))
    return results


def _function_length_measurements(target):
    return [
        measurement(target, "size", function.nloc, FUNCTION_LINES_LIMIT, function)
        for function in touched_functions(target)
    ]


def _file_length_measurement(target):
    if target.language in COMMENT_PATTERNS:
        lines = _count_web_lines(target)
    else:
        lines = _count_code_lines(target)
    return measurement(target, "size", lines, FILE_LINES_LIMIT)


def _count_web_lines(target):
    text = target.path.read_text()
    if target.path.suffix == SCSS_SUFFIX:
        without_comments = SCSS_COMMENT_PATTERN.sub(
            lambda match: match.group(1) or "", text
        )
    else:
        without_comments = COMMENT_PATTERNS[target.language].sub("", text)
    return sum(1 for line in without_comments.splitlines() if line.strip())


def _count_code_lines(target):
    if target.language == BASH:
        return bash_file_lloc(
            target.path,
            run=lambda command: run_function_tool(target.tool_policy, command),
        )
    output = run_function_tool(
        target.tool_policy, ["lizard", "--xml", str(target.path)]
    )
    match = LIZARD_FILE_NCSS.search(output)
    if match is None:
        raise ToolError(f"lizard reported no file length for {target.path}")
    return int(match.group(1))
