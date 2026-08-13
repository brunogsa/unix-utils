"""Blackbox CLI tests for check-comment-format-regressions.py.

Fixtures: each test builds a throwaway git repo under tmp_path and
writes its own baseline file, so enumeration runs against real git
state instead of a mock, and no test reads the repo's own baseline.

Usage:
  pytest configs/ai-docs/claude/scripts/tests/\
check-comment-format-regressions.test.py
"""

import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent.parent / "check-comment-format-regressions.py"

BASELINE = Path(__file__).parent.parent / "comment-format-baseline.txt"

# unix-utils repo root: this test file's own checkout,
# five levels above scripts/tests/.
REPO_ROOT = Path(__file__).resolve().parents[5]

TYPESCRIPT = (
    REPO_ROOT
    / "configs/ai-docs/claude/skills/doc-standards/scripts"
    / "node_modules/typescript"
)

# A comment line wider than the checker's 64-char WIDTH
# limit, so any file carrying it violates for one reason.
OVERWIDE_COMMENT = (
    "# this single comment line is deliberately far wider than the "
    "checker's sixty-four character limit\n"
)

CLEAN_SCRIPT = "#!/usr/bin/env bash\n# short comment, well under the limit\necho ok\n"


def _git(repo, *args):
    subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _make_repo(tmp_path):
    """Return a fresh git repo with one committed clean shell script,
    so a test only has to add whatever file its own case is about."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "clean.sh").write_text(CLEAN_SCRIPT, encoding="utf-8")
    _git(repo, "add", "clean.sh")
    _git(repo, "commit", "-qm", "seed")
    return repo


def _commit(repo, relpath, content):
    path = repo / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    _git(repo, "add", relpath)
    _git(repo, "commit", "-qm", f"add {relpath}")
    return path


def _baseline(tmp_path, *relpaths):
    path = tmp_path / "baseline.txt"
    path.write_text("".join(f"{p}\n" for p in relpaths), encoding="utf-8")
    return path


def _run(repo, baseline):
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(repo),
            "--baseline",
            str(baseline),
        ],
        capture_output=True,
        text=True,
    )


def test_violation_in_a_file_outside_the_baseline_fails_the_gate(tmp_path):
    repo = _make_repo(tmp_path)
    _commit(repo, "regressed.sh", f"#!/usr/bin/env bash\n{OVERWIDE_COMMENT}")
    result = _run(repo, _baseline(tmp_path))

    assert result.returncode == 1
    assert "regressed.sh" in result.stdout


def test_violation_in_a_baselined_file_leaves_the_gate_green(tmp_path):
    repo = _make_repo(tmp_path)
    _commit(repo, "legacy.sh", f"#!/usr/bin/env bash\n{OVERWIDE_COMMENT}")
    result = _run(repo, _baseline(tmp_path, "legacy.sh"))

    assert result.returncode == 0


def test_untracked_new_file_is_scanned_by_the_gate(tmp_path):
    """A brand-new file is where a regression most often arrives, and
    it is untracked right up to the commit that ships it — so leaving
    untracked files out of enumeration would blind the gate exactly
    when it matters most."""
    repo = _make_repo(tmp_path)
    (repo / "arrival.sh").write_text(
        f"#!/usr/bin/env bash\n{OVERWIDE_COMMENT}", encoding="utf-8"
    )
    result = _run(repo, _baseline(tmp_path))

    assert result.returncode == 1
    assert "arrival.sh" in result.stdout


def test_missing_baseline_file_is_a_usage_error(tmp_path):
    """Exit 2, never a silent pass: a typo'd or deleted baseline must
    not read as 'nothing is grandfathered, everything is clean'."""
    repo = _make_repo(tmp_path)
    result = _run(repo, tmp_path / "does-not-exist.txt")

    assert result.returncode == 2
    assert "does-not-exist.txt" in result.stderr


def test_stale_baseline_entry_does_not_break_the_gate(tmp_path):
    """An entry for a path that no longer exists is the expected
    residue of someone deleting a grandfathered file, so it must be
    inert rather than a crash or a false failure."""
    repo = _make_repo(tmp_path)
    result = _run(repo, _baseline(tmp_path, "deleted-long-ago.sh"))

    assert result.returncode == 0


def test_baseline_comment_lines_are_not_read_as_paths(tmp_path):
    """The baseline has to carry its own prune-only instructions, or
    the next maintainer treats it as an append-anything allowlist —
    so a leading-# line must document, never grandfather."""
    repo = _make_repo(tmp_path)
    _commit(repo, "regressed.sh", f"#!/usr/bin/env bash\n{OVERWIDE_COMMENT}")
    baseline = tmp_path / "baseline.txt"
    baseline.write_text(
        "# regressed.sh\n# prune entries, never add them\n", encoding="utf-8"
    )
    result = _run(repo, baseline)

    assert result.returncode == 1


def test_tracked_file_deleted_from_the_worktree_is_skipped(tmp_path):
    """git still lists a deleted-but-not-yet-committed file as tracked,
    and handing that path to the checker makes it exit 2 — an
    environment error dressed up as a violation. Mid-deletion is a
    normal working-tree state, so it must stay green."""
    repo = _make_repo(tmp_path)
    (repo / "clean.sh").unlink()
    result = _run(repo, _baseline(tmp_path))

    assert result.returncode == 0


@pytest.mark.skipif(
    not TYPESCRIPT.is_dir(),
    reason="check-comment-format.js needs typescript for .js/.ts files; "
    "run install.sh to bootstrap it",
)
def test_this_repo_passes_its_own_comment_format_gate():
    """The gate run for real. The scan-set assertion is the load-
    bearing half: without it, a baseline that swallowed every file
    would still exit 0 and look like a passing gate."""
    listed = subprocess.run(
        [
            "git",
            "-C",
            str(REPO_ROOT),
            "ls-files",
            "-z",
            "--cached",
            "--others",
            "--exclude-standard",
            "--",
            "*.py",
            "*.sh",
            "*.js",
            "*.ts",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    enumerated = {p for p in listed.stdout.split("\0") if p}
    grandfathered = {
        line.strip()
        for line in BASELINE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    }
    assert enumerated - grandfathered, "baseline swallowed every source file"

    result = subprocess.run(
        [sys.executable, str(SCRIPT)], capture_output=True, text=True
    )

    assert result.returncode == 0, result.stdout
