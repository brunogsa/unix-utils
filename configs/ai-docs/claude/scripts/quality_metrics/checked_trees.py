"""The temp tree every new tool runs in: the branch's code with
the base ref's tool configs, so a branch cannot loosen its own
gate.
"""

import fnmatch
import os
import shutil
import tarfile
import tempfile
from contextlib import contextmanager
from pathlib import Path

from quality_metrics.dependency_trees import extract_tree_at
from quality_metrics.tools import ToolError, run_tool

DEPENDENCY_DIRECTORY = "node_modules"


@contextmanager
def checked_tree(repo_dir, head_ref, base_ref, config_names):
    """A temp tree path, removed on exit.

    With a head ref it holds that ref's files; without one, the
    working tree's tracked and untracked files, no ignored
    one. Every file matching `config_names` (fnmatch patterns
    on the file name) holds its `base_ref` text, and a match
    absent at `base_ref` is deleted. Each outermost
    node_modules of the working tree is linked in.
    """
    repo = Path(repo_dir)
    with tempfile.TemporaryDirectory() as tree_dir:
        tree = Path(tree_dir)
        if head_ref:
            _extract_head(repo, head_ref, tree)
        else:
            _copy_working_files(repo, tree)
        _pin_configs_to_base(repo, tree, base_ref, config_names)
        _link_dependencies(repo, tree)
        yield tree


def _extract_head(repo, head_ref, tree):
    try:
        extract_tree_at(repo, head_ref, tree)
    except tarfile.FilterError as refusal:
        raise ToolError(f"{head_ref} holds a link leaving the tree: {refusal}") from refusal


def _copy_working_files(repo, tree):
    listed = run_tool(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], cwd=repo
    ).split("\0")
    for name in filter(None, listed):
        source = repo / name
        if source.is_file() or source.is_symlink():
            (tree / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, tree / name, follow_symlinks=False)


def _is_config(path, config_names):
    return any(fnmatch.fnmatch(Path(path).name, pattern) for pattern in config_names)


def _pin_configs_to_base(repo, tree, base_ref, config_names):
    base_files = run_tool(
        ["git", "ls-tree", "-r", "-z", "--name-only", base_ref], cwd=repo
    ).split("\0")
    base_configs = {name for name in base_files if name and _is_config(name, config_names)}
    for current, _, files in os.walk(tree):
        for file_name in files:
            path = Path(current) / file_name
            relative = path.relative_to(tree).as_posix()
            if relative not in base_configs and _is_config(relative, config_names):
                path.unlink()
    for name in sorted(base_configs):
        text = run_tool(["git", "show", f"{base_ref}:{name}"], cwd=repo)
        _write_fresh_file(tree, name, text)


def _write_fresh_file(tree, name, text):
    """Write `text` at `name` in `tree` as a new regular file.

    A link at the destination is replaced. A link at a
    directory above it would carry the write out of the tree
    or onto another file, so it is refused.
    """
    parent = tree
    for part in Path(name).parent.parts:
        parent = parent / part
        if parent.is_symlink():
            raise ToolError(f"{name} sits under a symlink the branch committed: {part}")
    destination = tree / name
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_symlink() or destination.exists():
        destination.unlink()
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
    with os.fdopen(os.open(destination, flags, 0o644), "w") as handle:
        handle.write(text)


def _link_dependencies(repo, tree):
    for current, directories, _ in os.walk(repo):
        if DEPENDENCY_DIRECTORY in directories:
            relative = (Path(current) / DEPENDENCY_DIRECTORY).relative_to(repo)
            link = tree / relative
            link.parent.mkdir(parents=True, exist_ok=True)
            if not link.exists() and not link.is_symlink():
                link.symlink_to(repo / relative)
        directories[:] = [
            name for name in directories if name not in (DEPENDENCY_DIRECTORY, ".git")
        ]
