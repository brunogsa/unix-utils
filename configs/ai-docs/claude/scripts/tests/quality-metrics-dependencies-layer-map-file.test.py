import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_dependencies_support import PYTHON_DECLARATION, write_layers
from quality_metrics_support import make_repo, run_measure


def run_measure_with_layers(tmp_path, layers_argument):
    repo = make_repo(tmp_path, {"tools/sync.py": "SYNC = 1\n"})
    declaration_path = tmp_path / "quality-metrics.yaml"
    declaration_path.write_text(PYTHON_DECLARATION)
    return run_measure(repo, declaration_path, "--layers", layers_argument)


def test_exits_not_measured_with_a_message_when_the_layer_map_file_does_not_exist(tmp_path):
    missing_layers = tmp_path / "no-such-layers.yaml"

    result = run_measure_with_layers(tmp_path, str(missing_layers))

    assert result.returncode == 2
    assert "no-such-layers.yaml" in result.stderr
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize("layers_text, expected_message", [
    ("- name: infra\n  paths: [infra/**]\n", "must be a mapping"),
    ("source: declared\nlayers: [\n", "layers.yaml"),
], ids=["a list, not a mapping", "not valid yaml"])
def test_exits_not_measured_with_a_message_when_the_layer_map_is_unreadable(
    tmp_path, layers_text, expected_message
):
    result = run_measure_with_layers(
        tmp_path, write_layers(tmp_path, layers_text)
    )

    assert result.returncode == 2
    assert expected_message in result.stderr
    assert "Traceback" not in result.stderr
