"""Changed-line coverage of a JS/TS file with no executable
code: a type-only file or a barrel of re-exports has nothing a
test can run, so it reads not applicable, never 0%.

The call is made from the source text alone, and only when it
is certain: any statement that may run keeps the measured
reading.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_support import SCRIPTS_DIR

sys.path.insert(0, str(SCRIPTS_DIR))

from quality_metrics.coverage import coverage_measurement
from quality_metrics.touched import Target

NO_EXECUTABLE_CODE = "not applicable: no executable code"

TYPE_ONLY_SOURCE = """\
import type { Contract } from './contract';

/** One SKU line of a merged agreement. */
export interface SkuLine {
  sku: string;
  quantity: number;
}

type Grade =
  | 'EF1'
  | 'EF2';

export type MergedLines = {
  lines: SkuLine[];
  grade: Grade;
  contract: Contract;
};
"""

BARREL_SOURCE = """\
// Public surface of the merge-contracts module.
export * from './merge-b2c-contracts';
export * as validators from './validators';
export { translateB2bContract } from './translate-b2b-contract';
export type { MergedLines } from './types';
"""


def target_for(tmp_path, name, text):
    source = tmp_path / name
    source.write_text(text)
    return Target(source, "ts", None, repo_path=name)


class TestFilesWithNoExecutableCode:
    def test_should_read_a_type_only_file_missing_from_the_coverage_report_as_not_applicable(self, tmp_path):
        record = coverage_measurement(target_for(tmp_path, "types.ts", TYPE_ONLY_SOURCE), line_hits=None)

        assert record["value"] is None
        assert record["status"] == NO_EXECUTABLE_CODE
        assert record["uncovered_lines"] is None

    def test_should_read_a_barrel_of_re_exports_whose_lines_never_ran_as_not_applicable(self, tmp_path):
        record = coverage_measurement(
            target_for(tmp_path, "index.ts", BARREL_SOURCE), line_hits={2: 0, 3: 0, 4: 0}
        )

        assert record["value"] is None
        assert record["status"] == NO_EXECUTABLE_CODE


class TestFilesThatMayRunCode:
    @pytest.mark.parametrize("statement", [
        "export enum Segment { B2B = 'B2B', B2C = 'B2C' }",
        "export const DEFAULT_GRADE = 'EF1';",
        "const grade = 'EF1';\nexport { grade };",
        "export default function merge() { return []; }",
        "import './register-classifiers';\nconsole.log('loaded');",
    ])
    def test_should_keep_the_0_percent_reading_of_a_file_missing_from_the_coverage_report_when_it_holds_code(
        self, tmp_path, statement
    ):
        source = f"export type Grade = 'EF1';\n{statement}\n"

        record = coverage_measurement(target_for(tmp_path, "grades.ts", source), line_hits=None)

        assert record["value"] == 0
        assert "status" not in record

    def test_should_keep_the_measured_reading_when_the_source_cannot_be_parsed(self, tmp_path):
        source = "export type Grade = 'EF1' |;\nexport interface {\n"

        record = coverage_measurement(target_for(tmp_path, "broken.ts", source), line_hits=None)

        assert record["value"] == 0
