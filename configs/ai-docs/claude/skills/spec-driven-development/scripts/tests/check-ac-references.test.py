"""Blackbox CLI tests for check-ac-references.py.

Fixtures: none on disk except what each test writes to tmp_path, so no
suite run can be steered, or broken, by a planning document its author
is still editing.

Each passing fixture holds one anchor shape the planning docs join on,
and each failing fixture holds one prose citation of an acceptance
criterion by its ID, the shape SKILL.md bans.

Usage:
  pytest scripts/tests/check-ac-references.test.py
"""

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "check-ac-references.py"


def run_checker(*paths):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *map(str, paths)],
        capture_output=True,
        text=True,
    )


def write_doc(tmp_path, body, name="doc.md"):
    doc = tmp_path / name
    doc.write_text(body)
    return doc


# Happy cases - every anchor shape passes


def test_should_pass_the_spec_definition_heading_of_an_acceptance_criterion(tmp_path):
    doc = write_doc(tmp_path, "## Testable Acceptance Criteria\n\n### AC-12: When a CNPJ has no account, the lookup shall return none\n")
    result = run_checker(doc)
    assert (result.returncode, result.stdout) == (0, "")


def test_should_pass_the_spec_heading_of_a_retired_acceptance_criterion(tmp_path):
    doc = write_doc(tmp_path, "### Retired: AC-14\n\nMerged into the record-type rule.\n")
    result = run_checker(doc)
    assert (result.returncode, result.stdout) == (0, "")


def test_should_pass_the_plan_coverage_list_header_of_an_acceptance_criterion(tmp_path):
    doc = write_doc(tmp_path, "- **AC-3** Each CNPJ syncs as its own Escola\n")
    result = run_checker(doc)
    assert (result.returncode, result.stdout) == (0, "")


def test_should_pass_a_test_design_row_whose_trailing_annotation_names_its_criteria_and_tasks(tmp_path):
    doc = write_doc(
        tmp_path,
        "## Test Design\n\n```\n"
        'describe("SchoolSync", () => {\n'
        '  it("should skip an Institution event with an info log");  // AC-10 AC-34 T9 [on-demand]\n'
        "});\n```\n",
    )
    result = run_checker(doc)
    assert (result.returncode, result.stdout) == (0, "")


def test_should_pass_the_prose_coverage_marker_line_in_test_design(tmp_path):
    doc = write_doc(
        tmp_path,
        "```\n// AC-7 - prose, verified by direct-coder diff review, no test\n```\n",
    )
    result = run_checker(doc)
    assert (result.returncode, result.stdout) == (0, "")


def test_should_pass_the_task_details_criteria_field_another_gate_joins_on(tmp_path):
    # check-ac-task-consistency.py reads every AC token on
    # this field's lines as the task's declared criteria, so
    # the IDs are a join key.
    doc = write_doc(
        tmp_path,
        "## Task Details\n\n<details>\n<summary>Task 3 - lookups</summary>\n\n"
        "**Testable Acceptance criteria**:\n"
        "- AC-4, AC-7: lookups see allowlisted accounts only.\n\n"
        "**Verification**: `yarn test`\n</details>\n",
    )
    result = run_checker(doc)
    assert (result.returncode, result.stdout) == (0, "")


def test_should_pass_a_document_that_spells_out_every_behavior(tmp_path):
    doc = write_doc(tmp_path, "- Covers the no-CNPJ rule: the event goes to the DLQ.\n")
    result = run_checker(doc)
    assert (result.returncode, result.stdout) == (0, "")


# Failure scenarios - every prose citation fails, naming its
# file and line


def test_should_flag_a_prose_bullet_leading_with_criterion_ids(tmp_path):
    doc = write_doc(tmp_path, "## Technical Approach\n\n- AC-4, AC-7: lookups see allowlisted accounts only.\n")
    result = run_checker(doc)
    assert result.returncode == 1
    assert result.stdout == f"{doc}:3: - AC-4, AC-7: lookups see allowlisted accounts only.\n"


def test_should_flag_a_criterion_cited_as_spec_ac_in_running_prose(tmp_path):
    doc = write_doc(tmp_path, "The guard-miss composite verifies the premise of spec AC-37.\n")
    result = run_checker(doc)
    assert result.returncode == 1
    assert result.stdout == f"{doc}:1: The guard-miss composite verifies the premise of spec AC-37.\n"


def test_should_flag_a_parenthesized_criterion_inside_a_decision(tmp_path):
    doc = write_doc(tmp_path, "## Decisions\n\n- Check the record type before PIC (AC-41), since PIC is costly.\n")
    result = run_checker(doc)
    assert result.returncode == 1
    assert result.stdout == f"{doc}:3: - Check the record type before PIC (AC-41), since PIC is costly.\n"


def test_should_flag_a_criterion_id_inside_a_test_title_even_with_a_valid_trailing_annotation(tmp_path):
    row = '  it("should satisfy AC-5 for a LegalUnit event");  // AC-1 T3'
    doc = write_doc(tmp_path, f"## Test Design\n\n```\n{row}\n```\n")
    result = run_checker(doc)
    assert result.returncode == 1
    assert result.stdout == f"{doc}:4: {row}\n"


def test_should_flag_a_criterion_cited_in_a_prose_comment_inside_test_design(tmp_path):
    line = "// AC-22 asserts contract validation in all 4 consumers."
    doc = write_doc(tmp_path, f"```\n{line}\n```\n")
    result = run_checker(doc)
    assert result.returncode == 1
    assert result.stdout == f"{doc}:2: {line}\n"


def test_should_flag_a_second_criterion_cited_after_an_anchor_on_the_same_line(tmp_path):
    line = "### AC-37: The write-back shall retry, unlike AC-4"
    doc = write_doc(tmp_path, f"{line}\n")
    result = run_checker(doc)
    assert result.returncode == 1
    assert result.stdout == f"{doc}:1: {line}\n"


def test_should_flag_a_criterion_cited_after_the_task_details_criteria_field_ends(tmp_path):
    doc = write_doc(
        tmp_path,
        "## Task Details\n\n<summary>Task 3 - lookups</summary>\n\n"
        "**Testable Acceptance criteria**:\n- AC-4: lookups see allowlisted accounts only.\n\n"
        "**Verification**: the test proving AC-4\n",
    )
    result = run_checker(doc)
    assert result.returncode == 1
    assert result.stdout == f"{doc}:8: **Verification**: the test proving AC-4\n"


def test_should_report_hits_from_every_named_file(tmp_path):
    spec = write_doc(tmp_path, "See AC-2.\n", name="spec.md")
    plan = write_doc(tmp_path, "See AC-3.\n", name="plan.md")
    result = run_checker(spec, plan)
    assert result.returncode == 1
    assert result.stdout == f"{spec}:1: See AC-2.\n{plan}:1: See AC-3.\n"


def test_should_exit_2_with_usage_when_given_no_file():
    result = run_checker()
    assert result.returncode == 2
    assert "usage:" in result.stderr


def test_should_exit_2_naming_the_file_when_a_named_file_is_missing(tmp_path):
    missing = tmp_path / "absent.md"
    result = run_checker(missing)
    assert result.returncode == 2
    assert str(missing) in result.stderr
