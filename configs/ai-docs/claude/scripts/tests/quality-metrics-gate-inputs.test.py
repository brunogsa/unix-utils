import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
HOOK = SCRIPTS_DIR.parent / "hooks" / "check-lint-suppressions.py"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_support import (
    commit_all, head_of, install_stub_tool, make_repo, measure_report,
)

from quality_metrics import gate_inputs
from quality_metrics.sourcing import measure_coverage_with_repo_tool
from quality_metrics.touched import Target

FEEDBACK_EXIT = 2

# Records its arguments and the config text it was handed, then
# writes an empty lcov report where jest was told to.
JEST_RECORDING_STUB = """#!/bin/bash
: > "$ARGS_LOG"
for argument in "$@"; do
  echo "$argument" >> "$ARGS_LOG"
  case "$argument" in
    --coverageDirectory=*) report_dir="${argument#--coverageDirectory=}";;
  esac
  if [ "$previous" = "--config" ]; then cp "$argument" "$CONFIG_COPY_LOG"; fi
  previous="$argument"
done
: > "$report_dir/lcov.info"
"""

# Loads the config it was handed with node, as jest does, then
# writes an empty lcov report where told.
JEST_CONFIG_LOADING_STUB = """#!/bin/bash
for argument in "$@"; do
  case "$argument" in
    --coverageDirectory=*) report_dir="${argument#--coverageDirectory=}";;
  esac
  if [ "$previous" = "--config" ]; then
    node -e 'require(process.argv[1])' "$argument" || exit 1
  fi
  previous="$argument"
done
: > "$report_dir/lcov.info"
"""

DECLARATION_TEXT = """\
excluded_paths: []
ignored_extensions: [.md]
per_unit: []
languages:
  ts:
    extensions: [.ts]
    metrics: [size]
  js:
    extensions: [.js]
    metrics: [size]
"""

PARSE_SOURCE = "export function parse(text: string): number {\n  return text.length;\n}\n"
PARSE_SOURCE_WITH_ISTANBUL_IGNORE = (
    "/* istanbul ignore next */\n" + PARSE_SOURCE
)

JEST_CONFIG_WITHOUT_EXCLUDES = (
    "module.exports = {\n  collectCoverageFrom: ['src/**/*.ts'],\n};\n"
)
JEST_CONFIG_EXCLUDING_REPORT = (
    "module.exports = {\n"
    "  collectCoverageFrom: ['src/**/*.ts'],\n"
    "  coveragePathIgnorePatterns: ['src/report.ts'],\n"
    "};\n"
)
JEST_CONFIG_IGNORING_SPEC_FILES = (
    "module.exports = {\n"
    "  coveragePathIgnorePatterns: ['\\\\.(spec|test)\\\\.[jt]s$'],\n"
    "};\n"
)
JEST_CONFIG_IGNORING_SPEC_FILES_AND_REPORT = (
    "module.exports = {\n"
    "  coveragePathIgnorePatterns: ['\\\\.(spec|test)\\\\.[jt]s$', 'src/report.ts'],\n"
    "};\n"
)
JEST_CONFIG_COLLECTING_FROM_SRC_FILES = (
    "module.exports = {\n  collectCoverageFrom: ['src/[a-z]*.ts'],\n};\n"
)
JEST_CONFIG_COLLECTING_WITHOUT_REPORT = (
    "module.exports = {\n"
    "  collectCoverageFrom: ['src/[a-z]*.ts', '!src/report.ts'],\n"
    "};\n"
)
REPORT_SOURCE = "export function render(rows: string[]): string {\n  return rows.join('\\n');\n}\n"


# The declaration is committed beside the code it judges, so
# its own extension is ignored rather than asked about.
COMMITTED_DECLARATION_NAME = "quality-metrics.yaml"
COMMITTED_DECLARATION = DECLARATION_TEXT.replace(
    "ignored_extensions: [.md]", "ignored_extensions: [.md, .yaml]"
).replace("metrics: [size]\n  js:", "metrics: [size, parameters]\n  js:")
DECLARATION_WITHOUT_TS_SIZE = COMMITTED_DECLARATION.replace(
    "metrics: [size, parameters]", "metrics: [parameters]"
)
DECLARATION_EXCLUDING_SRC = COMMITTED_DECLARATION.replace(
    "excluded_paths: []", "excluded_paths: [src/]"
)


def size_records_of(report, file_name):
    return [
        record for record in report["measurements"]
        if record["metric"] == "size" and record["file"].endswith(file_name)
    ]


def write_declaration(tmp_path):
    path = tmp_path / COMMITTED_DECLARATION_NAME
    path.write_text(DECLARATION_TEXT)
    return path


def run_hook_on_added_line(file_path, added_line):
    payload = {
        "hook_event_name": "PostToolUse",
        "tool_name": "Edit",
        "tool_input": {
            "file_path": file_path,
            "old_string": "value = 1\n",
            "new_string": added_line + "value = 1\n",
        },
        "tool_response": {"filePath": file_path},
    }
    return subprocess.run(
        [sys.executable, str(HOOK)], input=json.dumps(payload),
        capture_output=True, text=True, timeout=30,
    )


