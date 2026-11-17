"""The coverage result every collector returns, and the lcov
report reading they share.

Each collector writes its lcov report into a temp dir and passes
that file here, so a run leaves no `coverage/` in the measured
repo.

A run that reads as no coverage data (no tests, no report, or a
report older than the run) scores 0%.
A run whose tests fail is a red build: it scores 0% too, marked
pessimistic.
"""

from dataclasses import dataclass
from typing import Optional

from quality_metrics.crap import parse_lcov
from quality_metrics.repo_paths import repo_relative_hits
from quality_metrics.tools import ToolError


@dataclass(frozen=True)
class CoverageResult:
    """Line hits per repo-relative file.

    `has_failed_tests` marks a red build; `is_deferred` marks a
    global tool that could not run and was deferred.
    `failure_reason` says why a global test run failed.
    """

    hits_by_file: dict
    has_failed_tests: bool
    is_deferred: bool = False
    failure_reason: Optional[str] = None


NO_COVERAGE_DATA = CoverageResult(hits_by_file={}, has_failed_tests=False)
RED_BUILD = CoverageResult(hits_by_file={}, has_failed_tests=True)
DEFERRED_COVERAGE = CoverageResult(hits_by_file={}, has_failed_tests=False, is_deferred=True)


class NoFreshCoverageError(ToolError):
    """A passing coverage run left no report newer than the
    run."""


def read_fresh_lcov(lcov_file, repo_dir, run_started):
    """Hits from the lcov file, or no data when it is missing or
    predates the run; names are made relative to `repo_dir`."""
    if not lcov_file.exists() or lcov_file.stat().st_mtime < run_started:
        raise NoFreshCoverageError(f"the passing coverage run wrote no coverage data under {repo_dir}")
    hits_by_file = parse_lcov(lcov_file.read_text())
    return CoverageResult(
        hits_by_file=normalized_hits(repo_dir, hits_by_file, _go_module_prefix(repo_dir)),
        has_failed_tests=False,
    )


def normalized_hits(repo_dir, hits_by_file, module_prefix):
    """Hits keyed by repo-relative name, with any go module
    prefix dropped."""
    return {
        _without_prefix(name, module_prefix): hits
        for name, hits in repo_relative_hits(repo_dir, hits_by_file).items()
    }


def _go_module_prefix(repo_dir):
    """`<module path>/` from go.mod, or "" when there is none.

    gcov2lcov writes each SF as `<module path>/<pkg>/a.go`.
    """
    go_mod = repo_dir / "go.mod"
    if not go_mod.exists():
        return ""
    for line in go_mod.read_text().splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[0] == "module":
            return parts[1].strip('"') + "/"
    return ""


def _without_prefix(name, prefix):
    if prefix and name.startswith(prefix):
        return name[len(prefix):]
    return name
