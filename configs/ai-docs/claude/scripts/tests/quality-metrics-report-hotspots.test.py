import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_report_support import (
    CRAP_LIMIT,
    DEFERRED_LABEL,
    FILE_LINES_LIMIT,
    NODE_LINE,
    FunctionMeasure,
    coverage,
    crap_record,
    dependencies,
    deferred_records,
    file_record,
    hotspots,
    measured,
    mermaid_block,
    nodes_by_file,
    report,
    target,
)
from quality_metrics_support import (
    verdict_entry_headings as entry_headings,
    verdict_section as section,
)


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
    crap_record("src/red.py", "tangle", 42),
    file_record("src/red.py", "size", 100, FILE_LINES_LIMIT),
    crap_record("src/amber.py", "branchy", 24),
    crap_record("src/green.py", "tidy", 3),
    file_record("src/limit.py", "size", 512, FILE_LINES_LIMIT),
    file_record("src/edge70.py", "size", 359, FILE_LINES_LIMIT),
    file_record("src/under70.py", "size", 358, FILE_LINES_LIMIT),
)


class TestHotspotView:
    def test_should_show_every_touched_file_in_the_hotspot_view_colored_by_its_worst_metrics_ratio_to_its_limit(self):
        view = hotspots.hotspot_view(HOTSPOT_RUN["measurements"])

        colors = nodes_by_file(view)
        assert colors["src/red.py"] == "red"
        assert colors["src/limit.py"] == "red"
        assert colors["src/amber.py"] == "amber"
        assert colors["src/edge70.py"] == "amber"
        assert colors["src/green.py"] == "green"
        assert colors["src/under70.py"] == "green"

    def test_should_embed_the_hotspot_view_in_the_verdict_within_the_code_design(self):
        verdict = report.build_verdict(HOTSPOT_RUN)

        assert "```mermaid" in section(verdict, "Code design")


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

        first, second = entry_headings(section(verdict, "Ranked: Coverage"))
        assert "src/untested.py" in first
        assert "src/solid.py" in second

    def test_should_draw_a_file_by_its_amber_crap_when_its_coverage_of_95_percent_passes(self):
        run = measured(
            coverage.coverage_record(target("src/mixed.py"), 95),
            crap_record("src/mixed.py", "branchy", 24),
        )

        view = hotspots.hotspot_view(run["measurements"])

        [(_, label, color)] = NODE_LINE.findall(view)
        assert color == "amber"
        assert "crap 80%" in label


class TestNoValueRecords:
    def test_should_skip_a_coverage_with_no_coverable_line_in_the_ranking_and_the_colors(self):
        run = measured(
            coverage.not_applicable_record(target("src/prose_only.py")),
            crap_record("src/prose_only.py", "tidy", 3),
        )

        verdict = report.build_verdict(run)

        assert "Ranked: Coverage" not in verdict
        assert nodes_by_file(mermaid_block(verdict)) == {"src/prose_only.py": "green"}

    def test_should_rank_a_deferred_crap_first_print_it_as_no_value_and_paint_its_file_red(self):
        function = FunctionMeasure("tangle", 4, 30, 26, 12, None, None)
        run = measured(
            crap_record("src/known.py", "branchy", 7),
            deferred_records.deferred_measurement(
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
        run = measured(deferred_records.unmeasured_file_measurement("docs/notes.weird"))

        verdict = report.build_verdict(run)

        assert "(1)" in section(verdict, "Deferred metrics").splitlines()[0]
        assert "docs/notes.weird" in verdict


class TestDependencyDirection:
    def test_should_draw_a_file_red_for_an_introduced_dependency_problem_and_green_for_none(self):
        metric = dependencies.METRIC
        run = measured(
            file_record("src/ui.py", metric, dependencies.FLAGGED_COUNT, dependencies.LIMIT_COUNT),
            file_record("src/core.py", metric, 0, dependencies.LIMIT_COUNT),
        )

        colors = nodes_by_file(hotspots.hotspot_view(run["measurements"]))

        assert colors == {"src/ui.py": "red", "src/core.py": "green"}


class TestNoCodeMeasured:
    def test_should_state_that_no_code_file_was_measured_and_draw_no_hotspot_when_only_prose_files_change(self):
        verdict = report.build_verdict(measured())

        assert "no code file was measured" in verdict.lower()
        assert "```mermaid" not in verdict
        assert "flowchart" not in verdict


class TestHotspotCoverageLabel:
    def test_should_label_a_file_with_coverage_of_89_996_percent_as_coverage_89_99_percent(self):
        run = measured(coverage.coverage_record(target("src/untested.py"), 89.996))

        view = hotspots.hotspot_view(run["measurements"])

        [(_, label, _)] = NODE_LINE.findall(view)
        assert "coverage 89.99%" in label
        assert "89.996" not in label
