#!/usr/bin/env python3
# check-settings-json-integrity.py - detect a settings.json detached from its
# repo symlink.
#
# Usage:
#   check-settings-json-integrity.py [--settings-path PATH] [--source-path PATH]
#
# Defaults: --settings-path ~/.claude/settings.json, --source-path this
# script's own configs/ai-docs/claude/settings.json.
#
# stdin: none
# stdout: nothing on success; on failure, one line naming the detached path
# exit: 0 when --settings-path is a symlink resolving to --source-path,
#       1 otherwise (missing, a regular file, or a symlink onto a
#       different target)

import argparse
import sys
from pathlib import Path

# This script sits at configs/ai-docs/claude/scripts/, so the repo's
# own settings.json is one parent up.
DEFAULT_SOURCE_PATH = Path(__file__).resolve().parent.parent / "settings.json"
DEFAULT_SETTINGS_PATH = Path.home() / ".claude" / "settings.json"


def find_detachment_reason(settings_path: Path, source_path: Path) -> str | None:
    """Return why settings_path is detached from source_path, or None if intact."""
    if not settings_path.is_symlink():
        if not settings_path.exists():
            return f"{settings_path} does not exist"
        return f"{settings_path} is a regular file, not a symlink"

    if settings_path.resolve() != source_path.resolve():
        return (
            f"{settings_path} is a symlink, but points to "
            f"{settings_path.resolve()} instead of {source_path.resolve()}"
        )

    return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Detect a settings.json detached from its repo symlink.")
    parser.add_argument(
        "--settings-path", type=Path, default=DEFAULT_SETTINGS_PATH,
        help="path expected to be a symlink (default: ~/.claude/settings.json)")
    parser.add_argument(
        "--source-path", type=Path, default=DEFAULT_SOURCE_PATH,
        help="repo source the symlink must resolve to "
             "(default: this script's own configs/ai-docs/claude/settings.json)")
    args = parser.parse_args()

    reason = find_detachment_reason(args.settings_path, args.source_path)
    if reason is not None:
        print(reason, file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
