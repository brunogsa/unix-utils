"""Finds the Python packages of a source tree and the Python
files that sit outside every one of them.
"""

import os
import posixpath
from pathlib import Path

from quality_metrics.tools import ToolError

PYTHON_PACKAGE_MARKER = "__init__.py"
SKIPPED_DIRECTORY_NAMES = ("node_modules",)


class NoPythonPackageError(ToolError):
    """The tree holds no directory with an `__init__.py`."""


class OutsidePackageError(ToolError):
    """A Python file sits outside every package."""


def is_outside_every_package(repo_path, package_roots):
    package_dirs = [
        posixpath.join(parent, name) for name, parent in package_roots.items()
    ]
    return not any(
        repo_path.startswith(f"{package_dir}/") for package_dir in package_dirs
    )


def _walkable(directory_names):
    return [
        name for name in directory_names
        if not name.startswith(".") and name not in SKIPPED_DIRECTORY_NAMES
    ]


def python_package_roots(tree):
    """Each top-most package at any depth: its name -> parent
    dir.

    The parent is relative to the tree, `""` for the tree
    itself.
    """
    roots = {}
    for directory, subdirectories, files in os.walk(tree):
        subdirectories[:] = sorted(_walkable(subdirectories))
        package_dir = Path(directory)
        if PYTHON_PACKAGE_MARKER in files and package_dir != tree:
            subdirectories.clear()
            parent = package_dir.parent.relative_to(tree).as_posix()
            roots.setdefault(package_dir.name, "" if parent == "." else parent)
    return roots
