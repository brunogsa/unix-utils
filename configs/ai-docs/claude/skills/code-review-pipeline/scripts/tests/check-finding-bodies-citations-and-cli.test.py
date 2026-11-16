"""Blackbox CLI tests for check-finding-bodies.py: internal
rule citations, exit codes and file handling, and the
--findings-json mode.

Usage:
  ./run-tests.py <this file>
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from finding_bodies_support import (
    NON_MANDATORY_CAP,
    PT_SUGGESTION,
    PT_TRADEOFF,
    assert_passes,
    check_text,
    make_body,
    make_finding,
    make_json_finding,
    make_pt_body,
    make_verdict,
    padded_body,
    run_findings_json,
    run_script,
    violations_of,
    write_file,
    write_json_file,
)

PT_CITING_SUMMARY = (
    "resolveLargeMessageBody usa o verbo vago resolve, que o code-standards"
    " pede para trocar por um verbo que nomeie a operação."
)


class TestExitCodesAndFiles:
    def test_no_arguments_exits_two_with_usage_on_stderr(self):
        result = run_script()
        assert result.returncode == 2
        assert "usage" in result.stderr.lower()

    def test_unreadable_path_exits_two_naming_it_on_stderr(self, tmp_path):
        missing = tmp_path / "verdict_missing.md"
        result = run_script(missing)
        assert result.returncode == 2
        assert str(missing) in result.stderr

    def test_one_unreadable_path_among_valid_ones_still_exits_two(self, tmp_path):
        good = write_file(tmp_path, make_verdict(make_finding()))
        result = run_script(good, tmp_path / "verdict_missing.md")
        assert result.returncode == 2

    def test_violations_in_two_files_are_each_reported_under_their_own_path(self, tmp_path):
        first = write_file(tmp_path, make_verdict(make_finding(prefix="[LOW]")), "verdict_a.md")
        second = write_file(tmp_path, make_verdict(make_finding(prefix="[MEDIUM]")), "verdict_b.md")
        lines = violations_of(run_script(first, second))
        assert len(lines) == 2
        assert lines[0].startswith(f"{first}: finding 1: ")
        assert lines[1].startswith(f"{second}: finding 1: ")

    def test_clean_file_beside_a_failing_one_contributes_no_lines(self, tmp_path):
        clean = write_file(tmp_path, make_verdict(make_finding()), "verdict_clean.md")
        failing = write_file(tmp_path, make_verdict(make_finding(prefix="[LOW]")), "verdict_bad.md")
        lines = violations_of(run_script(clean, failing))
        assert len(lines) == 1
        assert lines[0].startswith(f"{failing}: ")


class TestInternalRuleCitations:
    def test_portuguese_body_justified_by_a_standards_skill_is_flagged_naming_it(
        self, tmp_path,
    ):
        body = make_pt_body(PT_CITING_SUMMARY)
        path = write_file(tmp_path, make_verdict(make_finding(body=body)))
        lines = violations_of(run_script(path))
        assert len(lines) == 1
        assert lines[0].startswith(f"{path}: finding 1: ")
        assert '"code-standards"' in lines[0]
        assert "state the principle" in lines[0]

    @pytest.mark.parametrize("citation", [
        "per CLAUDE.md",
        "as AGENTS.md requires",
        "see review-principles",
        "the review-checklists entry says so",
        "the common-preamble forbids it",
        "~/.claude/skills/test-standards/SKILL.md says so",
    ])
    def test_english_body_justified_by_a_private_rule_file_is_flagged(
        self, tmp_path, citation,
    ):
        body = make_body(summary=f"Fees come out 100x too high, which is wrong {citation}.")
        lines = violations_of(check_text(tmp_path, make_verdict(make_finding(body=body))))
        assert lines
        assert all("internal rule source" in line for line in lines)

    def test_each_distinct_cited_source_gets_its_own_reason(self, tmp_path):
        body = make_body(summary="Both code-standards and CLAUDE.md, and code-standards again, say so.")
        lines = violations_of(check_text(tmp_path, make_verdict(make_finding(body=body))))
        assert len(lines) == 2
        assert any('"code-standards"' in line for line in lines)
        assert any('"CLAUDE.md"' in line for line in lines)

    def test_source_named_only_inside_a_code_block_passes(self, tmp_path):
        suggestion = "```diff\n-# see code-standards in CLAUDE.md\n+fee = total * rate / 100\n```"
        body = make_body(suggestion_text=suggestion)
        assert_passes(check_text(tmp_path, make_verdict(make_finding(body=body))))

    def test_finding_on_the_cited_file_itself_may_name_it(self, tmp_path):
        finding = make_finding(
            body=make_pt_body(PT_CITING_SUMMARY),
            location="configs/ai-docs/claude/skills/code-standards/SKILL.md:12-14",
        )
        assert_passes(check_text(tmp_path, make_verdict(finding)))

    def test_finding_on_a_hook_may_cite_its_installed_path_under_home_claude(self, tmp_path):
        body = make_body(summary="Fees come out 100x too high in ~/.claude/hooks/x.sh when the rate is read.")
        finding = make_finding(body=body, location="configs/ai-docs/claude/hooks/x.sh:12-14")
        assert_passes(check_text(tmp_path, make_verdict(finding)))

    def test_finding_on_a_hook_citing_a_different_home_claude_rule_file_is_flagged(
        self, tmp_path,
    ):
        body = make_body(summary="Fees come out 100x too high per ~/.claude/skills/code-standards/SKILL.md.")
        finding = make_finding(body=body, location="configs/ai-docs/claude/hooks/x.sh:12-14")
        lines = violations_of(check_text(tmp_path, make_verdict(finding)))
        assert any("internal rule source" in line for line in lines)

    def test_body_stating_the_principle_without_citing_a_source_passes(self, tmp_path):
        summary = (
            "resolveLargeMessageBody usa o verbo vago resolve: quem lê precisa abrir o corpo"
            " para saber se a função baixa, decodifica ou valida a mensagem."
        )
        body = make_pt_body(summary)
        assert_passes(check_text(tmp_path, make_verdict(make_finding(body=body))))


class TestFindingsJsonMode:
    def test_array_of_well_formed_portuguese_bodies_passes(self, tmp_path):
        nitpick = make_body(
            tag="NITPICK", before_tag="> Opinião subjetiva - fique à vontade para ignorar.",
            suggestion_label=PT_SUGGESTION, tradeoff_label=PT_TRADEOFF,
        )
        findings = [make_json_finding(), make_json_finding(body=nitpick, line=7, severity="low")]
        assert_passes(run_findings_json(write_json_file(tmp_path, findings)))

    def test_body_over_the_512_char_cap_is_flagged_with_its_index_path_and_line(self, tmp_path):
        long_body = padded_body(NON_MANDATORY_CAP + 1, "RECOMENDADO")
        findings = [
            make_json_finding(),
            make_json_finding(body=long_body, path="src/orders/validate.py", line=18),
        ]
        path = write_json_file(tmp_path, findings)
        lines = violations_of(run_findings_json(path))
        assert len(lines) == 1
        assert lines[0].startswith(f"{path}: finding 2 (src/orders/validate.py:18): ")
        assert "513" in lines[0] and "512" in lines[0]

    def test_body_breaking_the_tag_and_section_layout_is_flagged(self, tmp_path):
        body = "**CONFIRMADO.** A taxa é aplicada duas vezes.\n\n" + make_body(
            tag="RECOMENDADO", suggestion_label=None, tradeoff_label=None,
        )
        path = write_json_file(tmp_path, [make_json_finding(body=body)])
        joined = "\n".join(violations_of(run_findings_json(path)))
        assert "severity tag" in joined
        assert "Sugestão" in joined
        assert "Trade-off" in joined

    def test_body_citing_an_internal_rule_source_is_flagged(self, tmp_path):
        path = write_json_file(tmp_path, [make_json_finding(body=make_pt_body(PT_CITING_SUMMARY))])
        lines = violations_of(run_findings_json(path))
        assert lines == [
            f'{path}: finding 1 (src/billing/fees.py:42): body cites internal rule source'
            ' "code-standards"; state the principle and why it matters for this code instead'
        ]

    def test_body_on_the_cited_file_itself_may_name_it(self, tmp_path):
        finding = make_json_finding(
            body=make_pt_body(PT_CITING_SUMMARY),
            path="configs/ai-docs/claude/skills/code-standards/SKILL.md",
        )
        assert_passes(run_findings_json(write_json_file(tmp_path, [finding])))

    def test_heading_checks_do_not_apply_since_a_json_finding_has_no_heading(self, tmp_path):
        path = write_json_file(tmp_path, [make_json_finding(severity="low")])
        assert_passes(run_findings_json(path))

    def test_empty_array_passes(self, tmp_path):
        assert_passes(run_findings_json(write_json_file(tmp_path, [])))


class TestFindingsJsonModeErrors:
    @pytest.mark.parametrize("content,expected", [
        ("[{\"path\": ", "invalid JSON"),
        ('{"path": "a.py", "body": "x"}', "array"),
        ('[{"path": "a.py", "line": 1}]', "body"),
        ('[{"line": 1, "body": "x"}]', "path"),
        ('["just a string"]', "body"),
    ])
    def test_malformed_findings_file_exits_two_explaining_why_on_stderr(
        self, tmp_path, content, expected,
    ):
        path = write_file(tmp_path, content, "wave4-findings.json")
        result = run_findings_json(path)
        assert result.returncode == 2, (result.stdout, result.stderr)
        assert expected in result.stderr
        assert str(path) in result.stderr

    def test_missing_findings_file_exits_two_naming_it_on_stderr(self, tmp_path):
        missing = tmp_path / "wave4-findings.json"
        result = run_findings_json(missing)
        assert result.returncode == 2
        assert str(missing) in result.stderr

    def test_verdict_paths_together_with_findings_json_is_a_usage_error(self, tmp_path):
        verdict = write_file(tmp_path, make_verdict(make_finding()))
        findings = write_json_file(tmp_path, [make_json_finding()])
        result = run_script(verdict, "--findings-json", findings)
        assert result.returncode == 2
        assert "usage" in result.stderr.lower()
