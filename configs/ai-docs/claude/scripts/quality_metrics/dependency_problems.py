"""The problem dicts every dependency tool's runner builds,
whatever its language.
"""

CYCLE_KIND = "cycle"
LAYER_KIND = "layer"
LAYER_RULE_PREFIX = "layer-"


def layer_problem(rule, importer, imported):
    return {
        "key": (LAYER_KIND, rule, importer, imported),
        "kind": LAYER_KIND,
        "detail": f"{importer} imports {imported}, breaking {rule}",
        "paths": [importer],
        "other_file": imported,
    }


def cycle_problem(key, detail, paths):
    return {
        "key": (CYCLE_KIND, *key),
        "kind": CYCLE_KIND,
        "detail": detail,
        "paths": paths,
    }
