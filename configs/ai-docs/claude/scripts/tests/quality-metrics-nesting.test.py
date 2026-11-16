import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from quality_metrics import declaration as declaring
from quality_metrics import functions
from quality_metrics.touched import Target

SHIPPED_DECLARATION = SCRIPTS_DIR / "quality-metrics.yaml"

PYTHON_SEQUENTIAL = """\
def flat(xs, a, b, c, d):
    if a:
        print(1)
    if b:
        print(2)
    if c:
        print(3)
    if d:
        print(4)
    return [x for x in xs if x]
"""

PYTHON_NESTED = """\
def deep(a):
    if a:
        for i in a:
            while i:
                if i > 2:
                    with open("x") as f:
                        if f:
                            return 1
    return 0
"""

JS_SOURCE = """\
function sequentialBraceless(a, b, c, d) {
  if (a) console.log(1);
  if (b) console.log(2);
  if (c) console.log(3);
  if (d) console.log(4);
  return 0;
}
function chain(x) {
  if (x === 1) { f(); } else if (x === 2) { g(); } else { h(); }
}
function chainInLoop(xs) {
  for (const x of xs) {
    if (x === 1) { f(); } else if (x === 2) { g(); } else { h(); }
  }
}
function bracelessLoops(xs) {
  for (const x of xs) if (x) f();
  for (const y of xs) if (y) g();
  return 0;
}
function nestedBraced(a) {
  if (a) { for (const i of a) { if (i) { while (i) { f(); } } } }
}
"""

JS_EXPECTED_NESTING = {
    "sequentialBraceless": 1,
    "chain": 1,
    "chainInLoop": 2,
    "bracelessLoops": 2,
    "nestedBraced": 4,
}


def nesting_by_function(tmp_path, file_name, source):
    path = tmp_path / file_name
    path.write_text(source)
    shipped = declaring.load_declaration(SHIPPED_DECLARATION)
    language = declaring.language_for_file(shipped, path)
    target = Target(
        path, language, None,
        nesting_reader=declaring.nesting_reader_for(shipped, language),
    )
    return {
        record["function"]: record["value"]
        for record in functions.measure(target, ["nesting"])
    }


def test_python_four_sequential_ifs_and_a_comprehension_measure_nesting_1(tmp_path):
    measured = nesting_by_function(tmp_path, "flat.py", PYTHON_SEQUENTIAL)

    assert measured == {"flat": 1}


def test_python_six_nested_blocks_measure_nesting_6(tmp_path):
    measured = nesting_by_function(tmp_path, "deep.py", PYTHON_NESTED)

    assert measured == {"deep": 6}


@pytest.mark.parametrize("file_name", ["probe.js", "probe.jsx", "probe.ts", "probe.tsx"])
def test_js_and_ts_nesting_reads_the_smaller_of_both_lizard_measures(
    tmp_path, file_name
):
    measured = nesting_by_function(tmp_path, file_name, JS_SOURCE)

    assert measured == JS_EXPECTED_NESTING


def test_a_language_with_no_declared_reader_keeps_the_nd_reading(tmp_path):
    shipped = declaring.load_declaration(SHIPPED_DECLARATION)

    assert declaring.nesting_reader_for(shipped, "go") == "nd"
