"""Runs go-arch-lint over a Go tree against a layer map."""

import json
import tempfile
from pathlib import Path

from quality_metrics.dependency_problems import LAYER_RULE_PREFIX, layer_problem
from quality_metrics.tools import ToolError, run_command

# go-arch-lint exits 1 on warnings alone, so only a missing
# report means it failed; the cap is set to the tool's own
# ceiling, 32768, as it rejects any larger value.
GO_ARCH_LINT_MAX_WARNINGS = "32768"


def find_with_go_arch_lint(tree, layer_map):
    # Go import cycles are compile errors, so without a layer
    # map there is nothing for a tool to find.
    if layer_map is None:
        return []
    with tempfile.TemporaryDirectory() as config_dir:
        config_path = Path(config_dir) / "go-arch-lint.yml"
        config_path.write_text(json.dumps(_go_arch_lint_config(layer_map)))
        result = run_command(
            ["go-arch-lint", "check", "--project-path", str(tree),
             "--arch-file", str(config_path), "--json",
             "--max-warnings", GO_ARCH_LINT_MAX_WARNINGS],
            cwd=tree,
        )

    try:
        payload = json.loads(result.stdout)["Payload"]
    except (json.JSONDecodeError, KeyError, TypeError) as error:
        raise ToolError(
            f"go-arch-lint wrote no report: {(result.stdout + result.stderr).strip()}"
        ) from error

    # A config notice makes it skip the check entirely.
    if payload.get("ExecutionWarnings"):
        raise ToolError(
            f"go-arch-lint skipped the check: {payload['ExecutionWarnings']}"
        )
    return [
        layer_problem(
            f"{LAYER_RULE_PREFIX}{warning['ComponentName']}",
            warning["FileRelativePath"].lstrip("/"),
            warning["ResolvedImportName"],
        )
        for warning in payload.get("ArchWarningsDeps") or ()
    ]


def _go_arch_lint_config(layer_map):
    """Each layer may depend on itself and the layers after
    it.
    """
    layers = layer_map.layers
    return {
        "version": 3,
        "allow": {
            "depOnAnyVendor": True,
            "deepScan": False,
            "ignoreNotFoundComponents": True,
        },
        "components": {layer.name: {"in": list(layer.paths)} for layer in layers},
        "deps": {
            layer.name: {
                "mayDependOn": [layer.name, *(inner.name for inner in layers[index + 1:])]
            }
            for index, layer in enumerate(layers)
        },
    }
