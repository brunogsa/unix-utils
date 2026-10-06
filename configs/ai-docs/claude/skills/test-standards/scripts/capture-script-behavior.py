#!/usr/bin/env python3
# capture-script-behavior.py - Capture-and-replay
# characterization harness.
#
# Run a table of input rows against a script, record its full
# (stdout, stderr, exit code, fixture post-state) tuple as
# golden, and emit a <stem>.test.py that replays the same table
# against a rewrite to prove behavioral equivalence.
#
# Usage:
#   capture-script-behavior.py capture --script PATH
#     --table TABLE.json [--json-out CAPTURED.json]
#     [--out STEM.test.py]
#
#   capture-script-behavior.py compare --expected EXPECTED.json
#     --actual ACTUAL.json
#
# stdin: none
# stdout: `compare` prints one JSON result object;
# `capture` prints
#   nothing on success (its output is --json-out / --out)
#
# exit: 0 on success; 1 on a row that fails without an
#   accepted divergence marker, a fixture-escape attempt,
#   or a bad invocation

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path, PurePosixPath
from typing import Callable, NamedTuple

# Shared, declared mask set - the ONLY place non-deterministic
# values get normalized.
#
# Both capture (before hashing fixture content) and compare
# (before comparing stdout/stderr) route through mask_text, so a
# script never needs its own private mask.
MASK_PATTERNS = (
    (re.compile(r"\b\d+(\.\d+)?s\b"), "<DURATION>"),
    (re.compile(r"\bpid[= ]\d+\b", re.IGNORECASE), "pid=<PID>"),
    (re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.IGNORECASE), "<UUID>"),

    # Both temp-dir patterns consume the rest of the path, so
    # macOS (/var/folders, or /private/var/folders once resolved
    # by `pwd -P`) and Linux (Python tempfile or GNU mktemp,
    # whose names carry a dot) mask to the same <TMPDIR>.
    (re.compile(r"/tmp/tmp[A-Za-z0-9_.][A-Za-z0-9_./-]{3,}"), "<TMPDIR>"),
    (re.compile(r"(?:/private)?/var/folders/[A-Za-z0-9_./-]+"), "<TMPDIR>"),
)

# The fixture dir differs every run, so a row's env value keeps
# this token in the table, --json-out and the emitted test.
#
# It becomes the real path only when the row runs, and mask_text
# turns that path back into the token in captured output.
FIXTURE_DIR_TOKEN = "<FIXTURE_DIR>"

# A fixture_files key that resolves outside its own fixture
# directory is the exact escape the Threat Model warns about - a
# capture must never be allowed to write into the real repo.
FIXTURE_ESCAPE_MARKERS = ("..",)

# Skipped when hashing: its contents (e.g. .git/index) differ
# run to run, and the row's git status is captured separately.
GIT_DIR_NAME = ".git"

# Generous for a real script row; a hung row would otherwise
# block the capture, and every replay, forever.
ROW_TIMEOUT_SECONDS = 60


class RowError(Exception):
    """Base of every error caused by one table row. The CLI catches
    only this, so a malformed table's JSONDecodeError (also a
    ValueError) is never mistaken for a bad row.

    `row` is the label the CLI prints: a quoted name, or `#<index>`
    for a row without one. A raiser that cannot know it leaves it
    None and the caller that can fills it in."""

    def __init__(self, reason: str, *, row: str | None = None):
        super().__init__(reason)
        self.reason = reason
        self.row = row

    def __str__(self) -> str:
        return self.reason if self.row is None else f"row {self.row}: {self.reason}"


class InvalidRowError(RowError, ValueError):
    """Raised when a row's own data is malformed."""


class FixtureEscapeError(RowError, ValueError):
    """Raised when a row's fixture_files key would write outside its
    isolated fixture directory."""


class TableError(ValueError):
    """Raised when the table itself is malformed, a fault about no
    single row. Kept apart from RowError because it names the table
    file, not a row. The CLI catches it by name, never a bare
    ValueError, so a JSONDecodeError still surfaces."""

    def __init__(self, table: Path, reason: str):
        super().__init__(reason)
        self.table = table
        self.reason = reason

    def __str__(self) -> str:
        return f"table {self.table}: {self.reason}"


