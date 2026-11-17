"""Builds the metrics verdict text from a
measure-quality-metrics report.

Order: deferred metrics, tooling asks and exceptions first, then
the open violations, then the rest, with the coverage sources
before the code design.
An exception counts only with a split diff saved on disk and no
rejection by the judge, so a claim made in prose alone, or one
the judge rejected, stays an open violation.
"""

import collections
import itertools
from pathlib import Path

from quality_metrics import debt, hotspots, record_keys
from quality_metrics.atomic_write import write_text_atomically
from quality_metrics.deferred import DEFERRED_LABEL
from quality_metrics.functions import display_value

METRICS_TAG = "[metrics]"

METRIC_TITLES = {
    ("crap", "function"): "CRAP",
    ("size", "function"): "Function size",
    ("size", "file"): "File size",
    ("nesting", "function"): "Nesting",
    ("parameters", "function"): "Parameters",
    ("cognitive_complexity", "function"): "Cognitive complexity",
    ("coverage", "file"): "Coverage",
    ("code_duplication", "file"): "Code duplication",
    ("test_duplication", "file"): "Test duplication",
    ("dependency_direction", "file"): "Dependency direction",
    ("unused_code", "file"): "Unused code",
    ("type_errors", "file"): "Type errors",
    ("dead_code", "file"): "Dead code",
    ("mutation", "file"): "Surviving mutant",
}

BULLET_MARK = "- "

# The doc-standards density cap for a bullet line, the one
# check-density.sh applies; an indented paragraph line gets
# twice as much.
BULLET_CAP_CHARS = 256
BULLET_CAP_WORDS = 32

# Where an over-cap bullet splits, tried in order: the record's
# ` - ` before its value, else a debt delta's `: `.
BULLET_SPLIT_SEPARATORS = (" - ", ": ")

PESSIMISTIC_NOTE = "pessimistic"
REJECTED_NOTE = ", exception rejected by the judge"

NO_CODE_MEASURED = "No code file was measured."

NO_GIT_SKIPPED = (
    "No git repo encloses the working directory, so the removed-code check "
    "and the base-ref reads were skipped."
)


def verdict_filename(timestamp, in_git=True):
    """The verdict's file name; a run outside git is named so a
    reader sees it."""
    if in_git:
        return f"verdict_metrics_{timestamp}.md"
    return f"verdict_quality-gate_no-git_{timestamp}.md"


def write_verdict(directory, timestamp, text, in_git=True):
    """Write the verdict into `directory` and return its path.

    The text goes to a hidden temp file in the same directory,
    then a rename, so a reader sees no verdict or the whole one.
    A killed run leaves only the temp file, whose name never
    matches `verdict_*`.
    """
    target = Path(directory) / verdict_filename(timestamp, in_git)
    write_text_atomically(target, text, temp_prefix=".verdict-tmp-")
    return target


def build_verdict(report, exceptions=(), in_git=True):
    """Verdict markdown.

    `exceptions` are claims with a saved split diff path, marked
    `rejected` once the judge ruled the split does not read
    worse; `in_git` is False when no git repo encloses the
    working directory.
    """
    numbers = itertools.count(1)
    accepted, open_violations = partition_claims(report["violations"], exceptions)
    keys = record_keys.keys_by_section(
        [violation for violation, _ in open_violations], report
    )
    sections = [
        _deferred_section(report["measurements"], numbers),
        _asks_section(report.get("asks", []), numbers),
        _exceptions_section(accepted, numbers),
        _violations_section(open_violations, keys["violations"]),
        _gate_inputs_section(report.get("gate_input_violations", []), keys["gate_inputs"]),
        _duplication_section(report.get("duplication_candidates", []), keys["duplication"]),
        *_new_candidate_sections(report, keys),
        _not_applicable_section(report.get("not_applicable", [])),
        _not_measured_section(report["measurements"]),
        _sources_section(report.get("sources", [])),
        *_leaked_processes_sections(report.get("leaked_processes")),
        _debt_section(report),
        _design_section(report["measurements"]),
    ]
    if not in_git:
        sections.append(_section("Skipped checks", [NO_GIT_SKIPPED]))
    return "\n\n".join(sections) + "\n"


