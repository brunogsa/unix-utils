import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_support import SCRIPTS_DIR

sys.path.insert(0, str(SCRIPTS_DIR))

PLUGIN_MODULE = "demo_pytest_plugin"

# The repo's pytest config loads the plugin, as a repo using
# pytest-asyncio does; without it pytest exits 4 (usage error).
PLUGIN_REPO_FILES = {
    "pytest.ini": f"[pytest]\naddopts = -p {PLUGIN_MODULE}\n",
    "calc.py": "def double(value):\n    return value * 2\n",
    "test_calc.py": (
        "from calc import double\n\n\n"
        "def test_doubles_a_number():\n"
        "    assert double(21) == 42\n"
    ),
}


def build_plugin_wheel(directory):
    """A local wheel of the demo plugin: no download needed."""
    wheel = directory / f"{PLUGIN_MODULE}-1.0-py3-none-any.whl"
    dist_info = f"{PLUGIN_MODULE}-1.0.dist-info"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr(f"{PLUGIN_MODULE}.py", "")
        archive.writestr(
            f"{dist_info}/METADATA",
            f"Metadata-Version: 2.1\nName: {PLUGIN_MODULE}\nVersion: 1.0\n",
        )
        archive.writestr(
            f"{dist_info}/WHEEL",
            "Wheel-Version: 1.0\nGenerator: test\nRoot-Is-Purelib: true\n"
            "Tag: py3-none-any\n",
        )
        archive.writestr(f"{dist_info}/RECORD", "")
    return wheel


def write_repo(tmp_path, files):
    repo = tmp_path / "repo"
    repo.mkdir()
    for name, text in files.items():
        (repo / name).write_text(text)
    return repo


def test_should_run_the_tests_of_a_repo_whose_requirements_test_file_declares_the_plugin_its_pytest_config_loads(tmp_path):
    from quality_metrics.collection import collect_python

    wheel = build_plugin_wheel(tmp_path)
    repo = write_repo(tmp_path, {
        **PLUGIN_REPO_FILES,
        "requirements-test.txt": f"{PLUGIN_MODULE} @ {wheel.as_uri()}\n",
    })

    result = collect_python(repo)

    assert not result.has_failed_tests
    assert result.hits_by_file["calc.py"][2] > 0


def test_should_run_the_tests_of_a_repo_whose_pyproject_test_group_declares_the_plugin_its_pytest_config_loads(tmp_path):
    from quality_metrics.collection import collect_python

    wheel = build_plugin_wheel(tmp_path)
    repo = write_repo(tmp_path, {
        **PLUGIN_REPO_FILES,
        "pyproject.toml": (
            "[dependency-groups]\n"
            f'test = ["{PLUGIN_MODULE} @ {wheel.as_uri()}"]\n'
        ),
    })

    result = collect_python(repo)

    assert not result.has_failed_tests
    assert result.hits_by_file["calc.py"][2] > 0


def test_should_report_a_red_build_naming_the_usage_error_when_the_repo_declares_no_test_dependencies(tmp_path):
    from quality_metrics.collection import collect_python

    repo = write_repo(tmp_path, PLUGIN_REPO_FILES)

    result = collect_python(repo)

    assert result.has_failed_tests
    assert "pytest exited 4" in result.failure_reason


def test_should_add_nothing_to_the_pytest_command_for_a_repo_that_declares_no_test_dependencies(tmp_path):
    from quality_metrics.python_test_deps import declared_test_dependency_args

    repo = write_repo(tmp_path, {
        "pyproject.toml": '[tool.other]\nkey = "value"\n',
    })

    assert declared_test_dependency_args(repo) == []
