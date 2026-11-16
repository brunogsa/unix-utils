import configparser
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_support import (
    GIT_ENV, commit_all, head_of, make_repo, measure_report, run_measure,
)

def declaration_for(language, extension):
    """A declaration measuring only dependency direction for
    one language."""
    return f"""\
excluded_paths: [dist/]
ignored_extensions: [.md, .txt, .json, .yaml, .yml, .toml]
per_unit: []
languages:
  {language}:
    extensions: [{extension}]
    metrics: [dependency_direction]
"""


PYTHON_DECLARATION = declaration_for("python", ".py")

JS_DECLARATION = declaration_for("js", ".js")

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

INFERRED_LABEL = "inferred, not declared"

INFERRED_LAYERS = DECLARED_LAYERS.replace("declared", INFERRED_LABEL)

BILLING_READS_ORDERS = "from shop.orders import order\n"
ORDER_READS_BILLING = "from shop.billing import invoice\n\nORDER_ID = 1\n"

DOMAIN_ORDER_WITHOUT_DB = "module.exports = { place: () => 'placed' };\n"
DOMAIN_ORDER_READING_DB = (
    "const db = require('../infra/db');\n\n"
    "module.exports = { place: () => db.save('placed') };\n"
)
INFRA_DB = "module.exports = { save: (row) => row };\n"
ORDERS_ORDER_WITHOUT_BILLING = "module.exports = { id: 1 };\n"
ORDERS_ORDER_READING_BILLING = (
    "const invoice = require('../billing/invoice');\n\n"
    "module.exports = { id: 1, invoice };\n"
)
BILLING_INVOICE_READING_ORDERS = (
    "const order = require('../orders/order');\n\n"
    "module.exports = { total: order.id };\n"
)


def report_for_branch(tmp_path, declaration, base_files, branch_files, *arguments, env=None):
    """Report of a branch adding `branch_files` on top of
    `base_files`."""
    repo = make_repo(tmp_path, base_files)
    base_sha = head_of(repo)
    for name, text in branch_files.items():
        (repo / name).parent.mkdir(parents=True, exist_ok=True)
        (repo / name).write_text(text)
    commit_all(repo, "branch")
    declaration_path = tmp_path / "quality-metrics.yaml"
    declaration_path.write_text(declaration)
    return measure_report(
        repo, declaration_path, "--diff", f"{base_sha}...HEAD", *arguments, env=env
    )


def measure_branch(tmp_path, declaration, base_files, branch_files, *arguments, env=None):
    """Violations of a branch adding `branch_files` on top of
    `base_files`."""
    return report_for_branch(
        tmp_path, declaration, base_files, branch_files, *arguments, env=env
    )["violations"]


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