def partition_claims(violations, exceptions):
    """Split violations into accepted ones (a claim whose
    diff file exists, not rejected) and open ones, each
    paired with whether its claim was rejected.
    """
    claims_by_key = {_key(claim): claim for claim in exceptions}
    accepted = []
    open_violations = []
    for violation in violations:
        claim = claims_by_key.get(_key(violation))
        is_rejected = bool(claim and claim.get("rejected"))
        if claim and not is_rejected and Path(claim["diff_path"]).is_file():
            accepted.append((violation, claim))
        else:
            open_violations.append((violation, is_rejected))
    return accepted, open_violations


def _key(item):
    return (item["file"], item["function"], item["metric"])


def _exceptions_section(accepted, numbers):
    entries = [
        _entry(
            next(numbers),
            f"{_describe(violation)}, split {_metric_name(violation)} "
            f"{display_value({'value': claim['split_value']})}, [split diff]({claim['diff_path']})",
        )
        for violation, claim in accepted
    ]
    return _section(f"Exceptions ({len(entries)})", entries)


def _deferred_section(measurements, numbers):
    """One entry per deferred metric, counting the records its
    tool could not measure.

    A failed test run is pessimistic too but carries no deferral
    label: it is a red build, not deferred tooling.
    """
    counts_by_title = collections.Counter(
        _metric_name(record)
        for record in measurements
        if record.get("label") == DEFERRED_LABEL
    )
    entries = [
        _entry(
            next(numbers),
            f"{title} - {counts_by_title[title]} measurements ({DEFERRED_LABEL})",
        )
        for title in sorted(counts_by_title)
    ]
    return _section(f"Deferred metrics ({len(entries)})", entries)


def _counted_section(title, items, describe_item, keys=None):
    """A titled section with one bullet per raw record, the
    title carrying the record count.

    Records are not findings, so they carry no `### N.` number.
    `keys`, aligned with `items`, puts each record's key on the
    line under its bullet, for a judge to cite.
    """
    texts = [describe_item(item) for item in items]
    if keys is not None:
        texts = [_with_record_line(text, key) for text, key in zip(texts, keys)]
    bullets = [_bullet(text) for text in texts]
    return _section(f"{title} ({len(bullets)})", bullets)


def _with_record_line(text, key):
    first, *rest = text.split("\n")
    return "\n".join([first, f"**Record**: `{key}`", *rest])


def _asks_section(asks, numbers):
    entries = [_entry(next(numbers), _describe_ask(ask)) for ask in asks]
    return _section(f"Tooling asks ({len(entries)})", entries)


def _describe_ask(ask):
    return f"{ask['tool']} ({ask['metric']}) - {ask['reason']}"


def _sources_section(sources):
    return _counted_section("Coverage sources", sources, _describe_source)


def _describe_source(item):
    source = item["source"]
    text = f"{item['language']} - measured by {source['kind']} {source['tool']}"
    if item["exit_class"] is not None:
        text += f", exit class {item['exit_class']}"
    if item["side_pr_candidate"] is not None:
        text += f", side-PR candidate: {item['side_pr_candidate']}"
    return text


def _violations_section(violations, keys):
    return _counted_section("Open violations", violations, _describe_open, keys)


def _describe_open(violation_and_rejection):
    item, is_rejected = violation_and_rejection
    return _describe(item) + (REJECTED_NOTE if is_rejected else "")


def _duplication_section(candidates, keys):
    return _counted_section("Duplication candidates", candidates, _describe, keys)


def _new_candidate_sections(report, keys):
    """Dead code and mutation sections; the mutation keys are
    absent until `--mutation` runs, and then so are the
    sections."""
    sections = [
        _counted_section(
            "Dead code candidates",
            report.get("dead_code_candidates", []),
            _describe_dead_code,
            keys["dead_code"],
        )
    ]
    survivors = report.get("surviving_mutants", [])
    not_run = report.get("mutants_not_run", [])
    if survivors or not_run:
        sections.append(
            _counted_section(
                "Surviving mutants", survivors, _describe_mutant, keys["survivors"]
            )
        )
        sections.append(
            _counted_section("Mutants not run", not_run, _describe_not_run)
        )
    return sections


