"""Blackbox CLI tests for check-finding-bodies.py.

Every case writes its own verdict .md under tmp_path and reads the
script's stdout/stderr/exit code back, so nothing depends on any file
outside tmp_path or the script itself.

Usage:
  pytest configs/ai-docs/claude/skills/code-review-pipeline/scripts/tests/check-finding-bodies.test.py
"""

import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent.parent / "check-finding-bodies.py"

SUMMARY = "Fees come out 100x too high because the rate unit is wrong."
SUGGESTION_TEXT = "Divide the percentage by 100 before multiplying the invoice total."
TRADEOFF_TEXT = "- [-] A R$ 1,058.33 invoice gets billed R$ 105,833.00 in fees."

EN_SUGGESTION = "**Suggestion**"
EN_TRADEOFF = "**Trade-off of not doing it**"
PT_SUGGESTION = "**Sugestão**"
PT_TRADEOFF = "**Trade-off de não fazer**"

NITPICK_PREFIX = "> Subjective opinion - feel free to ignore."

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

NON_MANDATORY_CAP = 512
MANDATORY_CAP = 1024
MANDATORY_LINE_CAP = 16


def _body(
    tag: str = "MANDATORY",
    summary: str = SUMMARY,
    suggestion_label: str | None = EN_SUGGESTION,
    tradeoff_label: str | None = EN_TRADEOFF,
    before_tag: str | None = None,
    suggestion_text: str = SUGGESTION_TEXT,
    tradeoff_text: str = TRADEOFF_TEXT,
) -> str:
    """Build a finding body; a None label or text drops that part."""
    parts = [
        before_tag,
        f"**[{tag}]**",
        summary,
        suggestion_label,
        suggestion_text if suggestion_label else None,
        tradeoff_label,
        tradeoff_text if tradeoff_label else None,
    ]
    return "\n\n".join(part for part in parts if part is not None)


def _finding(number=1, prefix="[HIGH]", body=None):
    body = _body() if body is None else body
    return f"### {number}. {prefix} `src/billing/fees.py:42-48`\n\n{body}\n"


def _verdict(*findings):
    return "# Auto Review: main vs 1a2b3c4d\n\n## Findings\n\n" + "\n".join(findings)


def _write(tmp_path, text, name="verdict.md"):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def _run(*paths):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *[str(p) for p in paths]],
        capture_output=True, text=True, encoding="utf-8",
    )


def _check(tmp_path, text):
    return _run(_write(tmp_path, text))


def _violations(result):
    assert result.returncode == 1, (result.returncode, result.stdout, result.stderr)
    return result.stdout.splitlines()


def _assert_passes(result):
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert result.stdout == ""


def _padded_body(length, tag):
    """A well-formed body whose stripped text is exactly `length` chars."""
    base = _body(tag=tag, summary="")
    filler = ("The rate unit is wrong. " * 60)[: length - len(base)]
    return _body(tag=tag, summary=filler)


class TestWellFormedFindings:
    def test_english_finding_with_all_sections_passes(self, tmp_path):
        _assert_passes(_check(tmp_path, _verdict(_finding())))

    def test_portuguese_finding_with_all_sections_passes(self, tmp_path):
        body = _body(
            tag="OBRIGATÓRIO", suggestion_label=PT_SUGGESTION,
            tradeoff_label=PT_TRADEOFF,
        )
        _assert_passes(_check(tmp_path, _verdict(_finding(body=body))))

    def test_verdict_whose_findings_section_says_none_passes(self, tmp_path):
        _assert_passes(_check(tmp_path, "# Review\n\n## Findings\n\nNone.\n"))

    @pytest.mark.parametrize("tag,ordinal", TAG_ORDINALS)
    def test_each_severity_tag_passes_under_its_matching_heading_ordinal(
        self, tmp_path, tag, ordinal,
    ):
        before_tag = NITPICK_PREFIX if tag == "NITPICK" else None
        body = _body(tag=tag, before_tag=before_tag)
        result = _check(tmp_path, _verdict(_finding(prefix=f"[{ordinal}]", body=body)))
        _assert_passes(result)

    def test_question_finding_with_no_concrete_fix_may_omit_the_suggestion(self, tmp_path):
        body = _body(tag="QUESTION", suggestion_label=None)
        _assert_passes(_check(tmp_path, _verdict(_finding(prefix="[QUESTION]", body=body))))


