"""Layout, length-budget and citation checks for one finding
body."""

import re

from finding_bodies.parsing import fence_body_text

SEVERITY_TAG_LINE = re.compile(r"^\*\*\[([^\]]+)\]\*\*$")

# Lines /address-verdicts appends after review, never part of
# the comment a reviewer wrote.
ANNOTATION_PREFIXES = ("APPLIED (", "SKIPPED (")

ORDINAL_BY_TAG = {
    "MANDATORY": "HIGH",
    "OBRIGATÓRIO": "HIGH",
    "RECOMMENDED": "MEDIUM",
    "RECOMENDADO": "MEDIUM",
    "NITPICK": "LOW",
    "OPTIONAL": "LOW",
    "OPCIONAL": "LOW",
    "QUESTION": "QUESTION",
    "PERGUNTA": "QUESTION",
}
HEADING_ORDINALS = set(ORDINAL_BY_TAG.values())
MANDATORY_TAGS = {"MANDATORY", "OBRIGATÓRIO"}
QUESTION_TAGS = {"QUESTION", "PERGUNTA"}
NITPICK_TAG = "NITPICK"
BLOCKQUOTE_PREFIX = "> "

SUGGESTION_LABELS = ("**Suggestion**", "**Sugestão**")
TRADEOFF_LABELS = ("**Trade-off of not doing it**", "**Trade-off de não fazer**")

CHAR_CAP = 512
MANDATORY_CHAR_CAP = 1024
MANDATORY_LINE_CAP = 16
QUOTED_LINE_MAX = 60

# The reviewer's private rule files: the PR author cannot open
# them, so a body citing one asks for trust instead of stating
# the principle.
INTERNAL_RULE_SOURCE = re.compile(
    r"\b[a-z]+-standards\b"
    r"|\b(?:CLAUDE|AGENTS)\.md\b"
    r"|\b(?:review-principles|review-checklists|common-preamble)\b"
    r"|~/\.claude/[^\s`'\")\]]*",
    re.IGNORECASE,
)
HOME_CLAUDE_PREFIX = "~/.claude/"
TRAILING_PUNCTUATION = ".,;:"


def _reviewer_lines(finding):
    """Body lines minus the annotations added after review."""
    return [
        (line, is_fenced) for line, is_fenced in finding.lines
        if is_fenced or not line.startswith(ANNOTATION_PREFIXES)
    ]


def _find_tag(body_lines):
    """Return (body index, tag) of the first known severity tag
    line outside a code block, or (None, None)."""
    for index, (line, is_fenced) in enumerate(body_lines):
        match = None if is_fenced else SEVERITY_TAG_LINE.match(line)
        if match and match.group(1) in ORDINAL_BY_TAG:
            return index, match.group(1)
    return None, None


def _first_index(prose, labels):
    return next((i for i, line in enumerate(prose) if line in labels), None)


def _check_tag_position(body, tag_line_index, tag):
    tag_names = ", ".join(ORDINAL_BY_TAG)
    if tag is None:
        return [f"body must open with a severity tag line **[TAG]**, TAG one of {tag_names}; none found"]
    opening = [line for line in body[:tag_line_index] if line.strip()]
    is_nitpick_prefix = (
        tag == NITPICK_TAG
        and len(opening) == 1
        and opening[0].startswith(BLOCKQUOTE_PREFIX)
    )
    if not opening or is_nitpick_prefix:
        return []
    first = opening[0][:QUOTED_LINE_MAX]
    return [f'body must open with the severity tag line **[{tag}]**; got "{first}"']


def _check_ordinal(heading_tokens, tag):
    ordinals = [token for token in heading_tokens if token in HEADING_ORDINALS]
    expected = ORDINAL_BY_TAG.get(tag)
    if not ordinals:
        needed = f"[{expected}]" if expected else "[HIGH], [MEDIUM], [LOW] or [QUESTION]"
        return [f"heading has no ordinal; it needs {needed}"]
    if expected and ordinals[0] != expected:
        return [f"heading ordinal [{ordinals[0]}] must be [{expected}] to match the tag [{tag}]"]
    return []


def _check_sections(prose, tag):
    suggestion_index = _first_index(prose, SUGGESTION_LABELS)
    tradeoff_index = _first_index(prose, TRADEOFF_LABELS)
    reasons = []
    if suggestion_index is None and tag not in QUESTION_TAGS:
        reasons.append(f"missing a {' / '.join(SUGGESTION_LABELS)} line")
    if tradeoff_index is None:
        reasons.append(f"missing a {' / '.join(TRADEOFF_LABELS)} line")
    is_misordered = (
        suggestion_index is not None
        and tradeoff_index is not None
        and tradeoff_index < suggestion_index
    )
    if is_misordered:
        reasons.append("the trade-off line must come after the suggestion line")
    return reasons


def _check_budget(prose, tag):
    is_mandatory = tag in MANDATORY_TAGS
    char_cap = MANDATORY_CHAR_CAP if is_mandatory else CHAR_CAP
    char_count = len("\n".join(prose).strip())
    reasons = []
    if char_count > char_cap:
        reasons.append(
            f"body is {char_count} chars, over the {char_cap}-char cap (code blocks excluded)"
        )
    line_count = sum(1 for line in prose if line.strip())
    if is_mandatory and line_count > MANDATORY_LINE_CAP:
        reasons.append(
            f"body is {line_count} non-blank lines, over the {MANDATORY_LINE_CAP}-line cap"
            " (code blocks excluded)"
        )
    return reasons


def _is_finding_own_file(token, path_lower):
    if not token.lower().startswith(HOME_CLAUDE_PREFIX):
        return token.lower() in path_lower
    installed_rest = token[len(HOME_CLAUDE_PREFIX):].lower()
    return bool(installed_rest) and path_lower.endswith(installed_rest)


def _check_citations(prose, path):
    """Flag each distinct internal rule source the prose names,
    unless the finding is about that very file (its path
    contains the name, or ends with the installed path
    `~/.claude/<rest>` the body cites)."""
    path_lower = path.lower()
    matches = INTERNAL_RULE_SOURCE.finditer("\n".join(prose))
    tokens = [match.group(0).rstrip(TRAILING_PUNCTUATION) for match in matches]
    cited = {}
    for token in tokens:
        if not _is_finding_own_file(token, path_lower):
            cited.setdefault(token.lower(), token)
    return [
        f'body cites internal rule source "{token}";'
        " state the principle and why it matters for this code instead"
        for token in cited.values()
    ]


def _split_body(body_lines):
    """Return (body, prose, tag body index, tag) for (text,
    is_fenced) pairs."""
    body = [line for line, _ in body_lines]
    prose = [line for line, is_fenced in body_lines if not is_fenced]
    tag_body_index, tag = _find_tag(body_lines)
    return body, prose, tag_body_index, tag


def check_finding(finding):
    """Return every layout, budget and citation violation of one
    finding."""
    body, prose, tag_body_index, tag = _split_body(_reviewer_lines(finding))
    return (
        _check_tag_position(body, tag_body_index, tag)
        + _check_ordinal(finding.heading_tokens, tag)
        + _check_sections(prose, tag)
        + _check_budget(prose, tag)
        + _check_citations(prose, finding.path)
    )


def check_json_body(text, path):
    """Return every violation of one JSON finding body; the
    heading checks are skipped because a JSON finding has no
    heading."""
    body, prose, tag_body_index, tag = _split_body(fence_body_text(text))
    return (
        _check_tag_position(body, tag_body_index, tag)
        + _check_sections(prose, tag)
        + _check_budget(prose, tag)
        + _check_citations(prose, path)
    )
