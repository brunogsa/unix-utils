"""Extracts the source trees a dependency tool runs over."""

import tarfile
import tempfile
from contextlib import contextmanager
from pathlib import Path

from quality_metrics.tools import run_tool


@contextmanager
def head_tree(repo_dir, head_ref):
    """With a head ref, its tree, not the working tree.

    An uncommitted edit to any file must not change what
    the range is judged on.
    """
    if not head_ref:
        yield Path(repo_dir)
        return
    with tempfile.TemporaryDirectory() as head_dir:
        extract_tree_at(repo_dir, head_ref, Path(head_dir))
        yield Path(head_dir)


def extract_tree_at(repo_dir, ref, destination):
    archive = destination / "tree.tar"
    run_tool(["git", "-C", str(repo_dir), "archive", "--format=tar", "-o", str(archive), ref])
    with tarfile.open(archive) as tree:
        tree.extractall(destination, filter="data")
    archive.unlink()