class TestSeverityTagLine:
    def test_finding_opening_with_prose_before_the_tag_is_flagged(self, tmp_path):
        body = _body(before_tag="**CONFIRMED.** The rate is applied twice.")
        path = _write(tmp_path, _verdict(_finding(body=body)))
        lines = _violations(_run(path))
        assert len(lines) == 1
        assert lines[0].startswith(f"{path}: finding 1: ")
        assert "severity tag" in lines[0]

    def test_tag_outside_the_allowed_set_is_flagged(self, tmp_path):
        body = _body(tag="CRITICAL")
        path = _write(tmp_path, _verdict(_finding(body=body)))
        lines = _violations(_run(path))
        assert any(
            line.startswith(f"{path}: finding 1: ") and "severity tag" in line
            for line in lines
        )

    def test_tag_without_bold_markup_is_flagged(self, tmp_path):
        body = _body().replace("**[MANDATORY]**", "[MANDATORY]")
        lines = _violations(_check(tmp_path, _verdict(_finding(body=body))))
        assert any("severity tag" in line for line in lines)


class TestHeadingOrdinal:
    def test_ordinal_contradicting_the_tag_is_flagged(self, tmp_path):
        path = _write(tmp_path, _verdict(_finding(prefix="[MEDIUM]")))
        lines = _violations(_run(path))
        assert len(lines) == 1
        assert lines[0].startswith(f"{path}: finding 1: ")
        assert "[MEDIUM]" in lines[0] and "[HIGH]" in lines[0]

    def test_heading_with_no_ordinal_is_flagged(self, tmp_path):
        lines = _violations(_check(tmp_path, _verdict(_finding(prefix="[Done]"))))
        assert len(lines) == 1
        assert "ordinal" in lines[0]

    def test_ordinal_is_read_between_a_done_mark_and_a_linter_gap_mark(self, tmp_path):
        finding = _finding(prefix="[Done][HIGH][LINTER GAP]")
        _assert_passes(_check(tmp_path, _verdict(finding)))


class TestSuggestionSection:
    def test_non_question_finding_without_a_suggestion_line_is_flagged(self, tmp_path):
        body = _body(tag="RECOMMENDED", suggestion_label=None)
        path = _write(tmp_path, _verdict(_finding(prefix="[MEDIUM]", body=body)))
        lines = _violations(_run(path))
        assert len(lines) == 1
        assert lines[0].startswith(f"{path}: finding 1: ")
        assert "Suggestion" in lines[0]

    def test_suggestion_label_inside_a_code_block_does_not_count(self, tmp_path):
        fenced = "```markdown\n**Suggestion**\n```"
        body = _body(suggestion_label=None, before_tag=None) + "\n\n" + fenced
        lines = _violations(_check(tmp_path, _verdict(_finding(body=body))))
        assert any("Suggestion" in line for line in lines)


class TestTradeOffSection:
    @pytest.mark.parametrize("tag,ordinal", [("MANDATORY", "HIGH"), ("QUESTION", "QUESTION")])
    def test_finding_without_a_trade_off_line_is_flagged_even_for_a_question(
        self, tmp_path, tag, ordinal,
    ):
        body = _body(tag=tag, tradeoff_label=None)
        path = _write(tmp_path, _verdict(_finding(prefix=f"[{ordinal}]", body=body)))
        lines = _violations(_run(path))
        assert len(lines) == 1
        assert lines[0].startswith(f"{path}: finding 1: ")
        assert "Trade-off" in lines[0]

    def test_trade_off_placed_before_the_suggestion_is_flagged(self, tmp_path):
        body = "\n\n".join([
            "**[MANDATORY]**", SUMMARY, EN_TRADEOFF, TRADEOFF_TEXT,
            EN_SUGGESTION, SUGGESTION_TEXT,
        ])
        lines = _violations(_check(tmp_path, _verdict(_finding(body=body))))
        assert len(lines) == 1
        assert "after" in lines[0]


