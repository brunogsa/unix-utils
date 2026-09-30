"""Tests for check-bullet-structure.py - the report-only list-structure checker.

Three rules, each asserted as exact `(line, detail)` rows rather than a count:

  dangling-colon  a list item ending in ":" whose next list item sits at the
                  same or a shallower indent, so the colon introduces nothing.
  dangling-dash   a list item ending in an em dash or " --" whose next list
                  item, at the same or a shallower indent, continues the
                  sentence in lowercase.
  staircase       a chain of 3+ list items, each the single child of the one
                  above, reported once at the chain's head with its span.

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


# --- dangling-dash: flag cases ---


def test_flags_a_bullet_ending_in_an_em_dash_whose_next_sibling_continues_the_sentence_in_lowercase(tmp_path):
    result = run(
        tmp_path,
        "- Either flag marks a run with nobody standing by —\n"
        "- the same premise the other step uses, so a prompt here stalls the run.\n",
    )

    assert hits(result) == [(1, "dangling-dash")]
    assert result.returncode == 1


def test_flags_a_bullet_ending_in_a_double_hyphen_the_same_way(tmp_path):
    result = run(
        tmp_path,
        "- Either flag marks a run with nobody standing by --\n"
        "- the same premise the other step uses, so a prompt here stalls the run.\n",
    )

    assert hits(result) == [(1, "dangling-dash")]


def test_flags_a_dash_ended_bullet_whose_lowercase_continuation_sits_at_a_shallower_indent(tmp_path):
    result = run(
        tmp_path,
        "- **Under `--auto-solve`, never prompt on a multi-match** and say so.\n"
        "  - Either flag marks a run dispatched by a skill with nobody standing by —\n"
        "\n"
        "- the same premise the other step uses, so a prompt here stalls the run.\n",
    )

    assert hits(result) == [(2, "dangling-dash")]


# --- dangling-dash: no-flag cases ---


def test_leaves_a_dash_ended_bullet_alone_when_its_continuation_is_nested_beneath_it(tmp_path):
    result = run(
        tmp_path,
        "- Either flag marks a run with nobody standing by —\n"
        "  - the same premise the other step uses, so a prompt here stalls the run.\n",
    )

    assert hits(result) == []


def test_leaves_a_dash_used_as_an_empty_value_placeholder_alone_when_the_next_bullet_opens_uppercase(tmp_path):
    result = run(
        tmp_path,
        "- Corpo da requisição: —\n"
        "- Comportamento interno: grava a escola e publica o evento.\n",
    )

    assert hits(result) == []


def test_ignores_a_dash_that_sits_inside_a_trailing_inline_code_span(tmp_path):
    result = run(
        tmp_path,
        "- Options end at the separator `--`\n"
        "- files after it are read as paths, never as flags.\n",
    )

    assert hits(result) == []


# --- staircase: flag cases ---


def test_three_level_single_child_chain_is_reported_once_at_its_head_with_its_span(tmp_path):
    result = run(
        tmp_path,
        "- **O desligamento do IS dependia de uma configuração ausente.**\n"
        "  - Sem essa chave, o use case do IS não envia a escola.\n"
        "  - Em 29/09/2026, o PR #2644 adicionou a chave.\n"
        "    - O sync do IS passou a enviar escolas ao Protheus em produção.\n"
        "      - No mesmo dia, a DLQ do IS recebeu uma mensagem recusada com HTTP 400.\n"
        "\n"
        "  - Ainda em 29/09/2026, o PR #2657 zerou o batch size do IS.\n",
    )

    assert hits(result) == [(3, "staircase:3-5")]
    assert result.returncode == 1


def test_four_level_single_child_chain_is_reported_once_spanning_all_four_levels(tmp_path):
    result = run(
        tmp_path,
        "- **Como o PIC 1.9 escreve os Acordos no Protheus SAS/IS?**\n"
        "  - A resposta importa porque o PIC 2.0 vai reutilizar o mecanismo.\n"
        "  - O sync de Acordos cadastra o cliente no ERP antes de enviar o Acordo.\n"
        "    - Em produção, usa os mesmos endpoints de cliente que o sync de escolas.\n"
        "      - Está desligado para SAS e IS.\n"
        "        - Ligá-lo antes do saneamento traz de volta a sobrescrita?\n",
    )

    assert hits(result) == [(3, "staircase:3-6")]


def test_numbered_item_counts_as_a_chain_level(tmp_path):
    result = run(
        tmp_path,
        "1. Desligar o sync de escolas do SAS.\n"
        "   - O batch size da fila foi zerado.\n"
        "     - Com batch size 0, o Integrador não consome a fila.\n",
    )

    assert hits(result) == [(1, "staircase:1-3")]


# --- staircase: no-flag cases ---


def test_parent_with_a_single_child_and_no_grandchild_is_not_reported(tmp_path):
    result = run(
        tmp_path,
        "- **Vínculo:** cada conta do CRM corresponde a um cliente no Protheus.\n"
        "  - O vínculo é feito pelo CNPJ da escola.\n"
        "- **Volume:** aprox. 1.031 CNPJs no total.\n"
        "  - O volume de alteração esperado na virada é baixo.\n",
    )

    assert hits(result) == []


def test_chain_where_a_middle_level_has_two_children_is_not_reported(tmp_path):
    result = run(
        tmp_path,
        "- Pedir ao Protheus SAS e IS o endpoint `PUT /schools`.\n"
        "  - Os syncs de SAS e IS passam pelo http-caller.\n"
        "    - Manda para a DLQ as respostas 4xx do Protheus.\n"
        "    - O sync hub genérico não usa o http-caller.\n"
        "      - Falta confirmar se o endereço de entrega é opcional.\n",
    )

    assert hits(result) == []


def test_staircase_shaped_example_inside_a_fenced_code_block_is_not_reported(tmp_path):
    result = run(
        tmp_path,
        "```markdown\n"
        "- Level one.\n"
        "  - Level two.\n"
        "    - Level three.\n"
        "```\n",
    )

    assert hits(result) == []


# --- --changed-only scope ---


def test_changed_only_reports_a_staircase_whose_only_changed_line_is_its_third_level(tmp_path):
    repo = new_repo(tmp_path, "- Level one of the chain.\n  - Level two of the chain.\n")
    with open(repo / "doc.md", "a", encoding="utf-8") as fh:
        fh.write("    - Level three, added after the base commit.\n")

    result = run_changed_only(repo)

    assert hits(result) == [(1, "staircase:1-3")]
    assert result.returncode == 1


def test_changed_only_reports_a_dangling_colon_whose_only_changed_line_is_the_next_sibling(tmp_path):
    repo = new_repo(tmp_path, "- The rollout happens in two waves:\n")
    with open(repo / "doc.md", "a", encoding="utf-8") as fh:
        fh.write("- Monitoring starts after the second wave.\n")

    result = run_changed_only(repo)

    assert hits(result) == [(1, "dangling-colon")]


def test_changed_only_keeps_a_dangling_dash_hit_when_only_the_continuation_line_changed(tmp_path):
    repo = new_repo(tmp_path, "- Either flag marks a run with nobody standing by —\n")
    with open(repo / "doc.md", "a", encoding="utf-8") as fh:
        fh.write("- the same premise the other step uses, so a prompt here stalls the run.\n")

    result = run_changed_only(repo)

    assert hits(result) == [(1, "dangling-dash")]


def test_changed_only_hides_defects_whose_lines_were_all_left_untouched(tmp_path):
    repo = new_repo(
        tmp_path,
        "- Level one.\n  - Level two.\n    - Level three.\n- Ends with a colon:\n- Sibling.\n",
    )
    with open(repo / "doc.md", "a", encoding="utf-8") as fh:
        fh.write("\nA new closing paragraph.\n")

    result = run_changed_only(repo)

    assert hits(result) == []
    assert result.returncode == 0


def test_exits_2_naming_check_bullet_gap_when_that_sibling_cannot_be_loaded(tmp_path):
    # The hook reads exit 1 as findings, so a broken install
    # must exit 2 (no signal) rather than a traceback's 1.
    lone_dir = tmp_path / "lone"
    lone_dir.mkdir()
    lone_script = lone_dir / "check-bullet-structure.py"
    lone_script.write_text(SCRIPT.read_text(encoding="utf-8"), encoding="utf-8")
    doc = tmp_path / "doc.md"
    doc.write_text("- A plain item.\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(lone_script), str(doc)],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2, result.stderr
    assert "check-bullet-gap.py" in result.stderr
    assert "Traceback" not in result.stderr
