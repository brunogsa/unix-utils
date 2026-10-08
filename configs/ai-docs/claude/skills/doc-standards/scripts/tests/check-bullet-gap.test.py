"""Tests for check-bullet-gap.py's report mode.

The --fix and --changed-only contracts live in test-check-bullet-gap-fix.sh;
this file covers which list shapes the scan reports at all.
"""

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "check-bullet-gap.py"


def run(tmp_path, content):
    """Write one fixture and run the checker over it as a subprocess, the way
    the prose-format PostToolUse hook calls it."""
    path = tmp_path / "doc.md"
    path.write_text(content, encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(path)],
        capture_output=True,
        text=True,
    )


def hits(result):
    """The `<line>:<detail>` rows as [(int, str)], dropping the `==` header.

    Asserts the checker actually ran first (exit 0 or 1): a crash prints no
    rows, which would otherwise pass every "is not reported" test.
    """
    assert result.returncode in (0, 1), result.stderr
    rows = []
    for line in result.stdout.splitlines():
        if not line.strip() or line.startswith("== "):
            continue
        number, detail = line.split(":", 1)
        rows.append((int(number), detail))
    return rows


def test_should_accept_a_team_pr_template_checklist_whose_nested_checkboxes_have_no_blank_lines(tmp_path):
    # Shape of the Checklist section in a team repo's
    # .github/PULL_REQUEST_TEMPLATE.md, which PR bodies
    # copy verbatim.
    content = (
        "Esse PR:\n"
        "\n"
        "- [x] Foi testado localmente\n"
        "- [ ] Nova migração no DB\n"
        "  - [X] Ativado run-migrations nas pipelines de qa, stage e prod\n"
        "- [ ] Novos recursos de infra que precisam ser criados no localstack\n"
        "  - [ ] Fila nova adicionada em scripts/testing/local-resources/setup_sqs.sh\n"
        "  - [ ] Tópico novo adicionado em scripts/testing/local-resources/setup_sns.sh\n"
        "- [ ] Nova variavel de ambiente\n"
    )

    result = run(tmp_path, content)

    assert hits(result) == []
    assert result.returncode == 0


def test_should_still_report_a_plain_nested_bullet_list_with_no_blank_line_after_the_child(tmp_path):
    content = (
        "- Retry the upload when the bucket returns 503\n"
        "  - Cap the retries at three attempts\n"
        "- Log the final failure with the object key\n"
    )

    result = run(tmp_path, content)

    assert hits(result) == [(2, "sub-bullet")]
    assert result.returncode == 1


def test_should_still_report_a_nested_checkbox_ending_flush_against_a_plain_bullet(tmp_path):
    content = (
        "- [ ] Nova variavel de ambiente\n"
        "  - [ ] cadastrada na AWS (QA, STAGE, PROD)\n"
        "- Observações do revisor sobre o deploy\n"
    )

    result = run(tmp_path, content)

    assert hits(result) == [(2, "sub-bullet")]
    assert result.returncode == 1
