import importlib
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))
declaration = importlib.import_module("quality_metrics.declaration")

SHIPPED_DECLARATION = SCRIPTS_DIR / "quality-metrics.yaml"

DECLARATION_WITH_GO_AND_WEB = """\
excluded_paths:
  - dist/
ignored_extensions: [.md, .txt, .json, .yaml, .yml, .toml]
per_unit: []
languages:
  go:
    extensions: [.go]
    metrics: [crap, size, code_duplication]
  html:
    extensions: [.html]
    metrics: [code_duplication, size]
  css:
    extensions: [.css]
    metrics: [code_duplication, size]
"""

RUST_ENTRY = """\
  rust:
    extensions: [.rs]
    metrics: [crap, size]
"""


def write_declaration(tmp_path, body):
    path = tmp_path / "quality-metrics.yaml"
    path.write_text(body)
    return path


def load_text(tmp_path, body):
    return declaration.load_declaration(write_declaration(tmp_path, body))


class TestHappyPath:
    def test_should_report_a_newly_added_languages_declared_metrics_without_editing_any_other_entry(
        self, tmp_path
    ):
        without_rust = load_text(tmp_path, DECLARATION_WITH_GO_AND_WEB)
        with_rust = load_text(tmp_path, DECLARATION_WITH_GO_AND_WEB + RUST_ENTRY)

        assert with_rust.languages["rust"].metrics == ("crap", "size")
        assert with_rust.languages["go"] == without_rust.languages["go"]
        assert with_rust.languages["html"] == without_rust.languages["html"]

    def test_should_run_per_unit_only_the_metrics_the_per_unit_list_names_and_every_metric_at_batch_end(
        self, tmp_path
    ):
        body = DECLARATION_WITH_GO_AND_WEB.replace("per_unit: []", "per_unit: [size]")
        loaded = load_text(tmp_path, body)

        per_unit = declaration.metrics_to_run(loaded, language="go", mode="per-unit")
        batch_end = declaration.metrics_to_run(loaded, language="go", mode="batch-end")

        assert set(per_unit) == {"size"}
        assert set(batch_end) == {"crap", "size", "code_duplication"}

    def test_should_load_the_shipped_declaration_with_all_seven_languages(self):
        loaded = declaration.load_declaration(SHIPPED_DECLARATION)

        assert set(loaded.languages) == {"js", "ts", "html", "css", "python", "bash", "go"}
        assert loaded.per_unit == ()


class TestCornerCases:
    def test_should_run_a_check_at_batch_end_when_the_per_unit_list_does_not_name_it(
        self, tmp_path
    ):
        loaded = load_text(tmp_path, DECLARATION_WITH_GO_AND_WEB)

        per_unit = declaration.metrics_to_run(loaded, language="go", mode="per-unit")
        batch_end = declaration.metrics_to_run(loaded, language="go", mode="batch-end")

        assert "crap" not in per_unit
        assert "crap" in batch_end


class TestFailureScenarios:
    def test_should_fail_before_measuring_and_name_the_entry_when_a_metric_name_is_unknown(
        self, tmp_path
    ):
        body = DECLARATION_WITH_GO_AND_WEB.replace("[crap, size, code_duplication]", "[crapp]")

        with pytest.raises(declaration.DeclarationError) as raised:
            load_text(tmp_path, body)

        assert "go" in str(raised.value)
        assert "crapp" in str(raised.value)

    def test_should_fail_before_measuring_and_name_the_entry_when_a_language_name_is_unknown(
        self, tmp_path
    ):
        body = DECLARATION_WITH_GO_AND_WEB + "  rust:\n    metrics: [size]\n"

        with pytest.raises(declaration.DeclarationError) as raised:
            load_text(tmp_path, body)

        assert "rust" in str(raised.value)

    def test_should_fail_loudly_when_the_yaml_library_is_missing(self, tmp_path, monkeypatch):
        path = write_declaration(tmp_path, DECLARATION_WITH_GO_AND_WEB)
        monkeypatch.setitem(sys.modules, "yaml", None)

        with pytest.raises(declaration.DeclarationError, match="pyyaml"):
            declaration.load_declaration(path)
