import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_support import SCRIPTS_DIR

sys.path.insert(0, str(SCRIPTS_DIR))

MODULE_SOURCE = "def double(value):\n    return value * 2\n"
PASSING_TEST = (
    "from pricing import double\n\n\n"
    "def test_doubles_a_price():\n"
    "    assert double(21) == 42\n"
)
FAILING_TEST = (
    "from pricing import double\n\n\n"
    "def test_doubles_a_price():\n"
    "    assert double(21) == 0\n"
)


def write_repo(tmp_path, files):
    repo = tmp_path / "repo"
    repo.mkdir()
    for name, text in files.items():
        (repo / name).write_text(text)
    return repo


def python_source_record(repo):
    from quality_metrics.collection import CoverageRun

    run = CoverageRun(repo)
    result = run.result_for("python")
    return result, run.sources[0]


def test_should_measure_coverage_of_a_repo_whose_pytest_config_runs_tests_with_n_workers(tmp_path):
    from quality_metrics.collection import collect_python

    repo = write_repo(tmp_path, {
        "pricing.py": MODULE_SOURCE,
        "test_pricing.py": PASSING_TEST,
        "pytest.ini": "[pytest]\naddopts = -n 2\n",
    })

    result = collect_python(repo)

    assert not result.has_failed_tests
    assert result.hits_by_file["pricing.py"][2] > 0


def test_should_name_exit_code_1_in_the_source_record_when_a_repo_test_fails(tmp_path):
    repo = write_repo(tmp_path, {"pricing.py": MODULE_SOURCE, "test_pricing.py": FAILING_TEST})

    result, source = python_source_record(repo)

    assert result.has_failed_tests
    assert result.hits_by_file == {}
    assert source["exit_class"].startswith("pytest exited 1: ")


def test_should_name_exit_code_4_and_the_usage_error_in_the_source_record_when_pytest_rejects_its_arguments(tmp_path):
    repo = write_repo(tmp_path, {
        "pricing.py": MODULE_SOURCE,
        "test_pricing.py": PASSING_TEST,
        "pytest.ini": "[pytest]\naddopts = --no-such-option\n",
    })

    result, source = python_source_record(repo)

    assert result.has_failed_tests
    assert source["exit_class"].startswith("pytest exited 4: ")
    assert "no-such-option" in source["exit_class"]
