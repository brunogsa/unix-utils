"""Prove every `test-*.sh` harness row in conversion-verdicts.md's
`unix-utils` table carries an unmissable per-row fate — delete alongside
its subject's conversion, or port its cases to a pytest suite when the
subject stays `.sh` — instead of the bare `convert`/`stays-sh` verdict a
table reader could misread as "convert the harness itself".

This is a doc-content contract test, not a behavior test: the "system
under test" is a markdown table, so assertions parse that table directly
rather than exercising a function. See
`configs/ai-docs/claude/skills/code-standards/references/conversion-verdicts.md`
and `spec_script-overhaul.md` (AC covering harness disposition) for the
rule this table must not contradict.

Usage:
  pytest configs/ai-docs/claude/skills/code-standards/scripts/tests/conversion-verdicts-harness-fate.test.py
"""

import re
import unittest
from pathlib import Path
from dataclasses import dataclass

REPO_ROOT = Path(__file__).resolve().parents[7]
VERDICTS_MD = (
    REPO_ROOT
    / "configs/ai-docs/claude/skills/code-standards/references"
    / "conversion-verdicts.md"
)

# A path counts as a harness when its final path component is a
# `test-*.sh` file, wherever it sits in the tree (leading directory
# is optional so a harness at repo root would still match).
HARNESS_PATH_RE = re.compile(r"(^|/)test-[\w.-]+\.sh$")

# The classifier's own vocabulary. A verdict cell outside this set
# means either a typo or a hand-rewrite of tool-emitted output (the
# provenance regression the file's own opening sentence forbids).
ALLOWED_VERDICTS = {"convert", "stays-sh", "excluded"}

# Plausibility band for the harness-row count: 41 rows measured by
# hand (38 convert + 3 stays-sh verdicts), with slack for the table
# gaining or losing a handful of rows before this band goes stale.
MIN_PLAUSIBLE_HARNESS_ROWS = 30
MAX_PLAUSIBLE_HARNESS_ROWS = 55

# Plausibility band for the non-harness counter-case scan (98 total
# unix-utils rows minus ~41 harness rows).
MIN_PLAUSIBLE_NON_HARNESS_ROWS = 40

# Three harnesses whose OWN verdict is `stays-sh` but whose subject
# script converts — pinned so a future edit can't slide these back
# to "port to pytest" by trusting the harness's own row instead of
# its subject's.
TRAP_STAYS_SH_HARNESS_PATHS_WHOSE_SUBJECT_CONVERTS = [
    "configs/ai-docs/claude/skills/implement/scripts/tests/test-get-pr-tasks.sh",
    "configs/ai-docs/claude/skills/implement/scripts/tests/test-need-git-checkout.sh",
    "configs/ai-docs/claude/skills/spec-driven-development/scripts/tests/test-check-open-questions.sh",
]

# The five harnesses whose subject stays `.sh` (four single-subject
# harnesses plus the one harness with no single subject script,
# which still has nothing to converge with and so still ports).
PORT_TO_PYTEST_HARNESS_PATHS = [
    "configs/ai-docs/claude/hooks/tests/test-claude-git-guard.sh",
    "configs/ai-docs/claude/hooks/tests/test-claude-rm-guard.sh",
    "configs/ai-docs/claude/scripts/tests/test-resolve-base-ref.sh",
    "configs/ai-docs/claude/skills/consistency-check-principles-and-skills"
    "/scripts/tests/test-verify-quote.sh",
    "configs/ai-docs/claude/tests/test-global-config-invariants.sh",
]


@dataclass
class Row:
    path: str
    verdict: str
    fate: str


