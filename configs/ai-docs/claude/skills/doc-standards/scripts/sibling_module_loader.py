"""Shared loader of the doc-standards checkers' sibling files.

Not a checker: the name avoids the check-* and fix-* globs that
tests/checker-failure-contract.test.py uses to find checkers.

A checker imports this normally: running a script puts its own
directory first on sys.path, symlinked directory included.
Hyphenated siblings cannot be imported by name, so they load by
path here.
"""

import importlib.util
import sys
from pathlib import Path


def load_sibling_module(caller_file, filename):
    """The module in `filename`, a sibling of `caller_file`,
    named after the file with hyphens as underscores.

    A load failure exits 2: the hook reads exit 1 as findings.
    """
    script_dir = Path(caller_file).resolve().parent
    module_name = Path(filename).stem.replace("-", "_")
    try:
        spec = importlib.util.spec_from_file_location(
            module_name, script_dir / filename
        )
        if spec is None or spec.loader is None:
            raise ImportError("no import spec")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    except Exception as error:
        print(
            f"{Path(caller_file).name}: cannot load {filename} "
            f"from {script_dir}: {error}",
            file=sys.stderr,
        )
        sys.exit(2)
    return module
