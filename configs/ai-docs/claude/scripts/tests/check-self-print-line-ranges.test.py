"""Blackbox CLI tests for check-self-print-line-ranges.py.

Fixtures: each test builds a throwaway git repo under tmp_path, so
enumeration runs against real git state instead of a mock.

Usage:
  pytest configs/ai-docs/claude/scripts/tests/\
check-self-print-line-ranges.test.py
"""

import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent.parent / "check-self-print-line-ranges.py"

SHEBANG = "#!/usr/bin/env bash\n"

HEADER = "# greet.sh - print a greeting.\n#\n# Usage: greet.sh [--help]\n"

# The robust --help printer create-pr's scripts already ship:
# it prints the whole leading comment block, however long.
AWK_LEADING_BLOCK_USAGE = (
    "usage() { awk 'NR > 1 && /^#/ { sub(/^# ?/, \"\"); print; next }"
    " NR > 1 { exit }' \"$0\"; }\n"
)

CLEAN_SCRIPT = f"{SHEBANG}{HEADER}{AWK_LEADING_BLOCK_USAGE}echo hello\n"


def _git(repo, *args):
    subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _make_repo(tmp_path):
    """Return a fresh git repo holding one committed clean script
    under configs/, so a test only has to add its own case's file."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    _commit(repo, "configs/tools/greet.sh", CLEAN_SCRIPT)
    return repo


def _commit(repo, relpath, content):
    path = repo / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    _git(repo, "add", relpath)
    _git(repo, "commit", "-qm", f"add {relpath}")
    return path


def _script_with_usage_line(usage_line):
    """Return a bash script whose usage() sits on line 5, so a hit
    reports as <path>:5."""
    return f"{SHEBANG}{HEADER}usage() {{ {usage_line}; }}\n"


def _run(repo):
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--repo-root", str(repo)],
        capture_output=True,
        text=True,
    )


class TestFlagsFixedRangeSelfPrinters:
    @pytest.mark.parametrize(
        "usage_line",
        [
            "sed -n '2,14p' \"$0\" | sed 's/^# \\{0,1\\}//'",
            "sed -n '2,14p' $0",
            "sed -n '2,25p' \"${BASH_SOURCE[0]}\" | sed 's/^# //'",
            "sed -n '2,25p' ${BASH_SOURCE[0]}",
        ],
        ids=[
            "sed-quoted-dollar-zero",
            "sed-bare-dollar-zero",
            "sed-quoted-bash-source",
            "sed-bare-bash-source",
        ],
    )
    def test_sed_line_range_over_the_script_itself_is_flagged(
        self, tmp_path, usage_line
    ):
        repo = _make_repo(tmp_path)
        _commit(
            repo,
            "configs/tools/stale-help.sh",
            _script_with_usage_line(usage_line),
        )
        result = _run(repo)

        assert result.returncode == 1
        assert result.stdout.splitlines() == ["configs/tools/stale-help.sh:5"]

    @pytest.mark.parametrize(
        "usage_line",
        [
            "head -n 14 \"$0\"",
            "head -14 \"${BASH_SOURCE[0]}\"",
            "awk 'NR<=14' \"$0\"",
        ],
        ids=["head-n", "head-dash-count", "awk-nr-bound"],
    )
    def test_head_or_awk_line_cap_over_the_script_itself_is_flagged(
        self, tmp_path, usage_line
    ):
        repo = _make_repo(tmp_path)
        _commit(
            repo,
            "configs/tools/stale-help.sh",
            _script_with_usage_line(usage_line),
        )
        result = _run(repo)

        assert result.returncode == 1
        assert result.stdout.splitlines() == ["configs/tools/stale-help.sh:5"]

    def test_bash_shebang_script_without_sh_extension_is_flagged(
        self, tmp_path
    ):
        repo = _make_repo(tmp_path)
        _commit(
            repo,
            "configs/bin/stale-help",
            _script_with_usage_line("sed -n '2,14p' \"$0\""),
        )
        result = _run(repo)

        assert result.returncode == 1
        assert result.stdout.splitlines() == ["configs/bin/stale-help:5"]


class TestLeavesOtherPrintersAlone:
    def test_awk_leading_comment_block_printer_is_not_flagged(self, tmp_path):
        repo = _make_repo(tmp_path)
        result = _run(repo)

        assert result.returncode == 0
        assert result.stdout == ""

    def test_sed_line_range_over_another_file_is_not_flagged(self, tmp_path):
        repo = _make_repo(tmp_path)
        _commit(
            repo,
            "configs/tools/excerpt.sh",
            _script_with_usage_line("sed -n '2,14p' some-other-file"),
        )
        result = _run(repo)

        assert result.returncode == 0
        assert result.stdout == ""

    def test_awk_program_reading_its_record_as_dollar_zero_is_not_flagged(
        self, tmp_path
    ):
        """Inside an awk program $0 is the current record, not the
        script's own path, so a line cap over another file stays
        clean even though the program text mentions $0."""
        repo = _make_repo(tmp_path)
        _commit(
            repo,
            "configs/tools/excerpt.sh",
            _script_with_usage_line("awk 'NR<=14 { print $0 }' notes.txt"),
        )
        result = _run(repo)

        assert result.returncode == 0
        assert result.stdout == ""

    def test_script_outside_configs_is_not_flagged(self, tmp_path):
        repo = _make_repo(tmp_path)
        _commit(
            repo,
            "scratch/stale-help.sh",
            _script_with_usage_line("sed -n '2,14p' \"$0\""),
        )
        result = _run(repo)

        assert result.returncode == 0
        assert result.stdout == ""


REPO_ROOT = Path(__file__).resolve().parents[5]

# The scripts whose --help once printed a fixed line range of
# their own file, each range ending before the header did.
FORMER_FIXED_RANGE_PRINTERS = [
    "code-review-pipeline/scripts/extract-commentable-lines.sh",
    "code-review-pipeline/scripts/extract-skipped-files.sh",
    "code-review-pipeline/scripts/filter-off-diff-findings.sh",
    "code-review-pipeline/scripts/prep-local-context.sh",
    "consistency-check-principles-and-skills/scripts/check-refs.sh",
    "consistency-check-principles-and-skills/scripts/"
    "gen-shard-manifest.sh",
    "consistency-check-principles-and-skills/scripts/verify-quote.sh",
    "english-coach/scripts/extract-user-messages.sh",
    "refactor/scripts/prep-refactor-context.sh",
]

SKILLS_DIR = REPO_ROOT / "configs" / "ai-docs" / "claude" / "skills"


def _last_header_line(script_path):
    """Return the last line of the comment block right under the
    shebang, with its leading "# " stripped - the line a truncated
    --help drops first."""
    lines = script_path.read_text(encoding="utf-8").splitlines()
    last = None
    for line in lines[1:]:
        if not line.startswith("#"):
            break
        last = line
    return last[2:] if last.startswith("# ") else last[1:]


class TestThisRepo:
    def test_this_repo_has_no_fixed_range_self_printers(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--repo-root", str(REPO_ROOT)],
            capture_output=True,
            text=True,
        )

        assert result.stdout == "", result.stdout
        assert result.returncode == 0

    @pytest.mark.parametrize("relpath", FORMER_FIXED_RANGE_PRINTERS)
    def test_help_prints_the_whole_header_through_its_last_line(
        self, relpath
    ):
        script_path = SKILLS_DIR / relpath
        result = subprocess.run(
            ["bash", str(script_path), "--help"],
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
        )

        last_line = _last_header_line(script_path)
        help_text = result.stdout + result.stderr
        assert last_line in help_text, (
            f"--help dropped {last_line!r}; it printed:\n{help_text}"
        )