def _read_section_rows(heading_pattern):
    """Return every `| \\`path\\` | verdict | ... |` data row inside the
    section that starts at the first line matching `heading_pattern`
    and ends at the next top-level `## ` heading (or end of file).
    Only rows whose first cell is a backtick-quoted path are kept —
    this excludes the file's other tables (Summary, Review-cap check)
    which share the `## ` heading level but describe repos/tasks, not
    individual scripts."""
    text = VERDICTS_MD.read_text()

    heading_match = re.search(heading_pattern, text, re.MULTILINE)
    if heading_match is None:
        raise AssertionError(
            f"{VERDICTS_MD} has no heading matching {heading_pattern!r}")

    next_heading = re.search(r"^## ", text[heading_match.end():], re.MULTILINE)
    section_end = (
        heading_match.end() + next_heading.start()
        if next_heading else len(text)
    )
    section = text[heading_match.end():section_end]

    rows = []
    for line in section.splitlines():
        line = line.strip()
        if not line.startswith("|") or not line.endswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if not cells[0].startswith("`"):
            continue
        path = cells[0].strip("`")
        verdict = cells[1] if len(cells) > 1 else ""
        fate = cells[4] if len(cells) > 4 else ""
        rows.append(Row(path=path, verdict=verdict, fate=fate))
    return rows


def _read_unix_utils_table_rows():
    """Return every script data row of the `## \\`unix-utils\\`` table."""
    return _read_section_rows(r"^## `unix-utils`.*$")


def _read_all_table_rows():
    """Return script data rows from both the `unix-utils` and
    `oh-my-zsh` tables, for checks that must hold repo-wide (e.g. the
    verdict vocabulary guard). Excludes the Summary and Review-cap
    tables, which describe repos/tasks rather than individual scripts."""
    return (
        _read_section_rows(r"^## `unix-utils`.*$")
        + _read_section_rows(r"^## `oh-my-zsh`.*$")
    )


def _find_row(rows, path):
    for row in rows:
        if row.path == path:
            return row
    return None


