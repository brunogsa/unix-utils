"""Builders and runners the check-finding-bodies suites share.

Every case writes its own verdict .md under tmp_path and
reads the script's stdout/stderr/exit code back, so nothing
depends on any file outside tmp_path or the script itself.

Named without a `.test.py` or `test_` marker, so pytest
imports it and never collects it.
"""

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "check-finding-bodies.py"

SUMMARY = "Fees come out 100x too high because the rate unit is wrong."
SUGGESTION_TEXT = "Divide the percentage by 100 before multiplying the invoice total."
TRADEOFF_TEXT = "- [-] A R$ 1,058.33 invoice gets billed R$ 105,833.00 in fees."

EN_SUGGESTION = "**Suggestion**"
EN_TRADEOFF = "**Trade-off of not doing it**"
PT_SUGGESTION = "**Sugestão**"
PT_TRADEOFF = "**Trade-off de não fazer**"

NITPICK_PREFIX = "> Subjective opinion - feel free to ignore."

NON_MANDATORY_CAP = 512
MANDATORY_CAP = 1024


@dataclass
class BodyParts:
    """The parts of a finding body; a None label or text drops
    that part."""

    tag: str = "MANDATORY"
    summary: str = SUMMARY
    suggestion_label: str | None = EN_SUGGESTION
    tradeoff_label: str | None = EN_TRADEOFF
    before_tag: str | None = None
    suggestion_text: str = SUGGESTION_TEXT
    tradeoff_text: str = TRADEOFF_TEXT


def make_body(tag: str = "MANDATORY", **overrides) -> str:
    """Build a finding body from the BodyParts defaults, with
    `overrides` naming the BodyParts fields to change."""
    parts = BodyParts(tag=tag, **overrides)
    pieces = [
        parts.before_tag,
        f"**[{parts.tag}]**",
        parts.summary,
        parts.suggestion_label,
        parts.suggestion_text if parts.suggestion_label else None,
        parts.tradeoff_label,
        parts.tradeoff_text if parts.tradeoff_label else None,
    ]
    return "\n\n".join(piece for piece in pieces if piece is not None)


def make_pt_body(summary: str) -> str:
    return make_body(
        tag="OBRIGATÓRIO", summary=summary,
        suggestion_label=PT_SUGGESTION, tradeoff_label=PT_TRADEOFF,
    )


def make_finding(number=1, prefix="[HIGH]", body=None, location="src/billing/fees.py:42-48"):
    body = make_body() if body is None else body
    return f"### {number}. {prefix} `{location}`\n\n{body}\n"


def make_verdict(*findings):
    return "# Auto Review: main vs 1a2b3c4d\n\n## Findings\n\n" + "\n".join(findings)


def write_file(tmp_path, text, name="verdict.md"):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def run_script(*args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *[str(arg) for arg in args]],
        capture_output=True, text=True, encoding="utf-8",
    )


def check_text(tmp_path, text):
    return run_script(write_file(tmp_path, text))


def violations_of(result):
    assert result.returncode == 1, (result.returncode, result.stdout, result.stderr)
    return result.stdout.splitlines()


def assert_passes(result):
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert result.stdout == ""


def padded_body(length, tag):
    """A well-formed body whose stripped text is exactly
    `length` chars."""
    base = make_body(tag=tag, summary="")
    filler = ("The rate unit is wrong. " * 60)[: length - len(base)]
    return make_body(tag=tag, summary=filler)


def make_json_finding(body=None, path="src/billing/fees.py", line=42, severity="high"):
    body = make_pt_body(SUMMARY) if body is None else body
    return {"path": path, "line": line, "severity": severity, "body": body}


def write_json_file(tmp_path, findings):
    text = json.dumps(findings, ensure_ascii=False)
    return write_file(tmp_path, text, "wave4-findings.json")


def run_findings_json(path):
    return run_script("--findings-json", path)