class RowTimeoutError(RowError, RuntimeError):
    """Raised when a row's script outlives its timeout."""


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
    env: dict | None = None
    executable_files: list = field(default_factory=list)
    script_relpath: str | None = None

    @classmethod
    def from_dict(cls, data: dict) -> "Row":
        # Dropping an unknown key silently would capture a
        # typo'd row (`expected_stdut`) without its intended
        # data and still exit 0.
        if "name" not in data:
            raise InvalidRowError("missing required key 'name'")
        unknown = [key for key in data if key not in cls.__dataclass_fields__]
        if unknown:
            listed = ", ".join(repr(key) for key in unknown)
            raise InvalidRowError(f"unknown key(s) {listed}")
        _validate_field_types(data)
        _validate_env(data.get("env"))
        _validate_executable_files(data.get("executable_files", []), data.get("fixture_files"))
        for key in data.get("fixture_files") or {}:
            _validate_fixture_key(key)
        _validate_script_relpath(data.get("script_relpath"), data.get("fixture_files"))
        return cls(**data)

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
    KNOW is unique per run - the generic patterns below only catch
    the common shapes, not every OS's real temp-dir layout."""
    if fixture_dir is not None:
        # Longest-first: the resolved path (e.g. macOS's
        # /private/var/... symlink target) contains the raw path
        # as a substring.
        #
        # So replacing the raw form first would strand the
        # "/private" prefix un-masked instead of consuming the
        # whole resolved match.
        #
        # A plain set() has no ordering guarantee, which made
        # this fail non-deterministically depending on
        # PYTHONHASHSEED.
        candidates = sorted({str(fixture_dir), str(fixture_dir.resolve())}, key=len, reverse=True)
        for candidate in candidates:
            if candidate:
                text = text.replace(candidate, FIXTURE_DIR_TOKEN)
    for pattern, replacement in MASK_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def _is_string_or_null(value) -> bool:
    return value is None or isinstance(value, str)


def _is_string(value) -> bool:
    return isinstance(value, str)


def _is_list(value) -> bool:
    return isinstance(value, list)


def _is_object(value) -> bool:
    return isinstance(value, dict)


def _is_integer_or_null(value) -> bool:
    # A Python bool is an int, but JSON true is not an exit
    # code.
    return value is None or (isinstance(value, int) and not isinstance(value, bool))


def _is_object_or_null(value) -> bool:
    return value is None or isinstance(value, dict)


class FieldType(NamedTuple):
    """What one Row field accepts, as the error message words it
    and as a check. An array or object field also says what each
    entry accepts, so a bad entry is named on its own."""

    accepted: str
    is_accepted: Callable
    entry_accepted: str | None = None
    is_entry_accepted: Callable | None = None


# One entry per Row field.
# A test fails when a Row field has no entry, so a field added
# later cannot skip the type check.
ROW_FIELD_TYPES = {
    "name": FieldType("a string", _is_string),
    "argv": FieldType("an array of strings", _is_list, "a string", _is_string),
    "stdin": FieldType("a string", _is_string),
    "branch": FieldType("a string or null", _is_string_or_null),
    "fixture_files": FieldType("an object whose values are strings", _is_object, "a string", _is_string),
    "git_init": FieldType("a boolean", lambda value: isinstance(value, bool)),
    "divergence": FieldType("a string or null", _is_string_or_null),
    "expected_stdout": FieldType("a string or null", _is_string_or_null),
    "expected_stderr": FieldType("a string or null", _is_string_or_null),
    "expected_exit_code": FieldType("an integer or null", _is_integer_or_null),
    "expected_post_state": FieldType("an object or null", _is_object_or_null),
    "env": FieldType("an object or null", _is_object_or_null, "a string or null", _is_string_or_null),
    "executable_files": FieldType("an array of strings", _is_list, "a string", _is_string),
    "script_relpath": FieldType("a string or null", _is_string_or_null),
}


