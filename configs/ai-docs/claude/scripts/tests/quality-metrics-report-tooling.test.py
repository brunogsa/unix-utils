"""The metrics verdict's tooling sections: asks raised and
coverage sources, and the tooling-only verdict quality-gate puts
ahead of the merged findings."""

import re
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import quality_metrics_report_support as support_report
import quality_metrics_support as support

sys.path.insert(0, str(support.SCRIPTS_DIR))

from quality_metrics import failures, report

section = support.verdict_section
entry_headings = support.verdict_entry_headings


def empty_report(**extra):
    return {"measurements": [], "violations": [], "gate_input_violations": [], **extra}


class TestToolingAsks:
    def test_should_list_each_tooling_ask_in_the_verdict_after_the_deferred_metrics(self):
        ask = failures.tooling_ask("c8", "coverage", "c8 crashed with exit 1")

        verdict = report.build_verdict(empty_report(asks=[ask], sources=[]))

        asks_section = section(verdict, "Tooling asks")
        assert "(1)" in asks_section.splitlines()[0]
        assert entry_headings(asks_section) == [
            "### 1. [metrics] c8 (coverage) - c8 crashed with exit 1"
        ]
        assert verdict.index("## Deferred metrics") < verdict.index("## Tooling asks")
        assert verdict.index("## Tooling asks") < verdict.index("## Exceptions")


class TestCoverageSources:
    def test_should_list_each_coverage_source_with_its_side_pr_candidate_in_the_verdict(self):
        sources = [
            {
                "metric": "coverage", "language": "js",
                "source": {"kind": "global", "tool": "c8"},
                "exit_class": "crash",
                "side_pr_candidate": "no repo coverage tool for js",
            },
            {
                "metric": "coverage", "language": "python",
                "source": {"kind": "repo", "tool": "pytest-cov"},
                "exit_class": None,
                "side_pr_candidate": None,
            },
        ]

        verdict = report.build_verdict(empty_report(asks=[], sources=sources))

        sources_section = section(verdict, "Coverage sources")
        assert "(2)" in sources_section.splitlines()[0]
        js_entry, python_entry = support.verdict_record_bullets(sources_section)
        assert "js" in js_entry
        assert "global c8" in js_entry
        assert "crash" in js_entry
        assert "side-PR candidate: no repo coverage tool for js" in js_entry
        assert "python" in python_entry
        assert "repo pytest-cov" in python_entry
        assert "side-PR" not in python_entry
        assert "exit" not in python_entry
        assert verdict.index("## Coverage sources") < verdict.index("## Code design")

    def test_should_render_empty_tooling_sections_for_a_report_without_sources_or_asks(self):
        verdict = report.build_verdict(empty_report())

        assert "(0)" in section(verdict, "Tooling asks").splitlines()[0]
        assert "(0)" in section(verdict, "Coverage sources").splitlines()[0]


TOOLING_HEADING = "## Tooling / Process issues"

CRASHED_SOURCE = {
    "metric": "coverage", "language": "js",
    "source": {"kind": "global", "tool": "c8"},
    "exit_class": "crash",
    "side_pr_candidate": "repo jest crashed",
}

THRESHOLD_SOURCE = {
    "metric": "coverage", "language": "ts",
    "source": {"kind": "repo", "tool": "jest"},
    "exit_class": "repo_threshold",
    "side_pr_candidate": None,
}

NOT_RUN_RANGE = {"file": "src/cart.py", "lines": "1-40", "label": "not run (budget)"}

OVER_LIMIT_CRAP = {
    "file": "src/invoice.py", "function": "reconcile_invoice", "scope": "function",
    "metric": "crap", "value": 41.5, "limit": 30, "line": 12,
}

DEFERRED_COVERAGE = {
    "file": "src/cart.py", "function": None, "scope": "file", "metric": "coverage",
    "value": None, "limit": 80, "line": None,
    "label": support_report.DEFERRED_LABEL, "pessimistic": True,
}

LEAKED_WORKER = {
    "pid": 4242, "command": "node jest-worker", "rss_kb": 204800,
    "age_seconds": 5400, "repo": "/Users/dev/shop", "is_repo_scout_candidate": False,
}


