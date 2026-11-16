import importlib
import re
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

crap = importlib.import_module("quality_metrics.crap")
size = importlib.import_module("quality_metrics.size")
report = importlib.import_module("quality_metrics.report")
hotspots = importlib.import_module("quality_metrics.hotspots")

CRAP_LIMIT = crap.CRAP_LIMIT
FILE_LINES_LIMIT = size.FILE_LINES_LIMIT

NODE_LINE = re.compile(r'^\s*(n\d+)\["(.*)"\]:::(\w+)$', re.M)
EDGE_LINE = re.compile(r"^\s*(n\d+) --> (n\d+)$", re.M)


def function_record(file, function, metric, value, limit):
    return {
        "file": file, "function": function, "scope": "function",
        "metric": metric, "value": value, "limit": limit, "line": 10,
    }


def file_record(file, metric, value, limit):
    return {
        "file": file, "function": None, "scope": "file",
        "metric": metric, "value": value, "limit": limit, "line": None,
    }


def measured(*records):
    """A measure report: every record, and the over-limit ones as violations."""
    return {
        "measurements": list(records),
        "violations": [item for item in records if item["value"] >= item["limit"]],
        "gate_input_violations": [],
    }


def section(verdict, title_prefix):
    """The text of the `## <title_prefix>...` section, up to the next `## `."""
    match = re.search(
        rf"^## {re.escape(title_prefix)}.*?$(.*?)(?=^## |\Z)", verdict, re.M | re.S
    )
    assert match, f"no section starting with {title_prefix!r} in:\n{verdict}"
    return match.group(0)


def entry_headings(text):
    return re.findall(r"^### \d+\. .*$", text, re.M)


class TestExceptions:
    def test_should_open_with_1_exception_naming_the_function_its_score_the_splits_score_and_the_diff_link(
        self, tmp_path
    ):
        split_diff = tmp_path / "split_buildReport.diff"
        split_diff.write_text("--- a/src/report.py\n+++ b/src/report.py\n")
        claim = {
            "file": "src/report.py", "function": "buildReport", "metric": "crap",
            "split_value": 6, "diff_path": str(split_diff),
        }
        run = measured(function_record("src/report.py", "buildReport", "crap", 11, CRAP_LIMIT))

        verdict = report.build_verdict(run, exceptions=[claim])

        exceptions = section(verdict, "Exceptions")
        assert "(1)" in exceptions.splitlines()[0]
        [entry] = entry_headings(exceptions)
        assert entry.startswith("### 1. [metrics]")
        assert "buildReport" in entry
        assert "CRAP 11" in entry
        assert "split CRAP 6" in entry
        assert f"]({split_diff})" in entry
        assert verdict.index("## Exceptions") < verdict.index("## Open violations")

    def test_should_list_buildreport_as_a_crap_violation_with_no_exception_when_no_split_diff_is_saved(
        self, tmp_path
    ):
        unsaved_diff = tmp_path / "split_buildReport.diff"
        claim = {
            "file": "src/report.py", "function": "buildReport", "metric": "crap",
            "split_value": 6, "diff_path": str(unsaved_diff),
        }
        run = measured(function_record("src/report.py", "buildReport", "crap", 11, CRAP_LIMIT))

        verdict = report.build_verdict(run, exceptions=[claim])

        assert "(0)" in section(verdict, "Exceptions").splitlines()[0]
        violations = section(verdict, "Open violations")
        assert "(1)" in violations.splitlines()[0]
        [entry] = entry_headings(violations)
        assert "buildReport" in entry
        assert "CRAP 11" in entry


class TestDeferredMetrics:
    def test_should_list_deferred_metrics_first_beside_the_exceptions_with_a_count(self):
        label = "pessimistic, tooling deferred"
        deferred = [
            {
                **function_record("src/report.py", name, "crap", CRAP_LIMIT, CRAP_LIMIT),
                "pessimistic": True, "label": label,
            }
            for name in ("buildReport", "mergeRows")
        ]

        verdict = report.build_verdict(measured(*deferred))

        deferred_section = section(verdict, "Deferred metrics")
        assert "(1)" in deferred_section.splitlines()[0]
        [entry] = entry_headings(deferred_section)
        assert entry.startswith("### 1. [metrics]")
        assert "CRAP" in entry
        assert "2 measurements" in entry
        assert label in entry
        assert verdict.index("## Deferred metrics") < verdict.index("## Exceptions")
        violations = section(verdict, "Open violations")
        assert "(2)" in violations.splitlines()[0]
        assert "buildReport" in violations
        assert "mergeRows" in violations


class TestRankedLists:
    def test_should_rank_each_metric_in_its_own_list_worst_first_as_markable_metrics_entries(self):
        run = measured(
            function_record("src/low.py", "tidy", "crap", 3, CRAP_LIMIT),
            function_record("src/worst.py", "tangle", "crap", 14, CRAP_LIMIT),
            function_record("src/middle.py", "branchy", "crap", 9, CRAP_LIMIT),
            file_record("src/grown.py", "size", 400, FILE_LINES_LIMIT),
        )

        verdict = report.build_verdict(run)

        crap_entries = entry_headings(section(verdict, "Ranked: CRAP"))
        assert [entry.split("] ")[1].split(" ")[0] for entry in crap_entries] == [
            "tangle", "branchy", "tidy",
        ]
        assert all(re.match(r"### \d+\. \[metrics\] ", entry) for entry in crap_entries)
        [file_size_entry] = entry_headings(section(verdict, "Ranked: File size"))
        assert "src/grown.py" in file_size_entry
        assert "400" in file_size_entry


