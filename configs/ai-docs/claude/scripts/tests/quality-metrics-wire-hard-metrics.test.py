import importlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_support import (
    SCRIPTS_DIR, commit_all, head_of, install_stub_tool,
    load_measure_script, make_repo, run_measure,
)

sys.path.insert(0, str(SCRIPTS_DIR))

declaring = importlib.import_module("quality_metrics.declaration")
measuring = importlib.import_module("quality_metrics.measuring")
type_check = importlib.import_module("quality_metrics.type_check")
tools = importlib.import_module("quality_metrics.tools")

DECLARATION = """\
excluded_paths: []
ignored_extensions: [.md, .json, .yaml, .toml]
per_unit: []
languages:
  python:
    extensions: [.py]
    metrics: [unused_code, type_errors]
"""

CLEAN_MODULE = "def total(items):\n    return sum(items)\n"
UNUSED_IMPORT_MODULE = "import os\n\n\n" + CLEAN_MODULE
TYPE_ERROR_MODULE = CLEAN_MODULE + '\nlimit: int = "ten"\n'
MISSING_TOOL_STUB = "#!/bin/sh\necho 'uvx: not found' >&2\nexit 127\n"


def write_declaration(tmp_path):
    path = tmp_path / "quality-metrics.yaml"
    path.write_text(DECLARATION)
    return path


def records_of(result, key, metric):
    return [item for item in json.loads(result.stdout)[key] if item["metric"] == metric]


class TestUnusedCodeAtBatchEnd:
    def test_should_report_an_unused_import_as_an_open_violation_and_exit_1(self, tmp_path):
        repo = make_repo(tmp_path, {"cart.py": CLEAN_MODULE})
        (repo / "cart.py").write_text(UNUSED_IMPORT_MODULE)

        result = run_measure(repo, write_declaration(tmp_path), "--batch-end")

        found = records_of(result, "violations", "unused_code")
        assert result.returncode == 1
        assert [item["value"] for item in found] == [1]
        assert found[0]["findings"] == [{"line": 1, "rule": "F401", "name": "os"}]


class TestTypeErrorsAtDiff:
    def test_should_list_the_pyright_error_of_a_changed_file_and_none_for_an_unchanged_one(
        self, tmp_path
    ):
        repo = make_repo(
            tmp_path,
            {"cart.py": CLEAN_MODULE, "legacy.py": TYPE_ERROR_MODULE},
        )
        base = head_of(repo)
        (repo / "cart.py").write_text(TYPE_ERROR_MODULE)
        commit_all(repo, "add a type error")

        result = run_measure(repo, write_declaration(tmp_path), "--diff", f"{base}...HEAD")

        found = records_of(result, "violations", "type_errors")
        assert result.returncode == 1
        assert [Path(item["file"]).name for item in found] == ["cart.py"]
        error = found[0]["errors"][0]
        assert error["line"] == 4
        assert error["rule"] == "reportAssignmentType"
        assert 'Literal[\'ten\']' in error["message"]


class TestMissingTool:
    def run_main(self, repo, tmp_path, capsys, *extra):
        script = load_measure_script()
        code = script.main(
            ["--batch-end", "--declaration", str(write_declaration(tmp_path)), *extra]
        )
        return code, capsys.readouterr()

    def prepare(self, tmp_path, monkeypatch):
        repo = make_repo(tmp_path, {"cart.py": CLEAN_MODULE})
        (repo / "cart.py").write_text(UNUSED_IMPORT_MODULE)
        (tmp_path / "maps").mkdir()
        monkeypatch.chdir(repo)
        monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "cli")
        return repo

    def test_should_flag_unused_code_pessimistically_and_ask_when_ruff_is_missing(
        self, tmp_path, monkeypatch, capsys
    ):
        repo = self.prepare(tmp_path, monkeypatch)
        install_stub_tool(tmp_path, monkeypatch, "uvx", MISSING_TOOL_STUB)

        code, output = self.run_main(
            repo, tmp_path, capsys, "--session-id", "s-w1", "--map-dir", str(tmp_path / "maps")
        )

        report = json.loads(output.out)
        flagged = [item for item in report["violations"] if item["metric"] == "unused_code"]
        assert code == 1
        assert [(item["value"], item["pessimistic"]) for item in flagged] == [(1, True)]
        assert [(ask["tool"], ask["metric"]) for ask in report["asks"]] == [("ruff", "unused_code")]

    def test_should_flag_type_errors_pessimistically_and_ask_when_pyright_fails(
        self, tmp_path, monkeypatch, capsys
    ):
        repo = self.prepare(tmp_path, monkeypatch)

        def failing(tree, targets):
            raise tools.ToolError("pyright gave no JSON report")

        monkeypatch.setattr(type_check, "type_error_records", failing)
        (repo / "cart.py").write_text(CLEAN_MODULE + "# changed\n")

        code, output = self.run_main(
            repo, tmp_path, capsys, "--session-id", "s-w1", "--map-dir", str(tmp_path / "maps")
        )

        report = json.loads(output.out)
        flagged = [item for item in report["violations"] if item["metric"] == "type_errors"]
        assert code == 1
        assert [(item["value"], item["pessimistic"]) for item in flagged] == [(1, True)]
        assert ("pyright", "type_errors") in [(ask["tool"], ask["metric"]) for ask in report["asks"]]

    def test_should_exit_2_when_a_metric_tool_is_missing_and_there_is_no_tool_map(
        self, tmp_path, monkeypatch, capsys
    ):
        repo = self.prepare(tmp_path, monkeypatch)
        install_stub_tool(tmp_path, monkeypatch, "uvx", MISSING_TOOL_STUB)

        code, output = self.run_main(repo, tmp_path, capsys)

        assert code == 2
        assert output.out == ""
        assert "uvx" in output.err


class TestBaseSidePass:
    def test_should_skip_unused_code_and_type_errors_when_measuring_a_base_side_copy(
        self, tmp_path
    ):
        copy_path = tmp_path / "cart.py"
        copy_path.write_text(UNUSED_IMPORT_MODULE + 'limit: int = "ten"\n')
        declaration = declaring.load_declaration(write_declaration(tmp_path))

        found = measuring._measure_at_base(declaration, "batch-end", None, copy_path, "cart.py")

        assert found == []
