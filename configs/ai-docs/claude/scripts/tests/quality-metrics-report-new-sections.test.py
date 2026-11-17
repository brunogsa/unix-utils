import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_report_support import file_record, measured, report
from quality_metrics_support import (
    verdict_entry_headings as entry_headings,
    verdict_section as section,
)

debt = importlib.import_module("quality_metrics.debt")


def dead_code_record(file, line, name, kind="function", tool="vulture"):
    return {
        "file": file, "line": line, "function": None, "scope": "file",
        "metric": "dead_code", "value": 1, "limit": 0,
        "name": name, "kind": kind, "tool": tool,
    }


def mutant_record(file, line, mutator, replacement, status="survived"):
    return {
        "file": file, "line": line, "scope": "file", "metric": "mutation",
        "value": 1, "limit": 0, "mutator": mutator,
        "replacement": replacement, "status": status,
    }


def with_extras(**extras):
    run = measured(file_record("src/a.py", "size", 100, 512))
    run.update(extras)
    return run


class TestDeadCodeCandidates:
    def test_should_list_each_candidate_with_file_line_name_kind_and_tool(self):
        run = with_extras(dead_code_candidates=[
            dead_code_record("src/a.py", 7, "unused_helper"),
            dead_code_record("web/b.ts", 3, "oldExport", "export", "knip"),
        ])

        text = section(report.build_verdict(run), "Dead code candidates")

        assert "(2)" in text.splitlines()[0]
        first, second = entry_headings(text)
        assert "src/a.py:7" in first and "unused_helper" in first
        assert "function" in first and "vulture" in first
        assert "web/b.ts:3" in second and "export" in second and "knip" in second

    def test_should_count_dead_code_and_mutants_in_debt_like_duplication(self):
        candidate = dead_code_record("src/a.py", 7, "unused_helper")
        mutant = mutant_record("src/a.py", 4, "ArithmeticOperator", "a - b")
        run = with_extras(
            dead_code_candidates=[candidate], surviving_mutants=[mutant]
        )
        minutes = debt.minutes_for(candidate) + debt.minutes_for(mutant)

        text = section(report.build_verdict(run), "Debt")

        assert f"{minutes} min of remediation" in text


class TestMutantSections:
    def test_should_list_surviving_mutants_and_not_run_ranges(self):
        run = with_extras(
            surviving_mutants=[
                mutant_record("src/a.py", 4, "ArithmeticOperator", "a - b"),
                mutant_record("src/b.ts", 9, "EqualityOperator", "a !== b", "no coverage"),
            ],
            mutants_not_run=[
                {"file": "src/c.ts", "lines": "10-20", "label": "not run (budget)"}
            ],
        )

        verdict = report.build_verdict(run)

        survivors = section(verdict, "Surviving mutants")
        assert "(2)" in survivors.splitlines()[0]
        first, second = entry_headings(survivors)
        assert "src/a.py:4" in first and "ArithmeticOperator" in first
        assert "a - b" in first and "survived" in first
        assert "src/b.ts:9" in second and "no coverage" in second
        not_run = section(verdict, "Mutants not run (budget)")
        assert "(1)" in not_run.splitlines()[0]
        [entry] = entry_headings(not_run)
        assert "src/c.ts" in entry and "10-20" in entry

    def test_should_render_neither_section_when_the_report_has_no_mutation_keys(self):
        verdict = report.build_verdict(with_extras())

        assert "Surviving mutants" not in verdict
        assert "Mutants not run" not in verdict


class TestFindingLines:
    def test_should_list_one_line_per_unused_code_finding(self):
        record = file_record("src/a.py", "unused_code", 2, 0)
        record["findings"] = [
            {"line": 3, "rule": "F401", "name": "os"},
            {"line": 9, "rule": "F841", "name": "tmp"},
        ]

        text = section(report.build_verdict(measured(record)), "Open violations")

        assert "line 3: F401 os" in text
        assert "line 9: F841 tmp" in text

    def test_should_list_one_line_per_type_error(self):
        record = file_record("src/a.py", "type_errors", 2, 0)
        record["errors"] = [
            {"line": 5, "rule": "reportArgumentType", "message": "str is not int"},
            {"line": 12, "rule": "reportCallIssue", "message": "too many args"},
        ]

        text = section(report.build_verdict(measured(record)), "Open violations")

        assert "line 5: reportArgumentType - str is not int" in text
        assert "line 12: reportCallIssue - too many args" in text


LEAKED_JEST_WORKER = {
    "pid": 48211,
    "command": "node /Users/dev/integrator/node_modules/jest-worker/build/workers/processChild.js",
    "rss_kb": 811008, "age_seconds": 5400,
    "repo": "/Users/dev/integrator", "is_repo_scout_candidate": True,
}


class TestLeakedProcesses:
    def test_should_list_each_killed_process_with_its_command_memory_age_and_repo(self):
        run = with_extras(leaked_processes={"killed": [LEAKED_JEST_WORKER]})

        text = section(report.build_verdict(run), "Leaked processes")

        [entry] = entry_headings(text)
        assert "pid 48211" in entry and LEAKED_JEST_WORKER["command"] in entry
        assert "RSS 792 MB" in entry and "age 90 min" in entry
        assert "repo /Users/dev/integrator" in entry

    def test_should_mark_a_killed_process_inside_the_measured_repo_as_a_repo_scout_candidate(self):
        run = with_extras(leaked_processes={"killed": [LEAKED_JEST_WORKER]})

        text = section(report.build_verdict(run), "Leaked processes")

        assert "candidate repo scout" in text

    def test_should_list_the_busiest_processes_when_headroom_stayed_no_go(self):
        run = with_extras(leaked_processes={
            "killed": [],
            "busiest_by_cpu": [{"pid": 501, "command": "Slack", "cpu_percent": 87.5, "rss_kb": 409600}],
            "busiest_by_rss": [{"pid": 502, "command": "Google Chrome", "cpu_percent": 3.0, "rss_kb": 2097152}],
        })

        text = section(report.build_verdict(run), "Leaked processes")

        assert "busiest by CPU: pid 501 - Slack - CPU 87.5%, RSS 400 MB" in text
        assert "busiest by RSS: pid 502 - Google Chrome - CPU 3.0%, RSS 2048 MB" in text

    def test_should_render_no_leaked_process_section_when_no_reclaim_ran(self):
        verdict = report.build_verdict(with_extras(leaked_processes=None))

        assert "Leaked processes" not in verdict
