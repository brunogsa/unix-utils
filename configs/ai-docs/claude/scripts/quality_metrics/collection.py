"""Runs a repo's tests under a coverage tool and reads the lcov
report.

Each collector falls back to a global tool: uv with coverage for
Python (`python_coverage`), c8 for JavaScript and TypeScript
(`javascript_coverage`), gcov2lcov for Go (`go_coverage`).
`coverage_result` holds the result type and the lcov reading
they share, and says how a run with no data or red tests scores.
"""

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Callable, Optional

from quality_metrics.coverage_result import (
    DEFERRED_COVERAGE,
    NO_COVERAGE_DATA,
    RED_BUILD,
    CoverageResult,
    NoFreshCoverageError,
    normalized_hits,
    read_fresh_lcov,
)
from quality_metrics.dependencies import head_tree
from quality_metrics.dependency_trees import is_clean_checkout_of
from quality_metrics.failures import TimeoutPolicy, add_ask_once, ask_or_defer
from quality_metrics.go_coverage import collect_go
from quality_metrics.javascript_coverage import collect_javascript, declares_npm_test
from quality_metrics.python_coverage import collect_python
from quality_metrics.related_e2e_specs import failed_specs_reason
from quality_metrics.sourcing import (
    FAILED_TESTS,
    FALL_THROUGH_REASONS,
    JEST,
    MUTATION_OPT_OUT_REASONS,
    NO_HEADROOM,
    REPO_COVERAGE_RUNNERS,
    RepoToolFailure,
    global_tool_for,
    run_repo_coverage_under_policy,
    source_for,
)
from quality_metrics.tool_map import LazyToolMap
from quality_metrics.tools import ToolError

# Names other modules import from here, though the collectors
# and the result type now live in their own modules.
__all__ = [
    "COLLECTORS", "DEFERRED_COVERAGE", "NO_COVERAGE_DATA", "RED_BUILD",
    "CoverageResult", "CoverageRun", "NoFreshCoverageError",
    "collect_go", "collect_javascript", "collect_python",
    "declares_npm_test", "read_fresh_lcov",
]


@dataclass(frozen=True)
class _Measured:
    """A language's coverage and the tool that produced it."""

    result: CoverageResult
    exit_class: Optional[str]
    source: dict
    side_pr_candidate: Optional[str]


