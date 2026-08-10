"""Prove `conversion-verdicts.md` states, per column, which cell values
are genuine `classify-conversion.py` output and which are hand-derived
prose — instead of the blanket "nothing here was hand-adjusted" claim
that was false the moment the `Triggering reason` and `Harness fate`
columns existed (neither has a source in the tool's four emitted keys:
`path`, `target_language`, `tree_root`, `verdict`).

This is a doc-content contract test, not a behavior test: the "system
under test" is prose in a markdown file, so assertions read that prose
directly rather than exercising a function. Distinct subject from
`conversion-verdicts-harness-fate.test.py`, which guards the `Harness
fate` column's own row-by-row values, not the file's provenance claims
about which columns are tool output versus hand-derived. See
`configs/ai-docs/claude/skills/code-standards/references/conversion-verdicts.md`.

Usage:
  pytest configs/ai-docs/claude/skills/code-standards/scripts/tests/conversion-verdicts-provenance.test.py
"""

import re
import unittest
from pathlib import Path

# unix-utils repo root: this test file's own checkout,
# seven levels above scripts/tests/.
UNIX_UTILS_ROOT = Path(__file__).resolve().parents[7]
VERDICTS_MD = (
    UNIX_UTILS_ROOT
    / "configs/ai-docs/claude/skills/code-standards/references"
    / "conversion-verdicts.md"
)

# The four keys classify-conversion.py actually emits (verified against
# its source in this session) — the hand-derived-columns claim must name
# these, so a reader can check the claim against the tool itself rather
# than trusting prose alone.
CLASSIFIER_EMITTED_KEYS = ["path", "target_language", "tree_root", "verdict"]

# Columns with no source in the classifier's output — Triggering reason
# is hand-derived prose explaining each verdict; Harness fate is a fifth
# column added by a later commit, also hand-derived (looked up from each
# harness's subject script, not read from any tool).
HAND_DERIVED_COLUMN_NAMES = ["Triggering reason", "Harness fate"]

# Columns that genuinely are classify-conversion.py's own output —
# Path/Verdict always; Target only for `convert` rows since commit
# d012ceb9, but the snapshot predates that commit so every row here
# (including `stays-sh` ones) still carries the tool's pre-d012ceb9
# Target value.
TOOL_OUTPUT_COLUMN_NAMES = ["Path", "Verdict", "Target"]


def _read_opening_paragraph():
    """Return the file's opening prose — from the `# ` title line up to
    (not including) the first `## ` heading. This is the paragraph that
    carries the file's provenance claim."""
    text = VERDICTS_MD.read_text()

    title_match = re.search(r"^# .*$", text, re.MULTILINE)
    if title_match is None:
        raise AssertionError(f"{VERDICTS_MD} has no top-level '# ' title line")

    next_heading = re.search(r"^## ", text[title_match.end():], re.MULTILINE)
    if next_heading is None:
        raise AssertionError(
            f"{VERDICTS_MD} has no '## ' heading after its title — "
            "cannot bound the opening paragraph")

    paragraph = text[title_match.end():title_match.end() + next_heading.start()].strip()
    if not paragraph:
        raise AssertionError(
            f"the opening paragraph of {VERDICTS_MD} (between its title "
            "and first '## ' heading) is empty — the provenance claim "
            "this test checks would have nothing to check")
    return paragraph


def _read_snapshot_provenance_section():
    """Return the `## Snapshot provenance` section's raw text, from its
    own heading up to the next top-level `## ` heading."""
    text = VERDICTS_MD.read_text()

    heading_match = re.search(r"^## Snapshot provenance$", text, re.MULTILINE)
    if heading_match is None:
        raise AssertionError(
            f"{VERDICTS_MD} has no '## Snapshot provenance' heading")

    next_heading = re.search(r"^## ", text[heading_match.end():], re.MULTILINE)
    section_end = (
        heading_match.end() + next_heading.start()
        if next_heading else len(text)
    )
    section = text[heading_match.end():section_end].strip()
    if not section:
        raise AssertionError(
            f"the '## Snapshot provenance' section of {VERDICTS_MD} is "
            "empty — the staleness disclosure this test checks would "
            "have nothing to check")
    return section


