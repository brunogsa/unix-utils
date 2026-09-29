"""Tests for check-bullet-structure.py - the report-only list-structure checker.

Asserted as exact `(line, detail)` rows rather than a count:

  dangling-colon  a list item ending in ":" whose next list item sits at the
                  same or a shallower indent, so the colon introduces nothing.

Every fixture is hand-built. The Portuguese ones reproduce the shapes observed
in a real ADR run, rewritten here so an edit to that ADR never moves them.
"""

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "check-bullet-structure.py"


def run(tmp_path, content, name="doc.md"):
    """Write one fixture and run the checker over it as a subprocess.

    The exit code and the output rows are the contract the PostToolUse hook
    and the markdown-standards-fixer agent consume, and only a subprocess
    exercises both.
    """
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(path)],
        capture_output=True,
        text=True,
    )


def hits(result):
    """The `<line>:<detail>` rows as [(int, str)], dropping the `==` header.

    Asserts the checker actually ran first (exit 0 or 1): a crash prints no
    rows, which would otherwise pass every "is not reported" test.
    """
    assert result.returncode in (0, 1), result.stderr
    rows = []
    for line in result.stdout.splitlines():
        if not line.strip() or line.startswith("== "):
            continue
        number, _, detail = line.partition(":")
        rows.append((int(number), detail))
    return rows


def git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def new_repo(tmp_path, base_content):
    """A scratch repo with `doc.md` committed as `base_content`.

    resolve() matters on macOS: get-changed-lines.sh compares paths against
    `git rev-parse --show-toplevel`, which is always physical (/private/var).
    """
    repo = (tmp_path / "repo").resolve()
    repo.mkdir()
    git(repo, "init", "-q", ".")
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "user.name", "test")
    (repo / "doc.md").write_text(base_content, encoding="utf-8")
    git(repo, "add", "doc.md")
    git(repo, "commit", "-q", "-m", "base")
    return repo


def run_changed_only(repo):
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--changed-only", "doc.md"],
        capture_output=True,
        text=True,
        cwd=repo,
    )


# --- dangling-colon: flag cases ---


def test_colon_item_followed_by_a_sibling_at_the_same_indent_is_reported(tmp_path):
    result = run(
        tmp_path,
        "1. **Desligar o sync de escolas**, antes da carga oficial de 15/06/2026.\n"
        "   - A decisão foi tomada na reunião de 12/06/2026 e executada no mesmo dia:\n"
        "   - SAS: `BATCH_SIZE_X` = 0 em `terraform/prod.tfvars`.\n"
        "     - Com batch size 0, o Integrador não consome a fila.\n"
        "\n"
        "   - IS: nenhuma mudança foi feita.\n",
    )

    assert hits(result) == [(2, "dangling-colon")]
    assert result.returncode == 1


def test_colon_item_followed_by_a_shallower_item_across_a_blank_line_is_reported(tmp_path):
    result = run(
        tmp_path,
        "- Parent item about the rollout plan.\n"
        "  - The rollout happens in two waves:\n"
        "\n"
        "- Next top-level item about monitoring.\n",
    )

    assert hits(result) == [(2, "dangling-colon")]


def test_bold_label_ending_in_a_colon_followed_by_a_sibling_is_reported(tmp_path):
    result = run(
        tmp_path,
        "- **Notas:**\n"
        "- Nenhuma mudança de contrato foi necessária.\n",
    )

    assert hits(result) == [(1, "dangling-colon")]


# --- dangling-colon: no-flag cases ---


def test_colon_item_introducing_deeper_children_after_a_blank_line_is_not_reported(tmp_path):
    result = run(
        tmp_path,
        "- **Como religar o sync?** Em 29/09/2026, surgiram dois caminhos:\n"
        "\n"
        "  - Confirmar o saneamento e religar o sync atual.\n"
        "  - Pedir ao Protheus SAS e IS o endpoint `PUT /schools`.\n",
    )

    assert hits(result) == []
    assert result.returncode == 0


def test_colon_item_introducing_a_deeper_code_fence_is_not_reported(tmp_path):
    result = run(
        tmp_path,
        "- Run the migration first:\n"
        "  ```bash\n"
        "  yarn db:migrate\n"
        "  ```\n"
        "- Then restart the consumer.\n",
    )

    assert hits(result) == []


def test_colon_item_introducing_a_deeper_continuation_paragraph_is_not_reported(tmp_path):
    result = run(
        tmp_path,
        "- The consumer reads one setting:\n"
        "\n"
        "  Its batch size, which zero disables entirely.\n"
        "- The producer is unaffected.\n",
    )

    assert hits(result) == []


def test_plain_paragraph_ending_in_a_colon_before_a_list_is_not_reported(tmp_path):
    result = run(
        tmp_path,
        "Pontos técnicos relevantes:\n"
        "\n"
        "- O sync de escolas usa o http-caller.\n"
        "- O sync hub genérico não usa.\n",
    )

    assert hits(result) == []


def test_colon_inside_a_trailing_inline_code_span_is_not_reported(tmp_path):
    result = run(
        tmp_path,
        "- The log prefix is `sync-school:`\n"
        "- The queue name is `crm-sync-sas`.\n",
    )

    assert hits(result) == []


def test_label_items_whose_value_is_a_trailing_inline_code_span_are_not_reported(tmp_path):
    result = run(
        tmp_path,
        "- **Mode:** `local`\n"
        "- Single line: `src/services/auth.ts:42`\n"
        "- Range: `src/services/auth.ts:42-48`\n",
    )

    assert hits(result) == []


def test_colon_items_inside_a_fenced_code_block_are_not_reported(tmp_path):
    result = run(
        tmp_path,
        "```markdown\n"
        "- An example item that ends with a colon:\n"
        "- An example sibling right below it.\n"
        "```\n",
    )

    assert hits(result) == []


# --- --changed-only scope ---


def test_changed_only_reports_a_dangling_colon_whose_only_changed_line_is_the_next_sibling(tmp_path):
    repo = new_repo(tmp_path, "- The rollout happens in two waves:\n")
    with open(repo / "doc.md", "a", encoding="utf-8") as fh:
        fh.write("- Monitoring starts after the second wave.\n")

    result = run_changed_only(repo)

    assert hits(result) == [(1, "dangling-colon")]


def test_changed_only_hides_defects_whose_lines_were_all_left_untouched(tmp_path):
    repo = new_repo(
        tmp_path,
        "- Ends with a colon:\n- Sibling.\n",
    )
    with open(repo / "doc.md", "a", encoding="utf-8") as fh:
        fh.write("\nA new closing paragraph.\n")

    result = run_changed_only(repo)

    assert hits(result) == []
    assert result.returncode == 0
