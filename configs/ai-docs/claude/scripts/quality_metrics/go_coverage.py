"""Go coverage: `go test` writes a profile that gcov2lcov turns
into the lcov report."""

import tempfile
import time
from pathlib import Path

from quality_metrics.coverage_result import RED_BUILD, read_fresh_lcov
from quality_metrics.tools import run_command

GO_TEST_COMMAND = ["go", "test", "./..."]


def collect_go(repo_dir):
    with tempfile.TemporaryDirectory() as data_dir:
        profile = Path(data_dir) / "cover.out"
        run_started = time.time()
        test_run = run_command(
            [*GO_TEST_COMMAND, f"-coverprofile={profile}"], cwd=repo_dir
        )
        if test_run.returncode != 0:
            return RED_BUILD
        lcov_file = Path(data_dir) / "lcov.info"
        run_command(
            ["gcov2lcov", f"-infile={profile}", f"-outfile={lcov_file}"],
            cwd=repo_dir,
        )
        return read_fresh_lcov(lcov_file, repo_dir, run_started)
