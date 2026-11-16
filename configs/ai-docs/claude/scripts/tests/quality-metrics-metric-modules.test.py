import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_support import (
    SCRIPTS_DIR, SHIPPED_DECLARATION, commit_all, head_of,
    make_repo, run_measure,
)

sys.path.insert(0, str(SCRIPTS_DIR))

declaring = importlib.import_module("quality_metrics.declaration")
measuring = importlib.import_module("quality_metrics.measuring")

DECLARATION = """\
excluded_paths: [dist/]
ignored_extensions: [.md, .txt, .json, .yaml, .yml, .toml]
per_unit: []
languages:
  go:
    extensions: [.go]
    metrics: [{metrics}]
"""

GO_BASE = "package main\n\nfunc keep(a int) int {\n\treturn a\n}\n"
GO_CHANGED = GO_BASE + "\nfunc added(a int) int {\n\treturn a + 1\n}\n"


def run_diff_with_metrics(tmp_path, metrics):
    repo = make_repo(tmp_path, {"report.go": GO_BASE})
    base = head_of(repo)
    (repo / "report.go").write_text(GO_CHANGED)
    commit_all(repo, "add a function")
    declaration_path = tmp_path / "quality-metrics.yaml"
    declaration_path.write_text(DECLARATION.format(metrics=metrics))
    return run_measure(repo, declaration_path, "--diff", f"{base}...HEAD")


class TestDeclaredMetricsWithoutAModule:
    def test_should_exit_not_measured_naming_the_metric_when_a_declared_metric_has_no_module(
        self, tmp_path
    ):
        result = run_diff_with_metrics(tmp_path, "size, complexity")

        assert result.returncode == 2
        assert result.stdout == ""
        assert "complexity" in result.stderr

    def test_should_leave_entangled_tests_out_of_every_module_group_when_it_is_declared(self):
        grouped = measuring._group_by_module(["size", "entangled_tests"])

        assert grouped == {"size": ["size"]}

    def test_should_map_or_skip_on_purpose_every_metric_the_shipped_declaration_declares(self):
        loaded = declaring.load_declaration(SHIPPED_DECLARATION)
        declared = {
            metric
            for language in loaded.languages.values()
            for metric in language.metrics
        }

        mapped = set(measuring.METRIC_MODULES)

        unhandled = declared - mapped - measuring.SKIPPED_ON_PURPOSE

        assert unhandled == set()