def _accepted_exception(tmp_path):
    diff_path = tmp_path / "reconcile_invoice.split.diff"
    diff_path.write_text("--- a\n+++ b\n")
    return [{
        "file": "src/invoice.py", "function": "reconcile_invoice", "metric": "crap",
        "diff_path": str(diff_path), "split_value": 12, "rejected": False,
    }]


def _with_every_tooling_problem(tmp_path):
    """A report, its exception claims and its in-git flag, with
    every tooling subsection non-zero."""
    run = empty_report(
        measurements=[DEFERRED_COVERAGE, OVER_LIMIT_CRAP],
        violations=[OVER_LIMIT_CRAP],
        asks=[failures.tooling_ask("c8", "coverage", "c8 crashed with exit 1")],
        mutants_not_run=[NOT_RUN_RANGE],
        not_applicable=[{"file": "src/schema.py", "metric": "coverage", "reason": "generated file"}],
        sources=[CRASHED_SOURCE],
        leaked_processes={"killed": [LEAKED_WORKER]},
    )
    return run, _accepted_exception(tmp_path), False


class TestToolingOnlyVerdict:
    # why: the merged verdict a human reads shows only
    # the tooling and process problems ahead of the
    # findings; the full render stays the judge's input.
    @pytest.mark.parametrize("subsection", [
        "Deferred metrics (1)",
        "Tooling asks (1)",
        "Exceptions (1)",
        "Not measured (1)",
        "Mutants not run (1)",
        "Not applicable (1)",
        "Coverage sources with a tooling problem (1)",
        "Leaked processes (1)",
        "Skipped checks",
    ])
    def test_should_show_a_tooling_subsection_under_the_tooling_heading_when_it_has_an_entry(
        self, tmp_path, subsection
    ):
        run, exceptions, in_git = _with_every_tooling_problem(tmp_path)

        tooling = report.build_tooling_verdict(run, exceptions, in_git=in_git)

        assert tooling.startswith(TOOLING_HEADING + "\n")
        assert f"### {subsection}\n" in tooling

    def test_should_render_nothing_when_the_only_coverage_source_is_a_repo_tool_that_stopped_at_its_threshold(self):
        run = empty_report(asks=[], sources=[THRESHOLD_SOURCE])

        assert report.build_tooling_verdict(run) == ""

    def test_should_render_nothing_for_open_violations_candidates_and_surviving_mutants_alone(self):
        run = empty_report(
            measurements=[OVER_LIMIT_CRAP],
            violations=[OVER_LIMIT_CRAP],
            duplication_candidates=[{**OVER_LIMIT_CRAP, "metric": "code_duplication", "function": None}],
            surviving_mutants=[{
                "file": "src/cart.py", "line": 7, "mutator": "ConditionalExpression",
                "replacement": "true", "status": "Survived",
            }],
        )

        assert report.build_tooling_verdict(run) == ""

    def test_should_leave_out_every_tooling_subsection_with_no_entry(self):
        run = empty_report(mutants_not_run=[NOT_RUN_RANGE], sources=[THRESHOLD_SOURCE])

        tooling = report.build_tooling_verdict(run)

        assert re.findall(r"^#{2,3} .*$", tooling, re.M) == [
            TOOLING_HEADING, "### Mutants not run (1)"
        ]

    def test_should_number_the_deferred_ask_and_exception_entries_as_the_full_verdict_numbers_them(
        self, tmp_path
    ):
        run, exceptions, in_git = _with_every_tooling_problem(tmp_path)

        full = report.build_verdict(run, exceptions, in_git=in_git)
        tooling = report.build_tooling_verdict(run, exceptions, in_git=in_git)

        assert len(entry_headings(full)) == 3
        assert entry_headings(tooling) == entry_headings(full)

    @pytest.mark.parametrize("checker", support_report.PROSE_CHECKERS)
    def test_should_render_a_tooling_verdict_the_prose_checker_passes(self, tmp_path, checker):
        run, exceptions, in_git = _with_every_tooling_problem(tmp_path)
        verdict_path = tmp_path / "tooling.md"
        verdict_path.write_text(report.build_tooling_verdict(run, exceptions, in_git=in_git))

        result = subprocess.run(
            [str(support_report.DOC_SCRIPTS_DIR / checker), str(verdict_path)],
            capture_output=True, text=True,
        )

        assert (result.returncode, result.stdout) == (0, ""), result.stdout + result.stderr
