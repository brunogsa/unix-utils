"""One atomic text writer shared by every file this package
persists."""

import os
import tempfile
from pathlib import Path


def write_text_atomically(path, text, temp_prefix):
    """Write `text` to `path` so a reader sees the old file or
    the whole new one.

    The text goes to a temp file in the same directory, named
    with `temp_prefix`, then a rename. A failed write removes
    the temp file.
    """
    descriptor, temp_name = tempfile.mkstemp(dir=path.parent, prefix=temp_prefix)
    try:
        with os.fdopen(descriptor, "w") as temp_file:
            temp_file.write(text)
        os.replace(temp_name, path)
    except BaseException:
        Path(temp_name).unlink(missing_ok=True)
        raise
