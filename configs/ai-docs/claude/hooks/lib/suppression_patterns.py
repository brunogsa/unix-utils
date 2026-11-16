"""The lint/type-checker suppression comments the harness rejects.

The edit-time hook and the quality-metrics script share this one
pattern, so a token blocked at edit time is also listed as a
violation at measure time.
"""

import re

SUPPRESSION_PATTERN = re.compile(
    r"eslint-disable(?:-next-line|-line)?"
    r"|@ts-(?:ignore|expect-error|nocheck)"
    r"|#\s*type:\s*ignore"
    r"|#\s*noqa"
    r"|#\s*pylint:\s*disable"
    r"|//\s*nolint"
    r"|#\s*shellcheck\s+disable"
    r"|biome-ignore"
    r"|pragma:\s*no\s+cover"
    r"|istanbul\s+ignore"
    r"|c8\s+ignore"
    r"|jscpd:ignore"
)

# Rules and docs quote these tokens on purpose.
PROSE_SUFFIXES = (".md", ".txt")
