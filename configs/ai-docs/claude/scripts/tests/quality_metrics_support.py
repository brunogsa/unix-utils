"""Temp-git-repo and measure-script helpers the quality-metrics suites share.

Named without a `.test.py` or `test_` marker, so pytest imports it
and never collects it.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
MEASURE_SCRIPT = SCRIPTS_DIR / "measure-quality-metrics.py"
SHIPPED_DECLARATION = SCRIPTS_DIR / "quality-metrics.yaml"

GIT_ENV = {
    **os.environ,
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "Fixture Author",
    "GIT_AUTHOR_EMAIL": "fixture.author@example.com",
    "GIT_COMMITTER_NAME": "Fixture Author",
    "GIT_COMMITTER_EMAIL": "fixture.author@example.com",
}


# A jest dying on an internal error: a stack trace, no report.
JEST_CRASH_STUB = """#!/bin/bash
echo "TypeError: Cannot read properties of undefined (reading 'config')" >&2
echo "    at Object.run (/repo/node_modules/jest-cli/build/run.js:31:18)" >&2
exit 1
"""


def install_stub_tool(tmp_path, monkeypatch, name, script):
    """Put an executable `name` first on PATH, standing in for a real tool."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    stub = bin_dir / name
    stub.write_text(script)
    stub.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")


def git(repo, *args):
    subprocess.run(["git", *args], cwd=repo, env=GIT_ENV, check=True, capture_output=True)


def make_repo(tmp_path, files):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "--quiet", "--initial-branch=main")
    for name, text in files.items():
        (repo / name).parent.mkdir(parents=True, exist_ok=True)
        (repo / name).write_text(text)
    git(repo, "add", "--all")
    git(repo, "commit", "--quiet", "-m", "base")
    return repo


def commit_all(repo, message):
    git(repo, "add", "--all")
    git(repo, "commit", "--quiet", "-m", message)


def head_of(repo):
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, env=GIT_ENV, check=True, capture_output=True, text=True
    ).stdout.strip()


def run_measure(repo, declaration_path, *arguments, env=None):
    return subprocess.run(
        [sys.executable, str(MEASURE_SCRIPT), *arguments, "--declaration", str(declaration_path)],
        cwd=repo, env=env or GIT_ENV, capture_output=True, text=True,
    )


COVERAGE_DECLARATION_TEXT = """\
excluded_paths: []
ignored_extensions: [.md]
per_unit: []
languages:
  js:
    extensions: [.js]
    metrics: [coverage]
  ts:
    extensions: [.ts]
    metrics: [coverage]
  python:
    extensions: [.py]
    metrics: [coverage]
"""


def coverage_records_of(tmp_path, target, coverage_run):
    """The coverage records `crap_coverage.measure` gives one target.

    Imports sit inside the function because a suite puts
    SCRIPTS_DIR on sys.path only after importing this module.
    """
    from quality_metrics import crap_coverage
    from quality_metrics.declaration import load_declaration

    declaration_path = tmp_path / "coverage-declaration.yaml"
    declaration_path.write_text(COVERAGE_DECLARATION_TEXT)
    return crap_coverage.measure(
        target, ["coverage"], load_declaration(declaration_path), coverage_run
    )


def install_global_collector(monkeypatch, calls, hits_by_file=None, error=None):
    """Stand in for the global coverage collector of every language.

    Records each call in `calls`; raises `error` when given, else
    reports `hits_by_file`.
    """
    from quality_metrics import collection

    def collector(repo_dir):
        calls.append(repo_dir)
        if error is not None:
            raise error
        return collection.CoverageResult(hits_by_file or {}, False)

    for language in ("js", "ts", "python"):
        monkeypatch.setitem(collection.COLLECTORS, language, collector)


def measure_report(repo, declaration_path, *arguments, env=None):
    """The measure script's parsed JSON report; fails loudly on no output."""
    result = run_measure(repo, declaration_path, *arguments, env=env)
    assert result.stdout, f"no output; stderr: {result.stderr}"
    return json.loads(result.stdout)