@dataclass(eq=False)
class CoverageRun:
    """Measures each language's coverage at most once per
    measuring run.

    The repo's own jest or pytest-cov runs first, once, for
    every language it measures; any other language, or a repo
    tool that crashed, timed out or wrote no coverage data, runs
    the global collector.

    A failing global collector asks (or defers on the spot in a
    session that cannot ask) and reads as deferred coverage.
    Failing tests are a red build.

    `sources` gets one entry per language measured, naming the
    tool and the repo gap; `asks` gets one entry per ask raised.
    A repo test run that timed out or never started sets
    `mutation_opt_out_reason`, which opts mutation out.

    When headroom reads NO-GO before the repo test run,
    `reclaim_leaked_processes(repo_dir)` kills leaked test
    workers once; `leaked_processes` keeps what it killed, plus
    the busiest processes when the run still never started.

    With a `head_ref`, tests run on an export of that ref, so an
    uncommitted file cannot change the coverage of the range.

    `changed_files` maps each changed repo-relative path to its
    language; the repo jest runs from the workspace of each.
    """

    repo_dir: Path
    tool_map: Optional[LazyToolMap] = None
    base_ref: Optional[str] = None
    head_ref: Optional[str] = None
    policy: Optional[TimeoutPolicy] = None
    environ: Optional[dict] = None
    changed_files: dict = field(default_factory=dict)
    reclaim_leaked_processes: Optional[Callable[[Path], dict]] = None
    leaked_processes: Optional[dict] = field(default=None, init=False)
    sources: list = field(default_factory=list, init=False)
    asks: list = field(default_factory=list, init=False)
    mutation_opt_out_reason: Optional[str] = field(default=None, init=False)
    _measured: dict = field(default_factory=dict, init=False)

    def __post_init__(self):
        self.repo_dir = Path(self.repo_dir)
        self.policy = self.policy or TimeoutPolicy()

    def result_for(self, language):
        collector = COLLECTORS.get(language)
        if collector is None:
            return NO_COVERAGE_DATA
        if collector not in self._measured:
            self._measured[collector] = self._measure(language, collector)
        measured = self._measured[collector]
        if not self._has_source_entry(language):
            self.sources.append(_source_entry(language, measured))
        return measured.result

    def _has_source_entry(self, language):
        return language in {entry["language"] for entry in self.sources}

    def _measure(self, language, collector):
        choice = source_for("coverage", self.tool_map, language)
        with head_tree(self.repo_dir, self.head_ref) as tree:
            if choice["source"]["tool"] in REPO_COVERAGE_RUNNERS:
                return self._measure_with_repo_tool(language, choice["source"], tree)
            return self._measure_globally(language, choice["side_pr_candidate"], tree)

    def _measure_with_repo_tool(self, language, source, tree):
        tool = source["tool"]
        collector = COLLECTORS[language]
        changed_paths = sorted(
            path for path, changed_language in self.changed_files.items()
            if COLLECTORS.get(changed_language) is collector
        )
        run_dir = self._repo_tool_run_dir(tool, tree, changed_paths)
        try:
            policy = replace(self.policy, on_no_headroom=self._reclaimer())
            run = run_repo_coverage_under_policy(
                tool, run_dir, policy, self.base_ref, changed_paths,
            )
        except RepoToolFailure as failure:
            self._keep_only_killed_once_started(failure.exit_class)
            if failure.exit_class == FAILED_TESTS:
                return _Measured(RED_BUILD, FAILED_TESTS, source, None)
            self.mutation_opt_out_reason = MUTATION_OPT_OUT_REASONS.get(failure.exit_class)
            reason = FALL_THROUGH_REASONS[failure.exit_class]
            return self._measure_globally(language, f"repo {tool} {reason}", tree, failure.exit_class)
        self._keep_only_killed_once_started(run["exit_class"])
        self._ask_about_failed_related_specs(tool, run.get("failed_related_specs", []))
        result = CoverageResult(normalized_hits(run_dir, run["hits_by_file"], ""), False)
        return _Measured(result, run["exit_class"], source, None)

    def _ask_about_failed_related_specs(self, tool, failed_specs):
        """One tooling ask naming each e2e or integration spec
        that failed or could not run, so its lost hits never
        pass unseen; coverage keeps the other specs' figure."""
        if not failed_specs or self.tool_map is None:
            return
        reason = failed_specs_reason(failed_specs)
        ask = ask_or_defer(self.tool_map, tool, "coverage", reason, self.environ)
        if ask is not None:
            add_ask_once(self, {**ask, "failed_specs": list(failed_specs)})

    def _reclaimer(self):
        if self.reclaim_leaked_processes is None:
            return None

        def reclaim():
            self.leaked_processes = self.reclaim_leaked_processes(self.repo_dir)

        return reclaim

    def _keep_only_killed_once_started(self, exit_class):
        """Drop the busiest lists once the run started: they
        explain only a run that never did."""
        if self.leaked_processes is not None and exit_class != NO_HEADROOM:
            self.leaked_processes = {"killed": self.leaked_processes["killed"]}

    def _repo_tool_run_dir(self, tool, tree, changed_paths):
        """Where the repo tool runs: the checkout itself for
        jest, when the head ref is the checked-out commit and no
        changed file has an uncommitted edit; else the head
        ref's tree.

        An export of the head ref holds no installed
        node_modules, so jest cannot run there. The global
        fall-through stays on the export.
        """
        if tool != JEST or not self.head_ref:
            return tree
        if not is_clean_checkout_of(self.repo_dir, self.head_ref, changed_paths):
            return tree
        return self.repo_dir

    def _measure_globally(self, language, side_pr_candidate, tree, exit_class=None):
        tool = global_tool_for("coverage", language)
        source = {"kind": "global", "tool": tool}
        collector = COLLECTORS[language]
        result = self._collect_globally(collector, tool, tree)
        return _Measured(result, result.failure_reason or exit_class, source, side_pr_candidate)

    def _collect_globally(self, collector, tool, tree):
        if self.tool_map is not None and tool in self.tool_map.entry()["deferred"]:
            return DEFERRED_COVERAGE
        try:
            return collector(tree)
        except ToolError as error:
            return self._defer_after_failure(tool, error)

    def _defer_after_failure(self, tool, error):
        if self.tool_map is None and isinstance(error, NoFreshCoverageError):
            return NO_COVERAGE_DATA
        if self.tool_map is None:
            raise error
        ask = ask_or_defer(self.tool_map, tool, "coverage", str(error), self.environ)
        if ask is not None:
            self.asks.append(ask)
        return DEFERRED_COVERAGE


def _source_entry(language, measured):
    return {
        "metric": "coverage",
        "language": language,
        "source": measured.source,
        "exit_class": measured.exit_class,
        "side_pr_candidate": measured.side_pr_candidate,
    }


COLLECTORS = {
    "python": collect_python,
    "js": collect_javascript,
    "ts": collect_javascript,
    "go": collect_go,
}
