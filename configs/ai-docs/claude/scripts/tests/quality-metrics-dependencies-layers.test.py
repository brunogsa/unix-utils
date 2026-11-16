import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_dependencies_support import (
    BILLING_INVOICE_READING_ORDERS,
    DECLARED_LAYERS,
    DOMAIN_ORDER_READING_DB,
    DOMAIN_ORDER_WITHOUT_DB,
    INFERRED_LABEL,
    INFERRED_LAYERS,
    INFRA_DB,
    JS_DECLARATION,
    ORDERS_ORDER_READING_BILLING,
    ORDERS_ORDER_WITHOUT_BILLING,
    PYTHON_DECLARATION,
    PYTHON_DOMAIN_READING_INFRA,
    PYTHON_DOMAIN_WITHOUT_INFRA,
    PYTHON_INFRA_DB,
    BranchChange,
    measure_branch,
    write_layers,
)

PYTHON_LAYER_BASE_FILES = {
    "domain/__init__.py": "",
    "domain/order.py": PYTHON_DOMAIN_WITHOUT_INFRA,
    "infra/__init__.py": "",
    "infra/db.py": PYTHON_INFRA_DB,
}


def test_flags_a_domain_to_infra_import_against_a_declared_layer_map(tmp_path):
    change = BranchChange(
        {"domain/order.js": DOMAIN_ORDER_WITHOUT_DB, "infra/db.js": INFRA_DB},
        {"domain/order.js": DOMAIN_ORDER_READING_DB},
    )

    violations = measure_branch(
        tmp_path, JS_DECLARATION, change,
        "--layers", write_layers(tmp_path, DECLARED_LAYERS),
    )

    assert len(violations) == 1
    layer_import = violations[0]
    assert layer_import["kind"] == "layer"
    assert layer_import["file"] == "domain/order.js"
    assert layer_import["other_file"] == "infra/db.js"
    assert layer_import["layer_map_source"] == "declared"


def test_flags_the_layer_import_and_the_cycle_from_an_inferred_map_labelled_inferred_not_declared(tmp_path):
    base_files = {
        "domain/order.js": DOMAIN_ORDER_WITHOUT_DB,
        "infra/db.js": INFRA_DB,
        "orders/order.js": ORDERS_ORDER_WITHOUT_BILLING,
        "billing/invoice.js": BILLING_INVOICE_READING_ORDERS,
    }
    change = BranchChange(base_files, {
        "domain/order.js": DOMAIN_ORDER_READING_DB,
        "orders/order.js": ORDERS_ORDER_READING_BILLING,
    })

    violations = measure_branch(
        tmp_path, JS_DECLARATION, change,
        "--layers", write_layers(tmp_path, INFERRED_LAYERS),
    )

    found = {(item["kind"], item["file"]) for item in violations}
    assert found == {("layer", "domain/order.js"), ("cycle", "orders/order.js")}
    assert {item["layer_map_source"] for item in violations} == {INFERRED_LABEL}


def test_flags_a_python_domain_to_infra_import_through_an_import_linter_layers_contract(tmp_path):
    change = BranchChange(
        PYTHON_LAYER_BASE_FILES, {"domain/order.py": PYTHON_DOMAIN_READING_INFRA}
    )

    violations = measure_branch(
        tmp_path, PYTHON_DECLARATION, change,
        "--layers", write_layers(tmp_path, DECLARED_LAYERS),
    )

    assert len(violations) == 1
    layer_import = violations[0]
    assert layer_import["kind"] == "layer"
    assert layer_import["file"] == "domain/order.py"
    assert layer_import["other_file"] == "infra/db.py"
    assert layer_import["layer_map_source"] == "declared"


def test_flags_a_python_layer_import_when_the_layer_packages_sit_under_a_src_directory(tmp_path):
    base_files = {
        "src/domain/__init__.py": "",
        "src/domain/order.py": PYTHON_DOMAIN_WITHOUT_INFRA,
        "src/infra/__init__.py": "",
        "src/infra/db.py": PYTHON_INFRA_DB,
    }
    src_layers = DECLARED_LAYERS.replace("infra/**", "src/infra/**").replace(
        "domain/**", "src/domain/**"
    )
    change = BranchChange(
        base_files, {"src/domain/order.py": PYTHON_DOMAIN_READING_INFRA}
    )

    violations = measure_branch(
        tmp_path, PYTHON_DECLARATION, change,
        "--layers", write_layers(tmp_path, src_layers),
    )

    assert len(violations) == 1
    assert violations[0]["kind"] == "layer"
    assert violations[0]["file"] == "src/domain/order.py"
    assert violations[0]["other_file"] == "src/infra/db.py"


def test_scores_a_python_file_as_a_deferred_violation_when_only_one_declared_layer_names_a_package(tmp_path):
    base_files = {
        "infra/__init__.py": "",
        "infra/db.py": PYTHON_INFRA_DB,
    }
    change = BranchChange(base_files, {"infra/db.py": "SAVED = 2\n"})

    violations = measure_branch(
        tmp_path, PYTHON_DECLARATION, change,
        "--layers", write_layers(tmp_path, DECLARED_LAYERS),
    )

    assert len(violations) == 1
    deferred = violations[0]
    assert deferred["metric"] == "dependency_direction"
    assert deferred["file"] == "infra/db.py"
    assert deferred["kind"] == "tool-failure"
    assert "domain" in deferred["detail"]
    assert deferred["layer_map_source"] == "declared"
    assert deferred["pessimistic"] is True
    assert "deferred" in deferred["label"]


def test_scores_a_python_file_as_a_deferred_violation_when_a_layer_glob_keeps_a_wildcard_in_its_path(tmp_path):
    wildcard_layers = DECLARED_LAYERS.replace("infra/**", "inf*/**")
    change = BranchChange(
        PYTHON_LAYER_BASE_FILES, {"domain/order.py": PYTHON_DOMAIN_READING_INFRA}
    )

    violations = measure_branch(
        tmp_path, PYTHON_DECLARATION, change,
        "--layers", write_layers(tmp_path, wildcard_layers),
    )

    assert len(violations) == 1
    assert violations[0]["kind"] == "tool-failure"
    assert "infra" in violations[0]["detail"]
    assert violations[0]["pessimistic"] is True
