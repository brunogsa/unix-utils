"""Measures function length and file length in non-blank, non-comment lines.

Code files count lines the way lizard counts NLOC. HTML and CSS have no
function syntax, so only their file length is measured, with a plain
count that drops blank lines and comment text.
"""

import re

from quality_metrics.functions import (
    ToolError,
    function_measurement,
    measure_functions,
    run_tool,
)

FUNCTION_LINES_LIMIT = 30
FILE_LINES_LIMIT = 300

COMMENT_PATTERNS = {
    "html": re.compile(r"<!--.*?-->", re.DOTALL),
    "css": re.compile(r"/\*.*?\*/", re.DOTALL),
}

# A lizard `--xml` File item holds Nr., NCSS, CCN, Functions;
# NCSS is the file's non-blank, non-comment line count.
LIZARD_FILE_NCSS = re.compile(
    r'<measure type="File">.*?<item name="[^"]*">\s*'
    r"<value>[^<]*</value>\s*<value>(\d+)</value>",
    re.DOTALL,
)


def measure(target, metrics):
    results = []
    if target.language not in COMMENT_PATTERNS:
        results += _function_length_measurements(target)
    results.append(_file_length_measurement(target))
    return results


def _function_length_measurements(target):
    return [
        function_measurement(target, function, "size", function.nloc, FUNCTION_LINES_LIMIT)
        for function in measure_functions(target.path, target.language)
        if target.touches(function.start, function.end)
    ]


def _file_length_measurement(target):
    if target.language in COMMENT_PATTERNS:
        lines = _count_web_lines(target)
    else:
        lines = _count_code_lines(target)
    return {
        "file": str(target.path),
        "function": None,
        "scope": "file",
        "metric": "size",
        "value": lines,
        "limit": FILE_LINES_LIMIT,
        "line": None,
    }


def _count_web_lines(target):
    without_comments = COMMENT_PATTERNS[target.language].sub("", target.path.read_text())
    return sum(1 for line in without_comments.splitlines() if line.strip())


def _count_code_lines(target):
    output = run_tool(["lizard", "--xml", str(target.path)])
    match = LIZARD_FILE_NCSS.search(output)
    if match is None:
        raise ToolError(f"lizard reported no file length for {target.path}")
    return int(match.group(1))