def test_flags_an_import_cycle_between_two_plain_modules_of_one_package(tmp_path):
    base_files = {
        "shop/__init__.py": "",
        "shop/orders.py": "ORDER_ID = 1\n",
        "shop/billing.py": BILLING_READS_ORDERS,
    }

    violations = measure_branch(
        tmp_path, PYTHON_DECLARATION, base_files,
        {"shop/orders.py": ORDER_READS_BILLING},
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

    violations = measure_branch(
        tmp_path, PYTHON_DECLARATION, base_files,
        {"shop/sales/orders/order.py": (
            "from shop.sales.billing import invoice\n\nORDER_ID = 1\n"
        )},
    )

    assert len(violations) == 1
    assert violations[0]["kind"] == "cycle"
    assert violations[0]["file"] == "shop/sales/orders/order.py"


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


def test_flags_the_layer_import_and_the_cycle_from_an_inferred_map_labelled_inferred_not_declared(tmp_path):
    base_files = {
        "domain/order.js": DOMAIN_ORDER_WITHOUT_DB,
        "infra/db.js": INFRA_DB,
        "orders/order.js": ORDERS_ORDER_WITHOUT_BILLING,
        "billing/invoice.js": BILLING_INVOICE_READING_ORDERS,
    }

    violations = measure_branch(
        tmp_path, JS_DECLARATION, base_files,
        {
            "domain/order.js": DOMAIN_ORDER_READING_DB,
            "orders/order.js": ORDERS_ORDER_READING_BILLING,
        },
        "--layers", write_layers(tmp_path, INFERRED_LAYERS),
    )

    found = {(item["kind"], item["file"]) for item in violations}
    assert found == {("layer", "domain/order.js"), ("cycle", "orders/order.js")}
    assert {item["layer_map_source"] for item in violations} == {INFERRED_LABEL}


def test_lists_a_cycle_already_present_at_the_base_ref_as_a_hotspot_not_a_violation(tmp_path):
    base_files = {
        "orders/order.js": ORDERS_ORDER_READING_BILLING,
        "billing/invoice.js": BILLING_INVOICE_READING_ORDERS,
    }

    report = report_for_branch(
        tmp_path, JS_DECLARATION, base_files,
        {"orders/order.js": ORDERS_ORDER_READING_BILLING + "// tweaked\n"},
    )

    assert report["violations"] == []
    hotspots = [item for item in report["measurements"] if item.get("hotspot")]
    assert [(item["kind"], item["file"]) for item in hotspots] == [("cycle", "orders/order.js")]
    assert "orders/order.js" in hotspots[0]["detail"]


PYTHON_DOMAIN_WITHOUT_INFRA = "ORDER_ID = 1\n"
PYTHON_DOMAIN_READING_INFRA = "from infra import db\n\nORDER_ID = db.SAVED\n"
PYTHON_INFRA_DB = "SAVED = 1\n"

GO_DECLARATION = declaration_for("go", ".go")

GO_MODULE = "module shop\n\ngo 1.25\n"
GO_DOMAIN_WITHOUT_INFRA = "package domain\n\nconst OrderID = 1\n"
GO_DOMAIN_READING_INFRA = (
    'package domain\n\nimport "shop/infra"\n\nvar OrderID = infra.Saved\n'
)
GO_INFRA_DB = "package infra\n\nconst Saved = 1\n"

# Stands in for go-arch-lint: it copies the archfile it was
# given to a capture path, and reports a domain-to-infra import
# only when the project's domain file mentions infra.
GO_ARCH_LINT_STUB = """#!/bin/sh
while [ $# -gt 0 ]; do
  case "$1" in
    --project-path) project="$2"; shift ;;
    --arch-file) archfile="$2"; shift ;;
    --max-warnings) max_warnings="$2"; shift ;;
  esac
  shift
done
if [ "$max_warnings" -lt 1 ] || [ "$max_warnings" -gt 32768 ]; then
  echo "flag 'max-warnings' should by in range [1 .. 32768]" >&2
  exit 1
fi
cp "$archfile" "@CAPTURE_PATH@"
if python3 -c 'import json, sys
deps = json.load(open(sys.argv[1]))["deps"]
sys.exit(0 if any(
    not dep.get("mayDependOn")
    and not dep.get("anyProjectDeps")
    and not dep.get("anyVendorDeps")
    for dep in deps.values()) else 1)' "$archfile"; then
  cat <<'JSON'
{"Type":"models.Check","Payload":{"ExecutionWarnings":[{"Text":"should have ref in 'mayDependOn'/'canUse' or at least one flag of ['anyProjectDeps', 'anyVendorDeps']","File":"config.yml"}],
"ArchHasWarnings":false,"ArchWarningsDeps":[],"ArchWarningsNotMatched":[],
"ArchWarningsDeepScan":[],"OmittedCount":0,"ModuleName":"shop","Qualities":[]}}
JSON
  exit 1
fi
if grep -q 'shop/infra' "$project/domain/order.go"; then
  cat <<'JSON'
{"Type":"models.Check","Payload":{"ExecutionWarnings":[],"ArchHasWarnings":true,
"ArchWarningsDeps":[{"ComponentName":"domain","FileRelativePath":"/domain/order.go",
"FileAbsolutePath":"/tmp/goshop/domain/order.go","ResolvedImportName":"shop/infra",
"Reference":{"Valid":true,"File":"/tmp/goshop/domain/order.go","Line":3,"Offset":8}}],
"ArchWarningsNotMatched":[],"ArchWarningsDeepScan":[],"OmittedCount":0,
"ModuleName":"shop","Qualities":[]}}
JSON
  exit 1
fi
cat <<'JSON'
{"Type":"models.Check","Payload":{"ExecutionWarnings":[],"ArchHasWarnings":false,
"ArchWarningsDeps":[],"ArchWarningsNotMatched":[],"ArchWarningsDeepScan":[],
"OmittedCount":0,"ModuleName":"shop","Qualities":[]}}
JSON
"""

# Stands in for a go-arch-lint that skips the check on a config
# notice, whatever the archfile holds.
GO_ARCH_LINT_STUB_SKIPPING_THE_CHECK = """#!/bin/sh
cat <<'JSON'
{"Type":"models.Check","Payload":{"ExecutionWarnings":[{"Text":"config notice","File":"config.yml"}],
"ArchHasWarnings":false,"ArchWarningsDeps":[],"ArchWarningsNotMatched":[],
"ArchWarningsDeepScan":[],"OmittedCount":0,"ModuleName":"shop","Qualities":[]}}
JSON
exit 1
"""

GO_BASE_FILES = {
    "go.mod": GO_MODULE,
    "domain/order.go": GO_DOMAIN_WITHOUT_INFRA,
    "infra/db.go": GO_INFRA_DB,
}


def env_with_go_arch_lint_stub(tmp_path, capture_path):
    stub_dir = tmp_path / "stub-bin"
    stub_dir.mkdir()
    stub = stub_dir / "go-arch-lint"
    stub.write_text(
        GO_ARCH_LINT_STUB.replace("@CAPTURE_PATH@", str(capture_path))
    )
    stub.chmod(0o755)
    return {**GIT_ENV, "PATH": f"{stub_dir}{os.pathsep}{GIT_ENV['PATH']}"}


def env_without_go_arch_lint():
    """PATH with every directory that holds a go-arch-lint
    removed."""
    kept = [
        directory for directory in GIT_ENV["PATH"].split(os.pathsep)
        if not (Path(directory) / "go-arch-lint").exists()
    ]
    return {**GIT_ENV, "PATH": os.pathsep.join(kept)}


ALL_LANGUAGES_DECLARATION = """\
excluded_paths: [dist/]
ignored_extensions: [.md, .txt, .json, .yaml, .yml, .toml]
per_unit: []
languages:
  js:
    extensions: [.js]
    metrics: [dependency_direction]
  python:
    extensions: [.py]
    metrics: [dependency_direction]
  go:
    extensions: [.go]
    metrics: [dependency_direction]
"""

# Hands its config file to a capture path, then runs the tool
# that was really on PATH, so the tool's own run stays real.
CONFIG_CAPTURE_WRAPPER = """#!/bin/sh
previous=""
for argument in "$@"; do
  case "$previous" in
    --config|--arch-file)
      cp "$argument" "{capture_dir}/{name}.config"
      echo "$argument" > "{capture_dir}/{name}.path" ;;
  esac
  previous="$argument"
done
exec "{real_tool}" "$@"
"""


def env_capturing_configs(tmp_path, capture_dir):
    """Env where dependency-cruiser, lint-imports and
    go-arch-lint save their configs."""
    stubbed_env = env_with_go_arch_lint_stub(tmp_path, capture_dir / "unused-copy")
    wrapper_dir = tmp_path / "capture-bin"
    wrapper_dir.mkdir()
    for name in ("depcruise", "lint-imports", "go-arch-lint"):
        real_tool = shutil.which(name, path=stubbed_env["PATH"])
        wrapper = wrapper_dir / name
        wrapper.write_text(CONFIG_CAPTURE_WRAPPER.format(
            capture_dir=capture_dir, name=name, real_tool=real_tool
        ))
        wrapper.chmod(0o755)
    return {**stubbed_env, "PATH": f"{wrapper_dir}{os.pathsep}{stubbed_env['PATH']}"}


def test_translates_one_layer_map_into_dependency_cruiser_import_linter_and_go_arch_lint_configs_in_a_temp_directory(tmp_path):
    capture_dir = tmp_path / "captured"
    capture_dir.mkdir()
    base_files = {
        "go.mod": GO_MODULE,
        "domain/__init__.py": "",
        "domain/order.py": PYTHON_DOMAIN_WITHOUT_INFRA,
        "domain/order.js": DOMAIN_ORDER_WITHOUT_DB,
        "domain/order.go": GO_DOMAIN_WITHOUT_INFRA,
        "infra/__init__.py": "",
        "infra/db.py": PYTHON_INFRA_DB,
        "infra/db.js": INFRA_DB,
        "infra/db.go": GO_INFRA_DB,
    }

    report_for_branch(
        tmp_path, ALL_LANGUAGES_DECLARATION, base_files,
        {
            "domain/order.py": PYTHON_DOMAIN_WITHOUT_INFRA + "# tweaked\n",
            "domain/order.js": DOMAIN_ORDER_WITHOUT_DB + "// tweaked\n",
            "domain/order.go": GO_DOMAIN_WITHOUT_INFRA + "// tweaked\n",
        },
        "--layers", write_layers(tmp_path, DECLARED_LAYERS),
        env=env_capturing_configs(tmp_path, capture_dir),
    )

    assert_dependency_cruiser_config_layers(capture_dir)
    assert_import_linter_config_layers(capture_dir)
    assert_go_arch_lint_config_layers(capture_dir)
    assert_configs_sit_in_the_system_temp_directory(capture_dir, tmp_path)


def assert_dependency_cruiser_config_layers(capture_dir):
    depcruise = json.loads((capture_dir / "depcruise.config").read_text())
    rules = {rule["name"]: rule for rule in depcruise["forbidden"]}
    assert set(rules) == {"no-circular", "layer-domain"}
    domain_rule = rules["layer-domain"]
    assert re.search(domain_rule["from"]["path"], "domain/order.js")
    assert not re.search(domain_rule["from"]["path"], "infra/db.js")
    assert re.search(domain_rule["to"]["path"], "infra/db.js")
    assert not re.search(domain_rule["to"]["path"], "domain/order.js")


def assert_import_linter_config_layers(capture_dir):
    import_linter = configparser.ConfigParser()
    import_linter.read_string((capture_dir / "lint-imports.config").read_text())
    layers_contract = import_linter["importlinter:contract:layers"]
    assert layers_contract["type"] == "layers"
    assert layers_contract["layers"].split() == ["infra", "domain"]


def assert_go_arch_lint_config_layers(capture_dir):
    go_arch_lint = yaml.safe_load((capture_dir / "go-arch-lint.config").read_text())
    assert list(go_arch_lint["components"]) == ["infra", "domain"]
    assert go_arch_lint["deps"] == {
        "infra": {"mayDependOn": ["infra", "domain"]},
        "domain": {"mayDependOn": ["domain"]},
    }


def assert_configs_sit_in_the_system_temp_directory(capture_dir, tmp_path):
    system_temp = Path(tempfile.gettempdir()).resolve()
    for name in ("depcruise", "lint-imports", "go-arch-lint"):
        config_path = Path((capture_dir / f"{name}.path").read_text().strip()).resolve()
        assert config_path.is_relative_to(system_temp)
        assert not config_path.is_relative_to(tmp_path.resolve())


def test_flags_a_python_domain_to_infra_import_through_an_import_linter_layers_contract(tmp_path):
    base_files = {
        "domain/__init__.py": "",
        "domain/order.py": PYTHON_DOMAIN_WITHOUT_INFRA,
        "infra/__init__.py": "",
        "infra/db.py": PYTHON_INFRA_DB,
    }

    violations = measure_branch(
        tmp_path, PYTHON_DECLARATION, base_files,
        {"domain/order.py": PYTHON_DOMAIN_READING_INFRA},
        "--layers", write_layers(tmp_path, DECLARED_LAYERS),
    )

    assert len(violations) == 1
    layer_import = violations[0]
    assert layer_import["kind"] == "layer"
    assert layer_import["file"] == "domain/order.py"
    assert layer_import["other_file"] == "infra/db.py"
    assert layer_import["layer_map_source"] == "declared"


def test_flags_an_import_cycle_in_a_package_kept_under_a_src_directory(tmp_path):
    base_files = {
        "src/shop/__init__.py": "",
        "src/shop/orders/__init__.py": "",
        "src/shop/orders/order.py": "ORDER_ID = 1\n",
        "src/shop/billing/__init__.py": "",
        "src/shop/billing/invoice.py": BILLING_READS_ORDERS,
    }

    violations = measure_branch(
        tmp_path, PYTHON_DECLARATION, base_files,
        {"src/shop/orders/order.py": ORDER_READS_BILLING},
    )

    assert len(violations) == 1
    assert violations[0]["kind"] == "cycle"
    assert violations[0]["file"] == "src/shop/orders/order.py"


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

    violations = measure_branch(
        tmp_path, PYTHON_DECLARATION, base_files,
        {"src/domain/order.py": PYTHON_DOMAIN_READING_INFRA},
        "--layers", write_layers(tmp_path, src_layers),
    )

    assert len(violations) == 1
    assert violations[0]["kind"] == "layer"
    assert violations[0]["file"] == "src/domain/order.py"
    assert violations[0]["other_file"] == "src/infra/db.py"


def test_scores_a_python_file_as_a_deferred_violation_when_the_tree_has_no_package(tmp_path):
    violations = measure_branch(
        tmp_path, PYTHON_DECLARATION, {"tools/sync.py": "SYNC = 1\n"},
        {"tools/sync.py": "SYNC = 2\n"},
    )

    assert len(violations) == 1
    deferred = violations[0]
    assert deferred["metric"] == "dependency_direction"
    assert deferred["file"] == "tools/sync.py"
    assert deferred["pessimistic"] is True
    assert "deferred" in deferred["label"]


def test_scores_a_python_file_outside_every_package_as_a_deferred_tool_failure(tmp_path):
    base_files = {**PYTHON_CYCLE_BASE_FILES, "tools/sync.py": "SYNC = 1\n"}

    violations = measure_branch(
        tmp_path, PYTHON_DECLARATION, base_files,
        {"tools/sync.py": "SYNC = 2\n"},
    )

    assert len(violations) == 1
    deferred = violations[0]
    assert deferred["metric"] == "dependency_direction"
    assert deferred["file"] == "tools/sync.py"
    assert deferred["kind"] == "tool-failure"
    assert "outside any Python package" in deferred["detail"]
    assert deferred["other_file"] is None
    assert deferred["layer_map_source"] is None
    assert deferred["pessimistic"] is True
    assert "deferred" in deferred["label"]


def test_scores_loose_python_scripts_as_one_deferred_record_not_one_per_file(tmp_path):
    scripts = ("a.py", "b.py", "c.py")
    base_files = {f"tools/{name}": "X = 1\n" for name in scripts}

    violations = measure_branch(
        tmp_path, PYTHON_DECLARATION, base_files,
        {f"tools/{name}": "X = 2\n" for name in scripts},
    )

    assert len(violations) == 1
    deferred = violations[0]
    assert deferred["metric"] == "dependency_direction"
    assert deferred["pessimistic"] is True
    assert "deferred" in deferred["label"]
    assert deferred["file"].startswith("tools/")
    assert "3 Python files" in deferred["detail"]


def test_flags_a_cycle_in_the_first_package_a_branch_adds_to_a_tree_without_one(tmp_path):
    violations = measure_branch(
        tmp_path, PYTHON_DECLARATION, {"tools/sync.py": "SYNC = 1\n"},
        {
            "shop/__init__.py": "",
            "shop/orders.py": ORDER_READS_BILLING,
            "shop/billing.py": BILLING_READS_ORDERS,
        },
    )

    assert len(violations) == 2
    assert {violation["kind"] for violation in violations} == {"cycle"}
    assert {violation["file"] for violation in violations} == {
        "shop/orders.py", "shop/billing.py"
    }


# Stands in for lint-imports: it records its arguments, then
# reports one contract kept, as a run with nothing to flag does.
LINT_IMPORTS_STUB_RECORDING_ARGUMENTS = """#!/bin/sh
echo "$@" > "{capture_path}"
echo "Contracts: 1 kept, 0 broken."
exit 0
"""

# A broken-contract exit whose report no line pattern reads, as
# a reworded release of import-linter would print.
LINT_IMPORTS_STUB_BREAKING_IN_AN_UNKNOWN_FORMAT = """#!/bin/sh
echo "Contracts: 0 kept, 1 broken."
echo "Contract failed: cycles-shop. shop.orders and shop.billing import each other."
exit 1
"""

# An import-linter run that checked no contract: no summary
# line, as when it cannot read its config.
LINT_IMPORTS_STUB_PRINTING_NO_CONTRACT_SUMMARY = """#!/bin/sh
echo "Could not read configuration."
exit 0
"""

PYTHON_CYCLE_BASE_FILES = {
    "shop/__init__.py": "",
    "shop/orders/__init__.py": "",
    "shop/orders/order.py": "ORDER_ID = 1\n",
    "shop/billing/__init__.py": "",
    "shop/billing/invoice.py": BILLING_READS_ORDERS,
}


# A uv that fails the run: import-linter measured through it
# would defer, so a real measurement proves uv was never called.
UV_STUB_FAILING = """#!/bin/sh
echo "uv must not run import-linter" >&2
exit 99
"""


def env_with_lint_imports_stub(tmp_path, script):
    stub_dir = tmp_path / "lint-imports-stub-bin"
    stub_dir.mkdir()
    stub = stub_dir / "lint-imports"
    stub.write_text(script)
    stub.chmod(0o755)
    failing_uv = stub_dir / "uv"
    failing_uv.write_text(UV_STUB_FAILING)
    failing_uv.chmod(0o755)
    return {**GIT_ENV, "PATH": f"{stub_dir}{os.pathsep}{GIT_ENV['PATH']}"}


def env_without_lint_imports():
    kept_dirs = [
        directory for directory in GIT_ENV["PATH"].split(os.pathsep)
        if not (Path(directory) / "lint-imports").exists()
    ]
    return {**GIT_ENV, "PATH": os.pathsep.join(kept_dirs)}


def test_runs_lint_imports_directly_without_going_through_uv(tmp_path):
    capture_path = tmp_path / "lint-imports.arguments"

    violations = measure_branch(
        tmp_path, PYTHON_DECLARATION, PYTHON_CYCLE_BASE_FILES,
        {"shop/orders/order.py": ORDER_READS_BILLING},
        env=env_with_lint_imports_stub(
            tmp_path,
            LINT_IMPORTS_STUB_RECORDING_ARGUMENTS.format(capture_path=capture_path),
        ),
    )

    assert violations == []
    assert "--no-cache" in capture_path.read_text()


@pytest.mark.parametrize("lint_imports_stub", [
    None,
    LINT_IMPORTS_STUB_BREAKING_IN_AN_UNKNOWN_FORMAT,
    LINT_IMPORTS_STUB_PRINTING_NO_CONTRACT_SUMMARY,
], ids=["not installed", "unread broken-contract format", "no contract checked"])
def test_scores_a_python_file_as_a_deferred_violation_when_lint_imports_cannot_check_its_contracts(
    tmp_path, lint_imports_stub
):
    env = (
        env_without_lint_imports() if lint_imports_stub is None
        else env_with_lint_imports_stub(tmp_path, lint_imports_stub)
    )

    violations = measure_branch(
        tmp_path, PYTHON_DECLARATION, PYTHON_CYCLE_BASE_FILES,
        {"shop/orders/order.py": ORDER_READS_BILLING}, env=env,
    )

    assert len(violations) == 1
    deferred = violations[0]
    assert deferred["file"] == "shop/orders/order.py"
    assert deferred["pessimistic"] is True
    assert "deferred" in deferred["label"]


def test_scores_a_go_file_as_a_deferred_violation_when_go_arch_lint_skips_the_check(tmp_path):
    stub_dir = tmp_path / "skipping-stub-bin"
    stub_dir.mkdir()
    stub = stub_dir / "go-arch-lint"
    stub.write_text(GO_ARCH_LINT_STUB_SKIPPING_THE_CHECK)
    stub.chmod(0o755)

    violations = measure_branch(
        tmp_path, GO_DECLARATION, GO_BASE_FILES,
        {"domain/order.go": GO_DOMAIN_READING_INFRA},
        "--layers", write_layers(tmp_path, DECLARED_LAYERS),
        env={**GIT_ENV, "PATH": f"{stub_dir}{os.pathsep}{GIT_ENV['PATH']}"},
    )

    assert len(violations) == 1
    deferred = violations[0]
    assert deferred["file"] == "domain/order.go"
    assert deferred["pessimistic"] is True
    assert "deferred" in deferred["label"]


def test_hands_go_arch_lint_a_config_where_each_layer_may_depend_on_itself_and_the_layers_after_it(tmp_path):
    capture_path = tmp_path / "captured-archfile.yaml"

    measure_branch(
        tmp_path, GO_DECLARATION, GO_BASE_FILES,
        {"domain/order.go": GO_DOMAIN_READING_INFRA},
        "--layers", write_layers(tmp_path, DECLARED_LAYERS),
        env=env_with_go_arch_lint_stub(tmp_path, capture_path),
    )

    config = yaml.safe_load(capture_path.read_text())
    assert config["version"] == 3
    assert config["components"] == {
        "infra": {"in": ["infra/**"]},
        "domain": {"in": ["domain/**"]},
    }
    assert config["deps"] == {
        "infra": {"mayDependOn": ["infra", "domain"]},
        "domain": {"mayDependOn": ["domain"]},
    }
    assert config["allow"]["ignoreNotFoundComponents"] is True


def test_flags_a_go_domain_to_infra_import_from_the_go_arch_lint_report(tmp_path):
    violations = measure_branch(
        tmp_path, GO_DECLARATION, GO_BASE_FILES,
        {"domain/order.go": GO_DOMAIN_READING_INFRA},
        "--layers", write_layers(tmp_path, DECLARED_LAYERS),
        env=env_with_go_arch_lint_stub(tmp_path, tmp_path / "archfile.yaml"),
    )

    assert len(violations) == 1
    layer_import = violations[0]
    assert layer_import["kind"] == "layer"
    assert layer_import["file"] == "domain/order.go"
    assert layer_import["other_file"] == "shop/infra"
    assert layer_import["layer_map_source"] == "declared"


def test_scores_a_go_file_as_a_deferred_violation_when_go_arch_lint_is_missing(tmp_path):
    violations = measure_branch(
        tmp_path, GO_DECLARATION, GO_BASE_FILES,
        {"domain/order.go": GO_DOMAIN_READING_INFRA},
        "--layers", write_layers(tmp_path, DECLARED_LAYERS),
        env=env_without_go_arch_lint(),
    )

    assert len(violations) == 1
    deferred = violations[0]
    assert deferred["metric"] == "dependency_direction"
    assert deferred["file"] == "domain/order.go"
    assert deferred["pessimistic"] is True
    assert "deferred" in deferred["label"]


def test_exits_not_measured_with_a_message_when_the_layer_map_file_does_not_exist(tmp_path):
    repo = make_repo(tmp_path, {"tools/sync.py": "SYNC = 1\n"})
    declaration_path = tmp_path / "quality-metrics.yaml"
    declaration_path.write_text(PYTHON_DECLARATION)
    missing_layers = tmp_path / "no-such-layers.yaml"

    result = run_measure(repo, declaration_path, "--layers", str(missing_layers))

    assert result.returncode == 2
    assert "no-such-layers.yaml" in result.stderr
    assert "Traceback" not in result.stderr


def test_exits_not_measured_with_a_message_when_the_layer_map_is_a_list_not_a_mapping(tmp_path):
    repo = make_repo(tmp_path, {"tools/sync.py": "SYNC = 1\n"})
    declaration_path = tmp_path / "quality-metrics.yaml"
    declaration_path.write_text(PYTHON_DECLARATION)
    list_layers = write_layers(tmp_path, "- name: infra\n  paths: [infra/**]\n")

    result = run_measure(repo, declaration_path, "--layers", list_layers)

    assert result.returncode == 2
    assert "must be a mapping" in result.stderr
    assert "Traceback" not in result.stderr


def test_exits_not_measured_naming_the_layer_map_file_when_it_is_not_valid_yaml(tmp_path):
    repo = make_repo(tmp_path, {"tools/sync.py": "SYNC = 1\n"})
    declaration_path = tmp_path / "quality-metrics.yaml"
    declaration_path.write_text(PYTHON_DECLARATION)
    broken_layers = write_layers(tmp_path, "source: declared\nlayers: [\n")

    result = run_measure(repo, declaration_path, "--layers", broken_layers)

    assert result.returncode == 2
    assert "layers.yaml" in result.stderr
    assert "Traceback" not in result.stderr


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
