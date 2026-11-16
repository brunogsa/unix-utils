"""Report-only debt delta of a branch on the files it touched.

Per touched file, the static debt minutes at the head ref minus
the minutes at the base ref, so a branch that adds clean lines
to a debt-heavy file is not diluted the way a ratio would be.
Static means the metrics measured from the file text alone:
size, nesting, parameters and cognitive complexity.
Coverage and CRAP are left out because measuring them at the
base ref would re-run the tests there, and duplication because
it scans the working tree's peer files, which the base ref
has no checkout of.
It never changes the exit code, `holds_commit` or the
violation list.
"""

import tempfile
from pathlib import Path

from quality_metrics import functions, size
from quality_metrics.debt import minutes_for
from quality_metrics.declaration import (
    DeclarationError,
    language_for_file,
    metrics_for_file,
    nesting_reader_for,
)
from quality_metrics.functions import is_over_limit
from quality_metrics.tools import ToolError
from quality_metrics.touched import (
    GitError,
    Target,
    all_changes_between,
    file_text_at,
    ref_exists,
)

NO_BASE_REF = "no base ref"

FUNCTION_METRICS = ("nesting", "parameters", "cognitive_complexity")
STATIC_METRICS = ("size", *FUNCTION_METRICS)


def branch_debt_delta(base_ref, head_ref, declaration):
    """Per-file and total debt delta, base ref to head ref.

    Not computable, with the reason, when the base ref is
    missing or a tool fails; a delta of 0 is never a stand-in.
    """
    try:
        if not ref_exists(base_ref):
            return _not_computable(NO_BASE_REF)
        files = [
            entry for change in all_changes_between(base_ref, head_ref)
            if (entry := _file_entry(change, base_ref, head_ref, declaration))
        ]
    except (GitError, ToolError) as error:
        return _not_computable(str(error))
    return {
        "computable": True,
        "files": files,
        "total_minutes": sum(entry["delta_minutes"] for entry in files),
    }


def _not_computable(reason):
    return {"computable": False, "reason": reason}


def _file_entry(change, base_ref, head_ref, declaration):
    """The delta of one changed file, None when no language
    entry measures it."""
    base_minutes = _minutes_at(base_ref, change.old_path, declaration)
    head_minutes = _minutes_at(head_ref, change.new_path, declaration)
    if base_minutes is None or head_minutes is None:
        return None
    return {
        "file": change.new_path or change.old_path,
        "old_file": change.old_path if change.old_path != change.new_path else None,
        "base_minutes": base_minutes,
        "head_minutes": head_minutes,
        "delta_minutes": head_minutes - base_minutes,
    }


def _minutes_at(ref, path, declaration):
    """Static debt minutes of `path` at `ref`: 0 when the file
    does not exist there, None when no language entry claims
    it."""
    if path is None:
        return 0
    try:
        language = language_for_file(declaration, path)
    except DeclarationError:
        return None
    if language is None:
        return None
    metrics = [
        metric for metric in metrics_for_file(declaration, path)
        if metric in STATIC_METRICS
    ]
    return _measured_minutes(file_text_at(ref, path), path, language, metrics, declaration)


def _measured_minutes(text, path, language, metrics, declaration):
    with tempfile.TemporaryDirectory() as directory:
        copy = Path(directory) / f"measured{Path(path).suffix}"
        copy.write_text(text)
        target = Target(
            path=copy, language=language, touched_lines=None, repo_path=path,
            nesting_reader=nesting_reader_for(declaration, language),
        )
        records = []
        if "size" in metrics:
            records += size.measure(target, metrics)
        function_metrics = [metric for metric in metrics if metric in FUNCTION_METRICS]
        if function_metrics:
            records += functions.measure(target, function_metrics)
    return sum(minutes_for(record) for record in records if is_over_limit(record))
