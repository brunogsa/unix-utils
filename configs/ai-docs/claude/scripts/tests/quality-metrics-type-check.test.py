"""type_errors: any type error in a changed file fails."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_support import SCRIPTS_DIR

sys.path.insert(0, str(SCRIPTS_DIR))

from quality_metrics.tools import ToolError
from quality_metrics.touched import Target
from quality_metrics.type_check import type_error_records

CLAUDE_DIR = SCRIPTS_DIR.parent
ERROR_FREE_PYTHON_FILES = [
    "scripts/quality_metrics/gate_inputs.py",
    "skills/implement/scripts/split-forced-refactors.py",
]


def _target(path):
    return Target(Path(path), None, None)


def _write(root, files):
    for name, text in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text)


@pytest.mark.parametrize("relative", ERROR_FREE_PYTHON_FILES)
def test_committed_pyright_config_resolves_every_import_of_a_real_changed_file(relative):
    records = type_error_records(CLAUDE_DIR, [_target(CLAUDE_DIR / relative)])

    rules = [error["rule"] for error in records[0]["errors"]]
    assert "reportMissingImports" not in rules


def test_python_type_error_reports_its_line_and_rule(tmp_path):
    _write(tmp_path, {
        "pkg/pyproject.toml": "[project]\nname = 'pkg'\n",
        "pkg/bad.py": "def double(value: int) -> int:\n    return value * 2\n\n\ndouble('seven')\n",
    })

    records = type_error_records(tmp_path, [_target(tmp_path / "pkg/bad.py")])

    assert len(records) == 1
    assert records[0]["metric"] == "type_errors"
    assert records[0]["value"] == 1
    assert records[0]["limit"] == 0
    assert records[0]["file"] == str(tmp_path / "pkg/bad.py")
    assert records[0]["errors"][0]["line"] == 5
    assert records[0]["errors"][0]["rule"] == "reportArgumentType"


def test_python_file_without_type_errors_reads_zero(tmp_path):
    _write(tmp_path, {"clean.py": "VALUE: int = 3\n"})

    records = type_error_records(tmp_path, [_target(tmp_path / "clean.py")])

    assert records[0]["value"] == 0
    assert records[0]["errors"] == []


TS_CONFIG = '{"compilerOptions": {"strict": true, "noEmit": true}, "include": ["src"]}\n'


def test_typescript_error_in_a_changed_file_gives_a_record(tmp_path):
    _write(tmp_path, {
        "tsconfig.json": TS_CONFIG,
        "src/bad.ts": 'export const count: number = "seven";\n',
    })

    records = type_error_records(tmp_path, [_target(tmp_path / "src/bad.ts")])

    assert records[0]["value"] == 1
    assert records[0]["errors"][0]["line"] == 1
    assert records[0]["errors"][0]["rule"] == "TS2322"
    assert "not assignable" in records[0]["errors"][0]["message"]


def test_typescript_file_the_tsconfig_does_not_include_is_a_tool_error(tmp_path):
    _write(tmp_path, {
        "tsconfig.json": TS_CONFIG,
        "src/ok.ts": "export const one = 1;\n",
        "other/new.ts": "export const two = 2;\n",
    })

    with pytest.raises(ToolError, match="new.ts"):
        type_error_records(tmp_path, [_target(tmp_path / "other/new.ts")])


GO_VET_FAILURE = {
    "go.mod": "module example.com/pkg\n\ngo 1.21\n",
    "main.go": 'package main\n\nimport "fmt"\n\nfunc main() {\n\tfmt.Printf("%d\\n", "text")\n}\n',
}


def test_go_vet_finding_in_a_changed_file_gives_a_record(tmp_path):
    _write(tmp_path, GO_VET_FAILURE)

    records = type_error_records(tmp_path, [_target(tmp_path / "main.go")])

    assert records[0]["value"] == 1
    assert records[0]["errors"][0]["line"] == 6
    assert "wrong type" in records[0]["errors"][0]["message"]


def test_go_vet_finding_in_a_sibling_file_does_not_count_for_the_changed_file(tmp_path):
    _write(tmp_path, GO_VET_FAILURE)
    _write(tmp_path, {"helper.go": "package main\n\nconst Helper = 1\n"})

    records = type_error_records(tmp_path, [_target(tmp_path / "helper.go")])

    assert records[0]["value"] == 0


def test_go_vet_failure_with_no_parseable_line_is_a_tool_error(tmp_path):
    _write(tmp_path, {"orphan.go": "package main\n\nconst Orphan = 1\n"})

    with pytest.raises(ToolError, match="go vet failed"):
        type_error_records(tmp_path, [_target(tmp_path / "orphan.go")])
