import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_dependencies_support import (
    DECLARED_LAYERS,
    GO_BASE_FILES,
    GO_DECLARATION,
    GO_DOMAIN_READING_INFRA,
    BranchChange,
    env_with_go_arch_lint_stub,
    env_with_stub_tools,
    env_without_tool,
    measure_branch,
    write_layers,
)

DOMAIN_READS_INFRA_CHANGE = BranchChange(
    GO_BASE_FILES, {"domain/order.go": GO_DOMAIN_READING_INFRA}
)

# Stands in for a go-arch-lint that skips the check on a config
# notice, whatever the archfile holds.
GO_ARCH_LINT_STUB_SKIPPING_THE_CHECK = """#!/bin/sh
cat <<'JSON'
{"Type":"models.Check","Payload":{"ExecutionWarnings":[{"Text":"config notice","File":"config.yml"}],
"ArchHasWarnings":false,"ArchWarningsDeps":[],"ArchWarningsNotMatched":[],
"ArchWarningsDeepScan":[],"OmittedCount":0,"ModuleName":"shop","Qualities":[]}}
JSON
exit 1
"""


def test_scores_a_go_file_as_a_deferred_violation_when_go_arch_lint_skips_the_check(tmp_path):
    env = env_with_stub_tools(
        tmp_path, "skipping-stub-bin",
        {"go-arch-lint": GO_ARCH_LINT_STUB_SKIPPING_THE_CHECK},
    )

    violations = measure_branch(
        tmp_path, GO_DECLARATION, DOMAIN_READS_INFRA_CHANGE,
        "--layers", write_layers(tmp_path, DECLARED_LAYERS), env=env,
    )

    assert len(violations) == 1
    deferred = violations[0]
    assert deferred["file"] == "domain/order.go"
    assert deferred["pessimistic"] is True
    assert "deferred" in deferred["label"]


def test_hands_go_arch_lint_a_config_where_each_layer_may_depend_on_itself_and_the_layers_after_it(tmp_path):
    capture_path = tmp_path / "captured-archfile.yaml"

    measure_branch(
        tmp_path, GO_DECLARATION, DOMAIN_READS_INFRA_CHANGE,
        "--layers", write_layers(tmp_path, DECLARED_LAYERS),
        env=env_with_go_arch_lint_stub(tmp_path, capture_path),
    )

    config = yaml.safe_load(capture_path.read_text())
    assert config["version"] == 3
    assert config["components"] == {
        "infra": {"in": ["infra/**"]},
        "domain": {"in": ["domain/**"]},
    }
    assert config["deps"] == {
        "infra": {"mayDependOn": ["infra", "domain"]},
        "domain": {"mayDependOn": ["domain"]},
    }
    assert config["allow"]["ignoreNotFoundComponents"] is True


def test_flags_a_go_domain_to_infra_import_from_the_go_arch_lint_report(tmp_path):
    violations = measure_branch(
        tmp_path, GO_DECLARATION, DOMAIN_READS_INFRA_CHANGE,
        "--layers", write_layers(tmp_path, DECLARED_LAYERS),
        env=env_with_go_arch_lint_stub(tmp_path, tmp_path / "archfile.yaml"),
    )

    assert len(violations) == 1
    layer_import = violations[0]
    assert layer_import["kind"] == "layer"
    assert layer_import["file"] == "domain/order.go"
    assert layer_import["other_file"] == "shop/infra"
    assert layer_import["layer_map_source"] == "declared"


def test_scores_a_go_file_as_a_deferred_violation_when_go_arch_lint_is_missing(tmp_path):
    violations = measure_branch(
        tmp_path, GO_DECLARATION, DOMAIN_READS_INFRA_CHANGE,
        "--layers", write_layers(tmp_path, DECLARED_LAYERS),
        env=env_without_tool("go-arch-lint"),
    )

    assert len(violations) == 1
    deferred = violations[0]
    assert deferred["metric"] == "dependency_direction"
    assert deferred["file"] == "domain/order.go"
    assert deferred["pessimistic"] is True
    assert "deferred" in deferred["label"]
