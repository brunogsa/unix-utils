"""The key of each raw metrics record a judge must rule on.

The verdict prints each key under its record, and
check-metrics-judge-coverage.py reads the same keys from the
report, so a judge finding or dismissal cites a record by a
string both sides derive from one place.

A key is `<metric> <file>[:<line>][ <detail>]`. Two records
whose keys still match get ` #2`, ` #3` in report order.
"""

import collections

RULED_SECTIONS = ("violations", "gate_inputs", "duplication", "dead_code", "survivors")


def keys_by_section(open_violations, report):
    """One key list per section of `RULED_SECTIONS`, aligned
    with that section's records.

    `open_violations` are the violation records left once
    accepted exceptions are taken out, so an accepted exception
    needs no ruling.
    """
    records_by_section = {
        "violations": open_violations,
        "gate_inputs": report.get("gate_input_violations", []),
        "duplication": report.get("duplication_candidates", []),
        "dead_code": report.get("dead_code_candidates", []),
        "survivors": report.get("surviving_mutants", []),
    }
    seen_counts = collections.Counter()
    keys = {}
    for section in RULED_SECTIONS:
        keys[section] = []
        for record in records_by_section[section]:
            base = _base_key(section, record)
            seen_counts[base] += 1
            suffix = f" #{seen_counts[base]}" if seen_counts[base] > 1 else ""
            keys[section].append(base + suffix)
    return keys


def _base_key(section, record):
    if section == "gate_inputs":
        return f"{record['kind']} {record['file']}"
    where = _location(record["file"], record.get("line"))
    if section == "duplication" and record.get("other_file"):
        return f"{record['metric']} {where} ~ {_location(record['other_file'], record.get('other_line'))}"
    detail = {
        "violations": record.get("function"),
        "duplication": None,
        "dead_code": record.get("name"),
        "survivors": record.get("mutator"),
    }[section]
    metric = "mutation" if section == "survivors" else record["metric"]
    return f"{metric} {where}" + (f" {detail}" if detail else "")


def _location(file, line):
    return file if line is None else f"{file}:{line}"
