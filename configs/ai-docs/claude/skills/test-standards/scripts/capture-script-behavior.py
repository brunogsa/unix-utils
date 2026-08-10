#!/usr/bin/env python3
# capture-script-behavior.py - Capture-and-replay characterization
# harness: run a table of input rows against a script, record its
# full (stdout, stderr, exit code, fixture post-state) tuple as
# golden, and emit a <stem>.test.py that replays the same table
# against a rewrite to prove behavioral equivalence.
#
# Usage:
#   capture-script-behavior.py capture --script PATH --table TABLE.json
#     [--json-out CAPTURED.json] [--out STEM.test.py]
#   capture-script-behavior.py compare --expected EXPECTED.json
#     --actual ACTUAL.json
#
# stdin: none
# stdout: `compare` prints one JSON result object; `capture` prints
#   nothing on success (its output is --json-out / --out)
#
# exit: 0 on success; 1 on a row that fails without an accepted
#   divergence marker, a fixture-escape attempt, or a bad invocation

import argparse
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

# Shared, declared mask set — the ONLY place non-deterministic
# values get normalized. Both capture (before hashing fixture
# content) and compare (before comparing stdout/stderr) route
# through mask_text, so a script never needs its own private mask.
MASK_PATTERNS = (
    (re.compile(r"\b\d+(\.\d+)?s\b"), "<DURATION>"),
    (re.compile(r"\bpid[= ]\d+\b", re.IGNORECASE), "pid=<PID>"),
    (re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.IGNORECASE), "<UUID>"),
    (re.compile(r"/tmp/tmp[A-Za-z0-9_]{4,}"), "<TMPDIR>"),
    (re.compile(r"/var/folders/[A-Za-z0-9_./-]+"), "<TMPDIR>"),
)

# A fixture_files key that resolves outside its own fixture
# directory is the exact escape the Threat Model warns about — a
# capture must never be allowed to write into the real repo.
FIXTURE_ESCAPE_MARKERS = ("..",)


class FixtureEscapeError(ValueError):
    """Raised when a row's fixture_files key would write outside its
    isolated fixture directory."""


@dataclass
class Row:
    name: str
    argv: list = field(default_factory=list)
    stdin: str = ""
    branch: str | None = None
    fixture_files: dict = field(default_factory=dict)
    git_init: bool = False
    divergence: str | None = None
    expected_stdout: str | None = None
    expected_stderr: str | None = None
    expected_exit_code: int | None = None
    expected_post_state: dict | None = None

    @classmethod
    def from_dict(cls, data: dict) -> "Row":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})

    def has_golden(self) -> bool:
        return self.expected_exit_code is not None


@dataclass
class Captured:
    name: str
    branch: str | None
    stdout: str
    stderr: str
    exit_code: int
    post_state: dict


def mask_text(text: str, *, fixture_dir: Path | None = None) -> str:
    """Normalize non-deterministic values so two captures differing
    only in duration/pid/uuid/temp-path compare equal. `fixture_dir`
    is substituted first (both its raw and resolved form, since
    macOS symlinks /tmp -> /private/tmp) because it's a value we
    KNOW is unique per run — the generic patterns below only catch
    the common shapes, not every OS's real temp-dir layout."""
    if fixture_dir is not None:
        # Longest-first: the resolved path (e.g. macOS's
        # /private/var/... symlink target) contains the raw path as
        # a substring, so replacing the raw form first would strand
        # the "/private" prefix un-masked instead of consuming the
        # whole resolved match. A plain set() has no ordering
        # guarantee, which made this fail non-deterministically
        # depending on PYTHONHASHSEED.
        candidates = sorted({str(fixture_dir), str(fixture_dir.resolve())}, key=len, reverse=True)
        for candidate in candidates:
            if candidate:
                text = text.replace(candidate, "<FIXTURE_DIR>")
    for pattern, replacement in MASK_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def _validate_fixture_key(key: str) -> None:
    if Path(key).is_absolute() or any(marker in Path(key).parts for marker in FIXTURE_ESCAPE_MARKERS):
        raise FixtureEscapeError(
            f"fixture_files key {key!r} escapes its fixture directory "
            "(absolute paths and '..' segments are rejected before the "
            "script ever runs)"
        )


def hash_fixture_tree(root: Path, *, fixture_dir: Path) -> dict:
    """Recursively hash every file under `root` (masking content
    first) into a {relpath: sha256} map — the post-state half of the
    captured tuple."""
    tree = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            relpath = path.relative_to(root).as_posix()
            raw = path.read_bytes()
            try:
                masked = mask_text(raw.decode("utf-8"), fixture_dir=fixture_dir).encode("utf-8")
            except UnicodeDecodeError:
                masked = raw
            tree[relpath] = hashlib.sha256(masked).hexdigest()
    return tree


