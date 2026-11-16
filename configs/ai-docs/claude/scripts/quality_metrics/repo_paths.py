"""Repo-relative path handling shared by the measuring modules.

It sits apart from `collection` so that modules `collection`
imports can use it without importing `collection` back.
"""

import os


def repo_relative(repo_dir, name):
    """A repo-relative path, whether `name` is absolute or typed
    `./a`.

    gcov2lcov, c8 and jest may name a file by absolute path, and
    a `--files` argument may be typed either way. Both sides are
    resolved first, so `/tmp/x` and `/private/tmp/x` compare
    equal.
    A path outside the repo comes back unchanged.
    """
    name = os.path.normpath(name)
    if not os.path.isabs(name):
        return name
    relative = os.path.relpath(os.path.realpath(name), os.path.realpath(repo_dir))
    return name if relative.startswith("..") else relative


def repo_relative_hits(repo_dir, hits_by_file):
    """Line hits re-keyed by each file's repo-relative path."""
    return {repo_relative(repo_dir, name): hits for name, hits in hits_by_file.items()}