class TestConversionVerdictsProvenanceHappy(unittest.TestCase):
    def test_should_read_a_non_empty_opening_paragraph_naming_the_classifier_as_source(self):
        paragraph = _read_opening_paragraph()

        self.assertIn(
            "classify-conversion.py", paragraph,
            msg="opening paragraph must name classify-conversion.py as "
                f"the tool this table's provenance is measured against, "
                f"got: {paragraph!r}")

    def test_should_not_claim_that_nothing_in_the_file_was_hand_adjusted(self):
        text = VERDICTS_MD.read_text()
        self.assertGreater(
            len(text), 500,
            msg=f"{VERDICTS_MD} read back suspiciously short — the read "
                "itself may have failed silently")

        blanket_claim = re.search(
            r"nothing\b[^.]{0,60}hand[- ]adjusted", text, re.IGNORECASE)
        self.assertIsNone(
            blanket_claim,
            msg="the file must not claim that nothing in it was "
                "hand-adjusted — the Triggering reason and Harness fate "
                f"columns are hand-derived; found: {blanket_claim and blanket_claim.group(0)!r}")

    def test_should_not_claim_a_hand_derived_column_is_tool_output(self):
        text = VERDICTS_MD.read_text()

        tool_provenance_words = r"(exactly what|tool output|classify-conversion\.py returned)"
        offenders = []
        for column_name in HAND_DERIVED_COLUMN_NAMES:
            match = re.search(
                rf"{re.escape(column_name)}[^\n]{{0,80}}{tool_provenance_words}",
                text)
            if match:
                offenders.append((column_name, match.group(0)))

        self.assertEqual(
            offenders, [],
            msg="a hand-derived column must never be described as tool "
                f"output; found: {offenders}")

    def test_should_positively_state_the_path_verdict_and_target_columns_are_tool_output(self):
        paragraph = _read_opening_paragraph()

        missing_columns = [
            name for name in TOOL_OUTPUT_COLUMN_NAMES
            if name not in paragraph
        ]
        self.assertEqual(
            missing_columns, [],
            msg="opening paragraph must name every genuinely tool-"
                f"sourced column ({TOOL_OUTPUT_COLUMN_NAMES}) so a "
                "reader knows which cells to trust as classifier "
                f"output; missing: {missing_columns} from: {paragraph!r}")

        self.assertRegex(
            paragraph, r"(exactly what|tool output|classify-conversion\.py returned)",
            msg="opening paragraph must positively affirm that the "
                "tool-sourced columns really are the classifier's own "
                f"output, not just list their names; got: {paragraph!r}")

    def test_should_positively_state_the_triggering_reason_and_harness_fate_columns_are_hand_derived(self):
        paragraph = _read_opening_paragraph()

        missing_columns = [
            name for name in HAND_DERIVED_COLUMN_NAMES
            if name not in paragraph
        ]
        self.assertEqual(
            missing_columns, [],
            msg="opening paragraph must name every hand-derived column "
                f"({HAND_DERIVED_COLUMN_NAMES}) so a reader knows which "
                f"cells were human-written; missing: {missing_columns} "
                f"from: {paragraph!r}")

        self.assertRegex(
            paragraph, r"hand[- ]derived|hand[- ]written",
            msg="opening paragraph must positively state that these "
                f"columns are hand-derived/hand-written, not merely "
                f"list their names; got: {paragraph!r}")

    def test_should_name_the_classifiers_four_actual_output_keys_to_ground_the_hand_derived_claim(self):
        paragraph = _read_opening_paragraph()

        missing_keys = [
            key for key in CLASSIFIER_EMITTED_KEYS
            if key not in paragraph
        ]
        self.assertEqual(
            missing_keys, [],
            msg="opening paragraph must name the classifier's actual "
                f"four emitted keys ({CLASSIFIER_EMITTED_KEYS}) so a "
                "reader can verify the hand-derived claim against the "
                f"tool itself; missing: {missing_keys} from: {paragraph!r}")

    def test_should_disclose_in_snapshot_provenance_that_the_target_column_is_stale_on_stays_sh_rows(self):
        section = _read_snapshot_provenance_section()

        self.assertIn(
            "stays-sh", section,
            msg="Snapshot provenance section must name the `stays-sh` "
                f"verdict the Target-column staleness affects, got: "
                f"{section!r}")
        self.assertIn(
            "Target", section,
            msg="Snapshot provenance section must name the `Target` "
                f"column the staleness affects, got: {section!r}")
        self.assertIn(
            "d012ceb9", section,
            msg="Snapshot provenance section must cite commit d012ceb9, "
                "which changed classify-conversion.py to stop reporting "
                f"a target for non-convert verdicts, got: {section!r}")


if __name__ == "__main__":
    unittest.main()
