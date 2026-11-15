import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_support import commit_all, head_of, make_repo, measure_report

PYTHON_DECLARATION = """\
excluded_paths: [dist/]
ignored_extensions: [.md, .txt, .json, .yaml, .yml, .toml]
per_unit: []
languages:
  python:
    extensions: [.py]
    metrics: [dependency_direction]
"""

JS_DECLARATION = """\
excluded_paths: [dist/]
ignored_extensions: [.md, .txt, .json, .yaml, .yml, .toml]
per_unit: []
languages:
  js:
    extensions: [.js]
    metrics: [dependency_direction]
"""

# Layers run from the outermost to the innermost: infra may
# import domain, and domain may never import infra.
DECLARED_LAYERS = """\
source: declared
layers:
  - name: infra
    paths: [infra/**]
  - name: domain
    paths: [domain/**]
"""

BILLING_READS_ORDERS = "from shop.orders import order\n"
ORDER_READS_BILLING = "from shop.billing import invoice\n\nORDER_ID = 1\n"

DOMAIN_ORDER_WITHOUT_DB = "module.exports = { place: () => 'placed' };\n"
DOMAIN_ORDER_READING_DB = (
    "const db = require('../infra/db');\n\n"
    "module.exports = { place: () => db.save('placed') };\n"
)
INFRA_DB = "module.exports = { save: (row) => row };\n"
def measure_branch(tmp_path, declaration, base_files, branch_files, *arguments):
    """Violations of a branch adding `branch_files` on top of `base_files`."""
    repo = make_repo(tmp_path, base_files)
    base_sha = head_of(repo)
    for name, text in branch_files.items():
        (repo / name).write_text(text)
    commit_all(repo, "branch")
    declaration_path = tmp_path / "quality-metrics.yaml"
    declaration_path.write_text(declaration)
    report = measure_report(
        repo, declaration_path, "--diff", f"{base_sha}...HEAD", *arguments
    )
    return report["violations"]


def write_layers(tmp_path, text):
    layers_path = tmp_path / "layers.yaml"
    layers_path.write_text(text)
    return str(layers_path)


def test_flags_an_orders_billing_import_cycle_the_branch_introduces(tmp_path):
    base_files = {
        "shop/__init__.py": "",
        "shop/orders/__init__.py": "",
        "shop/orders/order.py": "ORDER_ID = 1\n",
        "shop/billing/__init__.py": "",
        "shop/billing/invoice.py": BILLING_READS_ORDERS,
    }

    violations = measure_branch(
        tmp_path, PYTHON_DECLARATION, base_files,
        {"shop/orders/order.py": ORDER_READS_BILLING},
    )

    assert len(violations) == 1
    cycle = violations[0]
    assert cycle["metric"] == "dependency_direction"
    assert cycle["kind"] == "cycle"
    assert cycle["file"] == "shop/orders/order.py"
    assert "orders" in cycle["detail"] and "billing" in cycle["detail"]


def test_flags_a_domain_to_infra_import_against_a_declared_layer_map(tmp_path):
    base_files = {
        "domain/order.js": DOMAIN_ORDER_WITHOUT_DB,
        "infra/db.js": INFRA_DB,
    }

    violations = measure_branch(
        tmp_path, JS_DECLARATION, base_files,
        {"domain/order.js": DOMAIN_ORDER_READING_DB},
        "--layers", write_layers(tmp_path, DECLARED_LAYERS),
    )

    assert len(violations) == 1
    layer_import = violations[0]
    assert layer_import["kind"] == "layer"
    assert layer_import["file"] == "domain/order.js"
    assert layer_import["other_file"] == "infra/db.js"
    assert layer_import["layer_map_source"] == "declared"