class TestLengthBudget:
    @pytest.mark.parametrize("tag,ordinal", [("RECOMMENDED", "MEDIUM"), ("NITPICK", "LOW")])
    def test_non_mandatory_body_at_512_chars_passes(self, tmp_path, tag, ordinal):
        body = _padded_body(NON_MANDATORY_CAP, tag)
        result = _check(tmp_path, _verdict(_finding(prefix=f"[{ordinal}]", body=body)))
        _assert_passes(result)

    def test_non_mandatory_body_at_513_chars_is_flagged_with_measure_and_cap(self, tmp_path):
        body = _padded_body(NON_MANDATORY_CAP + 1, "RECOMMENDED")
        path = _write(tmp_path, _verdict(_finding(prefix="[MEDIUM]", body=body)))
        lines = _violations(_run(path))
        assert len(lines) == 1
        assert lines[0].startswith(f"{path}: finding 1: ")
        assert "513" in lines[0] and "512" in lines[0]

    def test_mandatory_body_at_1024_chars_passes(self, tmp_path):
        body = _padded_body(MANDATORY_CAP, "MANDATORY")
        _assert_passes(_check(tmp_path, _verdict(_finding(body=body))))

    def test_mandatory_body_at_1025_chars_is_flagged_with_measure_and_cap(self, tmp_path):
        body = _padded_body(MANDATORY_CAP + 1, "MANDATORY")
        lines = _violations(_check(tmp_path, _verdict(_finding(body=body))))
        assert len(lines) == 1
        assert "1025" in lines[0] and "1024" in lines[0]

    def test_mandatory_body_over_16_non_blank_lines_is_flagged_with_measure_and_cap(
        self, tmp_path,
    ):
        bullets = "\n".join(f"- [-] Invoice {n} is overbilled." for n in range(1, 13))
        body = _body(tradeoff_text=bullets)
        lines = _violations(_check(tmp_path, _verdict(_finding(body=body))))
        assert len(lines) == 1
        assert "17" in lines[0] and "16" in lines[0]

    def test_mandatory_body_with_blank_lines_between_16_lines_passes(self, tmp_path):
        bullets = "\n\n".join(f"- [-] Invoice {n} is overbilled." for n in range(1, 12))
        _assert_passes(_check(tmp_path, _verdict(_finding(body=_body(tradeoff_text=bullets)))))

    def test_fenced_code_block_counts_toward_neither_chars_nor_lines(self, tmp_path):
        code_lines = "\n".join(f"+    fee_{n} = total * rate / 100" for n in range(40))
        suggestion = f"```diff\n{code_lines}\n```"
        body = _body(tag="RECOMMENDED", suggestion_text=suggestion)
        _assert_passes(_check(tmp_path, _verdict(_finding(prefix="[MEDIUM]", body=body))))


class TestFindingBoundaries:
    def test_horizontal_rule_ends_the_finding_so_text_after_it_is_not_charged(self, tmp_path):
        appendix = "Appendix. " * 80
        text = _verdict(_finding(prefix="[MEDIUM]", body=_body(tag="RECOMMENDED")))
        _assert_passes(_check(tmp_path, f"{text}\n---\n\n{appendix}\n"))

    def test_level_two_heading_ends_the_finding_so_text_after_it_is_not_charged(
        self, tmp_path,
    ):
        appendix = "Appendix. " * 80
        text = _verdict(_finding(prefix="[MEDIUM]", body=_body(tag="RECOMMENDED")))
        _assert_passes(_check(tmp_path, f"{text}\n## Counts\n\n{appendix}\n"))

    def test_hash_comment_inside_a_code_block_does_not_end_the_finding(self, tmp_path):
        suggestion = "```diff\n# src/billing/fees.py\n-fee = total * rate\n+fee = total * rate / 100\n```"
        body = _body(suggestion_text=suggestion)
        _assert_passes(_check(tmp_path, _verdict(_finding(body=body))))

    def test_each_finding_is_reported_under_its_own_number(self, tmp_path):
        text = _verdict(
            _finding(number=1),
            _finding(number=2, body=_body(tradeoff_label=None)),
        )
        path = _write(tmp_path, text)
        lines = _violations(_run(path))
        assert len(lines) == 1
        assert lines[0].startswith(f"{path}: finding 2: ")