class TestConversionVerdictsHarnessFateHappy(unittest.TestCase):
    def test_should_measure_a_plausible_nonzero_number_of_harness_rows_in_the_unix_utils_table(self):
        rows = _read_unix_utils_table_rows()
        harness_rows = [r for r in rows if HARNESS_PATH_RE.search(r.path)]

        self.assertGreaterEqual(
            len(harness_rows), MIN_PLAUSIBLE_HARNESS_ROWS,
            msg=f"found only {len(harness_rows)} 'test-*.sh' harness rows "
                f"in the unix-utils table of {VERDICTS_MD} — expected at "
                f"least {MIN_PLAUSIBLE_HARNESS_ROWS}; either the table "
                "regex broke or the table lost rows")
        self.assertLessEqual(
            len(harness_rows), MAX_PLAUSIBLE_HARNESS_ROWS,
            msg=f"found {len(harness_rows)} 'test-*.sh' harness rows, "
                f"more than the {MAX_PLAUSIBLE_HARNESS_ROWS} plausibility "
                "ceiling — the harness-path regex is probably "
                "over-matching non-harness rows")

    def test_should_tag_every_test_sh_harness_row_with_a_harness_fate_marker(self):
        rows = _read_unix_utils_table_rows()
        harness_rows = [r for r in rows if HARNESS_PATH_RE.search(r.path)]

        untagged = [
            r.path for r in harness_rows
            if not r.fate or "delete" not in r.fate.lower()
            and "port" not in r.fate.lower()
        ]

        self.assertEqual(
            untagged, [],
            msg="every 'test-*.sh' harness row must carry a 'Harness "
                "fate' cell naming either 'delete' or 'port', got no "
                f"such marker on: {untagged}")

    def test_should_not_tag_a_non_harness_row_with_a_harness_fate_marker(self):
        rows = _read_unix_utils_table_rows()
        non_harness_rows = [r for r in rows if not HARNESS_PATH_RE.search(r.path)]

        self.assertGreaterEqual(
            len(non_harness_rows), MIN_PLAUSIBLE_NON_HARNESS_ROWS,
            msg=f"found only {len(non_harness_rows)} non-harness rows in "
                f"the unix-utils table of {VERDICTS_MD} — expected at "
                f"least {MIN_PLAUSIBLE_NON_HARNESS_ROWS}; the table regex "
                "probably broke (this is the counter-case scan's own "
                "silent-zero guard)")

        wrongly_tagged = [
            r.path for r in non_harness_rows
            if "delete" in r.fate.lower() or "port" in r.fate.lower()
        ]

        self.assertEqual(
            wrongly_tagged, [],
            msg="only 'test-*.sh' harness rows may carry a 'delete' or "
                "'port' harness-fate marker; these non-harness rows "
                f"wrongly carry one: {wrongly_tagged}")

    def test_should_include_both_delete_and_port_to_pytest_fates_among_the_harness_markers(self):
        rows = _read_unix_utils_table_rows()
        harness_rows = [r for r in rows if HARNESS_PATH_RE.search(r.path)]

        self.assertTrue(
            any("delete" in r.fate.lower() for r in harness_rows),
            msg="no harness row is marked for deletion — expected at "
                "least one row whose subject converts")
        self.assertTrue(
            any("port" in r.fate.lower() for r in harness_rows),
            msg="no harness row is marked for porting to pytest — "
                "expected at least one row whose subject stays `.sh`")

    def test_should_mark_the_three_stays_sh_verdict_harnesses_for_deletion_when_their_subject_converts(self):
        rows = _read_unix_utils_table_rows()

        for path in TRAP_STAYS_SH_HARNESS_PATHS_WHOSE_SUBJECT_CONVERTS:
            row = _find_row(rows, path)
            if row is None:
                self.fail(msg=f"expected a row for {path!r} in the "
                              f"unix-utils table of {VERDICTS_MD}, "
                              "found none")
            self.assertEqual(
                row.verdict, "stays-sh",
                msg=f"{path} was expected to still carry its own "
                    f"'stays-sh' verdict (the trap this test pins), "
                    f"found {row.verdict!r} instead — the table's "
                    "verdict column changed, update this test's "
                    "expectation deliberately")
            self.assertIn(
                "delete", row.fate.lower(),
                msg=f"{path} carries its own 'stays-sh' verdict but its "
                    "subject script converts, so its fate must say "
                    f"'delete' (not follow its own stale verdict); got "
                    f"fate={row.fate!r}")

    def test_should_mark_the_five_stays_sh_subject_harnesses_for_porting_to_pytest(self):
        rows = _read_unix_utils_table_rows()

        for path in PORT_TO_PYTEST_HARNESS_PATHS:
            row = _find_row(rows, path)
            if row is None:
                self.fail(msg=f"expected a row for {path!r} in the "
                              f"unix-utils table of {VERDICTS_MD}, "
                              "found none")
            self.assertIn(
                "port", row.fate.lower(),
                msg=f"{path}'s subject stays `.sh`, so its fate must "
                    f"say 'port' (to a pytest suite); got "
                    f"fate={row.fate!r}")

    def test_should_keep_every_verdict_column_value_within_the_classifiers_known_set(self):
        rows = _read_all_table_rows()

        self.assertGreaterEqual(
            len(rows), 100,
            msg=f"found only {len(rows)} total table rows across both "
                f"tables of {VERDICTS_MD} — expected at least 100 "
                "(98 unix-utils + 29 oh-my-zsh, minus header/separator "
                "rows the parser should already exclude); the table "
                "regex probably broke (silent-zero guard)")

        bad_verdicts = sorted({
            (r.path, r.verdict) for r in rows
            if r.verdict not in ALLOWED_VERDICTS
        })

        self.assertEqual(
            bad_verdicts, [],
            msg="the 'Verdict' column must only ever contain tool-"
                f"emitted values {sorted(ALLOWED_VERDICTS)} — found "
                f"other values (path, verdict): {bad_verdicts}. Adding "
                "a harness-fate marker must never rewrite this column.")


if __name__ == "__main__":
    unittest.main()
