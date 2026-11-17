"""Records how often each measured file changed recently.

Churn is the number of commits that touched the file in the
last 90 days. Outside a git repo it is None: "not measured",
which is never the same as zero commits.
"""

from quality_metrics.touched import GitError, commit_count_since

CHURN_WINDOW = "90.days"


def with_churn(measurements):
    """The measurements, each carrying its file's churn."""
    churn_by_file = {}
    for record in measurements:
        path = record["file"]
        if path not in churn_by_file:
            churn_by_file[path] = _churn_of(path)
    return [{**record, "churn": churn_by_file[record["file"]]} for record in measurements]


def _churn_of(path):
    try:
        return commit_count_since(path, CHURN_WINDOW)
    except GitError:
        return None
