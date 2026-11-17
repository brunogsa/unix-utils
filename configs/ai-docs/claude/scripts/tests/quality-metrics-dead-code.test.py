"""dead_code: soft candidates, only in changed files."""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_support import SCRIPTS_DIR

sys.path.insert(0, str(SCRIPTS_DIR))

from quality_metrics.dead_code import dead_code_records
from quality_metrics.touched import Target

GO_MODULE = "module example\n\ngo 1.21\n"


def _target(path):
    return Target(Path(path), None, None)


def _write(root, files):
    for name, text in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text)


def _track(root):
    for command in (["init", "-q"], ["add", "-A"]):
        subprocess.run(["git", "-C", str(root), *command], check=True)


def test_vulture_reports_only_the_changed_file(tmp_path):
    _write(tmp_path, {
        "changed.py": "def unused_in_changed():\n    return 1\n",
        "unchanged.py": "def unused_elsewhere():\n    return 2\n",
    })
    _track(tmp_path)

    records = dead_code_records(tmp_path, [_target(tmp_path / "changed.py")])

    assert len(records) == 1
    assert records[0] == {
        "file": str(tmp_path / "changed.py"),
        "line": 1,
        "function": None,
        "scope": "file",
        "metric": "dead_code",
        "value": 1,
        "limit": 0,
        "name": "unused_in_changed",
        "kind": "function",
        "tool": "vulture",
    }


def test_knip_reports_unused_exports_and_files_but_not_public_ones(tmp_path):
    _write(tmp_path, {
        "package.json": '{"name": "fixture", "version": "1.0.0"}\n',
        "tsconfig.json": '{"include": ["src"]}\n',
        "knip.json": '{"entry": ["src/index.ts"], "project": ["src/**/*.ts"]}\n',
        "src/index.ts": 'import { used } from "./lib";\n\nconsole.log(used);\n',
        "src/lib.ts": (
            "export const used = 1;\n"
            "export const unusedExport = 2;\n"
            "/** @public */\n"
            "export const publicExport = 3;\n"
        ),
        "src/orphan.ts": "export const alone = 1;\n",
    })

    records = dead_code_records(
        tmp_path, [_target(tmp_path / "src/lib.ts"), _target(tmp_path / "src/orphan.ts")]
    )

    found = {(Path(r["file"]).name, r["name"], r["kind"], r["line"]) for r in records}
    assert found == {
        ("lib.ts", "unusedExport", "export", 2),
        ("orphan.ts", "src/orphan.ts", "file", 1),
    }
    assert {r["tool"] for r in records} == {"knip"}
    assert {r["metric"] for r in records} == {"dead_code"}


def test_deadcode_reports_unreachable_function_in_changed_file(tmp_path):
    _write(tmp_path, {
        "go.mod": GO_MODULE,
        "main.go": "package main\n\nfunc unreachable() int { return 1 }\n\nfunc main() { println(1) }\n",
        "other.go": "package main\n\nfunc alsoUnreachable() int { return 2 }\n",
    })

    records = dead_code_records(tmp_path, [_target(tmp_path / "main.go")])

    assert len(records) == 1
    assert records[0]["file"] == str(tmp_path / "main.go")
    assert records[0]["line"] == 3
    assert records[0]["name"] == "unreachable"
    assert records[0]["kind"] == "function"
    assert records[0]["tool"] == "deadcode"
    assert "pessimistic" not in records[0]


def test_deadcode_without_a_main_package_flags_every_changed_go_file(tmp_path):
    _write(tmp_path, {
        "go.mod": GO_MODULE,
        "a.go": "package lib\n\nfunc A() int { return 1 }\n",
        "b.go": "package lib\n\nfunc B() int { return 2 }\n",
    })

    records = dead_code_records(
        tmp_path, [_target(tmp_path / "a.go"), _target(tmp_path / "b.go")]
    )

    assert [r["file"] for r in records] == [str(tmp_path / "a.go"), str(tmp_path / "b.go")]
    for record in records:
        assert record["metric"] == "dead_code"
        assert record["value"] == 1
        assert record["limit"] == 0
        assert record["pessimistic"] is True
        assert record["tool"] == "deadcode"
