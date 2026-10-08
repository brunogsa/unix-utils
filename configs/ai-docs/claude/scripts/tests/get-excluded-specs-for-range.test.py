"""Blackbox CLI tests for get-excluded-specs-for-range.py.

Fixtures: each test builds a throwaway git repo under tmp_path that
mirrors the shape of the incident this finder exists for - a nested
`core/tsconfig.json` mapping `@orders/*` to `src/modules/orders/*`, a
changed `create-x/index.ts` use case, and an integration spec that
builds it through the alias. Nothing reads or writes the live repo.

Usage:
  pytest configs/ai-docs/claude/scripts/tests/get-excluded-specs-for-range.test.py
"""

import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "get-excluded-specs-for-range.py"

CHANGED_USE_CASE = "core/src/modules/orders/create-x/index.ts"

UNCHANGED_USE_CASE = "core/src/modules/orders/cancel-y/index.ts"

GIT_IDENTITY_ENV = {
    "GIT_AUTHOR_NAME": "Fixture Author",
    "GIT_AUTHOR_EMAIL": "fixture@example.com",
    "GIT_COMMITTER_NAME": "Fixture Author",
    "GIT_COMMITTER_EMAIL": "fixture@example.com",
}


def _git(repo, *args):
    subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
        env={**os.environ, **GIT_IDENTITY_ENV},
    )


def _write(repo, relative_path, content):
    path = repo / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _run(repo, *args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        cwd=repo,
    )


def _init_incident_shaped_repo(repo):
    """Commit the baseline the range will diff against: the tsconfig
    with its alias, two use cases, and no specs yet."""
    _git(repo, "init", "-q")
    _write(
        repo,
        "core/tsconfig.json",
        json.dumps(
            {
                "extends": "../tsconfig.json",
                "compilerOptions": {
                    "baseUrl": "./",
                    "paths": {"@orders/*": ["src/modules/orders/*"]},
                },
            }
        ),
    )
    _write(repo, CHANGED_USE_CASE, "export class CreateX {}\n")
    _write(repo, UNCHANGED_USE_CASE, "export class CancelY {}\n")


def _commit_all(repo, message):
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)


def _change_use_case(repo, relative_path):
    _write(repo, relative_path, "export class Changed { constructor(dep: unknown) {} }\n")
    _commit_all(repo, "change a use case")


class TestFinderListsSpecsReferencingAChangedFile:
    def test_should_list_an_integration_spec_that_imports_the_changed_use_case_through_a_tsconfig_alias(
        self, tmp_path
    ):
        _init_incident_shaped_repo(tmp_path)
        spec = "core/test/modules/orders/consumers/x.consumer.integration.spec.ts"
        _write(tmp_path, spec, "import { CreateX } from '@orders/create-x';\n")
        _commit_all(tmp_path, "baseline")
        _change_use_case(tmp_path, CHANGED_USE_CASE)

        result = _run(tmp_path, "HEAD~1..HEAD")

        assert result.returncode == 0, result.stderr
        assert result.stdout.splitlines() == [spec]

    def test_should_list_an_e2e_spec_that_imports_the_changed_use_case_by_relative_path(
        self, tmp_path
    ):
        _init_incident_shaped_repo(tmp_path)
        spec = "core/src/modules/orders/create-x/create-x.e2e.spec.ts"
        _write(tmp_path, spec, "import { CreateX } from './index';\n")
        _commit_all(tmp_path, "baseline")
        _change_use_case(tmp_path, CHANGED_USE_CASE)

        result = _run(tmp_path, "HEAD~1..HEAD")

        assert result.returncode == 0, result.stderr
        assert result.stdout.splitlines() == [spec]

