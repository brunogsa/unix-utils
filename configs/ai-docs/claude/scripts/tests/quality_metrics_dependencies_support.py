"""Declarations, repo fixtures, tool stubs and branch measuring
helpers the quality-metrics dependencies suites share.

Named without a `.test.py` or `test_` marker, so pytest
imports it and never collects it.
"""

import os
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_support import (
    GIT_ENV, commit_all, head_of, make_repo, measure_report,
    path_without_tool,
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

GO_DECLARATION = declaration_for("go", ".go")

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

PYTHON_CYCLE_BASE_FILES = {
    "shop/__init__.py": "",
    "shop/orders/__init__.py": "",
    "shop/orders/order.py": "ORDER_ID = 1\n",
    "shop/billing/__init__.py": "",
    "shop/billing/invoice.py": BILLING_READS_ORDERS,
}

PYTHON_DOMAIN_WITHOUT_INFRA = "ORDER_ID = 1\n"
PYTHON_DOMAIN_READING_INFRA = "from infra import db\n\nORDER_ID = db.SAVED\n"
PYTHON_INFRA_DB = "SAVED = 1\n"

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

GO_MODULE = "module shop\n\ngo 1.25\n"
GO_DOMAIN_WITHOUT_INFRA = "package domain\n\nconst OrderID = 1\n"
GO_DOMAIN_READING_INFRA = (
    'package domain\n\nimport "shop/infra"\n\nvar OrderID = infra.Saved\n'
)
GO_INFRA_DB = "package infra\n\nconst Saved = 1\n"

GO_BASE_FILES = {
    "go.mod": GO_MODULE,
    "domain/order.go": GO_DOMAIN_WITHOUT_INFRA,
    "infra/db.go": GO_INFRA_DB,
}

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


@dataclass(frozen=True)
class BranchChange:
    """The files a repo starts with, and the files its branch
    then adds or rewrites."""

    base_files: dict
    branch_files: dict


def report_for_branch(tmp_path, declaration, change, *arguments, env=None):
    """Report of a branch applying `change` on top of its
    base files."""
    repo = make_repo(tmp_path, change.base_files)
    base_sha = head_of(repo)
    for name, text in change.branch_files.items():
        (repo / name).parent.mkdir(parents=True, exist_ok=True)
        (repo / name).write_text(text)
    commit_all(repo, "branch")
    declaration_path = tmp_path / "quality-metrics.yaml"
    declaration_path.write_text(declaration)
    return measure_report(
        repo, declaration_path, "--diff", f"{base_sha}...HEAD", *arguments, env=env
    )


def measure_branch(tmp_path, declaration, change, *arguments, env=None):
    """Violations of a branch applying `change` on top of its
    base files."""
    return report_for_branch(
        tmp_path, declaration, change, *arguments, env=env
    )["violations"]


def write_layers(tmp_path, text):
    layers_path = tmp_path / "layers.yaml"
    layers_path.write_text(text)
    return str(layers_path)


def write_executable(path, text):
    path.write_text(text)
    path.chmod(0o755)


def env_with_stub_tools(tmp_path, dir_name, scripts, base_env=GIT_ENV):
    """`base_env` with a new directory of executable stubs, one
    per `scripts` entry of tool name to script, first on
    PATH."""
    stub_dir = tmp_path / dir_name
    stub_dir.mkdir()
    for tool_name, script in scripts.items():
        write_executable(stub_dir / tool_name, script)
    return {**base_env, "PATH": f"{stub_dir}{os.pathsep}{base_env['PATH']}"}


def env_without_tool(tool_name):
    return {**GIT_ENV, "PATH": path_without_tool(tool_name, GIT_ENV["PATH"])}


def env_with_go_arch_lint_stub(tmp_path, capture_path):
    script = GO_ARCH_LINT_STUB.replace("@CAPTURE_PATH@", str(capture_path))
    return env_with_stub_tools(tmp_path, "stub-bin", {"go-arch-lint": script})