class TestCornerCases:
    @pytest.mark.parametrize("added_line, token", [
        ("x = 1  # pragma: no cover", "pragma: no cover"),
        ("/* istanbul ignore next */", "istanbul ignore"),
        ("/* c8 ignore next */", "c8 ignore"),
        ("// jscpd:ignore-start", "jscpd:ignore"),
    ])
    def test_should_block_pragma_no_cover_istanbul_ignore_c8_ignore_and_jscpd_ignore_comments_at_edit_time(
        self, added_line, token
    ):
        result = run_hook_on_added_line("/repo/src/parse.ts", added_line)

        assert result.returncode == FEEDBACK_EXIT
        assert token in result.stderr


class TestFailureScenarios:
    def test_should_list_a_changed_limit_as_a_violation_and_keep_measuring_with_the_committed_limit(
        self, tmp_path
    ):
        repo = make_repo(tmp_path, {
            COMMITTED_DECLARATION_NAME: COMMITTED_DECLARATION,
            "src/parse.ts": PARSE_SOURCE,
        })
        base = head_of(repo)
        (repo / COMMITTED_DECLARATION_NAME).write_text(DECLARATION_EXCLUDING_SRC)
        (repo / "src/parse.ts").write_text(PARSE_SOURCE + "\n// edited\n")
        commit_all(repo, "exclude src from measuring")

        report = measure_report(
            repo, repo / COMMITTED_DECLARATION_NAME, "--diff", f"{base}...HEAD"
        )

        assert report["gate_input_violations"] == [
            {"kind": "declaration_change", "file": COMMITTED_DECLARATION_NAME,
             "value": "excluded_paths"}
        ]
        assert len(size_records_of(report, "src/parse.ts")) == 1

    def test_should_list_an_uncommitted_opt_out_as_a_violation_and_keep_measuring_with_the_committed_entry(
        self, tmp_path
    ):
        repo = make_repo(tmp_path, {
            COMMITTED_DECLARATION_NAME: COMMITTED_DECLARATION,
            "src/parse.ts": PARSE_SOURCE,
        })
        (repo / COMMITTED_DECLARATION_NAME).write_text(DECLARATION_WITHOUT_TS_SIZE)
        (repo / "src/parse.ts").write_text(PARSE_SOURCE + "\n// edited\n")

        report = measure_report(repo, repo / COMMITTED_DECLARATION_NAME)

        assert report["gate_input_violations"] == [
            {"kind": "opt_out", "file": COMMITTED_DECLARATION_NAME, "value": "ts.size"}
        ]
        assert len(size_records_of(report, "src/parse.ts")) == 1


class TestRunFromASubdirectory:
    def test_should_not_list_a_committed_jest_exclude_as_a_violation_when_run_from_a_package_subdirectory(
        self, tmp_path
    ):
        repo = make_repo(tmp_path, {
            "mono/pkg/jest.config.js": JEST_CONFIG_EXCLUDING_REPORT,
            "mono/pkg/src/report.ts": REPORT_SOURCE,
        })

        report = measure_report(repo / "mono/pkg", write_declaration(tmp_path))

        assert report["gate_input_violations"] == []


class TestJestListsWithCharacterClasses:
    def test_should_list_a_coverage_path_ignore_added_after_an_entry_holding_a_character_class(
        self, tmp_path
    ):
        repo = make_repo(tmp_path, {
            "jest.config.js": JEST_CONFIG_IGNORING_SPEC_FILES,
            "src/report.ts": REPORT_SOURCE,
        })
        (repo / "jest.config.js").write_text(JEST_CONFIG_IGNORING_SPEC_FILES_AND_REPORT)

        report = measure_report(repo, write_declaration(tmp_path))

        assert report["gate_input_violations"] == [
            {"kind": "coverage_exclude", "file": "jest.config.js", "value": "src/report.ts"}
        ]

    def test_should_list_a_negated_collect_glob_added_after_a_glob_holding_a_character_class(
        self, tmp_path
    ):
        repo = make_repo(tmp_path, {
            "jest.config.js": JEST_CONFIG_COLLECTING_FROM_SRC_FILES,
            "src/report.ts": REPORT_SOURCE,
        })
        (repo / "jest.config.js").write_text(JEST_CONFIG_COLLECTING_WITHOUT_REPORT)

        report = measure_report(repo, write_declaration(tmp_path))

        assert report["gate_input_violations"] == [
            {"kind": "coverage_exclude", "file": "jest.config.js", "value": "!src/report.ts"}
        ]


