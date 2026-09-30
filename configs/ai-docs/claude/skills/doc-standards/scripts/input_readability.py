"""Shared unreadable-input handling for the doc-standards checkers.

Not a checker: the name avoids the check-* and fix-* globs that
tests/checker-failure-contract.test.py uses to find checkers.

Each checker loads this by path (its hyphenated siblings cannot be
imported, and an importlib load of a checker puts no directory on
sys.path).
"""


def cannot_read_message(script, path, err):
    # An uncaught decode error would exit 1, which
    # callers read as findings; a load failure exits 2.
    #
    # strerror, since str(err) repeats the path this line names.
    reason = "not valid UTF-8" if isinstance(err, UnicodeDecodeError) else err.strerror or err
    return f"{script}: cannot read {path}: {reason}"


def first_unreadable_input(script, files):
    """cannot_read_message for the first file that is not readable UTF-8,
    or None - checked for every file before any is reported or changed,
    so a bad later file never follows an earlier file's output or
    rewrite."""
    for path in files:
        try:
            with open(path, encoding="utf-8") as fh:
                fh.read()
        except (OSError, UnicodeDecodeError) as err:
            return cannot_read_message(script, path, err)
    return None
