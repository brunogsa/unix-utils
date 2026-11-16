"""Repo-relative path handling shared by the measuring modules.

It sits apart from `collection` so that modules `collection`
imports can use it without importing `collection` back.
"""

import os


def repo_relative(repo_dir, name):
    """A repo-relative path, whether `name` is absolute or typed `./a`.

    gcov2lcov and c8 may name a file by absolute path, and a
    `--files` argument may be typed either way.
    """
    name = os.path.normpath(name)
    if not os.path.isabs(name):
        return name
    relative = os.path.relpath(name, repo_dir)
    return name if relative.startswith("..") else relative
