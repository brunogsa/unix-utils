#!/usr/bin/env python3
"""Convert Markdown (from stdin) to Atlassian Document Format JSON (to stdout).

The Jira Cloud REST API v3 requires descriptions, comments, and other rich-text
fields to be ADF documents — not plain markdown. This script does a minimal
markdown -> ADF conversion sufficient for typical issue descriptions:

  - H1-H6 headings (cap at H6 since ADF supports up to level 6)
  - Paragraphs (consecutive non-blank lines folded)
  - Bullet lists (- or *)
  - Numbered lists (1. 2. 3.)
  - Inline: **bold**, `code`, [text](url)

Anything more exotic (tables, blockquotes, fenced code blocks, images, nested
lists) falls back to paragraphs of plain text — preserves the words, not the
formatting.

Usage:
    python3 md-to-adf.py < input.md > output.adf.json
    echo '## Title' | python3 md-to-adf.py

Pipe with jq to build a Jira update payload:
    adf=$(python3 md-to-adf.py < desc.md)
    jq -n --argjson desc "$adf" '{fields: {description: $desc}}'
"""
import json
import re
import sys


def parse_inline(text):
    """Convert inline markup to an ADF content array.

    Order matters: longer/more-specific patterns first.
    """
    nodes = []
    pattern = re.compile(
        r'(\*\*([^*]+)\*\*)'          # **bold**
        r'|(`([^`]+)`)'                # `code`
        r'|(\[([^\]]+)\]\(([^)]+)\))'  # [text](url)
    )
    pos = 0
    for m in pattern.finditer(text):
        if m.start() > pos:
            nodes.append({"type": "text", "text": text[pos:m.start()]})
        if m.group(2):
            nodes.append({"type": "text", "text": m.group(2),
                          "marks": [{"type": "strong"}]})
        elif m.group(4):
            nodes.append({"type": "text", "text": m.group(4),
                          "marks": [{"type": "code"}]})
        elif m.group(6):
            nodes.append({"type": "text", "text": m.group(6),
                          "marks": [{"type": "link",
                                     "attrs": {"href": m.group(7)}}]})
        pos = m.end()
    if pos < len(text):
        nodes.append({"type": "text", "text": text[pos:]})
    return nodes if nodes else ([{"type": "text", "text": text}] if text else [])


def md_to_adf(md):
    """Convert a markdown string to an ADF document dict."""
    lines = md.split('\n')
    content = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        # Heading
        m = re.match(r'^(#{1,6})\s+(.+)$', stripped)
        if m:
            level = len(m.group(1))
            content.append({
                "type": "heading",
                "attrs": {"level": min(level, 6)},
                "content": parse_inline(m.group(2))
            })
            i += 1
            continue

        # Bullet list (- item or * item)
        if re.match(r'^[-*]\s+', stripped):
            items = []
            while i < len(lines) and re.match(r'^[-*]\s+', lines[i].strip()):
                item_text = re.sub(r'^[-*]\s+', '', lines[i].strip())
                items.append({
                    "type": "listItem",
                    "content": [{"type": "paragraph",
                                 "content": parse_inline(item_text)}]
                })
                i += 1
            content.append({"type": "bulletList", "content": items})
            continue

        # Numbered list (1. item)
        if re.match(r'^\d+\.\s+', stripped):
            items = []
            while i < len(lines) and re.match(r'^\d+\.\s+', lines[i].strip()):
                item_text = re.sub(r'^\d+\.\s+', '', lines[i].strip())
                items.append({
                    "type": "listItem",
                    "content": [{"type": "paragraph",
                                 "content": parse_inline(item_text)}]
                })
                i += 1
            content.append({"type": "orderedList", "content": items})
            continue

        # Paragraph: collect consecutive non-blank, non-special lines
        para_lines = []
        while i < len(lines):
            ls = lines[i].strip()
            if not ls:
                break
            if re.match(r'^(#{1,6})\s+', ls):
                break
            if re.match(r'^[-*]\s+', ls):
                break
            if re.match(r'^\d+\.\s+', ls):
                break
            para_lines.append(ls)
            i += 1
        if para_lines:
            content.append({"type": "paragraph",
                            "content": parse_inline(' '.join(para_lines))})

    return {"type": "doc", "version": 1, "content": content}


if __name__ == "__main__":
    print(json.dumps(md_to_adf(sys.stdin.read()), ensure_ascii=False))
