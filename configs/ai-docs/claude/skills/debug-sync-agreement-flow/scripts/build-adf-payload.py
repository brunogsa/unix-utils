#!/usr/bin/env python3
"""Convert Markdown (from stdin or a file) to Atlassian Document Format JSON (to stdout).

The Jira Cloud REST API v3 requires comments and other rich-text fields to be ADF documents, not
markdown. This does the minimal conversion sufficient for an evidence comment:

  - H1-H6 headings
  - Paragraphs (consecutive non-blank lines folded)
  - Bullet lists (- or *) and numbered lists (1. 2. 3.)
  - Fenced code blocks (``` or ~~~), with the info-string language carried into ADF `codeBlock.attrs`
  - Inline: **bold**, `code`, [text](url)

Anything else — tables, blockquotes, nested lists, images — degrades to paragraphs of plain text: the
words survive, the formatting does not. That degradation is silent in the resulting comment, and a
comment is public the moment it posts, so unsupported constructs are reported on stderr.

Usage:
    build-adf-payload.py < comment.md > comment.adf.json
    build-adf-payload.py comment.md
"""
import json
import re
import sys

FENCE_RE = re.compile(r"^\s*(```|~~~)")
TABLE_RE = re.compile(r"^\s*\|.*\|\s*$")
QUOTE_RE = re.compile(r"^\s*>")
NESTED_ITEM_RE = re.compile(r"^\s+[-*]\s+")
IMAGE_RE = re.compile(r"!\[[^\]]*\]\(")

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")
BULLET_RE = re.compile(r"^[-*]\s+")
ORDERED_RE = re.compile(r"^\d+\.\s+")

INLINE_RE = re.compile(
    r"(\*\*([^*]+)\*\*)"  # **bold**
    r"|(`([^`]+)`)"  # `code`
    r"|(\[([^\]]+)\]\(([^)]+)\))"  # [text](url)
)


def warn_unsupported(md):
    """Report constructs this converter cannot represent, so the loss is noticed before posting."""
    findings = []
    for number, line in enumerate(md.split("\n"), start=1):
        if TABLE_RE.match(line):
            findings.append((number, "table — becomes a plain paragraph"))
        elif QUOTE_RE.match(line):
            findings.append((number, "blockquote — becomes a plain paragraph"))
        elif NESTED_ITEM_RE.match(line):
            findings.append((number, "nested list item — flattens"))
        if IMAGE_RE.search(line):
            findings.append((number, "image — becomes a link or plain text"))
    for number, reason in findings:
        print(f"warning: line {number}: {reason}", file=sys.stderr)
    return findings


def parse_inline(text):
    """Convert inline markup to an ADF content array."""
    nodes = []
    position = 0
    for match in INLINE_RE.finditer(text):
        if match.start() > position:
            nodes.append({"type": "text", "text": text[position:match.start()]})
        if match.group(2):
            nodes.append(
                {"type": "text", "text": match.group(2), "marks": [{"type": "strong"}]}
            )
        elif match.group(4):
            nodes.append({"type": "text", "text": match.group(4), "marks": [{"type": "code"}]})
        elif match.group(6):
            nodes.append(
                {
                    "type": "text",
                    "text": match.group(6),
                    "marks": [{"type": "link", "attrs": {"href": match.group(7)}}],
                }
            )
        position = match.end()
    if position < len(text):
        nodes.append({"type": "text", "text": text[position:]})
    if nodes:
        return nodes
    return [{"type": "text", "text": text}] if text else []


def collect_list(lines, index, item_re, list_type):
    items = []
    while index < len(lines) and item_re.match(lines[index].strip()):
        item_text = item_re.sub("", lines[index].strip(), count=1)
        items.append(
            {
                "type": "listItem",
                "content": [{"type": "paragraph", "content": parse_inline(item_text)}],
            }
        )
        index += 1
    return {"type": list_type, "content": items}, index


def md_to_adf(md):
    """Convert a markdown string to an ADF document dict."""
    lines = md.split("\n")
    content = []
    index = 0
    while index < len(lines):
        stripped = lines[index].strip()

        if not stripped:
            index += 1
            continue

        heading = HEADING_RE.match(stripped)
        if heading:
            content.append(
                {
                    "type": "heading",
                    "attrs": {"level": len(heading.group(1))},
                    "content": parse_inline(heading.group(2)),
                }
            )
            index += 1
            continue

        if BULLET_RE.match(stripped):
            node, index = collect_list(lines, index, BULLET_RE, "bulletList")
            content.append(node)
            continue

        if ORDERED_RE.match(stripped):
            node, index = collect_list(lines, index, ORDERED_RE, "orderedList")
            content.append(node)
            continue

        fence = FENCE_RE.match(stripped)
        if fence:
            marker = fence.group(1)
            language = stripped[len(marker):].strip()
            index += 1
            code_lines = []
            while index < len(lines) and not lines[index].strip().startswith(marker):
                code_lines.append(lines[index])
                index += 1
            index += 1  # skip the closing fence (or EOF on an unterminated block)
            node = {"type": "codeBlock", "attrs": {"language": language or "text"}}
            code_text = "\n".join(code_lines)
            if code_text:
                node["content"] = [{"type": "text", "text": code_text}]
            content.append(node)
            continue

        paragraph = []
        while index < len(lines):
            candidate = lines[index].strip()
            if not candidate:
                break
            if HEADING_RE.match(candidate) or BULLET_RE.match(candidate) or ORDERED_RE.match(candidate):
                break
            paragraph.append(candidate)
            index += 1
        if paragraph:
            content.append({"type": "paragraph", "content": parse_inline(" ".join(paragraph))})

    return {"type": "doc", "version": 1, "content": content}


def main():
    if len(sys.argv) > 2:
        print(f"usage: {sys.argv[0]} [markdown-file]", file=sys.stderr)
        return 1
    if len(sys.argv) == 2 and sys.argv[1] != "-":
        try:
            with open(sys.argv[1], encoding="utf-8") as handle:
                md = handle.read()
        except OSError as error:
            print(f"Error reading {sys.argv[1]}: {error}", file=sys.stderr)
            return 1
    else:
        md = sys.stdin.read()

    if not md.strip():
        print("Error: empty markdown input.", file=sys.stderr)
        return 1

    warn_unsupported(md)
    print(json.dumps(md_to_adf(md), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
