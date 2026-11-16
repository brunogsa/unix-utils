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
is_over_limit = importlib.import_module("quality_metrics.functions").is_over_limit
coverage = importlib.import_module("quality_metrics.coverage")
failures = importlib.import_module("quality_metrics.failures")
FunctionMeasure = importlib.import_module("quality_metrics.functions").FunctionMeasure
Target = importlib.import_module("quality_metrics.touched").Target

CRAP_LIMIT = crap.CRAP_LIMIT
FILE_LINES_LIMIT = size.FILE_LINES_LIMIT
DEFERRED_LABEL = "pessimistic, tooling deferred"

NODE_LINE = re.compile(r'^\s*(n\d+)\["(.*)"\]:::(\w+)$', re.M)
EDGE_LINE = re.compile(r"^\s*(n\d+) --> (n\d+)$", re.M)


def function_record(file, function, metric, value, limit):
    return {
        "file": file, "function": function, "scope": "function",
        "metric": metric, "value": value, "limit": limit, "line": 10,
    }


def crap_record(file, function, value):
    """A CRAP record, flagged at its limit as crap.py does."""
    record = function_record(file, function, "crap", value, CRAP_LIMIT)
    return {**record, "flagged_at_limit": True}


def file_record(file, metric, value, limit):
    return {
        "file": file, "function": None, "scope": "file",
        "metric": metric, "value": value, "limit": limit, "line": None,
    }


def target(file):
    return Target(Path(file), "python", None, repo_path=file)


