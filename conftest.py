"""Show pytest's operand diff for failed asserts in this repo's
`<stem>.test.py` suites.

Under `--import-mode=importlib` pytest imports `x.test.py` as
the module "x_test" (dots become underscores). Its assertion-
rewrite hook then looks for `x_test.py` beside it, finds none,
and leaves the asserts unrewritten: a failure prints a bare
AssertionError.

This finder resolves "x_test" to `x.test.py` and hands that
file to pytest's own rewrite hook.
"""

import importlib.util
import sys
from pathlib import Path

MODULE_NAME_SUFFIX = "_test"
DOTTED_TEST_FILE_GLOB = "*.test.py"
REWRITE_HOOK_CLASS_NAME = "AssertionRewritingHook"


def find_rewrite_hook():
    """pytest's assertion-rewrite hook, or None before it is
    installed."""
    for finder in sys.meta_path:
        if type(finder).__name__ == REWRITE_HOOK_CLASS_NAME:
            return finder
    return None


def find_dotted_test_file(directories, module_name):
    """The `<stem>.test.py` file that pytest names
    `module_name`, or None."""
    for directory in directories:
        for test_file in Path(directory).glob(DOTTED_TEST_FILE_GLOB):
            if test_file.stem.replace(".", "_") == module_name:
                return test_file
    return None


class DottedTestStemFinder:
    """Meta-path finder for `<stem>.test.py` files, loading
    them through pytest's assertion-rewrite hook."""

    def find_spec(self, name, path=None, target=None):
        if path is None or not name.endswith(MODULE_NAME_SUFFIX):
            return None
        rewrite_hook = find_rewrite_hook()
        test_file = find_dotted_test_file(path, name)
        if rewrite_hook is None or test_file is None:
            return None
        return importlib.util.spec_from_file_location(name, test_file, loader=rewrite_hook)


sys.meta_path.append(DottedTestStemFinder())
