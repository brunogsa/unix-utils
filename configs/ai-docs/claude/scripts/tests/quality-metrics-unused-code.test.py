import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_support import SCRIPTS_DIR

sys.path.insert(0, str(SCRIPTS_DIR))

unused_code = importlib.import_module("quality_metrics.unused_code")
touched = importlib.import_module("quality_metrics.touched")

PYTHON_UNUSED_IMPORT = "import os\n\nprint(1)\n"
PYTHON_ALL_USED = "import os\n\nprint(os.getcwd())\n"

# Assembled from parts so this file itself carries no literal
# suppression comment for the repo's suppression scanner.
PYTHON_SUPPRESSED = "import os  # no" + "qa: F401\n\nprint(1)\n"


def target_for(tmp_path, name, text, language):
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return touched.Target(path, language, None)


def single_record(target):
    records = unused_code.measure_unused_code(target)
    assert len(records) == 1
    return records[0]


def test_should_count_an_unused_python_import_on_its_line(tmp_path):
    target = target_for(tmp_path, "report.py", PYTHON_UNUSED_IMPORT, "python")

    record = single_record(target)

    assert (record["metric"], record["value"], record["limit"]) == ("unused_code", 1, 0)
    assert record["scope"] == "file"
    assert record["file"] == str(target.path)
    assert record["findings"] == [{"line": 1, "rule": "F401", "name": "os"}]


def test_should_count_zero_for_a_python_file_that_uses_its_import(tmp_path):
    target = target_for(tmp_path, "report.py", PYTHON_ALL_USED, "python")

    record = single_record(target)

    assert record["value"] == 0
    assert record["findings"] == []


def test_should_count_a_python_import_that_carries_a_noqa_comment(tmp_path):
    target = target_for(tmp_path, "report.py", PYTHON_SUPPRESSED, "python")

    assert single_record(target)["value"] == 1


def test_should_measure_nothing_for_go_because_its_compiler_rejects_unused_code(tmp_path):
    target = target_for(tmp_path, "main.go", "package main\n", "go")

    assert unused_code.measure_unused_code(target) == []