def _entries(value) -> list:
    """(label suffix, entry) pairs of an array or object value."""
    if isinstance(value, list):
        return [(f"[{index}]", entry) for index, entry in enumerate(value)]
    return [(f"[{key!r}]", entry) for key, entry in value.items()]


def _validate_field_types(data: dict) -> None:
    for field_name, value in data.items():
        field_type = ROW_FIELD_TYPES[field_name]
        if not field_type.is_accepted(value):
            raise InvalidRowError(f"{field_name} must be {field_type.accepted}, got {_json_type_name(value)}")
        if field_type.is_entry_accepted is None or value is None:
            continue
        for suffix, entry in _entries(value):
            if not field_type.is_entry_accepted(entry):
                raise InvalidRowError(
                    f"{field_name}{suffix} must be {field_type.entry_accepted}, got {_json_type_name(entry)}"
                )


def _validate_env(env) -> None:
    if env is None:
        return
    if not isinstance(env, dict):
        raise InvalidRowError(f"env must be an object mapping variable names to strings or null, got {env!r}")


def _build_env(row: Row, *, fixture_dir: Path) -> dict | None:
    """The full environment for a row's run, or None to inherit.
    subprocess.run(env=...) replaces the environment instead of
    merging, so the row's entries are layered on os.environ here."""
    if row.env is None:
        return None
    merged = dict(os.environ)
    for variable, value in row.env.items():
        if value is None:
            merged.pop(variable, None)
        else:
            merged[variable] = value.replace(FIXTURE_DIR_TOKEN, str(fixture_dir))
    return merged


def _validate_executable_files(executable_files, fixture_files) -> None:
    if not isinstance(executable_files, list):
        raise InvalidRowError(f"executable_files must be a list of fixture_files keys, got {executable_files!r}")
    for key in executable_files:
        if key not in (fixture_files or {}):
            raise InvalidRowError(f"executable_files entry {key!r} is not a key of fixture_files")


def _validate_script_relpath(script_relpath, fixture_files) -> None:
    if script_relpath is None:
        return
    if not isinstance(script_relpath, str) or not script_relpath:
        raise InvalidRowError(f"script_relpath must be a non-empty string, got {script_relpath!r}")
    script_path = Path(script_relpath)
    if script_path.is_absolute() or any(marker in script_path.parts for marker in FIXTURE_ESCAPE_MARKERS):
        raise InvalidRowError(
            f"script_relpath {script_relpath!r} escapes the fixture directory "
            "(absolute paths and '..' segments are rejected)"
        )
    _validate_path_form(script_relpath, field_name="script_relpath")
    for key in fixture_files or {}:
        key_path = Path(key)
        if key_path == script_path or key_path in script_path.parents or script_path in key_path.parents:
            raise InvalidRowError(
                f"script_relpath {script_relpath!r} collides with fixture_files key {key!r}: "
                "the same path, or one inside the other"
            )


def _validate_path_form(path: str, *, field_name: str) -> None:
    """One rule for a fixture key and script_relpath, so the two
    cannot drift: a path must name one file in normal form. A
    spelling like './a' or 'a/' reaches the same file but would
    not match the path string compared elsewhere, and '' or '.'
    names the fixture directory itself."""
    if "\0" in path or PurePosixPath(path).as_posix() != path or path == ".":
        raise InvalidRowError(
            f"{field_name} {path!r} is not a normalized relative file path "
            "(no empty path, '.', './' prefix, trailing or doubled '/', or NUL byte)"
        )


def _validate_fixture_key(key: str) -> None:
    if Path(key).is_absolute() or any(marker in Path(key).parts for marker in FIXTURE_ESCAPE_MARKERS):
        raise FixtureEscapeError(
            f"fixture_files key {key!r} escapes its fixture directory "
            "(absolute paths and '..' segments are rejected before the "
            "script ever runs)"
        )
    _validate_path_form(key, field_name="fixture_files key")


