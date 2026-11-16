"""The metrics verdict's tooling sections: asks raised and coverage sources."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

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
        js_entry, python_entry = entry_headings(sources_section)
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
