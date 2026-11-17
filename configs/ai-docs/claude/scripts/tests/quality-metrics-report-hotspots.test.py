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
    verdict_record_bullets as record_bullets,
    verdict_section as section,
)


HOTSPOT_RUN = measured(
    crap_record("src/red.py", "tangle", 42),
    file_record("src/red.py", "size", 100, FILE_LINES_LIMIT),
    crap_record("src/amber.py", "branchy", 12.8),
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
    def test_should_list_a_failing_20_percent_coverage_as_open_and_leave_a_passing_99_percent_one_out(self):
        run = measured(
            coverage.coverage_record(target("src/solid.py"), 99),
            coverage.coverage_record(target("src/untested.py"), 20),
        )

        verdict = report.build_verdict(run)

        [entry] = record_bullets(section(verdict, "Open violations"))
        assert "src/untested.py" in entry
        assert "src/solid.py" not in entry

    def test_should_draw_a_file_by_its_amber_crap_when_its_coverage_of_95_percent_passes(self):
        run = measured(
            coverage.coverage_record(target("src/mixed.py"), 95),
            crap_record("src/mixed.py", "branchy", 12.8),
        )

        view = hotspots.hotspot_view(run["measurements"])

        [(_, label, color)] = NODE_LINE.findall(view)
        assert color == "amber"
        assert "crap 80%" in label


class TestNoValueRecords:
    def test_should_skip_a_coverage_with_no_coverable_line_in_the_unmeasured_list_and_the_colors(self):
        run = measured(
            coverage.not_applicable_record(target("src/prose_only.py")),
            crap_record("src/prose_only.py", "tidy", 3),
        )

        verdict = report.build_verdict(run)

        assert "src/prose_only.py" not in section(verdict, "Not measured")
        assert nodes_by_file(mermaid_block(verdict)) == {"src/prose_only.py": "green"}

    def test_should_print_a_pessimistic_coverage_with_no_executable_code_by_its_status(self):
        run = measured({
            **coverage.not_applicable_record(
                target("src/types_only.ts"), coverage.NO_EXECUTABLE_CODE
            ),
            "pessimistic": True,
        })

        verdict = report.build_verdict(run)

        (heading,) = record_bullets(section(verdict, "Not measured"))
        assert f"no value ({coverage.NO_EXECUTABLE_CODE})" in heading

    def test_should_list_a_deferred_crap_as_not_measured_print_it_as_no_value_and_paint_its_file_red(self):
        function = FunctionMeasure("tangle", 4, 30, 26, 12, None, None)
        run = measured(
            crap_record("src/known.py", "branchy", 7),
            deferred_records.deferred_measurement(
                target("src/deferred.py"), "crap", CRAP_LIMIT, function
            ),
        )

        verdict = report.build_verdict(run)

        [first] = record_bullets(section(verdict, "Not measured"))
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


def with_churn(record, change_count):
    return {**record, "churn": change_count}


def labels_in_order(view):
    return [label for _, label, _ in NODE_LINE.findall(view)]


class TestHotspotChurn:
    def test_should_print_the_90_day_change_count_after_the_worst_metric_in_the_label_of_a_file(self):
        run = measured(with_churn(crap_record("src/busy.py", "branchy", 12.8), 2))

        view = hotspots.hotspot_view(run["measurements"])

        [label] = labels_in_order(view)
        assert label.endswith("crap 80% · 2 commits/90d")

    def test_should_draw_a_file_with_10_commits_at_50_percent_of_its_limit_before_a_file_with_1_commit_at_90_percent(
        self,
    ):
        run = measured(
            with_churn(crap_record("src/a_rare_but_bad.py", "tangle", 14.4), 1),
            with_churn(crap_record("src/z_busy_but_fine.py", "tidy", 8), 10),
        )

        view = hotspots.hotspot_view(run["measurements"])

        paths = [label.split("<br/>")[0] for label in labels_in_order(view)]
        assert paths == ["src/z_busy_but_fine.py", "src/a_rare_but_bad.py"]

    def test_should_say_churn_not_measured_and_draw_that_file_after_every_measured_file_even_at_zero_churn(
        self,
    ):
        run = measured(
            crap_record("src/no_history.py", "tangle", 90),
            with_churn(crap_record("src/untouched_lately.py", "tidy", 3), 0),
        )

        view = hotspots.hotspot_view(run["measurements"])

        [first, last] = labels_in_order(view)
        assert first.startswith("src/untouched_lately.py")
        assert first.endswith("0 commits/90d")
        assert last.startswith("src/no_history.py")
        assert last.endswith("churn not measured")

    def test_should_state_churn_not_measured_for_a_file_whose_churn_is_none_and_still_build_the_verdict(self):
        run = measured(with_churn(crap_record("src/outside_repo.py", "branchy", 24), None))

        verdict = report.build_verdict(run)

        assert "churn not measured" in mermaid_block(verdict)
