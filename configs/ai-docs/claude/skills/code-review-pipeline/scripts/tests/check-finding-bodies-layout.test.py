"""Blackbox CLI tests for check-finding-bodies.py: the layout
of a finding body (severity tag, heading ordinal, suggestion
and trade-off sections).

Usage:
  ./run-tests.py <this file>
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from finding_bodies_support import (
    EN_SUGGESTION,
    EN_TRADEOFF,
    NITPICK_PREFIX,
    PT_SUGGESTION,
    PT_TRADEOFF,
    SUGGESTION_TEXT,
    SUMMARY,
    TRADEOFF_TEXT,
    assert_passes,
    check_text,
    make_body,
    make_finding,
    make_verdict,
    run_script,
    violations_of,
    write_file,
)

TAG_ORDINALS = [
    ("MANDATORY", "HIGH"),
    ("OBRIGATÓRIO", "HIGH"),
    ("RECOMMENDED", "MEDIUM"),
    ("RECOMENDADO", "MEDIUM"),
    ("NITPICK", "LOW"),
    ("OPTIONAL", "LOW"),
    ("OPCIONAL", "LOW"),
    ("QUESTION", "QUESTION"),
    ("PERGUNTA", "QUESTION"),
]


class TestWellFormedFindings:
    def test_english_finding_with_all_sections_passes(self, tmp_path):
        assert_passes(check_text(tmp_path, make_verdict(make_finding())))

    def test_portuguese_finding_with_all_sections_passes(self, tmp_path):
        body = make_body(
            tag="OBRIGATÓRIO", suggestion_label=PT_SUGGESTION,
            tradeoff_label=PT_TRADEOFF,
        )
        assert_passes(check_text(tmp_path, make_verdict(make_finding(body=body))))

    def test_verdict_whose_findings_section_says_none_passes(self, tmp_path):
        assert_passes(check_text(tmp_path, "# Review\n\n## Findings\n\nNone.\n"))

    @pytest.mark.parametrize("tag,ordinal", TAG_ORDINALS)
    def test_each_severity_tag_passes_under_its_matching_heading_ordinal(
        self, tmp_path, tag, ordinal,
    ):
        before_tag = NITPICK_PREFIX if tag == "NITPICK" else None
        body = make_body(tag=tag, before_tag=before_tag)
        finding = make_finding(prefix=f"[{ordinal}]", body=body)
        assert_passes(check_text(tmp_path, make_verdict(finding)))

    def test_question_finding_with_no_concrete_fix_may_omit_the_suggestion(self, tmp_path):
        body = make_body(tag="QUESTION", suggestion_label=None)
        finding = make_finding(prefix="[QUESTION]", body=body)
        assert_passes(check_text(tmp_path, make_verdict(finding)))


class TestSeverityTagLine:
    def test_finding_opening_with_prose_before_the_tag_is_flagged(self, tmp_path):
        body = make_body(before_tag="**CONFIRMED.** The rate is applied twice.")
        path = write_file(tmp_path, make_verdict(make_finding(body=body)))
        lines = violations_of(run_script(path))
        assert len(lines) == 1
        assert lines[0].startswith(f"{path}: finding 1: ")
        assert "severity tag" in lines[0]

    def test_tag_outside_the_allowed_set_is_flagged(self, tmp_path):
        body = make_body(tag="CRITICAL")
        path = write_file(tmp_path, make_verdict(make_finding(body=body)))
        lines = violations_of(run_script(path))
        assert any(
            line.startswith(f"{path}: finding 1: ") and "severity tag" in line
            for line in lines
        )

    def test_tag_without_bold_markup_is_flagged(self, tmp_path):
        body = make_body().replace("**[MANDATORY]**", "[MANDATORY]")
        lines = violations_of(check_text(tmp_path, make_verdict(make_finding(body=body))))
        assert any("severity tag" in line for line in lines)


class TestHeadingOrdinal:
    def test_ordinal_contradicting_the_tag_is_flagged(self, tmp_path):
        path = write_file(tmp_path, make_verdict(make_finding(prefix="[MEDIUM]")))
        lines = violations_of(run_script(path))
        assert len(lines) == 1
        assert lines[0].startswith(f"{path}: finding 1: ")
        assert "[MEDIUM]" in lines[0] and "[HIGH]" in lines[0]

    def test_heading_with_no_ordinal_is_flagged(self, tmp_path):
        text = make_verdict(make_finding(prefix="[Done]"))
        lines = violations_of(check_text(tmp_path, text))
        assert len(lines) == 1
        assert "ordinal" in lines[0]

    def test_ordinal_is_read_between_a_done_mark_and_a_linter_gap_mark(self, tmp_path):
        finding = make_finding(prefix="[Done][HIGH][LINTER GAP]")
        assert_passes(check_text(tmp_path, make_verdict(finding)))


class TestSuggestionSection:
    def test_non_question_finding_without_a_suggestion_line_is_flagged(self, tmp_path):
        body = make_body(tag="RECOMMENDED", suggestion_label=None)
        finding = make_finding(prefix="[MEDIUM]", body=body)
        path = write_file(tmp_path, make_verdict(finding))
        lines = violations_of(run_script(path))
        assert len(lines) == 1
        assert lines[0].startswith(f"{path}: finding 1: ")
        assert "Suggestion" in lines[0]

    def test_suggestion_label_inside_a_code_block_does_not_count(self, tmp_path):
        fenced = "```markdown\n**Suggestion**\n```"
        body = make_body(suggestion_label=None, before_tag=None) + "\n\n" + fenced
        lines = violations_of(check_text(tmp_path, make_verdict(make_finding(body=body))))
        assert any("Suggestion" in line for line in lines)


class TestTradeOffSection:
    @pytest.mark.parametrize("tag,ordinal", [("MANDATORY", "HIGH"), ("QUESTION", "QUESTION")])
    def test_finding_without_a_trade_off_line_is_flagged_even_for_a_question(
        self, tmp_path, tag, ordinal,
    ):
        body = make_body(tag=tag, tradeoff_label=None)
        finding = make_finding(prefix=f"[{ordinal}]", body=body)
        path = write_file(tmp_path, make_verdict(finding))
        lines = violations_of(run_script(path))
        assert len(lines) == 1
        assert lines[0].startswith(f"{path}: finding 1: ")
        assert "Trade-off" in lines[0]

    def test_trade_off_placed_before_the_suggestion_is_flagged(self, tmp_path):
        body = "\n\n".join([
            "**[MANDATORY]**", SUMMARY, EN_TRADEOFF, TRADEOFF_TEXT,
            EN_SUGGESTION, SUGGESTION_TEXT,
        ])
        lines = violations_of(check_text(tmp_path, make_verdict(make_finding(body=body))))
        assert len(lines) == 1
        assert "after" in lines[0]


class TestNitpickBlockquote:
    def test_portuguese_nitpick_opening_with_the_subjective_prefix_passes(self, tmp_path):
        body = make_body(
            tag="NITPICK", before_tag="> Opinião subjetiva - fique à vontade para ignorar.",
            suggestion_label=PT_SUGGESTION, tradeoff_label=PT_TRADEOFF,
        )
        finding = make_finding(prefix="[LOW]", body=body)
        assert_passes(check_text(tmp_path, make_verdict(finding)))

    def test_blockquote_before_a_non_nitpick_tag_is_flagged(self, tmp_path):
        body = make_body(tag="RECOMMENDED", before_tag=NITPICK_PREFIX)
        finding = make_finding(prefix="[MEDIUM]", body=body)
        lines = violations_of(check_text(tmp_path, make_verdict(finding)))
        assert len(lines) == 1
        assert "severity tag" in lines[0]

    def test_two_blockquote_lines_before_a_nitpick_tag_are_flagged(self, tmp_path):
        body = make_body(tag="NITPICK", before_tag=f"{NITPICK_PREFIX}\n> And another aside.")
        finding = make_finding(prefix="[LOW]", body=body)
        lines = violations_of(check_text(tmp_path, make_verdict(finding)))
        assert len(lines) == 1
        assert "severity tag" in lines[0]


class TestEveryFailingCheckIsReported:
    def test_finding_breaking_four_checks_reports_all_four(self, tmp_path):
        filler = "The rate is applied twice on every invoice line. " * 25
        body = "\n\n".join([
            "**CONFIRMED.** How it happens:", "**[MANDATORY]**", filler,
            EN_SUGGESTION, SUGGESTION_TEXT,
        ])
        finding = make_finding(number=7, prefix="[MEDIUM]", body=body)
        path = write_file(tmp_path, make_verdict(finding))
        lines = violations_of(run_script(path))
        assert len(lines) == 4
        assert all(line.startswith(f"{path}: finding 7: ") for line in lines)
        joined = "\n".join(lines)
        assert "severity tag" in joined
        assert "[MEDIUM]" in joined
        assert "Trade-off" in joined
        assert "1024" in joined
