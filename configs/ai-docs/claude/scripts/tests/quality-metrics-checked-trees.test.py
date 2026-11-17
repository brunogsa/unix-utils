"""The temp tree every new tool runs in: the branch's code with
the base ref's tool configs, so a branch cannot loosen its own
gate.
"""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_support import SCRIPTS_DIR, commit_all, head_of, make_repo

sys.path.insert(0, str(SCRIPTS_DIR))

from quality_metrics.checked_trees import checked_tree

TSC = SCRIPTS_DIR / "quality_metrics/node_tools/node_modules/.bin/tsc"


def test_diff_tree_holds_head_code_base_configs_and_no_added_config(tmp_path):
    repo = make_repo(tmp_path, {
        "pyrightconfig.json": "strict-at-base\n",
        "src/app.py": "base\n",
    })
    base = head_of(repo)
    (repo / "pyrightconfig.json").write_text("loosened-by-branch\n")
    (repo / "src/app.py").write_text("head\n")
    (repo / "pkg").mkdir()
    (repo / "pkg/pyrightconfig.json").write_text("added-by-branch\n")
    commit_all(repo, "branch")
    head = head_of(repo)
    (repo / "src/app.py").write_text("uncommitted\n")

    with checked_tree(repo, head, base, ["pyrightconfig.json"]) as tree:
        assert (tree / "src/app.py").read_text() == "head\n"
        assert (tree / "pyrightconfig.json").read_text() == "strict-at-base\n"
        assert not (tree / "pkg/pyrightconfig.json").exists()

    assert not tree.exists()


def test_batch_end_tree_holds_tracked_and_untracked_but_no_ignored_file(tmp_path):
    repo = make_repo(tmp_path, {
        ".gitignore": "pyrightconfig.json\n",
        "tracked.py": "tracked\n",
    })
    (repo / "untracked.py").write_text("untracked\n")
    (repo / "pyrightconfig.json").write_text("ignored\n")

    with checked_tree(repo, None, "HEAD", ["pyrightconfig.json"]) as tree:
        assert (tree / "tracked.py").read_text() == "tracked\n"
        assert (tree / "untracked.py").read_text() == "untracked\n"
        assert not (tree / "pyrightconfig.json").exists()


def test_linked_node_modules_lets_real_tsc_resolve_a_package_type(tmp_path):
    repo = make_repo(tmp_path, {
        ".gitignore": "node_modules\n",
        "tsconfig.json": '{"compilerOptions": {"noEmit": true, "strict": true}, "include": ["src"]}\n',
        "src/use.ts": 'import { label } from "dep";\nexport const count: number = label;\n',
    })
    package = repo / "node_modules/dep"
    package.mkdir(parents=True)
    (package / "package.json").write_text('{"name": "dep", "types": "index.d.ts"}\n')
    (package / "index.d.ts").write_text("export declare const label: string;\n")
    nested = repo / "web/node_modules/other"
    nested.mkdir(parents=True)
    (nested / "index.js").write_text("")

    with checked_tree(repo, None, "HEAD", ["tsconfig*.json"]) as tree:
        assert (tree / "node_modules").is_symlink()
        assert (tree / "web/node_modules").is_symlink()
        assert not (tree / "node_modules/dep/node_modules").exists()
        result = subprocess.run(
            [str(TSC), "--project", str(tree / "tsconfig.json")],
            capture_output=True, text=True,
        )

    # TS2322 means `dep` resolved to its string type; a missing
    # link would give TS2307 (cannot find module) instead.
    assert "TS2322" in result.stdout
    assert "TS2307" not in result.stdout