class TestAddressVerdictsAnnotations:
    @pytest.mark.parametrize("annotation", [
        "APPLIED (fa169db4) - the rate is divided by 100 before billing.",
        "SKIPPED (the rate is already a fraction upstream)",
    ])
    def test_annotation_line_before_the_tag_is_ignored(self, tmp_path, annotation):
        body = _body(before_tag=annotation)
        _assert_passes(_check(tmp_path, _verdict(_finding(prefix="[Done][HIGH]", body=body))))

    def test_long_annotation_line_is_not_charged_against_the_budget(self, tmp_path):
        annotation = "APPLIED (fa169db4) - " + "verified on staging. " * 30
        body = annotation + "\n\n" + _padded_body(NON_MANDATORY_CAP, "RECOMMENDED")
        result = _check(tmp_path, _verdict(_finding(prefix="[Done][MEDIUM]", body=body)))
        _assert_passes(result)


class TestNitpickBlockquote:
    def test_portuguese_nitpick_opening_with_the_subjective_prefix_passes(self, tmp_path):
        body = _body(
            tag="NITPICK", before_tag="> Opinião subjetiva - fique à vontade para ignorar.",
            suggestion_label=PT_SUGGESTION, tradeoff_label=PT_TRADEOFF,
        )
        _assert_passes(_check(tmp_path, _verdict(_finding(prefix="[LOW]", body=body))))

    def test_blockquote_before_a_non_nitpick_tag_is_flagged(self, tmp_path):
        body = _body(tag="RECOMMENDED", before_tag=NITPICK_PREFIX)
        lines = _violations(_check(tmp_path, _verdict(_finding(prefix="[MEDIUM]", body=body))))
        assert len(lines) == 1
        assert "severity tag" in lines[0]

    def test_two_blockquote_lines_before_a_nitpick_tag_are_flagged(self, tmp_path):
        body = _body(tag="NITPICK", before_tag=f"{NITPICK_PREFIX}\n> And another aside.")
        lines = _violations(_check(tmp_path, _verdict(_finding(prefix="[LOW]", body=body))))
        assert len(lines) == 1
        assert "severity tag" in lines[0]


class TestEveryFailingCheckIsReported:
    def test_finding_breaking_four_checks_reports_all_four(self, tmp_path):
        filler = "The rate is applied twice on every invoice line. " * 25
        body = "\n\n".join([
            "**CONFIRMED.** How it happens:", "**[MANDATORY]**", filler,
            EN_SUGGESTION, SUGGESTION_TEXT,
        ])
        path = _write(tmp_path, _verdict(_finding(number=7, prefix="[MEDIUM]", body=body)))
        lines = _violations(_run(path))
        assert len(lines) == 4
        assert all(line.startswith(f"{path}: finding 7: ") for line in lines)
        joined = "\n".join(lines)
        assert "severity tag" in joined
        assert "[MEDIUM]" in joined
        assert "Trade-off" in joined
        assert "1024" in joined


class TestExitCodesAndFiles:
    def test_no_arguments_exits_two_with_usage_on_stderr(self):
        result = _run()
        assert result.returncode == 2
        assert "usage" in result.stderr.lower()

    def test_unreadable_path_exits_two_naming_it_on_stderr(self, tmp_path):
        missing = tmp_path / "verdict_missing.md"
        result = _run(missing)
        assert result.returncode == 2
        assert str(missing) in result.stderr

    def test_one_unreadable_path_among_valid_ones_still_exits_two(self, tmp_path):
        good = _write(tmp_path, _verdict(_finding()))
        result = _run(good, tmp_path / "verdict_missing.md")
        assert result.returncode == 2

    def test_violations_in_two_files_are_each_reported_under_their_own_path(self, tmp_path):
        first = _write(tmp_path, _verdict(_finding(prefix="[LOW]")), "verdict_a.md")
        second = _write(tmp_path, _verdict(_finding(prefix="[MEDIUM]")), "verdict_b.md")
        lines = _violations(_run(first, second))
        assert len(lines) == 2
        assert lines[0].startswith(f"{first}: finding 1: ")
        assert lines[1].startswith(f"{second}: finding 1: ")

    def test_clean_file_beside_a_failing_one_contributes_no_lines(self, tmp_path):
        clean = _write(tmp_path, _verdict(_finding()), "verdict_clean.md")
        failing = _write(tmp_path, _verdict(_finding(prefix="[LOW]")), "verdict_bad.md")
        lines = _violations(_run(clean, failing))
        assert len(lines) == 1
        assert lines[0].startswith(f"{failing}: ")