HOTSPOT_RUN = measured(
    function_record("src/red.py", "tangle", "crap", 14, CRAP_LIMIT),
    file_record("src/red.py", "size", 100, FILE_LINES_LIMIT),
    function_record("src/amber.py", "branchy", "crap", 6, CRAP_LIMIT),
    function_record("src/green.py", "tidy", "crap", 3, CRAP_LIMIT),
    file_record("src/limit.py", "size", 300, FILE_LINES_LIMIT),
    file_record("src/edge70.py", "size", 210, FILE_LINES_LIMIT),
    file_record("src/under70.py", "size", 209, FILE_LINES_LIMIT),
)
IMPORT_EDGES = [
    ("src/red.py", "lib/util.py"),
    ("tools/caller.py", "src/amber.py"),
    ("far/away.py", "lib/util.py"),
]


def nodes_by_file(view):
    """Each node's file path and color, read back from the Mermaid text."""
    return {
        label.split("<br/>")[0]: color for _, label, color in NODE_LINE.findall(view)
    }


class TestHotspotView:
    def test_should_show_every_touched_file_in_the_hotspot_view_colored_by_its_worst_metrics_ratio_to_its_limit(self):
        view = hotspots.hotspot_view(HOTSPOT_RUN, IMPORT_EDGES)

        colors = nodes_by_file(view)
        assert colors["src/red.py"] == "red"
        assert colors["src/limit.py"] == "red"
        assert colors["src/amber.py"] == "amber"
        assert colors["src/edge70.py"] == "amber"
        assert colors["src/green.py"] == "green"
        assert colors["src/under70.py"] == "green"

    def test_should_draw_the_files_one_import_hop_away_but_no_further(self):
        view = hotspots.hotspot_view(HOTSPOT_RUN, IMPORT_EDGES)

        colors = nodes_by_file(view)
        assert colors["lib/util.py"] == "context"
        assert colors["tools/caller.py"] == "context"
        assert "far/away.py" not in colors
        ids = {label.split("<br/>")[0]: id_ for id_, label, _ in NODE_LINE.findall(view)}
        assert set(EDGE_LINE.findall(view)) == {
            (ids["src/red.py"], ids["lib/util.py"]),
            (ids["tools/caller.py"], ids["src/amber.py"]),
        }

    def test_should_embed_the_hotspot_view_in_the_verdict_within_the_code_design(self):
        verdict = report.build_verdict(HOTSPOT_RUN, import_edges=IMPORT_EDGES)

        assert "```mermaid" in section(verdict, "Code design")


def mermaid_block(verdict):
    return re.search(r"```mermaid\n(.*?)```", verdict, re.S).group(1)


class TestHotspotLabels:
    def test_should_render_a_touched_path_holding_brackets_or_quotes_such_as_src_id_tsx_and_a_quote_b_ts(
        self, tmp_path
    ):
        mmdc = shutil.which("mmdc")
        assert mmdc, "mmdc is installed by install.sh; the render check needs it"
        run = measured(
            function_record("src/[id].tsx", "Page", "crap", 3, CRAP_LIMIT),
            function_record('a"b.ts', "pick", "crap", 6, CRAP_LIMIT),
        )

        verdict = report.build_verdict(run)

        source = tmp_path / "hotspot.mmd"
        source.write_text(mermaid_block(verdict))
        render = subprocess.run(
            [mmdc, "-i", str(source), "-o", str(tmp_path / "hotspot.svg")],
            capture_output=True, text=True,
        )
        assert render.returncode == 0, render.stderr
        svg = (tmp_path / "hotspot.svg").read_text()
        assert "src/[id].tsx" in svg
        assert 'a"b.ts' in svg


class TestNoCodeMeasured:
    def test_should_state_that_no_code_file_was_measured_and_draw_no_hotspot_when_only_prose_files_change(self):
        verdict = report.build_verdict(measured())

        assert "no code file was measured" in verdict.lower()
        assert "```mermaid" not in verdict
        assert "flowchart" not in verdict


class TestNoGitVerdict:
    def test_should_name_the_no_git_verdict_and_state_the_removed_code_check_and_base_ref_reads_were_skipped(self):
        run = measured(function_record("tool.sh", "main", "crap", 3, CRAP_LIMIT))

        verdict = report.build_verdict(run, in_git=False)

        assert (
            report.verdict_filename("2026-11-15_22-30", in_git=False)
            == "verdict_quality-gate_no-git_2026-11-15_22-30.md"
        )
        assert (
            report.verdict_filename("2026-11-15_22-30", in_git=True)
            == "verdict_metrics_2026-11-15_22-30.md"
        )
        skipped = section(verdict, "Skipped")
        assert "removed-code check" in skipped
        assert "base-ref" in skipped
        assert "Skipped" not in report.build_verdict(run)