def _leaked_processes_sections(leaked):
    """The leaked test workers killed before the repo test run,
    and the busiest processes when it still never started; no
    section when no reclaim ran."""
    if leaked is None:
        return []
    sections = [
        _counted_section("Leaked processes", leaked["killed"], _describe_leaked_process)
    ]
    busiest = [
        f"busiest by {label}: {_describe_busy_process(item)}"
        for label, key in (("CPU", "busiest_by_cpu"), ("RSS", "busiest_by_rss"))
        for item in leaked.get(key, [])
    ]
    if busiest:
        sections.append(_counted_section("Busiest processes", busiest, str))
    return sections


def _describe_leaked_process(item):
    repo = item["repo"] or "unknown"
    text = (
        f"pid {item['pid']} - {item['command']} - RSS {item['rss_kb'] // 1024} MB, "
        f"age {item['age_seconds'] // 60} min, repo {repo}"
    )
    if item["is_repo_scout_candidate"]:
        return f"{text} (candidate repo scout)"
    return text


def _describe_busy_process(item):
    return (
        f"pid {item['pid']} - {item['command']} - CPU {item['cpu_percent']}%, "
        f"RSS {item['rss_kb'] // 1024} MB"
    )


def _describe_dead_code(item):
    text = (
        f"{item['file']}:{item['line']} - {item.get('name')} "
        f"({item.get('kind')}, {item.get('tool')})"
    )
    if item.get("label") == DEFERRED_LABEL:
        return f"{text} ({DEFERRED_LABEL})"
    return text


def _describe_mutant(item):
    text = (
        f"{item['file']}:{item['line']} - {item.get('mutator')} -> "
        f"{item.get('replacement')} ({item.get('status')})"
    )
    if item.get("label") == DEFERRED_LABEL:
        return f"{text} ({DEFERRED_LABEL})"
    return text


def _describe_not_run(item):
    return f"{item['file']} lines {item['lines']} - {item['label']}"


def _not_applicable_section(items):
    """Files a metric could not judge: listed so a reader sees
    they were not measured, never counted as violations."""
    return _counted_section("Not applicable", items, _describe_not_applicable)


def _describe_not_applicable(item):
    title = METRIC_TITLES[(item["metric"], "file")]
    return f"{item['file']} - {title} - not applicable: {item['reason']}"


def _gate_inputs_section(gate_input_violations, keys):
    return _counted_section(
        "Gate input violations", gate_input_violations, _describe_gate_input, keys
    )


def _describe_gate_input(item):
    return f"{item['kind']} in {item['file']} - {item['value']}"


def _not_measured_section(measurements):
    """Limited records with no value, deferred or pessimistic.

    The violations list holds only records with a value, so
    this is the one place the verdict names them.

    A measurement within its limit is never listed.
    """
    unmeasured = [record for record in measurements if _is_unmeasured(record)]
    return _counted_section("Not measured", unmeasured, _describe)


def _is_unmeasured(record):
    has_limit = bool(record["limit"]) and record["limit"] > 0
    return has_limit and record["value"] is None and not hotspots.is_neutral(record)


def _debt_section(report):
    counted = (
        report["violations"]
        + report.get("duplication_candidates", [])
        + report.get("dead_code_candidates", [])
        + report.get("surviving_mutants", [])
    )
    score = debt.debt_score(counted, debt.measured_nloc(report["measurements"]))
    if score["ratio"] is None:
        text = f"{score['minutes']} min of remediation; ratio not computable, no file size was measured"
    else:
        text = (
            f"{score['minutes']} min of remediation over {score['nloc']} measured lines = "
            f"{score['ratio']:.1%}, band {score['band']}"
        )
    delta = report.get("debt", {}).get("delta")
    if delta is None:
        return _section("Debt", [text])
    return _section("Debt", [text, _debt_delta_text(delta)])


