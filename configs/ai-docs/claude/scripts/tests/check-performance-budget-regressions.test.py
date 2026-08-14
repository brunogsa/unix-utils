"""Blackbox CLI tests for check-performance-budget-regressions.py.

Fixtures: each hermetic test writes its own report and its own baseline
under tmp_path and passes both by flag, so the parser is exercised
against literal check.sh output shapes without running check.sh.

The two closing tests deliberately do run the real check.sh against the
repo source and the committed baseline — that end-to-end pair is what
proves the gate is wired to something, not parsing an empty report.

Usage:
  pytest configs/ai-docs/claude/scripts/tests/\
check-performance-budget-regressions.test.py
"""

import subprocess
import sys
import warnings
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "check-performance-budget-regressions.py"

BASELINE = Path(__file__).parent.parent / "performance-budget-baseline.txt"

# The four-column status table check.sh opens its report with.
# Its measured column is named "Measured".
STATUS_TABLE_HEADER = "| Target | Measured | Budget | Status |\n|---|---|---|---|\n"

# The five-column per-skill table, whose measured column
# is named "Ratio" and sits three cells right of the label.
CRITICAL_RATIO_TABLE = (
    "## *-standards CRITICAL ratio per skill\n"
    "\n"
    "| Skill | [Instruction] | CRITICAL | Ratio | Status |\n"
    "|---|---|---|---|---|\n"
    "| doc-standards | 31 | 8 | 25% | OVER |\n"
)

BUNDLED_HEADING = "## Bundled resources failing size or heading checks\n\n"


def _report(tmp_path, body):
    path = tmp_path / "report.md"
    path.write_text(
        f"# Performance Check — repo (configs/ai-docs/claude)\n\n{body}",
        encoding="utf-8",
    )
    return path


def _baseline(tmp_path, *entries):
    path = tmp_path / "baseline.txt"
    path.write_text("".join(f"{e}\n" for e in entries), encoding="utf-8")
    return path


def _run(report, baseline):
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--report",
            str(report),
            "--baseline",
            str(baseline),
        ],
        capture_output=True,
        text=True,
    )


def test_a_budget_overage_absent_from_the_baseline_fails_the_gate(tmp_path):
    """The bleeding-stops case: a file that has just crossed a bundled
    size cap is nowhere in the baseline, so it is new debt."""
    report = _report(
        tmp_path,
        BUNDLED_HEADING + "- implement/references/batch-end-pr.md: words=1036(>1024)\n",
    )
    result = _run(report, _baseline(tmp_path))

    assert result.returncode == 1
    assert "batch-end-pr.md" in result.stdout


def test_an_overage_that_grew_past_its_baseline_value_fails_the_gate(tmp_path):
    """Grandfathering a budget must not grandfather unlimited growth in
    it — an already-over count going further over is still a regression."""
    report = _report(
        tmp_path,
        STATUS_TABLE_HEADER + "| CLAUDE.md [Instruction] count | 104 | 100 | OVER |\n",
    )
    baseline = _baseline(
        tmp_path, "Budgets :: CLAUDE.md [Instruction] count :: measured = 103"
    )
    result = _run(report, baseline)

    assert result.returncode == 1
    assert "104" in result.stdout


def test_an_overage_holding_at_its_baseline_value_leaves_the_gate_green(tmp_path):
    report = _report(
        tmp_path,
        STATUS_TABLE_HEADER + "| CLAUDE.md [Instruction] count | 103 | 100 | OVER |\n",
    )
    baseline = _baseline(
        tmp_path, "Budgets :: CLAUDE.md [Instruction] count :: measured = 103"
    )
    result = _run(report, baseline)

    assert result.returncode == 0, result.stdout


