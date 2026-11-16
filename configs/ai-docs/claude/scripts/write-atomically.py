#!/usr/bin/env python3
# write-atomically.py - write stdin to a file, all or nothing.
#
# Usage:
#   write-atomically.py <target-path>
#   write-atomically.py --help
#
# stdin: the whole file content
# stdout: nothing
# exit: 0 on success, 1 when the target directory is missing or
#   the write fails, 2 on bad usage
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics.atomic_write import write_text_atomically

# A leading dot keeps a temp file that a killed run leaves
# behind from matching the target's own glob, such as
# verdict_quality-gate_*.
TEMP_PREFIX = ".write-atomically-"


def main():
    parser = argparse.ArgumentParser(
        description="Write stdin to a file so a reader sees the old "
        "file or the whole new one, never a partial write.",
    )
    parser.add_argument("target", type=Path, help="file to write")
    target = parser.parse_args().target

    if not target.parent.is_dir():
        print(f"write-atomically: directory {target.parent} does not exist", file=sys.stderr)
        return 1

    try:
        text = sys.stdin.read()
        write_text_atomically(target, text, TEMP_PREFIX)
    except (OSError, UnicodeDecodeError) as error:
        print(f"write-atomically: cannot write {target}: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
