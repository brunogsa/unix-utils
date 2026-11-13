#!/usr/bin/env python3
# learn-ledger.py - Skip feedback items already handled.
#
# Usage:
#   learn-ledger.py unseen < items.json
#   learn-ledger.py add --verdict <verdict> < items.json
#
# Verdicts: applied, rejected, covered, dropped.
#
# stdin: JSON array of objects with string origin and verbatim.
# stdout: unseen prints the items absent from the ledger.
# stderr: unseen prints how many items it dropped.
#
# Ledger: $LEARN_LEDGER, else
# ~/.claude/state/learn-ledger.jsonl.
# Exit: 0 on success, 2 on bad stdin or bad arguments.

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from typing import NoReturn

DEFAULT_LEDGER_PATH = "~/.claude/state/learn-ledger.jsonl"
VERDICTS = ("applied", "rejected", "covered", "dropped")


def die(msg, code=2) -> NoReturn:
    print(f"learn-ledger: {msg}", file=sys.stderr)
    sys.exit(code)


def ledger_path():
    return os.path.expanduser(os.environ.get("LEARN_LEDGER") or DEFAULT_LEDGER_PATH)


def item_key(item):
    """sha256 of origin + newline + the verbatim with whitespace runs collapsed."""
    normalized_verbatim = " ".join(item["verbatim"].split())
    return hashlib.sha256(f"{item['origin']}\n{normalized_verbatim}".encode()).hexdigest()


def read_items():
    """Parse stdin into a list of items, dying before any write on bad shape."""
    try:
        items = json.load(sys.stdin)
    except json.JSONDecodeError as error:
        die(f"stdin is not valid JSON: {error}")
    if not isinstance(items, list):
        die("stdin must be a JSON array of objects")
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            die(f"item {index} is not a JSON object")
        for field in ("origin", "verbatim"):
            if not isinstance(item.get(field), str):
                die(f"item {index} needs a string '{field}'")
    return items


def read_handled_keys(path):
    """Keys already in the ledger; a malformed line is warned about and skipped."""
    handled_keys = set()
    try:
        with open(path, encoding="utf-8") as ledger_file:
            for line_number, line in enumerate(ledger_file, start=1):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                    handled_keys.add(record["key"])
                except (json.JSONDecodeError, KeyError, TypeError):
                    print(
                        f"learn-ledger: skipping malformed ledger line {line_number} in {path}",
                        file=sys.stderr,
                    )
    except FileNotFoundError:
        pass
    return handled_keys


def file_lacks_trailing_newline(path):
    try:
        with open(path, "rb") as ledger_file:
            ledger_file.seek(0, os.SEEK_END)
            if ledger_file.tell() == 0:
                return False
            ledger_file.seek(-1, os.SEEK_END)
            return ledger_file.read(1) != b"\n"
    except FileNotFoundError:
        return False


def run_unseen(args):
    items = read_items()
    handled_keys = read_handled_keys(ledger_path())
    unseen_items = [item for item in items if item_key(item) not in handled_keys]
    json.dump(unseen_items, sys.stdout)
    sys.stdout.write("\n")
    dropped_count = len(items) - len(unseen_items)
    print(f"learn-ledger: dropped {dropped_count} already-handled item(s)", file=sys.stderr)


def run_add(args):
    items = read_items()
    path = ledger_path()
    handled_keys = read_handled_keys(path)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    new_lines = []
    for item in items:
        key = item_key(item)
        if key in handled_keys:
            continue
        handled_keys.add(key)
        record = {"key": key, "origin": item["origin"], "verdict": args.verdict, "ts": timestamp}
        new_lines.append(json.dumps(record) + "\n")
    if not new_lines:
        return
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    if file_lacks_trailing_newline(path):
        new_lines.insert(0, "\n")
    with open(path, "a", encoding="utf-8") as ledger_file:
        ledger_file.write("".join(new_lines))


def build_parser():
    parser = argparse.ArgumentParser(
        description="Skip feedback items a learn run already handled."
    )
    subcommands = parser.add_subparsers(dest="command", required=True)
    unseen_parser = subcommands.add_parser(
        "unseen", help="print the stdin items not yet in the ledger"
    )
    unseen_parser.set_defaults(run=run_unseen)
    add_parser = subcommands.add_parser("add", help="record the stdin items in the ledger")
    add_parser.add_argument("--verdict", required=True, choices=VERDICTS)
    add_parser.set_defaults(run=run_add)
    return parser


def main():
    args = build_parser().parse_args()
    args.run(args)


if __name__ == "__main__":
    main()
