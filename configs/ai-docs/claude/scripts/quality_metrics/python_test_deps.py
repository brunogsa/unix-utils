"""Finds the test dependencies a measured Python repo declares.

A repo whose pytest config loads a plugin outside the
collector's fixed list (for example `-p pytest_asyncio`) makes
pytest exit 4 unless that plugin is installed. uv installs what
the repo declares, through `--with-requirements` and `--group`
(docs.astral.sh/uv/reference/cli/#uv-run).
"""

import tomllib
from pathlib import Path

# Files that only ever list test dependencies.
TEST_REQUIREMENTS_FILES = [
    "requirements-test.txt",
    "requirements-dev.txt",
    "test-requirements.txt",
    "dev-requirements.txt",
]
TEST_DEPENDENCY_GROUPS = ["test", "dev"]


def _read_pyproject(repo_dir):
    pyproject = Path(repo_dir) / "pyproject.toml"
    if not pyproject.exists():
        return {}
    try:
        return tomllib.loads(pyproject.read_text())
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError):
        return {}


def _declared_names(table, wanted):
    return [name for name in wanted if name in table]


def declared_test_dependency_args(repo_dir):
    """The `uv run` flags that install the repo's test
    dependencies, or [] when it declares none."""
    repo_dir = Path(repo_dir)
    args = []
    for name in TEST_REQUIREMENTS_FILES:
        if (repo_dir / name).is_file():
            args += ["--with-requirements", name]
    pyproject = _read_pyproject(repo_dir)
    declared_groups = pyproject.get("dependency-groups", {})
    for group in _declared_names(declared_groups, TEST_DEPENDENCY_GROUPS):
        args += ["--group", group]

    # uv rejects an --extra the [project] table does not define.
    declared_extras = pyproject.get("project", {}).get("optional-dependencies", {})
    for extra in _declared_names(declared_extras, TEST_DEPENDENCY_GROUPS):
        args += ["--extra", extra]
    return args