def measured(*records):
    """A measure report: every record, and the over-limit ones as violations."""
    return {
        "measurements": list(records),
        "violations": [item for item in records if is_over_limit(item)],
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
        run = measured(crap_record("src/report.py", "buildReport", 11))

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

    def test_should_list_a_kept_over_limit_function_as_a_violation_when_no_split_diff_file_is_linked(
        self, tmp_path
    ):
        unsaved_diff = tmp_path / "split_buildReport.diff"
        claim = {
            "file": "src/report.py", "function": "buildReport", "metric": "crap",
            "split_value": 6, "diff_path": str(unsaved_diff),
        }
        run = measured(crap_record("src/report.py", "buildReport", 11))

        verdict = report.build_verdict(run, exceptions=[claim])

        assert "(0)" in section(verdict, "Exceptions").splitlines()[0]
        violations = section(verdict, "Open violations")
        assert "(1)" in violations.splitlines()[0]
        [entry] = entry_headings(violations)
        assert "buildReport" in entry
        assert "CRAP 11" in entry


    def test_should_keep_an_unfixable_violation_and_a_rejected_exception_open_and_first(
        self, tmp_path
    ):
        split_diff = tmp_path / "split_splitCells.diff"
        split_diff.write_text("--- a/src/cells.py\n+++ b/src/cells.py\n")
        rejected_claim = {
            "file": "src/cells.py", "function": "splitCells", "metric": "crap",
            "split_value": 5, "diff_path": str(split_diff), "rejected": True,
        }
        run = measured(
            crap_record("src/rows.py", "mergeRows", 12),
            crap_record("src/cells.py", "splitCells", 9),
        )

        verdict = report.build_verdict(run, exceptions=[rejected_claim])

        assert "(0)" in section(verdict, "Exceptions").splitlines()[0]
        violations = section(verdict, "Open violations")
        assert "(2)" in violations.splitlines()[0]
        merge_rows, split_cells = sorted(entry_headings(violations))
        assert "mergeRows" in merge_rows
        assert "splitCells" in split_cells
        assert "exception rejected" in split_cells
        assert verdict.index("## Open violations") < verdict.index("## Ranked: CRAP")


class TestDeferredMetrics:
    def test_should_list_deferred_metrics_first_beside_the_exceptions_with_a_count(self):
        label = "pessimistic, tooling deferred"
        deferred = [
            {
                **crap_record("src/report.py", name, CRAP_LIMIT),
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
            crap_record("src/low.py", "tidy", 3),
            crap_record("src/worst.py", "tangle", 14),
            crap_record("src/middle.py", "branchy", 9),
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
    crap_record("src/red.py", "tangle", 14),
    file_record("src/red.py", "size", 100, FILE_LINES_LIMIT),
    crap_record("src/amber.py", "branchy", 6),
    crap_record("src/green.py", "tidy", 3),
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
            crap_record("src/[id].tsx", "Page", 3),
            crap_record('a"b.ts', "pick", 6),
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


class TestCoverageDirection:
    def test_should_rank_a_failing_20_percent_coverage_above_a_passing_99_percent_one(self):
        run = measured(
            coverage.coverage_record(target("src/solid.py"), 99),
            coverage.coverage_record(target("src/untested.py"), 20),
        )

        verdict = report.build_verdict(run)

        first, second = entry_headings(section(verdict, "Ranked: coverage"))
        assert "src/untested.py" in first
        assert "src/solid.py" in second

    def test_should_draw_a_file_by_its_amber_crap_when_its_coverage_of_95_percent_passes(self):
        run = measured(
            coverage.coverage_record(target("src/mixed.py"), 95),
            crap_record("src/mixed.py", "branchy", 6),
        )

        view = hotspots.hotspot_view(run, [])

        [(_, label, color)] = NODE_LINE.findall(view)
        assert color == "amber"
        assert "crap 75%" in label


class TestNoValueRecords:
    def test_should_skip_a_coverage_with_no_coverable_line_in_the_ranking_and_the_colors(self):
        run = measured(
            coverage.not_applicable_record(target("src/prose_only.py")),
            crap_record("src/prose_only.py", "tidy", 3),
        )

        verdict = report.build_verdict(run)

        assert "Ranked: coverage" not in verdict
        assert nodes_by_file(mermaid_block(verdict)) == {"src/prose_only.py": "green"}

    def test_should_rank_a_deferred_crap_first_print_it_as_no_value_and_paint_its_file_red(self):
        function = FunctionMeasure("tangle", 4, 30, 26, 12, None, None)
        run = measured(
            crap_record("src/known.py", "branchy", 7),
            failures.deferred_measurement(
                target("src/deferred.py"), "crap", CRAP_LIMIT, function
            ),
        )

        verdict = report.build_verdict(run)

        first, _ = entry_headings(section(verdict, "Ranked: CRAP"))
        assert "tangle" in first
        assert f"no value ({DEFERRED_LABEL})" in first
        colors = nodes_by_file(mermaid_block(verdict))
        assert colors["src/deferred.py"] == "red"

    def test_should_build_the_verdict_for_a_file_with_no_language_entry_that_has_no_limit(self):
        run = measured(failures.unmeasured_file_measurement("docs/notes.weird"))

        verdict = report.build_verdict(run)

        assert "(1)" in section(verdict, "Deferred metrics").splitlines()[0]
        assert "docs/notes.weird" in verdict


class TestNoCodeMeasured:
    def test_should_state_that_no_code_file_was_measured_and_draw_no_hotspot_when_only_prose_files_change(self):
        verdict = report.build_verdict(measured())

        assert "no code file was measured" in verdict.lower()
        assert "```mermaid" not in verdict
        assert "flowchart" not in verdict


class TestNoGitVerdict:
    def test_should_name_the_no_git_verdict_and_state_the_removed_code_check_and_base_ref_reads_were_skipped(self):
        run = measured(crap_record("tool.sh", "main", 3))

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


KILL_MID_WRITE = """
import os
import signal
import sys

sys.path.insert(0, sys.argv[1])
from quality_metrics import report

# The temp file is fully written; the process dies before the rename.
report.os.replace = lambda *_: os.kill(os.getpid(), signal.SIGKILL)
report.write_verdict(sys.argv[2], sys.argv[3], "new verdict body\\n")
"""


class TestAtomicVerdictWrite:
    def test_should_leave_no_partial_verdict_when_the_run_is_killed_mid_write(self, tmp_path):
        timestamp = "2026-11-15_22-30"
        old_verdict = tmp_path / report.verdict_filename(timestamp)
        old_verdict.write_text("old verdict body\n")

        killed = subprocess.run(
            [sys.executable, "-c", KILL_MID_WRITE, str(SCRIPTS_DIR), str(tmp_path), timestamp]
        )

        assert killed.returncode == -9
        assert old_verdict.read_text() == "old verdict body\n"
        assert list(tmp_path.glob("verdict_*")) == [old_verdict]
        leftovers = [p for p in tmp_path.iterdir() if p != old_verdict]
        assert leftovers, "the kill must have landed after the temp write began"

        written = report.write_verdict(tmp_path, timestamp, "new verdict body\n")

        assert written == old_verdict
        assert written.read_text() == "new verdict body\n"