def hash_fixture_tree(root: Path, *, fixture_dir: Path, skip_relpath: str | None = None) -> dict:
    """Recursively hash every file under `root` (masking content
    first) into a {relpath: sha256} map - the post-state half of the
    captured tuple. `skip_relpath` leaves one file out."""
    tree = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if path.is_file() and relative.parts[0] != GIT_DIR_NAME and relative.as_posix() != skip_relpath:
            relpath = relative.as_posix()
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
        if key in row.executable_files:
            target.chmod(0o755)
    if row.git_init:
        subprocess.run(["git", "init", "-q"], cwd=fixture_dir, capture_output=True)
        subprocess.run(["git", "add", "-A"], cwd=fixture_dir, capture_output=True)


def _place_script_in_fixture(script: Path, row: Row, *, fixture_dir: Path) -> str:
    """Copy `script` to row.script_relpath and return the program
    to run. A copy, not a symlink: Path.resolve() and readlink -f
    follow a symlink back into the repo. The './' prefix keeps
    $0 free of any temp path."""
    relpath = str(row.script_relpath)
    destination = fixture_dir / relpath
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(script, destination)
    if row.git_init:
        subprocess.run(["git", "add", "--", relpath], cwd=fixture_dir, capture_output=True)
    return f"./{relpath}"


