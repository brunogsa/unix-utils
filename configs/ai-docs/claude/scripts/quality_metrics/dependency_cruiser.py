"""Runs dependency-cruiser over a JS or TS tree."""

import json
import re
import tempfile
from pathlib import Path

from quality_metrics.dependency_problems import (
    LAYER_RULE_PREFIX,
    cycle_problem,
    layer_problem,
)
from quality_metrics.tools import ToolError, run_command

CYCLE_RULE_NAME = "no-circular"

# `**` crosses directories and `*` stays inside one.
GLOB_WILDCARD_REGEX = {"**": ".*", "*": "[^/]*"}


def find_with_dependency_cruiser(tree, excluded_paths, layer_map):
    config = _dependency_cruiser_config(excluded_paths, layer_map)
    with tempfile.TemporaryDirectory() as config_dir:
        config_path = Path(config_dir) / "dependency-cruiser.json"
        config_path.write_text(json.dumps(config))
        result = run_command(
            ["depcruise", "--config", str(config_path), "--output-type", "json", "."],
            cwd=tree,
        )

    # depcruise exits with its error count, so only a missing
    # report means it failed.
    try:
        report = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise ToolError(f"depcruise wrote no report: {result.stderr.strip()}") from error
    return [
        _problem_from_dependency_cruiser(violation)
        for violation in report["summary"]["violations"]
    ]


def _dependency_cruiser_config(excluded_paths, layer_map):
    ignored = "|".join(
        ["node_modules"] + [re.escape(path.rstrip("/")) for path in excluded_paths]
    )
    cycle_rule = {
        "name": CYCLE_RULE_NAME, "severity": "error",
        "from": {}, "to": {"circular": True},
    }
    return {
        "forbidden": [cycle_rule, *_layer_rules(layer_map)],
        "options": {"exclude": {"path": f"(^|/)({ignored})(/|$)"}},
    }


def _layer_rules(layer_map):
    """One rule per layer: it may not import any layer before
    it.
    """
    if layer_map is None:
        return []
    layers = layer_map.layers
    return [
        {
            "name": f"{LAYER_RULE_PREFIX}{layer.name}",
            "severity": "error",
            "from": {"path": _globs_to_regex(layer.paths)},
            "to": {"path": _globs_to_regex(
                [path for outer in layers[:index] for path in outer.paths]
            )},
        }
        for index, layer in enumerate(layers) if index > 0
    ]


def _globs_to_regex(globs):
    alternatives = []
    for glob in globs:
        pieces = re.split(r"(\*\*|\*)", glob)
        body = "".join(
            GLOB_WILDCARD_REGEX.get(piece) or re.escape(piece)
            for piece in pieces
        )
        alternatives.append(f"^{body}$")
    return "|".join(alternatives)


def _problem_from_dependency_cruiser(violation):
    if violation["rule"]["name"] == CYCLE_RULE_NAME:
        members = [step["name"] for step in violation["cycle"]]
        return cycle_problem(
            (violation["from"], violation["to"]),
            " -> ".join([*members, members[0]]),
            members,
        )
    return layer_problem(
        violation["rule"]["name"], violation["from"], violation["to"]
    )
