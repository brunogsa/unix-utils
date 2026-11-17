import configparser
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_dependencies_support import (
    DECLARED_LAYERS,
    DOMAIN_ORDER_WITHOUT_DB,
    GO_DOMAIN_WITHOUT_INFRA,
    GO_INFRA_DB,
    GO_MODULE,
    INFRA_DB,
    PYTHON_DOMAIN_WITHOUT_INFRA,
    PYTHON_INFRA_DB,
    BranchChange,
    env_with_go_arch_lint_stub,
    env_with_stub_tools,
    report_for_branch,
    write_layers,
)

ALL_LANGUAGES_DECLARATION = """\
excluded_paths: [dist/]
ignored_extensions: [.md, .txt, .json, .yaml, .yml, .toml]
per_unit: []
languages:
  js:
    extensions: [.js]
    metrics: [dependency_direction]
  python:
    extensions: [.py]
    metrics: [dependency_direction]
  go:
    extensions: [.go]
    metrics: [dependency_direction]
"""

# Hands its config file to a capture path, then runs the tool
# that was really on PATH, so the tool's own run stays real.
CONFIG_CAPTURE_WRAPPER = """#!/bin/sh
previous=""
for argument in "$@"; do
  case "$previous" in
    --config|--arch-file)
      cp "$argument" "{capture_dir}/{name}.config"
      echo "$argument" > "{capture_dir}/{name}.path" ;;
  esac
  previous="$argument"
done
exec "{real_tool}" "$@"
"""

CAPTURED_TOOLS = ("depcruise", "lint-imports", "go-arch-lint")


def env_capturing_configs(tmp_path, capture_dir):
    """Env where dependency-cruiser, lint-imports and
    go-arch-lint save their configs."""
    stubbed_env = env_with_go_arch_lint_stub(tmp_path, capture_dir / "unused-copy")
    wrappers = {
        name: CONFIG_CAPTURE_WRAPPER.format(
            capture_dir=capture_dir, name=name,
            real_tool=shutil.which(name, path=stubbed_env["PATH"]),
        )
        for name in CAPTURED_TOOLS
    }
    return env_with_stub_tools(tmp_path, "capture-bin", wrappers, stubbed_env)


def test_translates_one_layer_map_into_dependency_cruiser_import_linter_and_go_arch_lint_configs_in_a_temp_directory(tmp_path):
    capture_dir = tmp_path / "captured"
    capture_dir.mkdir()
    base_files = {
        "go.mod": GO_MODULE,
        "domain/__init__.py": "",
        "domain/order.py": PYTHON_DOMAIN_WITHOUT_INFRA,
        "domain/order.js": DOMAIN_ORDER_WITHOUT_DB,
        "domain/order.go": GO_DOMAIN_WITHOUT_INFRA,
        "infra/__init__.py": "",
        "infra/db.py": PYTHON_INFRA_DB,
        "infra/db.js": INFRA_DB,
        "infra/db.go": GO_INFRA_DB,
    }
    change = BranchChange(base_files, {
        "domain/order.py": PYTHON_DOMAIN_WITHOUT_INFRA + "# tweaked\n",
        "domain/order.js": DOMAIN_ORDER_WITHOUT_DB + "// tweaked\n",
        "domain/order.go": GO_DOMAIN_WITHOUT_INFRA + "// tweaked\n",
    })

    report_for_branch(
        tmp_path, ALL_LANGUAGES_DECLARATION, change,
        "--layers", write_layers(tmp_path, DECLARED_LAYERS),
        env=env_capturing_configs(tmp_path, capture_dir),
    )

    assert_dependency_cruiser_config_layers(capture_dir)
    assert_import_linter_config_layers(capture_dir)
    assert_go_arch_lint_config_layers(capture_dir)
    assert_configs_sit_in_the_system_temp_directory(capture_dir, tmp_path)


def assert_dependency_cruiser_config_layers(capture_dir):
    depcruise = json.loads((capture_dir / "depcruise.config").read_text())
    rules = {rule["name"]: rule for rule in depcruise["forbidden"]}
    assert set(rules) == {"no-circular", "layer-domain"}
    domain_rule = rules["layer-domain"]
    assert re.search(domain_rule["from"]["path"], "domain/order.js")
    assert not re.search(domain_rule["from"]["path"], "infra/db.js")
    assert re.search(domain_rule["to"]["path"], "infra/db.js")
    assert not re.search(domain_rule["to"]["path"], "domain/order.js")


def assert_import_linter_config_layers(capture_dir):
    import_linter = configparser.ConfigParser()
    import_linter.read_string((capture_dir / "lint-imports.config").read_text())
    layers_contract = import_linter["importlinter:contract:layers"]
    assert layers_contract["type"] == "layers"
    assert layers_contract["layers"].split() == ["infra", "domain"]


def assert_go_arch_lint_config_layers(capture_dir):
    go_arch_lint = yaml.safe_load((capture_dir / "go-arch-lint.config").read_text())
    assert isinstance(go_arch_lint, dict)
    assert list(go_arch_lint["components"]) == ["infra", "domain"]
    assert go_arch_lint["deps"] == {
        "infra": {"mayDependOn": ["infra", "domain"]},
        "domain": {"mayDependOn": ["domain"]},
    }


def assert_configs_sit_in_the_system_temp_directory(capture_dir, tmp_path):
    system_temp = Path(tempfile.gettempdir()).resolve()
    for name in CAPTURED_TOOLS:
        config_path = Path((capture_dir / f"{name}.path").read_text().strip()).resolve()
        assert config_path.is_relative_to(system_temp)
        assert not config_path.is_relative_to(tmp_path.resolve())