def _debt_delta_text(delta):
    if not delta["computable"]:
        return f"Debt delta: delta not computable: {delta['reason']}"
    bullets = [
        _bullet(
            f"{_delta_name(entry)}: {entry['base_minutes']} -> "
            f"{entry['head_minutes']} min ({entry['delta_minutes']:+d})"
        )
        for entry in delta["files"]
    ]

    # why: a blank line between bullets keeps a long one from
    # failing the doc-standards bullet-gap checker, and the
    # one before "Total:" keeps the hard-wrap checker from
    # reading it as a bullet's wrapped continuation.
    return "\n\n".join([
        "Debt delta on touched files, base ref to HEAD (static metrics only):",
        *bullets,
        f"Total: {delta['total_minutes']:+d} min",
    ])


def _delta_name(entry):
    if entry["old_file"]:
        return f"{entry['old_file']} -> {entry['file']}"
    return entry["file"]


def _design_section(measurements):
    if not measurements:
        return _section("Code design", [NO_CODE_MEASURED])
    view = hotspots.hotspot_view(measurements)
    return _section("Code design", [view])


def _section(title, entries):
    return "\n\n".join([f"## {title}", *entries])


def _entry(number, text):
    return f"### {number}. {METRICS_TAG} {text}"


def _bullet(text):
    """`text`'s first line as a `- ` bullet, its other lines
    indented under it so they stay part of that record.

    A blank line goes before each indented line, so the
    doc-standards hard-wrap checker never reads it as the
    bullet wrapped across lines.
    """
    first, *continuations = text.split("\n")
    blocks = [_fitted_bullet(first, indent="")]
    for line in continuations:
        if line.startswith(BULLET_MARK):
            blocks.append(_fitted_bullet(line[len(BULLET_MARK):], indent="  "))
        else:
            blocks.append(f"  {line}")
    return "\n\n".join(blocks)


def _fitted_bullet(text, indent):
    """`text` as one bullet at `indent`, its tail moved to a
    paragraph under it when the line runs past the bullet cap.

    A bullet line gets half the cap a paragraph line gets, so
    the tail after the first separator moves down instead.
    """
    line = f"{indent}{BULLET_MARK}{text}"
    if not _is_over_bullet_cap(line):
        return line
    for separator in BULLET_SPLIT_SEPARATORS:
        head, found, tail = text.partition(separator)
        if found:
            return f"{indent}{BULLET_MARK}{head}\n\n{indent}  {tail}"
    return line


def _is_over_bullet_cap(line):
    return len(line) > BULLET_CAP_CHARS or len(line.split()) > BULLET_CAP_WORDS


def _describe(record):
    subject = record["function"] or record["file"]
    where = f" in {record['file']}" if record["function"] else ""
    heading = (
        f"{subject}{where} - {_metric_name(record)} {_shown_value(record)} "
        f"(limit {record['limit']:g})"
    )
    lines = [heading]
    uncovered_lines = record.get("uncovered_lines")
    if uncovered_lines:
        lines.append(f"Uncovered lines: {', '.join(uncovered_lines)}")
    lines += [f"- line {f['line']}: {f['rule']} {f['name']}" for f in record.get("findings", [])]
    lines += [
        f"- line {e['line']}: {e['rule']} - {e['message']}" for e in record.get("errors", [])
    ]
    return "\n".join(lines)


def _shown_value(record):
    if record["value"] is None:
        return f"no value ({record.get('label') or record['status']})"
    if record.get("label") == DEFERRED_LABEL:
        return f"{display_value(record)} ({DEFERRED_LABEL})"
    if record.get("pessimistic"):
        return f"{display_value(record)} ({PESSIMISTIC_NOTE})"
    return display_value(record)


def _metric_name(record) -> str:
    metric = record["metric"]
    assert isinstance(metric, str), f"measurement record lacks a metric name: {record}"
    return METRIC_TITLES.get((metric, record["scope"]), metric)
