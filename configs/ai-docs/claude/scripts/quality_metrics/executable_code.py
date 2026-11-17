"""Tells a JS/TS file with no executable code - a type-only
file or a barrel of re-exports - from one a test can run.

The answer comes from the TypeScript parser and is only ever
yes when it is certain: a parse error, an unknown extension or
a failed parser call all answer no, so the file keeps its
measured reading.
"""

import functools
from pathlib import Path

from quality_metrics.tools import ToolError, run_command

NODE_TOOLS = Path(__file__).resolve().parent / "node_tools"
NO_EXECUTABLE_CODE_SCRIPT = NODE_TOOLS / "print-has-no-executable-code.mjs"

JS_TS_SUFFIXES = frozenset({".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".mts", ".cts"})


@functools.lru_cache(maxsize=None)
def has_no_executable_code(path):
    """True only when every top-level statement of the JS/TS
    file at `path` is an import, a re-export, a type-only
    export, a type alias or an interface."""
    if Path(path).suffix not in JS_TS_SUFFIXES:
        return False
    try:
        result = run_command(["node", str(NO_EXECUTABLE_CODE_SCRIPT), str(path)])
    except ToolError:
        return False
    return result.returncode == 0 and result.stdout.strip() == "true"
