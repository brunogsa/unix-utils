"""Prove the `## Scripts` section of code-standards/SKILL.md states the
five rules every later script-overhaul task is judged against, and that
it dropped the old contradictory Bash-or-Node language rule.

This is a doc-content contract test, not a behavior test: the "system
under test" is prose in a markdown file, so assertions read that prose
directly rather than exercising a function.

Usage:
  pytest configs/ai-docs/claude/skills/code-standards/scripts/tests/code-standards-scripts-section.test.py
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[7]
SKILL_MD = (
    REPO_ROOT
    / "configs/ai-docs/claude/skills/code-standards/SKILL.md"
)

# The shortest of the three real script headers this work
# measures as a baseline (dag-check-helper.sh) — the SKILL.md
# example must drop strictly below this line count.
SHORTEST_MEASURED_BASELINE_LINES = 23

# The pre-rewrite language-rule sentence this task deletes;
# it must not survive in the rewritten section.
OLD_CONTRADICTORY_RULE = "Bash for linear/glue, Node.js for structured data"


def _read_scripts_section():
    """Return the `## Scripts` section's raw text, from its own
    heading up to (not including) the next top-level `## ` heading,
    or end of file if `## Scripts` is the last section."""
    text = SKILL_MD.read_text()
    match = re.search(r"^## Scripts$", text, re.MULTILINE)
    if match is None:
        raise AssertionError("SKILL.md has no '## Scripts' heading")
    start = match.end()
    next_heading = re.search(r"^## ", text[start:], re.MULTILINE)
    end = start + next_heading.start() if next_heading else len(text)
    return text[start:end]


def _extract_first_fenced_block(section_text):
    """Return the content lines of the first fenced code block in
    the section (the usage-header example), excluding the fence
    markers themselves."""
    match = re.search(r"```[a-zA-Z0-9]*\n(.*?)```", section_text, re.DOTALL)
    if match is None:
        raise AssertionError(
            "no fenced code block found in the '## Scripts' section")
    return match.group(1).splitlines()


class TestCodeStandardsScriptsSectionHappy(unittest.TestCase):
    def test_should_carry_exactly_one_unix_philosophy_instruction(self):
        section = _read_scripts_section()

        instruction_lines_with_unix_philosophy = [
            line for line in section.splitlines()
            if line.strip().startswith("- [Instruction]")
            and "Unix philosophy" in line
        ]

        self.assertEqual(
            len(instruction_lines_with_unix_philosophy), 1,
            msg="expected exactly one [Instruction] bullet mentioning "
                "'Unix philosophy' in the '## Scripts' section, found: "
                f"{instruction_lines_with_unix_philosophy}")

    def test_should_keep_the_rewritten_usage_header_example_under_the_shortest_measured_baseline(self):
        section = _read_scripts_section()
        fence_lines = _extract_first_fenced_block(section)

        # First line is the shebang; the comment block excludes
        # the shebang itself and any trailing blank line.
        self.assertTrue(
            fence_lines and fence_lines[0].startswith("#!"),
            msg=f"expected the example's first line to be a shebang, "
                f"got: {fence_lines[:1]}")

        comment_lines = fence_lines[1:]
        while comment_lines and comment_lines[-1].strip() == "":
            comment_lines.pop()

        self.assertLess(
            len(comment_lines), SHORTEST_MEASURED_BASELINE_LINES,
            msg=f"example header is {len(comment_lines)} comment lines, "
                f"must be under {SHORTEST_MEASURED_BASELINE_LINES} "
                "(dag-check-helper.sh's own baseline, the shortest "
                "of the three real headers this work measures)")

    def test_should_keep_the_rewritten_example_naming_the_script_its_purpose_invocation_forms_and_io_contract(self):
        section = _read_scripts_section()
        fence_lines = _extract_first_fenced_block(section)
        fence_text = "\n".join(fence_lines)

        # Name + purpose: a "# <name> - <purpose>" style line
        # right after the shebang.
        self.assertRegex(
            fence_text, r"#\s*[\w.-]+\s*[-—]\s*\S+",
            msg="example must name the script and its one-line purpose "
                "on the line right after the shebang")

        # Invocation forms: an explicit "Usage:" block with
        # 2+ forms.
        usage_match = re.search(r"Usage:\n((?:#.*\n?)+)", fence_text)

        # Guard before .group(): a missing Usage: block is the
        # regression this test catches, so it must fail naming
        # the absent content and its file, not AttributeError.
        if usage_match is None:
            self.fail(
                msg="example must carry a 'Usage:' block — no "
                    "'Usage:' line followed by comment lines in the "
                    "first fenced block of the '## Scripts' section "
                    f"of {SKILL_MD}")
        usage_form_lines = [
            line for line in usage_match.group(1).splitlines()
            if line.strip().lstrip("#").strip()
        ]
        self.assertGreaterEqual(
            len(usage_form_lines), 2,
            msg="example must show at least 2 invocation forms under "
                f"Usage:, found {len(usage_form_lines)}")

        # stdin/stdout/exit-code I/O contract, named explicitly.
        self.assertIn("stdin", fence_text.lower())
        self.assertIn("stdout", fence_text.lower())
        self.assertIn("exit", fence_text.lower())

    def test_should_state_the_python_default_language_rule_with_no_surviving_bash_or_node_contradiction(self):
        section = _read_scripts_section()

        self.assertNotIn(
            OLD_CONTRADICTORY_RULE, section,
            msg="the old 'Bash for linear/glue, Node.js for structured "
                "data' rule must not survive the rewrite")

        self.assertRegex(
            section, r"[Dd]efault\b.*\bPython\b",
            msg="section must state Python as the default target "
                "language")

        self.assertIn(
            "# Requires-npm: <package> — <stdlib gap>", section,
            msg="section must state the exact "
                "'# Requires-npm: <package> — <stdlib gap>' header "
                "line convention for the .js exception")

        self.assertRegex(
            section, r"stdlib\s+cannot",
            msg="section must require the Requires-npm line to name "
                "a gap Python's stdlib cannot cover")


if __name__ == "__main__":
    unittest.main()