def capture_git_status(root: Path, *, fixture_dir: Path) -> str | None:
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=root, capture_output=True, text=True,
    )
    if result.returncode != 0:
        return None
    return mask_text(result.stdout, fixture_dir=fixture_dir)


def setup_fixture(fixture_dir: Path, row: Row) -> None:
    for key, content in row.fixture_files.items():
        _validate_fixture_key(key)
        target = (fixture_dir / key).resolve()
        if fixture_dir.resolve() not in target.parents and target != fixture_dir.resolve():
            raise FixtureEscapeError(
                f"fixture_files key {key!r} resolves outside {fixture_dir}"
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
    if row.git_init:
        subprocess.run(["git", "init", "-q"], cwd=fixture_dir, capture_output=True)
        subprocess.run(["git", "add", "-A"], cwd=fixture_dir, capture_output=True)


def capture_row(script: Path, row: Row, *, fixture_dir: Path) -> Captured:
    """Run one table row against `script` inside its own, already-
    prepared fixture_dir and return the full captured tuple."""
    result = subprocess.run(
        [str(script), *row.argv],
        cwd=fixture_dir, input=row.stdin,
        capture_output=True, text=True,
    )
    post_state = {
        "tree": hash_fixture_tree(fixture_dir, fixture_dir=fixture_dir),
        "git_status": capture_git_status(fixture_dir, fixture_dir=fixture_dir) if row.git_init else None,
    }
    return Captured(
        name=row.name,
        branch=row.branch,
        stdout=mask_text(result.stdout, fixture_dir=fixture_dir),
        stderr=mask_text(result.stderr, fixture_dir=fixture_dir),
        exit_code=result.returncode,
        post_state=post_state,
    )


@dataclass
class ComparisonResult:
    matches: bool
    diff: dict


def compare_captured(expected: dict, actual: Captured) -> ComparisonResult:
    """Pure masked-field comparison of a row's golden fields against
    a fresh Captured tuple — stdout, stderr, exit_code AND
    post_state all participate, closing the gap of an older 3-tuple
    comparison that ignored fixture state. No divergence logic here:
    this is what both `compare` and the emitted <stem>.test.py call,
    and a genuine regression must always fail it."""
    diff = {}
    for field_name, expected_key in (
        ("stdout", "expected_stdout"),
        ("stderr", "expected_stderr"),
    ):
        exp_val = expected.get(expected_key)
        act_val = mask_text(getattr(actual, field_name))
        if exp_val is not None and mask_text(exp_val) != act_val:
            diff[field_name] = {"expected": exp_val, "actual": getattr(actual, field_name)}
    if expected.get("expected_exit_code") is not None and expected["expected_exit_code"] != actual.exit_code:
        diff["exit_code"] = {"expected": expected["expected_exit_code"], "actual": actual.exit_code}
    if expected.get("expected_post_state") is not None and expected["expected_post_state"] != actual.post_state:
        diff["post_state"] = {"expected": expected["expected_post_state"], "actual": actual.post_state}
    return ComparisonResult(matches=not diff, diff=diff)


def compute_branch_hits(known_branches: list, rows: list) -> dict:
    hits = {branch: 0 for branch in known_branches}
    for row in rows:
        if row.branch is not None:
            hits[row.branch] = hits.get(row.branch, 0) + 1
    return hits


def render_test_file(script: Path, rows: list, branch_hits: dict) -> str:
    # Embedded as a JSON *string literal* (parsed via json.loads at
    # import time), not as a raw Python literal — JSON's null/true/
    # false are not valid Python syntax, and repr()-ing the string
    # (rather than f-string-interpolating it raw) lets Python's own
    # escaping handle any quote/backslash in captured stdout/stderr.
    rows_json = repr(json.dumps([asdict(r) for r in rows], indent=4))
    branch_hits_json = repr(json.dumps(branch_hits, indent=4))
    # "# DIVERGENCE: <reason>" (colon immediately after the word) is
    # the exact, grep-able marker AC-23 defines — a future `grep
    # '# DIVERGENCE:'` must find every intentional behavior change,
    # so the row name goes in a trailing parenthetical instead of
    # between DIVERGENCE and the colon.
    divergence_comments = "\n".join(
        f"# DIVERGENCE: {row.divergence} (row: {row.name})"
        for row in rows if row.divergence
    )
    module_dir = Path(__file__).parent
    return f'''# Generated by capture-script-behavior.py — do not hand-edit the
# ROWS/BRANCH_HITS data below; regenerate via `capture` instead.
# Edit SCRIPT_UNDER_TEST to point at a rewrite, then run:
#   pytest --import-mode=importlib <this file>
{divergence_comments}

import importlib.util
import json
import sys
from pathlib import Path

SCRIPT_UNDER_TEST = {str(script)!r}

_HARNESS_PATH = Path({str(module_dir)!r}) / "capture-script-behavior.py"
_spec = importlib.util.spec_from_file_location("capture_script_behavior", _HARNESS_PATH)
_harness = importlib.util.module_from_spec(_spec)
sys.modules["capture_script_behavior"] = _harness
_spec.loader.exec_module(_harness)

ROWS = json.loads({rows_json})

# Branch coverage recorded at capture time — 0 means the branch is
# explicitly unexercised, not silently absent.
BRANCH_HITS = json.loads({branch_hits_json})


def test_replays_every_captured_row():
    import tempfile
    failures = []
    for row_dict in ROWS:
        row = _harness.Row.from_dict(row_dict)
        with tempfile.TemporaryDirectory() as fixture_dir:
            fixture_path = Path(fixture_dir)
            _harness.setup_fixture(fixture_path, row)
            actual = _harness.capture_row(Path(SCRIPT_UNDER_TEST), row, fixture_dir=fixture_path)
            result = _harness.compare_captured(row_dict, actual)
            if not result.matches:
                failures.append((row.name, result.diff))
    assert not failures, failures
'''


def _load_table(path: Path) -> tuple:
    data = json.loads(path.read_text())
    rows = [Row.from_dict(r) for r in data.get("rows", [])]
    known_branches = data.get("known_branches", [])
    return rows, known_branches


def cmd_capture(args) -> int:
    # Resolved to absolute up front: capture_row runs the script
    # with cwd=fixture_dir, so a relative --script path would
    # otherwise be looked up inside the fixture directory instead
    # of from the caller's original working directory.
    script = Path(args.script).resolve()
    table_path = Path(args.table)
    rows, known_branches = _load_table(table_path)

    updated_rows = []
    for row in rows:
        import tempfile
        with tempfile.TemporaryDirectory() as fixture_dir:
            fixture_path = Path(fixture_dir)
            try:
                setup_fixture(fixture_path, row)
            except FixtureEscapeError as exc:
                print(f"error: row {row.name!r}: {exc}", file=sys.stderr)
                return 1
            actual = capture_row(script, row, fixture_dir=fixture_path)

        if row.has_golden():
            expected = asdict(row)
            result = compare_captured(expected, actual)
            if not result.matches:
                if row.divergence:
                    row.expected_stdout = actual.stdout
                    row.expected_stderr = actual.stderr
                    row.expected_exit_code = actual.exit_code
                    row.expected_post_state = actual.post_state
                else:
                    print(
                        f"error: row {row.name!r} diverged from its captured golden "
                        f"and carries no divergence reason — either fix the script "
                        f"under test, or add a `divergence` reason to this row and "
                        f"rerun (it will be recorded in the emitted file as "
                        f"`# DIVERGENCE: <reason>`). diff: {json.dumps(result.diff)}",
                        file=sys.stderr,
                    )
                    return 1
        else:
            row.expected_stdout = actual.stdout
            row.expected_stderr = actual.stderr
            row.expected_exit_code = actual.exit_code
            row.expected_post_state = actual.post_state

        updated_rows.append(row)

    branch_hits = compute_branch_hits(known_branches, updated_rows)

    if args.json_out:
        Path(args.json_out).write_text(json.dumps({
            "known_branches": known_branches,
            "rows": [asdict(r) for r in updated_rows],
            "branch_hits": branch_hits,
        }, indent=2))

    if args.out:
        Path(args.out).write_text(render_test_file(script, updated_rows, branch_hits))

    return 0


def cmd_compare(args) -> int:
    expected = json.loads(Path(args.expected).read_text())
    actual_data = json.loads(Path(args.actual).read_text())
    actual = Captured(
        name=actual_data.get("name", ""),
        branch=actual_data.get("branch"),
        stdout=actual_data.get("stdout", ""),
        stderr=actual_data.get("stderr", ""),
        exit_code=actual_data.get("exit_code", 0),
        post_state=actual_data.get("post_state"),
    )
    result = compare_captured(expected, actual)
    print(json.dumps({"matches": result.matches, "diff": result.diff}))
    return 0 if result.matches else 1


def main(argv) -> int:
    parser = argparse.ArgumentParser(
        description="Capture-and-replay characterization harness for "
                     "shell-to-Python/JS script conversions."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    capture_parser = subparsers.add_parser("capture", help="run a table against a script and record its golden tuple")
    capture_parser.add_argument("--script", required=True)
    capture_parser.add_argument("--table", required=True)
    capture_parser.add_argument("--json-out")
    capture_parser.add_argument("--out")

    compare_parser = subparsers.add_parser("compare", help="masked-compare a captured golden against a fresh actual")
    compare_parser.add_argument("--expected", required=True)
    compare_parser.add_argument("--actual", required=True)

    args = parser.parse_args(argv)
    if args.command == "capture":
        return cmd_capture(args)
    if args.command == "compare":
        return cmd_compare(args)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
