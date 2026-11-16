"""A repo coverage tool that crashes, through the real script.

The repo's jest dies on an internal error and the global c8 then
writes no data, so no tool measured: the run asks and exits 1.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_support import (
    COVERAGE_DECLARATION_TEXT,
    JEST_CRASH_STUB,
    install_stub_tool,
    measure_cart_where_global_c8_writes_no_data,
)

JEST_CONFIG = "module.exports = { collectCoverage: true };\n"


def test_should_ask_and_list_the_jest_crash_as_a_side_pr_candidate_and_exit_1_when_no_tool_measured_coverage(
    tmp_path, monkeypatch
):
    install_stub_tool(tmp_path, monkeypatch, "jest", JEST_CRASH_STUB)

    result = measure_cart_where_global_c8_writes_no_data(
        tmp_path, monkeypatch, {"jest.config.js": JEST_CONFIG}, COVERAGE_DECLARATION_TEXT
    )

    report = json.loads(result.stdout)
    assert result.returncode == 1
    (ask,) = report["asks"]
    assert ask["tool"] == "c8"
    (source,) = report["sources"]
    assert source["exit_class"] == "crash"
    assert source["source"] == {"kind": "global", "tool": "c8"}
    assert source["side_pr_candidate"] == "repo jest crashed"
