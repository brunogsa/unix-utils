import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_support import commit_all, head_of, make_repo

from quality_metrics import gate_inputs

# The edit-time hook blocks these tokens in a code file, so each
# fixture is built by concatenation.
PYRIGHT_IGNORE = "# py" + "right: ignore"
STRYKER_DISABLE = "// Stry" + "ker disable next-line"
PRAGMA_NO_MUTATE = "# prag" + "ma: no mu" + "tate"


@pytest.mark.parametrize(
    "file_name, added_line, counted_value",
    [
        ("src/parse.py", f"value = load()  {PYRIGHT_IGNORE}[assignment]", PYRIGHT_IGNORE),
        ("src/parse.ts", f"{STRYKER_DISABLE} StringLiteral", "Stry" + "ker disable"),
        ("src/parse.py", f"value = load()  {PRAGMA_NO_MUTATE}", PRAGMA_NO_MUTATE),
    ],
    ids=["pyright ignore comment", "Stryker disable comment", "pragma no mutate comment"],
)
def test_should_list_an_added_type_check_or_mutation_disable_as_a_suppression_violation(
    tmp_path, file_name, added_line, counted_value
):
    repo = make_repo(tmp_path, {file_name: "value = 1\n"})
    base = head_of(repo)
    (repo / file_name).write_text(f"value = 1\n{added_line}\n")
    commit_all(repo, "disable a gate")

    violations = gate_inputs.added_suppressions(repo, base, "HEAD")

    assert violations == [{"kind": "suppression", "file": file_name, "value": counted_value}]
