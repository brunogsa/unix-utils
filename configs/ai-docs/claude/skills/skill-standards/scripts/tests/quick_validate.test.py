"""Blackbox CLI tests for quick_validate.py.

Fixtures: none on disk except what each test writes to tmp_path.
Every skill directory the tests write and read lives under
tmp_path - never against the live skills tree, which
concurrent sibling tasks are actively editing.

Usage:
  ./run-tests.py <this file>
"""

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "quick_validate.py"


def _validate(tmp_path, extra_frontmatter):
    skill_dir = tmp_path / "demo-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: demo-skill\n"
        "description: Summarizes a quarterly sales report for the finance team.\n"
        f"{extra_frontmatter}\n"
        "---\n"
        "\n"
        "# Demo skill\n"
    )
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(skill_dir)],
        capture_output=True,
        text=True,
    )


def test_accepts_disable_model_invocation_key_that_claude_code_supports(tmp_path):
    result = _validate(tmp_path, "disable-model-invocation: true")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Skill is valid!" in result.stdout


def test_still_rejects_an_unknown_frontmatter_key(tmp_path):
    result = _validate(tmp_path, "bogus-key: 1")

    assert result.returncode == 1
    assert "Unexpected key(s)" in result.stdout
    assert "bogus-key" in result.stdout
