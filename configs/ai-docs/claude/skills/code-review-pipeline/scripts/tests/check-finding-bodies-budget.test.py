"""Blackbox CLI tests for check-finding-bodies.py: the length
budget, where a finding starts and ends, and which lines or
findings are exempt from the checks.

Usage:
  ./run-tests.py <this file>
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from finding_bodies_support import (
    EN_SUGGESTION,
    MANDATORY_CAP,
    NON_MANDATORY_CAP,
    assert_passes,
    check_text,
    make_body,
    make_finding,
    make_verdict,
    padded_body,
    run_script,
    violations_of,
    write_file,
)


class TestLengthBudget:
    @pytest.mark.parametrize("tag,ordinal", [("RECOMMENDED", "MEDIUM"), ("NITPICK", "LOW")])
    def test_non_mandatory_body_at_512_chars_passes(self, tmp_path, tag, ordinal):
        body = padded_body(NON_MANDATORY_CAP, tag)
        finding = make_finding(prefix=f"[{ordinal}]", body=body)
        assert_passes(check_text(tmp_path, make_verdict(finding)))

    def test_non_mandatory_body_at_513_chars_is_flagged_with_measure_and_cap(self, tmp_path):
        body = padded_body(NON_MANDATORY_CAP + 1, "RECOMMENDED")
        path = write_file(tmp_path, make_verdict(make_finding(prefix="[MEDIUM]", body=body)))
        lines = violations_of(run_script(path))
        assert len(lines) == 1
        assert lines[0].startswith(f"{path}: finding 1: ")
        assert "513" in lines[0] and "512" in lines[0]

    def test_mandatory_body_at_1024_chars_passes(self, tmp_path):
        body = padded_body(MANDATORY_CAP, "MANDATORY")
        assert_passes(check_text(tmp_path, make_verdict(make_finding(body=body))))

    def test_mandatory_body_at_1025_chars_is_flagged_with_measure_and_cap(self, tmp_path):
        body = padded_body(MANDATORY_CAP + 1, "MANDATORY")
        lines = violations_of(check_text(tmp_path, make_verdict(make_finding(body=body))))
        assert len(lines) == 1
        assert "1025" in lines[0] and "1024" in lines[0]

    def test_mandatory_body_over_16_non_blank_lines_is_flagged_with_measure_and_cap(
        self, tmp_path,
    ):
        bullets = "\n".join(f"- [-] Invoice {n} is overbilled." for n in range(1, 13))
        body = make_body(tradeoff_text=bullets)
        lines = violations_of(check_text(tmp_path, make_verdict(make_finding(body=body))))
        assert len(lines) == 1
        assert "17" in lines[0] and "16" in lines[0]

    def test_mandatory_body_with_blank_lines_between_16_lines_passes(self, tmp_path):
        bullets = "\n\n".join(f"- [-] Invoice {n} is overbilled." for n in range(1, 12))
        body = make_body(tradeoff_text=bullets)
        assert_passes(check_text(tmp_path, make_verdict(make_finding(body=body))))

    def test_fenced_code_block_counts_toward_neither_chars_nor_lines(self, tmp_path):
        code_lines = "\n".join(f"+    fee_{n} = total * rate / 100" for n in range(40))
        suggestion = f"```diff\n{code_lines}\n```"
        body = make_body(tag="RECOMMENDED", suggestion_text=suggestion)
        finding = make_finding(prefix="[MEDIUM]", body=body)
        assert_passes(check_text(tmp_path, make_verdict(finding)))


class TestFindingBoundaries:
    def test_horizontal_rule_ends_the_finding_so_text_after_it_is_not_charged(self, tmp_path):
        appendix = "Appendix. " * 80
        finding = make_finding(prefix="[MEDIUM]", body=make_body(tag="RECOMMENDED"))
        text = make_verdict(finding)
        assert_passes(check_text(tmp_path, f"{text}\n---\n\n{appendix}\n"))

    def test_level_two_heading_ends_the_finding_so_text_after_it_is_not_charged(
        self, tmp_path,
    ):
        appendix = "Appendix. " * 80
        finding = make_finding(prefix="[MEDIUM]", body=make_body(tag="RECOMMENDED"))
        text = make_verdict(finding)
        assert_passes(check_text(tmp_path, f"{text}\n## Counts\n\n{appendix}\n"))

    def test_hash_comment_inside_a_code_block_does_not_end_the_finding(self, tmp_path):
        suggestion = "```diff\n# src/billing/fees.py\n-fee = total * rate\n+fee = total * rate / 100\n```"
        body = make_body(suggestion_text=suggestion)
        assert_passes(check_text(tmp_path, make_verdict(make_finding(body=body))))

    def test_each_finding_is_reported_under_its_own_number(self, tmp_path):
        text = make_verdict(
            make_finding(number=1),
            make_finding(number=2, body=make_body(tradeoff_label=None)),
        )
        path = write_file(tmp_path, text)
        lines = violations_of(run_script(path))
        assert len(lines) == 1
        assert lines[0].startswith(f"{path}: finding 2: ")


class TestNumberedHeadingLevel:
    @pytest.mark.parametrize("hashes", ["#", "##", "####", "######"])
    def test_numbered_finding_under_a_heading_level_other_than_three_is_flagged_with_its_line(
        self, tmp_path, hashes,
    ):
        finding = make_finding().replace("###", hashes, 1)
        path = write_file(tmp_path, "# Refactor review\n\n## Findings\n\n" + finding)
        lines = violations_of(run_script(path))
        assert lines == [f"{path}: line 5: numbered finding heading must be '### N.'"]

    def test_numbered_heading_inside_a_code_block_is_not_flagged(self, tmp_path):
        suggestion = "```markdown\n## 1. [MEDIUM] title\n```"
        body = make_body(suggestion_text=suggestion)
        assert_passes(check_text(tmp_path, make_verdict(make_finding(body=body))))


class TestAddressVerdictsAnnotations:
    @pytest.mark.parametrize("annotation", [
        "APPLIED (fa169db4) - the rate is divided by 100 before billing.",
        "SKIPPED (the rate is already a fraction upstream)",
    ])
    def test_annotation_line_before_the_tag_is_ignored(self, tmp_path, annotation):
        body = make_body(before_tag=annotation)
        finding = make_finding(prefix="[Done][HIGH]", body=body)
        assert_passes(check_text(tmp_path, make_verdict(finding)))

    def test_long_annotation_line_is_not_charged_against_the_budget(self, tmp_path):
        annotation = "APPLIED (fa169db4) - " + "verified on staging. " * 30
        body = annotation + "\n\n" + padded_body(NON_MANDATORY_CAP, "RECOMMENDED")
        finding = make_finding(prefix="[Done][MEDIUM]", body=body)
        assert_passes(check_text(tmp_path, make_verdict(finding)))


class TestQualityGateJudgeRuling:
    RULING = (
        '**Standards check**: Skip - "Keep functions short"; '
        "considered fix: split the fee calculation in two"
    )
    SKIPPED = "SKIPPED (judge ruled Skip)"

    def _judged(self, body):
        return f"{body}\n\n{self.RULING}\n\n{self.SKIPPED}"

    def test_body_of_512_reviewer_chars_passes_with_judge_ruling_appended_and_513_still_fails(
        self, tmp_path
    ):
        at_cap = padded_body(NON_MANDATORY_CAP, "RECOMMENDED")
        assert_passes(check_text(
            tmp_path, make_verdict(make_finding(prefix="[MEDIUM]", body=self._judged(at_cap)))))
        over_cap = padded_body(NON_MANDATORY_CAP + 1, "RECOMMENDED")
        lines = violations_of(check_text(
            tmp_path, make_verdict(make_finding(prefix="[MEDIUM]", body=self._judged(over_cap)))))
        assert len(lines) == 1
        assert "513" in lines[0] and "512" in lines[0]

    def test_line_mentioning_the_standards_check_label_mid_line_still_counts(self, tmp_path):
        at_cap = padded_body(NON_MANDATORY_CAP, "RECOMMENDED")
        body = f"{at_cap}\n\nSee the **Standards check**: Fix label below."
        lines = violations_of(check_text(
            tmp_path, make_verdict(make_finding(prefix="[MEDIUM]", body=body))))
        assert len(lines) == 1
        assert "512" in lines[0]


class TestTestSddLensExemption:
    UNPLANNED_BULLETS = "\n".join(
        f"- `test_case_{index}` in `tests/billing/test_fees_{index}.py` was not in the plan"
        for index in range(12)
    )

    def _unplanned_finding(self):
        heading = "[LOW][test-sdd] Unplanned tests added by the branch"
        return f"### 1. {heading}\n\n{self.UNPLANNED_BULLETS}\n"

    def _auto_review_finding(self, is_suggestion_present):
        body = make_body(
            tag="RECOMMENDED",
            suggestion_label=EN_SUGGESTION if is_suggestion_present else None,
        )
        return f"### 2. [MEDIUM][auto-review] Fee rate unit\n\n{body}\n"

    def test_test_sdd_finding_is_skipped_while_a_same_file_auto_review_finding_is_checked(
        self, tmp_path,
    ):
        assert len(self.UNPLANNED_BULLETS) > NON_MANDATORY_CAP
        text = "# Merged\n\n" + self._unplanned_finding() + "\n" + self._auto_review_finding(False)
        path = write_file(tmp_path, text)
        lines = violations_of(run_script(path))
        assert lines
        assert all(line.startswith(f"{path}: finding 2: ") for line in lines)

        fixed = "# Merged\n\n" + self._unplanned_finding() + "\n" + self._auto_review_finding(True)
        assert_passes(check_text(tmp_path, fixed))

    def test_finding_whose_title_merely_mentions_test_sdd_is_still_checked(self, tmp_path):
        finding = "### 1. [LOW] Rename the test-sdd helper\n\n- no layout here\n"
        lines = violations_of(check_text(tmp_path, "# Merged\n\n" + finding))
        assert all("finding 1:" in line for line in lines)
