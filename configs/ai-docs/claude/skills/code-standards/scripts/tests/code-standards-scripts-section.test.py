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

# unix-utils repo root: this test file's own checkout,
# seven levels above scripts/tests/.
UNIX_UTILS_ROOT = Path(__file__).resolve().parents[7]
SKILL_MD = (
    UNIX_UTILS_ROOT
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


def _find_unix_philosophy_instruction_lines(text):
    """Return every '- [Instruction]' bullet line in `text` that
    mentions the Unix philosophy.

    Takes raw text rather than reading SKILL_MD itself, so the
    same AC-32 counting rule can run against the whole file and
    against an inline fixture — the fixture is what proves the
    rule actually counts file-wide, not just within one section.
    """
    return [
        line for line in text.splitlines()
        if line.strip().startswith("- [Instruction]")
        and "Unix philosophy" in line
    ]


def _classify_header_comment_lines(comment_lines):
    """Partition a script header's comment lines (the shebang
    line excluded) into the four roles AC-18 permits, returning
    whichever lines match none of them.

    The four permitted roles: the name+purpose line right after
    the shebang, the 'Usage:' header plus its indented
    invocation-form lines, the stdin/stdout/exit I/O-contract
    lines, and bare '#' separator lines. Anything left over is a
    fifth element AC-18 forbids.

    A Usage: continuation line only counts as an invocation form
    when indented 2+ spaces past the '#' (real forms carry 3).
    A same-indent line like '# Examples:' or '# Background:'
    closes the block instead of being swept in, so content AC-18
    excludes can't hide inside Usage: before any separator.
    """
    name_purpose_pattern = re.compile(r"^#\s*[\w.-]+\s*[-—]\s*\S")
    usage_header_pattern = re.compile(r"^#\s*Usage:\s*$")
    usage_continuation_pattern = re.compile(r"^#\s{2,}\S")
    io_contract_pattern = re.compile(r"^#\s*(stdin|stdout|exit):")
    bare_separator_pattern = re.compile(r"^#\s*$")

    unclassified_lines = []
    in_usage_block = False

    for index, line in enumerate(comment_lines):
        if index == 0 and name_purpose_pattern.match(line):
            continue

        if usage_header_pattern.match(line):
            in_usage_block = True
            continue

        if bare_separator_pattern.match(line):
            in_usage_block = False
            continue

        if in_usage_block:
            if usage_continuation_pattern.match(line):
                continue
            # Falls through on a clean slate: a same-indent line
            # (e.g. "# Examples:") closes the block instead of
            # being swept in as an invocation form, so it still
            # gets classified on its own merits below.
            in_usage_block = False

        if io_contract_pattern.match(line):
            in_usage_block = False
            continue

        unclassified_lines.append(line)

    return unclassified_lines


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
    def test_should_carry_exactly_one_unix_philosophy_instruction_in_the_whole_file(self):
        whole_file_text = SKILL_MD.read_text()

        instruction_lines_with_unix_philosophy = (
            _find_unix_philosophy_instruction_lines(whole_file_text))

        self.assertEqual(
            len(instruction_lines_with_unix_philosophy), 1,
            msg="expected exactly one [Instruction] bullet mentioning "
                "'Unix philosophy' in the whole SKILL.md, found: "
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

        # Upper bound: partition every comment line after the
        # shebang into one of the four permitted roles; anything
        # left over is a fifth element AC-18 forbids.
        comment_lines = fence_lines[1:]
        while comment_lines and comment_lines[-1].strip() == "":
            comment_lines.pop()

        unclassified_lines = _classify_header_comment_lines(
            comment_lines)
        self.assertEqual(
            unclassified_lines, [],
            msg="header carries lines outside the four permitted "
                "roles (name+purpose, Usage:, I/O contract, bare "
                f"'#' separators): {unclassified_lines}")

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


class TestCodeStandardsScriptsSectionGuardHelpers(unittest.TestCase):
    """Prove the AC-32 and AC-18 counting/partitioning helpers
    genuinely detect the violations those ACs forbid, against
    inline fixtures the real (already-compliant) SKILL.md can
    never exercise on its own."""

    def test_should_report_a_second_unix_philosophy_instruction_found_outside_the_scripts_section(self):
        fixture_text = (
            "## Scripts\n"
            "\n"
            "- [Instruction] **CRITICAL: Follow the Unix "
            "philosophy — make each script do one thing well.**\n"
            "\n"
            "## Naming\n"
            "\n"
            "- [Instruction] **CRITICAL: Follow the Unix "
            "philosophy — name things by purpose.**\n"
        )

        instruction_lines_with_unix_philosophy = (
            _find_unix_philosophy_instruction_lines(fixture_text))

        self.assertEqual(
            len(instruction_lines_with_unix_philosophy), 2,
            msg="a whole-file guard must count both the "
                "'## Scripts' instruction and the duplicate added "
                "in a different section, not stop at the first one "
                f"found: {instruction_lines_with_unix_philosophy}")

    def test_should_report_header_lines_outside_the_four_permitted_roles(self):
        fixture_header_lines_with_a_fifth_element = [
            "# extract-field.py - Extract a field from JSON lines",
            "#",
            "# Usage:",
            "#   extract-field.py <field> [file]",
            "#   cat data.jsonl | extract-field.py .name",
            "#",
            "# stdin: JSON lines, when no file argument is given",
            "# stdout: the extracted field value, one per line",
            "# exit: 0 on success, 1 on bad input",
            "#",
            "# Examples:",
            "#   extract-field.py .id data.jsonl",
        ]

        unclassified_lines = _classify_header_comment_lines(
            fixture_header_lines_with_a_fifth_element)

        self.assertEqual(
            unclassified_lines,
            ["# Examples:", "#   extract-field.py .id data.jsonl"],
            msg="an 'Examples:' block added past the four permitted "
                "roles (name+purpose, Usage:, I/O contract, bare "
                "'#' separators) must be reported, not silently "
                f"accepted: {unclassified_lines}")

    def test_should_report_a_worked_example_block_placed_inside_the_usage_block_before_any_separator(self):
        fixture_header_lines_with_examples_inside_usage = [
            "# extract-field.py - Extract a field from JSON lines",
            "#",
            "# Usage:",
            "#   extract-field.py <field> [file]",
            "#   cat data.jsonl | extract-field.py .name",
            "# Examples:",
            "#   extract-field.py .id data.jsonl",
            "#",
            "# stdin: JSON lines, when no file argument is given",
            "# stdout: the extracted field value, one per line",
            "# exit: 0 on success, 1 on bad input",
        ]

        unclassified_lines = _classify_header_comment_lines(
            fixture_header_lines_with_examples_inside_usage)

        self.assertEqual(
            unclassified_lines,
            ["# Examples:", "#   extract-field.py .id data.jsonl"],
            msg="a worked-example block slipped inside the 'Usage:' "
                "block, before any bare '#' separator closes it, "
                "must still be reported, not silently swept in as "
                f"an invocation form: {unclassified_lines}")

    def test_should_report_a_rationale_line_placed_inside_the_usage_block_before_any_separator(self):
        fixture_header_lines_with_rationale_inside_usage = [
            "# extract-field.py - Extract a field from JSON lines",
            "#",
            "# Usage:",
            "#   extract-field.py <field> [file]",
            "#   cat data.jsonl | extract-field.py .name",
            "# Background: written because jq was unavailable on "
            "the build box.",
            "#",
            "# stdin: JSON lines, when no file argument is given",
            "# stdout: the extracted field value, one per line",
            "# exit: 0 on success, 1 on bad input",
        ]

        unclassified_lines = _classify_header_comment_lines(
            fixture_header_lines_with_rationale_inside_usage)

        self.assertEqual(
            unclassified_lines,
            ["# Background: written because jq was unavailable on "
             "the build box."],
            msg="a rationale/background line slipped inside the "
                "'Usage:' block, before any bare '#' separator "
                "closes it, must still be reported, not silently "
                f"swept in as an invocation form: {unclassified_lines}")


if __name__ == "__main__":
    unittest.main()