def test_a_critical_ratio_row_is_gated_on_its_ratio_not_its_instruction_count(tmp_path):
    """The per-skill table puts three numbers on every row, and only the
    ratio is the measurement its OVER status refers to. Reading the
    leftmost number instead would compare an instruction count against a
    percentage and fail a row that has not moved."""
    report = _report(tmp_path, CRITICAL_RATIO_TABLE)
    baseline = _baseline(
        tmp_path, "*-standards CRITICAL ratio per skill :: doc-standards :: ratio = 25"
    )
    result = _run(report, baseline)

    assert result.returncode == 0, result.stdout


def test_an_overage_measured_below_its_baseline_asks_for_a_tighter_baseline(tmp_path):
    """Draining debt has to be the direction the gate pushes, or the
    baseline becomes a place overages retire to."""
    report = _report(
        tmp_path,
        STATUS_TABLE_HEADER + "| CLAUDE.md [Instruction] count | 101 | 100 | OVER |\n",
    )
    baseline = _baseline(
        tmp_path, "Budgets :: CLAUDE.md [Instruction] count :: measured = 103"
    )
    result = _run(report, baseline)

    assert result.returncode == 0, result.stdout
    assert "tighten" in result.stdout.lower()
    assert "101" in result.stdout


def test_a_baselined_overage_that_no_longer_appears_is_reported_resolved(tmp_path):
    """A budget brought back under its cap drops out of check.sh's report
    entirely, so its stale baseline entry has to be called out by absence
    rather than by a smaller number."""
    report = _report(
        tmp_path,
        STATUS_TABLE_HEADER + "| CLAUDE.md [Instruction] count | 99 | 100 | OK |\n",
    )
    baseline = _baseline(
        tmp_path, "Budgets :: CLAUDE.md [Instruction] count :: measured = 103"
    )
    result = _run(report, baseline)

    assert result.returncode == 0, result.stdout
    assert "resolved" in result.stdout.lower()


def test_missing_baseline_file_is_a_usage_error(tmp_path):
    """Exit 2, never a silent pass: a typo'd or deleted baseline must not
    read as 'nothing is grandfathered, every budget is met'."""
    report = _report(tmp_path, STATUS_TABLE_HEADER)
    result = _run(report, tmp_path / "does-not-exist.txt")

    assert result.returncode == 2
    assert "does-not-exist.txt" in result.stderr


def test_malformed_baseline_entry_is_a_usage_error(tmp_path):
    """An entry with no measured value cannot be compared against
    anything, so treating it as absent would silently un-grandfather the
    budget it was written to cover."""
    report = _report(tmp_path, STATUS_TABLE_HEADER)
    baseline = _baseline(tmp_path, "Budgets :: CLAUDE.md [Instruction] count")
    result = _run(report, baseline)

    assert result.returncode == 2
    assert "CLAUDE.md [Instruction] count" in result.stderr


def test_this_repo_has_no_budget_regressions():
    """The gate run for real, against the repo source and the committed
    baseline. Improvements are surfaced as a warning rather than a
    failure: four sessions share this working tree, and a hard failure
    the moment anyone trims a word would red their harness for work that
    went the right way."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT)], capture_output=True, text=True
    )

    if "tighten" in result.stdout.lower():
        warnings.warn(
            "performance budgets improved — tighten "
            f"{BASELINE.name}:\n{result.stdout}",
            stacklevel=1,
        )

    assert result.returncode == 0, result.stdout + result.stderr


def test_a_worsened_repo_measurement_fails_the_real_gate(tmp_path):
    """The anti-vacuity check. A baseline that recorded nothing, or a
    check.sh that never ran, would leave the previous test passing on an
    empty report — so shave one off a real entry and require the real
    run to catch it."""
    entries = [
        line
        for line in BASELINE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    assert entries, "baseline records no overage, so the gate guards nothing"

    key, _, value = entries[0].rpartition(" = ")
    tampered = _baseline(tmp_path, f"{key} = {int(value) - 1}", *entries[1:])
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--baseline", str(tampered)],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1, result.stdout + result.stderr