class TestDeclarationOutsideTheMeasuredRepo:
    def test_should_list_an_uncommitted_opt_out_in_a_declaration_kept_in_another_repo_and_keep_measuring_with_its_committed_entry(
        self, tmp_path
    ):
        measured_repo = make_repo(tmp_path, {"src/parse.ts": PARSE_SOURCE})
        (measured_repo / "src/parse.ts").write_text(PARSE_SOURCE + "\n// edited\n")
        global_dir = tmp_path / "global-config"
        global_dir.mkdir()
        global_repo = make_repo(global_dir, {COMMITTED_DECLARATION_NAME: COMMITTED_DECLARATION})
        declaration = global_repo / COMMITTED_DECLARATION_NAME
        declaration.write_text(DECLARATION_WITHOUT_TS_SIZE)

        report = measure_report(measured_repo, declaration)

        assert report["gate_input_violations"] == [
            {"kind": "opt_out", "file": str(declaration.resolve()), "value": "ts.size"}
        ]
        assert len(size_records_of(report, "src/parse.ts")) == 1


class TestHappyPath:
    def test_should_pass_the_base_ref_config_to_a_repo_tool_through_its_config_flag_as_in_jest_config_tmp_jest_config_js(
        self, tmp_path, monkeypatch
    ):
        repo = make_repo(tmp_path, {
            "jest.config.js": JEST_CONFIG_WITHOUT_EXCLUDES,
            "src/report.ts": REPORT_SOURCE,
        })
        base = head_of(repo)
        (repo / "jest.config.js").write_text(JEST_CONFIG_EXCLUDING_REPORT)
        args_log, config_copy_log = tmp_path / "args.log", tmp_path / "config-copy.js"
        monkeypatch.setenv("ARGS_LOG", str(args_log))
        monkeypatch.setenv("CONFIG_COPY_LOG", str(config_copy_log))
        install_stub_tool(tmp_path, monkeypatch, "jest", JEST_RECORDING_STUB)
        target = Target(repo / "src/report.ts", "typescript", None)

        measure_coverage_with_repo_tool(target, repo, base_ref=base)

        arguments = args_log.read_text().splitlines()
        config_path = arguments[arguments.index("--config") + 1]
        assert Path(config_path).name == "jest.config.js"
        assert Path(config_path).parent != repo
        assert f"--rootDir={repo}" in arguments
        assert config_copy_log.read_text() == JEST_CONFIG_WITHOUT_EXCLUDES

    @pytest.mark.skipif(shutil.which("node") is None, reason="node is not on PATH")
    def test_should_load_a_base_ref_config_that_requires_a_preset_from_the_repo_node_modules(
        self, tmp_path, monkeypatch
    ):
        repo = make_repo(tmp_path, {
            "jest.config.js": 'module.exports = require("fakepreset");\n',
            "src/report.ts": REPORT_SOURCE,
        })
        base = head_of(repo)
        preset_dir = repo / "node_modules" / "fakepreset"
        preset_dir.mkdir(parents=True)
        (preset_dir / "index.js").write_text("module.exports = { collectCoverage: true };\n")
        install_stub_tool(tmp_path, monkeypatch, "jest", JEST_CONFIG_LOADING_STUB)
        target = Target(repo / "src/report.ts", "typescript", None)

        outcome = measure_coverage_with_repo_tool(target, repo, base_ref=base)

        assert outcome["exit_class"] == "passed"

    def test_should_list_an_added_istanbul_ignore_comment_as_a_violation(self, tmp_path):
        repo = make_repo(tmp_path, {"src/parse.ts": PARSE_SOURCE})
        base = head_of(repo)
        (repo / "src/parse.ts").write_text(PARSE_SOURCE_WITH_ISTANBUL_IGNORE)
        commit_all(repo, "ignore a branch")

        report = measure_report(repo, write_declaration(tmp_path), "--diff", f"{base}...HEAD")

        assert report["gate_input_violations"] == [
            {"kind": "suppression", "file": "src/parse.ts", "value": "istanbul ignore"}
        ]

    def test_should_list_a_suppression_in_a_new_uncommitted_file_as_a_violation(self, tmp_path):
        repo = make_repo(tmp_path, {"src/parse.ts": PARSE_SOURCE})
        (repo / "src/new.ts").write_text("// eslint-disable-next-line\nexport {};\n")

        report = measure_report(repo, write_declaration(tmp_path))

        assert report["gate_input_violations"] == [
            {"kind": "suppression", "file": "src/new.ts", "value": "eslint-disable-next-line"}
        ]

    def test_should_list_a_coverage_exclude_the_branch_adds_as_a_violation_and_measure_with_the_base_ref_excludes(
        self, tmp_path
    ):
        repo = make_repo(tmp_path, {
            "jest.config.js": JEST_CONFIG_WITHOUT_EXCLUDES,
            "src/report.ts": REPORT_SOURCE,
        })
        base = head_of(repo)
        (repo / "jest.config.js").write_text(JEST_CONFIG_EXCLUDING_REPORT)
        commit_all(repo, "exclude the report from coverage")
        measured_with = tmp_path / "base-ref-inputs"
        measured_with.mkdir()

        report = measure_report(repo, write_declaration(tmp_path), "--diff", f"{base}...HEAD")
        gate_inputs.write_base_ref_configs(repo, base, measured_with)

        assert report["gate_input_violations"] == [
            {"kind": "coverage_exclude", "file": "jest.config.js", "value": "src/report.ts"}
        ]
        assert (measured_with / "jest.config.js").read_text() == JEST_CONFIG_WITHOUT_EXCLUDES
