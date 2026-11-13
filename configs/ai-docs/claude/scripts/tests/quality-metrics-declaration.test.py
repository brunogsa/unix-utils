import importlib
import re
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

    @pytest.mark.parametrize("source_file", ["index.html", "styles.css"])
    def test_should_mark_complexity_and_crap_not_applicable_for_html_and_css_files(
        self, tmp_path, source_file
    ):
        loaded = load_text(tmp_path, DECLARATION_WITH_GO_AND_WEB)
        language = declaration.language_for_file(loaded, source_file)

        assert declaration.metric_status(loaded, language, "complexity") == "not applicable"
        assert declaration.metric_status(loaded, language, "crap") == "not applicable"
        assert declaration.metric_status(loaded, language, "size") == "applies"
        assert declaration.metric_status(loaded, language, "code_duplication") == "applies"

    @pytest.mark.parametrize(
        "prose_file",
        ["README.md", "notes.txt", "package.json", "settings.yaml", "pyproject.toml"],
    )
    def test_should_ignore_markdown_plain_text_json_yaml_and_toml_files_without_asking_for_a_language_entry(
        self, tmp_path, prose_file
    ):
        loaded = load_text(tmp_path, DECLARATION_WITH_GO_AND_WEB)

        assert declaration.language_for_file(loaded, prose_file) is None

    def test_should_read_an_opted_out_metric_as_not_applicable_never_as_passed(self, tmp_path):
        with_size = load_text(tmp_path, DECLARATION_WITH_GO_AND_WEB + RUST_ENTRY)
        size_opted_out = RUST_ENTRY.replace("[crap, size]", "[crap]")
        without_size = load_text(tmp_path, DECLARATION_WITH_GO_AND_WEB + size_opted_out)

        assert declaration.metric_status(with_size, "rust", "size") == "applies"
        status = declaration.metric_status(without_size, "rust", "size")
        assert status == "not applicable"
        assert status != "passed"


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


FULL_METRICS_FIXTURE = """\
excluded_paths: []
ignored_extensions: [.md]
per_unit: []
languages:
  python:
    extensions: [.py]
    metrics: [complexity, crap, coverage, size, nesting, parameters, code_duplication]
  ts:
    extensions: [.ts]
    metrics: [complexity, crap, coverage, size, nesting, parameters, code_duplication]
"""

CRAP_AND_COVERAGE = {"crap", "coverage"}
FOUR_FULL_LANGUAGES = ["js", "ts", "python", "go"]


class TestTestFileMetrics:
    @pytest.mark.parametrize(
        "test_file",
        [
            "src/sum.test.ts",
            "src/sum.spec.ts",
            "src/__tests__/sum.ts",
            "tests/test_sum.py",
            "pkg/test_sum.py",
            "pkg/sum_test.py",
        ],
    )
    def test_should_drop_crap_and_coverage_but_keep_every_other_declared_metric_for_a_test_file(
        self, tmp_path, test_file
    ):
        language = "python" if test_file.endswith(".py") else "ts"
        loaded = load_text(tmp_path, FULL_METRICS_FIXTURE)
        declared = set(loaded.languages[language].metrics)

        for_test_file = set(declaration.metrics_for_file(loaded, test_file))

        assert for_test_file == declared - CRAP_AND_COVERAGE
        assert for_test_file

    @pytest.mark.parametrize("source_file", ["src/sum.ts", "src/testing_utils.ts", "pkg/latest.py"])
    def test_should_keep_every_declared_metric_for_a_source_file_whose_name_only_resembles_a_test(
        self, tmp_path, source_file
    ):
        language = "python" if source_file.endswith(".py") else "ts"
        loaded = load_text(tmp_path, FULL_METRICS_FIXTURE)

        for_source = set(declaration.metrics_for_file(loaded, source_file))

        assert for_source == set(loaded.languages[language].metrics)

    def test_should_declare_the_same_metrics_for_javascript_typescript_python_and_go_in_the_shipped_file(
        self,
    ):
        loaded = declaration.load_declaration(SHIPPED_DECLARATION)

        metric_sets = {loaded.languages[name].metrics for name in FOUR_FULL_LANGUAGES}

        assert len(metric_sets) == 1

    @pytest.mark.parametrize("language", FOUR_FULL_LANGUAGES)
    def test_should_give_the_shipped_test_files_of_each_full_language_all_but_crap_and_coverage(
        self, language
    ):
        loaded = declaration.load_declaration(SHIPPED_DECLARATION)
        extension = loaded.languages[language].extensions[0]
        declared = set(loaded.languages[language].metrics)

        for_source = set(declaration.metrics_for_file(loaded, f"src/sum{extension}"))
        for_test = set(declaration.metrics_for_file(loaded, f"tests/test_sum{extension}"))

        assert for_source == declared
        assert for_test == declared - CRAP_AND_COVERAGE


INSTALL_SH = SCRIPTS_DIR.parent.parent.parent.parent / "install.sh"

# Global tools the checks need, with each OS's install line.
# Tools run via `uv run --with` (coverage, import-linter) are
# exempt: uv fetches them per run, so install.sh skips them.
# A later task declaring a global tool adds its row here.
GLOBAL_TOOL_INSTALL_LINES = {
    "uv": {"macos": r"brew install\b.*\buv\b", "linux": r"astral\.sh/uv/install\.sh"},
    "lizard": {"macos": r"pipx install\b.*\blizard\b", "linux": r"pipx install\b.*\blizard\b"},
    "shellmetrics": {
        "macos": r"curl\b.*shellspec/shellmetrics/[0-9a-f]{40}/shellmetrics",
        "linux": r"curl\b.*shellspec/shellmetrics/[0-9a-f]{40}/shellmetrics",
    },
}


def install_lines_by_os(install_text):
    """Group install.sh lines by the top-level OS branch that holds them."""
    lines_by_os = {"macos": [], "linux": []}
    current = None
    for line in install_text.splitlines():
        if line.startswith(("if ", "elif ", "else", "fi")):
            current = "macos" if '"macos"' in line else "linux" if '"linux"' in line else None
            continue
        if current:
            lines_by_os[current].append(line)
    return lines_by_os


class TestGlobalToolInstall:
    @pytest.mark.parametrize("tool", sorted(GLOBAL_TOOL_INSTALL_LINES))
    @pytest.mark.parametrize("operating_system", ["macos", "linux"])
    def test_should_find_an_install_line_for_both_operating_systems_for_uv_and_every_other_global_tool_declared_so_far(
        self, tool, operating_system
    ):
        lines = install_lines_by_os(INSTALL_SH.read_text())[operating_system]
        pattern = re.compile(GLOBAL_TOOL_INSTALL_LINES[tool][operating_system])

        assert any(pattern.search(line) for line in lines)

    def test_should_attribute_a_line_only_to_the_operating_system_branch_that_holds_it(self):
        sample = (
            'if [[ "$OS" == "macos" ]]; then\n    brew install uv\n'
            'elif [[ "$OS" == "linux" ]]; then\n    echo hi\nfi\n'
        )

        lines = install_lines_by_os(sample)

        assert any("brew install uv" in line for line in lines["macos"])
        assert not any("brew install uv" in line for line in lines["linux"])
