"""Record builders, modules and Mermaid readers the
quality-metrics report suites share.

Named without a `.test.py` or `test_` marker, so pytest
imports it and never collects it.
"""

import importlib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_support import (
    SCRIPTS_DIR,
    verdict_entry_headings as entry_headings,
    verdict_section as section,
)

sys.path.insert(0, str(SCRIPTS_DIR))

crap = importlib.import_module("quality_metrics.crap")
size = importlib.import_module("quality_metrics.size")
report = importlib.import_module("quality_metrics.report")
hotspots = importlib.import_module("quality_metrics.hotspots")
is_over_limit = importlib.import_module("quality_metrics.functions").is_over_limit
coverage = importlib.import_module("quality_metrics.coverage")
deferred_records = importlib.import_module("quality_metrics.deferred")
dependencies = importlib.import_module("quality_metrics.dependencies")
DUPLICATION_METRICS = importlib.import_module(
    "quality_metrics.duplication"
).DUPLICATION_METRICS
FunctionMeasure = importlib.import_module("quality_metrics.functions").FunctionMeasure
Target = importlib.import_module("quality_metrics.touched").Target

CRAP_LIMIT = crap.CRAP_LIMIT
DEFERRED_CRAP_SCORE = crap.DEFERRED_CRAP_SCORE
FILE_LINES_LIMIT = size.FILE_LINES_LIMIT
DEFERRED_LABEL = "pessimistic, tooling deferred"

NODE_LINE = re.compile(r'^\s*(n\d+)\["(.*)"\]:::(\w+)$', re.M)


def function_record(file, function, metric, value, limit):
    return {
        "file": file, "function": function, "scope": "function",
        "metric": metric, "value": value, "limit": limit, "line": 10,
    }


def crap_record(file, function, value):
    """A CRAP record, flagged only above its limit."""
    return function_record(file, function, "crap", value, CRAP_LIMIT)


def file_record(file, metric, value, limit):
    return {
        "file": file, "function": None, "scope": "file",
        "metric": metric, "value": value, "limit": limit, "line": None,
    }


def target(file):
    return Target(Path(file), "python", None, repo_path=file)


def measured(*records):
    """A measure report: every record, and the over-limit ones
    as violations."""
    over_limit = [item for item in records if is_over_limit(item)]
    return {
        "measurements": list(records),
        "violations": [
            item for item in over_limit if item["metric"] not in DUPLICATION_METRICS
        ],
        "duplication_candidates": [
            item for item in over_limit if item["metric"] in DUPLICATION_METRICS
        ],
        "gate_input_violations": [],
    }


def nodes_by_file(view):
    """Each node's file path and color, read back from the
    Mermaid text."""
    return {
        label.split("<br/>")[0]: color for _, label, color in NODE_LINE.findall(view)
    }


def mermaid_block(verdict):
    return re.search(r"```mermaid\n(.*?)```", verdict, re.S).group(1)
