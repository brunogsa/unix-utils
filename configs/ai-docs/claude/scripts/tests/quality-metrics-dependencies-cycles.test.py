import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_dependencies_support import (
    BILLING_INVOICE_READING_ORDERS,
    BILLING_READS_ORDERS,
    JS_DECLARATION,
    ORDER_READS_BILLING,
    ORDERS_ORDER_READING_BILLING,
    PYTHON_CYCLE_BASE_FILES,
    PYTHON_DECLARATION,
    BranchChange,
    measure_branch,
    report_for_branch,
)
from quality_metrics_support import (
    commit_all, head_of, make_repo, measure_report,
)


def test_flags_an_orders_billing_import_cycle_the_branch_introduces(tmp_path):
    change = BranchChange(
        PYTHON_CYCLE_BASE_FILES,
        {"shop/orders/order.py": ORDER_READS_BILLING},
    )

    violations = measure_branch(tmp_path, PYTHON_DECLARATION, change)

    assert len(violations) == 1
    cycle = violations[0]
    assert cycle["metric"] == "dependency_direction"
    assert cycle["kind"] == "cycle"
    assert cycle["file"] == "shop/orders/order.py"
    assert "orders" in cycle["detail"] and "billing" in cycle["detail"]


def test_flags_an_import_cycle_between_two_plain_modules_of_one_package(tmp_path):
    base_files = {
        "shop/__init__.py": "",
        "shop/orders.py": "ORDER_ID = 1\n",
        "shop/billing.py": BILLING_READS_ORDERS,
    }

    violations = measure_branch(
        tmp_path, PYTHON_DECLARATION,
        BranchChange(base_files, {"shop/orders.py": ORDER_READS_BILLING}),
    )

    assert len(violations) == 1
    assert violations[0]["kind"] == "cycle"
    assert violations[0]["file"] == "shop/orders.py"


def test_flags_an_import_cycle_between_two_packages_below_the_top_package(tmp_path):
    base_files = {
        "shop/__init__.py": "",
        "shop/sales/__init__.py": "",
        "shop/sales/orders/__init__.py": "",
        "shop/sales/orders/order.py": "ORDER_ID = 1\n",
        "shop/sales/billing/__init__.py": "",
        "shop/sales/billing/invoice.py": "from shop.sales.orders import order\n",
    }
    change = BranchChange(base_files, {"shop/sales/orders/order.py": (
        "from shop.sales.billing import invoice\n\nORDER_ID = 1\n"
    )})

    violations = measure_branch(tmp_path, PYTHON_DECLARATION, change)

    assert len(violations) == 1
    assert violations[0]["kind"] == "cycle"
    assert violations[0]["file"] == "shop/sales/orders/order.py"


def test_flags_an_import_cycle_in_a_package_kept_under_a_src_directory(tmp_path):
    base_files = {
        "src/shop/__init__.py": "",
        "src/shop/orders/__init__.py": "",
        "src/shop/orders/order.py": "ORDER_ID = 1\n",
        "src/shop/billing/__init__.py": "",
        "src/shop/billing/invoice.py": BILLING_READS_ORDERS,
    }
    change = BranchChange(
        base_files, {"src/shop/orders/order.py": ORDER_READS_BILLING}
    )

    violations = measure_branch(tmp_path, PYTHON_DECLARATION, change)

    assert len(violations) == 1
    assert violations[0]["kind"] == "cycle"
    assert violations[0]["file"] == "src/shop/orders/order.py"


def test_flags_a_cycle_in_the_first_package_a_branch_adds_to_a_tree_without_one(tmp_path):
    change = BranchChange(
        {"tools/sync.py": "SYNC = 1\n"},
        {
            "shop/__init__.py": "",
            "shop/orders.py": ORDER_READS_BILLING,
            "shop/billing.py": BILLING_READS_ORDERS,
        },
    )

    violations = measure_branch(tmp_path, PYTHON_DECLARATION, change)

    assert len(violations) == 2
    assert {violation["kind"] for violation in violations} == {"cycle"}
    assert {violation["file"] for violation in violations} == {
        "shop/orders.py", "shop/billing.py"
    }


def test_lists_a_cycle_already_present_at_the_base_ref_as_a_hotspot_not_a_violation(tmp_path):
    base_files = {
        "orders/order.js": ORDERS_ORDER_READING_BILLING,
        "billing/invoice.js": BILLING_INVOICE_READING_ORDERS,
    }
    change = BranchChange(
        base_files,
        {"orders/order.js": ORDERS_ORDER_READING_BILLING + "// tweaked\n"},
    )

    report = report_for_branch(tmp_path, JS_DECLARATION, change)

    assert report["violations"] == []
    hotspots = [item for item in report["measurements"] if item.get("hotspot")]
    assert [(item["kind"], item["file"]) for item in hotspots] == [("cycle", "orders/order.js")]
    assert "orders/order.js" in hotspots[0]["detail"]


def test_flags_a_cycle_the_range_adds_when_an_uncommitted_edit_to_an_untouched_file_breaks_it(tmp_path):
    repo = make_repo(tmp_path, PYTHON_CYCLE_BASE_FILES)
    base_sha = head_of(repo)
    (repo / "shop/orders/order.py").write_text(ORDER_READS_BILLING)
    commit_all(repo, "branch adds orders -> billing")

    # invoice.py is not in the range; the edit is uncommitted.
    (repo / "shop/billing/invoice.py").write_text("INVOICE_ID = 1\n")
    declaration_path = tmp_path / "quality-metrics.yaml"
    declaration_path.write_text(PYTHON_DECLARATION)

    report = measure_report(
        repo, declaration_path, "--diff", f"{base_sha}...HEAD"
    )

    assert [(item["kind"], item["file"]) for item in report["violations"]] == [
        ("cycle", "shop/orders/order.py")
    ]