def capture_row(
    script: Path, row: Row, *, fixture_dir: Path, timeout_seconds: float = ROW_TIMEOUT_SECONDS,
) -> Captured:
    """Run one table row against `script` inside its own, already-
    prepared fixture_dir and return the full captured tuple. A run
    past `timeout_seconds` raises RowTimeoutError rather than
    recording a golden from a killed process."""
    program = str(script)
    if row.script_relpath is not None:
        program = _place_script_in_fixture(script, row, fixture_dir=fixture_dir)
    try:
        result = subprocess.run(
            [program, *row.argv],
            cwd=fixture_dir, input=row.stdin, env=_build_env(row, fixture_dir=fixture_dir),
            capture_output=True, text=True, timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise RowTimeoutError(
            f"ran past {timeout_seconds}s and was killed; "
            "no golden is recorded from a killed run",
            row=repr(row.name),
        ) from exc
    post_state = {
        # The copy is not hashed: the original script and its
        # rewrite differ in content by design, so hashing it
        # would fail every replay.
        "tree": hash_fixture_tree(fixture_dir, fixture_dir=fixture_dir, skip_relpath=row.script_relpath),
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
    a fresh Captured tuple - stdout, stderr, exit_code AND
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


def render_test_file(script: Path, rows: list, branch_hits: dict, out_path: Path | None = None) -> str:
    # Embedded as a JSON *string literal* (parsed via json.loads
    # at import time), not as a raw Python literal - JSON's
    # null/true/false are not valid Python syntax.
    #
    # Repr()-ing the string (rather than f-string-interpolating
    # it raw) lets Python's own escaping handle any
    # quote/backslash in captured stdout/stderr.
    rows_json = repr(json.dumps([asdict(r) for r in rows], indent=4))
    branch_hits_json = repr(json.dumps(branch_hits, indent=4))

    # "# DIVERGENCE: <reason>" (colon immediately after the
    # word) is the exact, grep-able marker AC-23 defines - a
    # future `grep '# DIVERGENCE:'` must find every intentional
    # behavior change.
    #
    # The row name goes in a trailing parenthetical instead
    # of between DIVERGENCE and the colon.
    divergence_comments = "\n".join(
        f"# DIVERGENCE: {row.divergence} (row: {row.name})"
        for row in rows if row.divergence
    )
    module_dir = Path(__file__).parent

    # A committed <stem>.test.py is cloned onto machines other
    # than the one that ran `capture` (CLAUDE.md's
    # cross-platform MUST), so neither path below may be the
    # absolute string captured here.
    #
    # When out_path is known, embed each as a path relative to
    # the emitted file's own directory, reconstructed at import
    # time from that file's __file__.
    #
    # The offset between the test file and script (or harness)
    # is fixed by the repo's own layout and survives the repo
    # being cloned anywhere.
    #
    # Without an out_path (no destination file exists to anchor
    # against), fall back to the absolute path captured here.
    if out_path is not None:
        anchor = out_path.resolve().parent
        script_repr = f'(Path(__file__).resolve().parent / {os.path.relpath(script.resolve(), anchor)!r}).resolve()'
        harness_repr = f'(Path(__file__).resolve().parent / {os.path.relpath(module_dir.resolve(), anchor)!r}).resolve() / "capture-script-behavior.py"'
    else:
        script_repr = f'Path({str(script)!r})'
        harness_repr = f'Path({str(module_dir)!r}) / "capture-script-behavior.py"'
    return f'''# Generated by capture-script-behavior.py - do not hand-edit the
# ROWS/BRANCH_HITS data below; regenerate via `capture` instead.
# Edit SCRIPT_UNDER_TEST to point at a rewrite, then run:
#   pytest --import-mode=importlib <this file>
{divergence_comments}

import importlib.util
import json
import sys
from pathlib import Path

SCRIPT_UNDER_TEST = str({script_repr})

_HARNESS_PATH = {harness_repr}
if not _HARNESS_PATH.is_file():
    raise ImportError(
        f"capture-script-behavior.py harness not found at {{_HARNESS_PATH}}"
        f" - this generated test locates the harness relative to its own"
        f" path, so relocating either file breaks the link."
    )
_spec = importlib.util.spec_from_file_location("capture_script_behavior", _HARNESS_PATH)
if _spec is None or _spec.loader is None:
    raise ImportError(f"no import spec for the harness at {{_HARNESS_PATH}}")
_harness = importlib.util.module_from_spec(_spec)
sys.modules["capture_script_behavior"] = _harness
_spec.loader.exec_module(_harness)

ROWS = json.loads({rows_json})

# Branch coverage recorded at capture time - 0 means the branch is
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


def _json_type_name(value) -> str:
    """The JSON name of `value`'s type, for an error message."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    return "object"


def _load_table(path: Path) -> tuple:
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise TableError(path, f"the top level must be an object, got {_json_type_name(data)}")
    row_dicts = data.get("rows", [])
    if not isinstance(row_dicts, list):
        raise TableError(path, f"rows must be an array, got {_json_type_name(row_dicts)}")
    known_branches = data.get("known_branches", [])
    if not isinstance(known_branches, list) or not all(isinstance(branch, str) for branch in known_branches):
        raise TableError(path, "known_branches must be an array of strings")
    rows = []
    for index, row_dict in enumerate(row_dicts):
        try:
            if not isinstance(row_dict, dict):
                raise InvalidRowError(f"a row must be an object, got {_json_type_name(row_dict)}")
            rows.append(Row.from_dict(row_dict))
        except RowError as exc:
            # from_dict cannot know the row's table position.
            is_named = isinstance(row_dict, dict) and isinstance(row_dict.get("name"), str)
            exc.row = repr(row_dict["name"]) if is_named else f"#{index}"
            raise
    return rows, known_branches


def _report_row_error(exc: RowError, *, row_label: str) -> int:
    if exc.row is None:
        exc.row = row_label
    print(f"error: {exc}", file=sys.stderr)
    return 1


def _report_table_error(exc: "TableError") -> int:
    print(f"error: {exc}", file=sys.stderr)
    return 1


def cmd_capture(args) -> int:
    # Resolved to absolute up front: capture_row runs the script
    # with cwd=fixture_dir, so a relative --script path would
    # otherwise be looked up inside the fixture directory
    # instead of from the caller's original working directory.
    script = Path(args.script).resolve()
    table_path = Path(args.table)
    try:
        rows, known_branches = _load_table(table_path)
    except RowError as exc:
        return _report_row_error(exc, row_label="")
    except TableError as exc:
        return _report_table_error(exc)

    updated_rows = []
    for row in rows:
        import tempfile
        with tempfile.TemporaryDirectory() as fixture_dir:
            fixture_path = Path(fixture_dir)
            try:
                setup_fixture(fixture_path, row)
                actual = capture_row(script, row, fixture_dir=fixture_path)
            except RowError as exc:
                return _report_row_error(exc, row_label=repr(row.name))

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
                        f"and carries no divergence reason - either fix the script "
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
        out_path = Path(args.out)
        out_path.write_text(render_test_file(script, updated_rows, branch_hits, out_path=out_path))

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
