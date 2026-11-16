"""Report-only technical-debt score for a measure run.

Sonar-style debt ratio: the minutes to fix every open violation,
over the minutes it took to write the measured code.
It never changes the exit code, `holds_commit` or the violation
list; a pessimistic or deferred violation counts like a measured
one, so a missing measurement never lowers the debt.
"""

# Minutes to write one measured line, Sonar's default cost.
# https://docs.sonarsource.com/sonarqube-server/latest/user-guide/code-metrics/metrics-definition/
MINUTES_PER_LINE = 30

# Maintainability rating bands, from the same page: A up to 5%,
# B below 10%, C below 20%, D below 50%, E from 50%.
BEST_BAND_MAX_RATIO = 0.05
BAND_UPPER_EDGES = ((0.10, "B"), (0.20, "C"), (0.50, "D"))
BEST_BAND, LAST_BAND = "A", "E"

# Used for a violation whose metric has no entry below, so an
# unpriced metric never scores as free.
UNLISTED_METRIC_MINUTES = 30

# Minutes to remediate one violation of each metric the registry
# defines. Sonar's rule pages give size (function: S138, file:
# S104), parameters (S107), nesting (S134) and cognitive
# complexity (S3776, its 5 minute offset); the rest are choices.
REMEDIATION_MINUTES = {
    "size": {"function": 20, "file": 60},
    "parameters": 20,
    "nesting": 10,
    "cognitive_complexity": 5,
    "crap": 30,
    "coverage": 20,
    "code_duplication": 60,
    "test_duplication": 30,
    "dependency_direction": 60,
}


def band_for(ratio):
    if ratio <= BEST_BAND_MAX_RATIO:
        return BEST_BAND
    for upper_edge, band in BAND_UPPER_EDGES:
        if ratio < upper_edge:
            return band
    return LAST_BAND


def measured_nloc(measurements):
    """Code lines measured: the sum of the file size records."""
    return sum(
        record["value"]
        for record in measurements
        if record["metric"] == "size"
        and record["scope"] == "file"
        and record["value"] is not None
    )


def debt_score(violations, nloc):
    """Minutes, measured lines, ratio and band; ratio and band
    are None when no line was measured."""
    minutes = sum(_minutes_for(violation) for violation in violations)
    if nloc <= 0:
        return {"minutes": minutes, "nloc": nloc, "ratio": None, "band": None}
    ratio = minutes / (MINUTES_PER_LINE * nloc)
    return {"minutes": minutes, "nloc": nloc, "ratio": ratio, "band": band_for(ratio)}


def _minutes_for(violation):
    minutes = REMEDIATION_MINUTES.get(violation["metric"], UNLISTED_METRIC_MINUTES)
    if isinstance(minutes, dict):
        return minutes[violation["scope"]]
    return minutes
