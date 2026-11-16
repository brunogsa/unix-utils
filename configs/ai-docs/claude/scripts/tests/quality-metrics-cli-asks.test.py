"""The measure script reports tooling asks and never exits clean on one.

An ask means a metric went unmeasured. Its records read as the worst
case, so the run exits 1 like any failing measurement.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_support import (
    measure_cart_where_global_c8_writes_no_data,
)

COVERAGE_AND_CRAP_DECLARATION_TEXT = """\
excluded_paths: []
ignored_extensions: [.md]
per_unit: []
languages:
  js:
    extensions: [.js]
    metrics: [crap, coverage]
"""

DEFERRED_LABEL = "pessimistic, tooling deferred"


def records_for(report, metric):
    return [item for item in report["measurements"] if item["metric"] == metric]


def test_should_exit_1_and_print_a_fix_now_or_defer_ask_when_the_global_coverage_tool_passes_but_writes_no_data(
    tmp_path, monkeypatch
):
    result = measure_cart_where_global_c8_writes_no_data(
        tmp_path, monkeypatch, {}, COVERAGE_AND_CRAP_DECLARATION_TEXT
    )

    report = json.loads(result.stdout)
    assert result.returncode == 1
    (ask,) = report["asks"]
    assert ask["tool"] == "c8"
    assert ask["metric"] == "coverage"
    assert ask["choices"] == ["fix now", "defer"]


def test_should_score_coverage_and_crap_at_their_worst_case_when_the_coverage_tool_asked(
    tmp_path, monkeypatch
):
    result = measure_cart_where_global_c8_writes_no_data(
        tmp_path, monkeypatch, {}, COVERAGE_AND_CRAP_DECLARATION_TEXT
    )

    report = json.loads(result.stdout)
    (coverage,) = records_for(report, "coverage")
    (crap,) = records_for(report, "crap")
    assert coverage["value"] == 0
    assert coverage["pessimistic"] is True
    assert coverage["label"] == DEFERRED_LABEL
    assert crap["pessimistic"] is True
    assert crap["label"] == DEFERRED_LABEL
    assert {coverage["file"], crap["file"]} == {"src/cart.js"}
    assert coverage in report["violations"]
    assert crap in report["violations"]


def test_should_list_the_global_coverage_tool_and_the_repo_gap_as_the_source_when_the_repo_has_no_coverage_tool(
    tmp_path, monkeypatch
):
    result = measure_cart_where_global_c8_writes_no_data(
        tmp_path, monkeypatch, {}, COVERAGE_AND_CRAP_DECLARATION_TEXT
    )

    (source,) = json.loads(result.stdout)["sources"]
    assert source["metric"] == "coverage"
    assert source["language"] == "js"
    assert source["source"] == {"kind": "global", "tool": "c8"}
    assert source["side_pr_candidate"] == "no repo coverage tool for js"
