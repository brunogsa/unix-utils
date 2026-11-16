"""The suppression comments the harness rejects: lint, type-check,
coverage and duplication ignores.

The edit-time hook and the quality-metrics script share this one
pattern, so a token blocked at edit time is also listed as a
violation at measure time.
"""

import re
from collections import Counter

SUPPRESSION_PATTERN = re.compile(
    r"eslint-disable(?:-next-line|-line)?"
    r"|@ts-(?:ignore|expect-error|nocheck)"
    r"|#\s*type:\s*ignore"
    r"|#\s*noqa"
    r"|#\s*pylint:\s*disable"
    r"|//\s*nolint"
    r"|#\s*shellcheck\s+disable"
    r"|biome-ignore"
    r"|#\s*(?:pragma|PRAGMA)[:\s]?\s*(?:no|NO)\s*(?:cover|COVER)"
    r"|istanbul\s+ignore"
    r"|c8\s+ignore"
    r"|jscpd:ignore"
)

# Rules and docs quote these tokens on purpose.
PROSE_SUFFIXES = (".md", ".txt")


def count_suppressions(text):
    return Counter(SUPPRESSION_PATTERN.findall(text))
