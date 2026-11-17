"""The checked tree one measuring run shares across files.

type_errors runs its tools in a temp copy of the branch with the
base ref's configs, so a branch cannot loosen its own gate. The
copy is built on first use and the checkers run once for every
changed file, not once per file.
"""

from contextlib import ExitStack
from pathlib import Path

from quality_metrics import type_check
from quality_metrics.checked_trees import checked_tree
from quality_metrics.repo_paths import repo_relative
from quality_metrics.tools import ToolError
from quality_metrics.touched import Target, WHOLE_FILE

# pyright and tsc read these; the base ref's text wins.
CONFIG_NAMES = ("pyrightconfig.json", "pyproject.toml", "tsconfig*.json")
TYPE_CHECKED_LANGUAGES = ("python", "ts", "go")
VENV_DIRECTORY = ".venv"


class StaticRun:
    """Shared state for the metrics that read a checked tree.

    `changed_files` maps each changed repo-relative path to its
    language, like CoverageRun's.
    """

    def __init__(self, repo_dir, base_ref, head_ref, changed_files):
        self.repo_dir = Path(repo_dir)
        self.base_ref = base_ref
        self.head_ref = head_ref
        self.changed_files = changed_files
        self._stack = ExitStack()
        self._type_outcome = None

    def close(self):
        self._stack.close()

    def type_error_records_for(self, target):
        """The `type_errors` record of `target`, as one list."""
        outcome = self._type_errors()
        if isinstance(outcome, ToolError):
            raise outcome
        record = outcome.get(repo_relative(self.repo_dir, target.repo_path))
        return [] if record is None else [{**record, "file": str(target.path)}]

    def _type_errors(self):
        """Records by repo path, or the ToolError the checkers
        raised, kept so every file reads the same failure."""
        if self._type_outcome is None:
            try:
                self._type_outcome = self._check_changed_files()
            except ToolError as error:
                self._type_outcome = error
        return self._type_outcome

    def _check_changed_files(self):
        tree = self._tree()
        targets = {
            name: type_check_target(tree / name, language)
            for name, language in self.changed_files.items()
            if language in TYPE_CHECKED_LANGUAGES and (tree / name).is_file()
        }
        records = type_check.type_error_records(tree, list(targets.values()))
        return dict(zip(targets, records))

    def _tree(self):
        tree = self._stack.enter_context(
            checked_tree(self.repo_dir, self.head_ref, self.base_ref, CONFIG_NAMES)
        )
        _link_venv(self.repo_dir, tree)
        return tree


def type_check_target(path, language):
    return Target(path, language, WHOLE_FILE, repo_path=str(path))


def _link_venv(repo_dir, tree):
    """Link the repo's own interpreter, so pyright resolves
    third-party imports; no tree copy holds it."""
    venv = repo_dir / VENV_DIRECTORY
    link = tree / VENV_DIRECTORY
    if venv.is_dir() and not link.exists() and not link.is_symlink():
        link.symlink_to(venv)
