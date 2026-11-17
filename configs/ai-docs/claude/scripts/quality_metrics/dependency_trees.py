"""Extracts the source trees a dependency tool runs over."""

import tarfile
import tempfile
from contextlib import contextmanager
from pathlib import Path

from quality_metrics.tools import run_command, run_tool


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


def is_clean_checkout_of(repo_dir, head_ref, paths):
    """Whether the checkout sits on the head ref's commit with
    no uncommitted edit to any of the paths, so it holds the
    same files an export of the ref would."""
    head_commit = run_command(["git", "-C", str(repo_dir), "rev-parse", "--verify", f"{head_ref}^{{commit}}"])
    checkout_commit = run_command(["git", "-C", str(repo_dir), "rev-parse", "--verify", "HEAD"])
    if head_commit.returncode != 0 or checkout_commit.returncode != 0:
        return False
    if head_commit.stdout.strip() != checkout_commit.stdout.strip():
        return False
    status = run_command(["git", "-C", str(repo_dir), "status", "--porcelain", "--", *paths])
    return status.returncode == 0 and not status.stdout.strip()


def extract_tree_at(repo_dir, ref, destination):
    archive = destination / "tree.tar"
    run_tool(["git", "-C", str(repo_dir), "archive", "--format=tar", "-o", str(archive), ref])
    with tarfile.open(archive) as tree:
        tree.extractall(destination, filter="data")
    archive.unlink()
