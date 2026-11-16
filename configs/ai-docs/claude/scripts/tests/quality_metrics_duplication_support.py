"""Declaration, fixture sources and measuring helpers the
quality-metrics duplication suites share.

Named without a `.test.py` or `test_` marker, so pytest
imports it and never collects it.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_support import commit_all, make_repo, measure_report

DECLARATION = """\
excluded_paths: [dist/]
ignored_extensions: [.md, .txt, .json, .yaml, .yml, .toml]
per_unit: []
languages:
  python:
    extensions: [.py]
    metrics: [code_duplication, test_duplication]
"""

PRICING = """\
def total_price(items, tax):
    total = 0
    for item in items:
        price = item["price"]
        if price > 100:
            price = price - 10
        total = total + price
    total = total * tax
    if total > 1000:
        total = total - 50
    label = "total"
    return label, total
"""

COSTING = """\
def sum_cost(rows, rate):
    acc = 0
    for row in rows:
        cost = row["cost"]
        if cost > 200:
            cost = cost - 20
        acc = acc + cost
    acc = acc * rate
    if acc > 2000:
        acc = acc - 70
    name = "sum"
    return name, acc
"""

NINE_LINE_TEST = """\
def test_{name}():
    calculator = Calculator()
    calculator.reset()
    result = calculator.add({first}, {second})
    assert result == {total}
    assert calculator.history == [{total}]
    calculator.clear()
    assert calculator.history == []
    assert calculator.is_empty()
"""

# The shorter tests are the 9-line test cut after its 8th and
# 7th line, so the text is written once.
EIGHT_LINE_TEST = "".join(NINE_LINE_TEST.splitlines(keepends=True)[:8])
SEVEN_LINE_TEST = "".join(NINE_LINE_TEST.splitlines(keepends=True)[:7])


def measure_files(tmp_path, files, declaration_file=None):
    repo = make_repo(tmp_path, files)
    declaration_path = declaration_file or tmp_path / "quality-metrics.yaml"
    if declaration_file is None:
        declaration_path.write_text(DECLARATION)
    return measure_report(repo, declaration_path, "--files", *files)["violations"]


def measure_uncommitted_changes(tmp_path, committed, changed):
    repo = make_repo(tmp_path, {"notes.txt": "fixture repo\n"})
    if committed:
        for name, text in committed.items():
            (repo / name).parent.mkdir(parents=True, exist_ok=True)
            (repo / name).write_text(text)
        commit_all(repo, "add files")
    for name, text in changed.items():
        (repo / name).parent.mkdir(parents=True, exist_ok=True)
        (repo / name).write_text(text)
    declaration_path = tmp_path / "quality-metrics.yaml"
    declaration_path.write_text(DECLARATION)
    return measure_report(
        repo, declaration_path, "--batch-end", "--base", "HEAD"
    )["violations"]
