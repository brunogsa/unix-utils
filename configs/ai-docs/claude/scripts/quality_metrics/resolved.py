"""Finds the over-limit functions a change removed.

A removed function that broke a limit at the base is resolved by the
change. One that was under every limit is not reported, since nothing
was fixed by removing it.
"""

import tempfile
from pathlib import Path

from quality_metrics.touched import file_text_at


def resolved_measurements(changes, base_ref, measure_at_base, function_names_in):
    """List each over-limit function the changes removed, with its base-side score.

    `measure_at_base(copy_path, original_path)` measures a copy of the
    base-side file. `function_names_in(path)` names the functions the
    head-side file still holds.
    """
    resolved = []
    with tempfile.TemporaryDirectory() as directory:
        for change in changes:
            copy_path = Path(directory) / change.old_path
            copy_path.parent.mkdir(parents=True, exist_ok=True)
            copy_path.write_text(file_text_at(base_ref, change.old_path))
            over_limit = _over_limit_functions(measure_at_base(copy_path, change.old_path))
            if not over_limit:
                continue
            surviving = function_names_in(change.new_path) if change.new_path else set()
            resolved += [
                {**item, "file": change.old_path}
                for item in over_limit
                if item["function"] not in surviving
            ]
    return resolved


def _over_limit_functions(measurements):
    return [
        item for item in measurements
        if item["scope"] == "function" and item["value"] is not None and item["value"] > item["limit"]
    ]
