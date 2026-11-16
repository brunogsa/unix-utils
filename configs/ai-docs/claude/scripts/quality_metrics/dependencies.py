"""Finds the import cycles and layer imports a change
introduces.

- Each language's tool runs over the head tree and the base
  ref's tree: dependency-cruiser for JS/TS, import-linter for
  Python, go-arch-lint for Go.
- A touched file is flagged when it sits inside an introduced
  cycle or imports a layer it may not.
- A layer map lists layers from outermost to innermost; a layer
  may import itself and any layer after it, never one before it.
- Go import cycles are compile errors, so Go is checked against
  a layer map only.

The tool runners and the layer map loader live in sibling
modules; this one runs them once per tool and scores a target
file against what they found.
"""

import tempfile
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import Optional

from quality_metrics.dependency_cruiser import find_with_dependency_cruiser
from quality_metrics.dependency_records import (
    FLAGGED_COUNT,
    LIMIT_COUNT,
    METRIC,
    deferred_tool_failure,
    problem_records,
)
from quality_metrics.dependency_trees import extract_tree_at, head_tree
from quality_metrics.go_arch_lint import find_with_go_arch_lint
from quality_metrics.import_linter import find_with_import_linter
from quality_metrics.layer_map import load_layer_map
from quality_metrics.python_packages import (
    NoPythonPackageError,
    OutsidePackageError,
    count_python_files_outside,
    is_outside_every_package,
    python_package_roots,
)
from quality_metrics.repo_paths import repo_relative
from quality_metrics.tools import ToolError

# Re-exported: callers import these names from here.
__all__ = [
    "DEPENDENCY_CRUISER", "DependencyRun", "FLAGGED_COUNT", "GO_ARCH_LINT",
    "IMPORT_LINTER", "LIMIT_COUNT", "METRIC", "RefRange", "head_tree",
    "load_layer_map", "measure",
]

DEPENDENCY_CRUISER = "dependency-cruiser"
IMPORT_LINTER = "import-linter"
GO_ARCH_LINT = "go-arch-lint"
TOOL_BY_LANGUAGE = {
    "js": DEPENDENCY_CRUISER,
    "ts": DEPENDENCY_CRUISER,
    "python": IMPORT_LINTER,
    "go": GO_ARCH_LINT,
}

# These tools may be missing or fail, and their files must
# not read as clean then, so a failure scores as a deferred
# violation.
DEFERRABLE_TOOLS = (GO_ARCH_LINT, IMPORT_LINTER)

OUTSIDE_PACKAGE_DETAIL = (
    "file sits outside any Python package, so import-linter "
    "cannot check its imports"
)


@dataclass(frozen=True)
class RefRange:
    """The ref the problems are compared against, and the ref
    whose tree is judged (None: the working tree).
    """

    base_ref: str
    head_ref: Optional[str] = None


class DependencyRun:
    """Finds the head's problems once per tool, however many
    files ask.
    """

    def __init__(self, repo_dir, refs, excluded_paths, layer_map=None):
        self.repo_dir = Path(repo_dir)
        self.base_ref = refs.base_ref
        self.head_ref = refs.head_ref
        self.excluded_paths = excluded_paths
        self.layer_map = layer_map
        self._problems_by_tool = {}
        self._is_loose_python_reported = False

    def problems_by(self, tool):
        """The head's problems, each marked `is_introduced` or
        old.

        A tool that failed raises the same ToolError on every
        ask without running again.
        """
        if tool not in self._problems_by_tool:
            try:
                self._problems_by_tool[tool] = self._find_problems(tool)
            except ToolError as error:
                self._problems_by_tool[tool] = error
        found = self._problems_by_tool[tool]
        if isinstance(found, ToolError):
            raise found
        return found

    def _find_problems(self, tool):
        head = self._find_in_head(tool)
        with tempfile.TemporaryDirectory() as base_dir:
            extract_tree_at(self.repo_dir, self.base_ref, Path(base_dir))
            try:
                base = self._find_in(tool, Path(base_dir))
            except NoPythonPackageError:
                # The branch may add the repo's first package.
                base = []
        base_keys = {problem["key"] for problem in base}
        return [
            {**problem, "is_introduced": problem["key"] not in base_keys}
            for problem in head
        ]

    def require_checkable(self, tool, repo_path):
        """Raise ToolError for a Python file outside every
        package.

        import-linter sees only packages, so such a file would
        read as clean without having been checked.
        """
        if tool == IMPORT_LINTER and is_outside_every_package(
            repo_path, self._head_package_roots
        ):
            raise OutsidePackageError(OUTSIDE_PACKAGE_DETAIL)

    def claim_loose_python_report(self):
        """True for the first caller only.

        Python files outside every package share one deferred
        record per run, not one record each.
        """
        if self._is_loose_python_reported:
            return False
        self._is_loose_python_reported = True
        return True

    def loose_python_detail(self):
        count = self._loose_python_file_count
        noun = "file" if count == 1 else "files"
        return (
            f"{count} Python {noun} sit outside any Python package, "
            "so import-linter cannot check their imports"
        )

    @cached_property
    def _loose_python_file_count(self):
        with self._head_tree() as tree:
            return count_python_files_outside(
                tree, self._head_package_roots
            )

    @cached_property
    def _head_package_roots(self):
        with self._head_tree() as tree:
            return python_package_roots(tree)

    def _head_tree(self):
        return head_tree(self.repo_dir, self.head_ref)

    def _find_in_head(self, tool):
        with self._head_tree() as tree:
            return self._find_in(tool, tree)

    def _find_in(self, tool, tree):
        if tool == DEPENDENCY_CRUISER:
            return find_with_dependency_cruiser(
                tree, self.excluded_paths, self.layer_map
            )
        if tool == GO_ARCH_LINT:
            return find_with_go_arch_lint(tree, self.layer_map)
        if tool == IMPORT_LINTER:
            return find_with_import_linter(tree, self.layer_map)
        raise ValueError(f"no import finder for tool {tool!r}")


def measure(target, metrics, dependency_run):
    """One record per problem the target is part of.

    An introduced problem is flagged. One the base ref already
    had is a hotspot: listed with no count past the limit, so
    it never binds the change. A Go or Python file whose tool
    failed must not read as clean, so it is scored as a
    deferred violation.
    """
    tool = TOOL_BY_LANGUAGE.get(target.language)
    if METRIC not in metrics or tool is None:
        return []
    repo_path = repo_relative(Path.cwd(), target.repo_path or target.path)
    layer_map = dependency_run.layer_map
    layer_map_source = layer_map.source if layer_map else None
    try:
        problems = dependency_run.problems_by(tool)
        dependency_run.require_checkable(tool, repo_path)
    except (NoPythonPackageError, OutsidePackageError):
        if not dependency_run.claim_loose_python_report():
            return []
        return [deferred_tool_failure(
            target, repo_path, dependency_run.loose_python_detail(),
            layer_map_source,
        )]
    except ToolError as error:
        if tool not in DEFERRABLE_TOOLS:
            raise
        return [deferred_tool_failure(
            target, repo_path, str(error), layer_map_source
        )]
    return problem_records(target, repo_path, layer_map_source, problems)
