#!/usr/bin/env python3
"""Render Mermaid blocks in a markdown file and build a pandoc .docx ready for Google Docs.

Why a .docx (and not HTML or paste-from-markdown):
  Google Drive converts an uploaded .docx into a native Google Doc with full fidelity
  AND keeps embedded images, because a .docx carries images as real media parts. Google's
  HTML import, by contrast, silently strips inline/base64 images — so HTML loses every
  diagram. The .docx path is the only one that preserves images through the conversion.

What this does:
  1. Find every ```mermaid fenced block, render each to a PNG via mmdc.
  2. Resolve every relative image reference (e.g. ./assets/x.png) to an absolute path,
     relative to the markdown file's own directory, so pandoc finds the files no matter
     the working directory.
  3. Width-constrain every image so wide diagrams don't overflow the page.
  4. Run pandoc to emit a .docx with all images embedded.

Usage:
  render_and_build.py <input.md> [--out-dir DIR] [--width 6in] [--scale 2]

Prints the path of the generated .docx on the last line of stdout.
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input_md")
    ap.add_argument("--out-dir", default=None,
                    help="work/output dir (default: /tmp/md2gdoc/<stem>)")
    ap.add_argument("--width", default="6in",
                    help="max image width as a pandoc attr (page text width ~6.5in)")
    ap.add_argument("--scale", default="2",
                    help="mmdc render scale; 2 = crisp text without huge files")
    args = ap.parse_args()

    src = Path(args.input_md).resolve()
    if not src.exists():
        sys.exit(f"input not found: {src}")
    src_dir = src.parent

    out_dir = Path(args.out_dir) if args.out_dir else Path("/tmp/md2gdoc") / src.stem
    render_dir = out_dir / "rendered"
    render_dir.mkdir(parents=True, exist_ok=True)

    text = src.read_text(encoding="utf-8")
    width_attr = "{width=%s}" % args.width

    # 1. render mermaid blocks
    mermaid_re = re.compile(r"```mermaid\n(.*?)\n```", re.DOTALL)
    blocks = mermaid_re.findall(text)
    print(f"mermaid blocks: {len(blocks)}", file=sys.stderr)
    rendered = []
    for i, code in enumerate(blocks, 1):
        mmd = render_dir / f"mermaid_{i:02d}.mmd"
        png = render_dir / f"mermaid_{i:02d}.png"
        mmd.write_text(code + "\n", encoding="utf-8")
        r = subprocess.run(
            ["mmdc", "-i", str(mmd), "-o", str(png), "-b", "white", "-s", str(args.scale)],
            capture_output=True, text=True,
        )
        if r.returncode != 0 or not png.exists():
            sys.exit(f"mmdc failed on block {i}:\n{r.stderr}")
        rendered.append(png)
        print(f"  rendered block {i} -> {png.name}", file=sys.stderr)

    # 2. swap mermaid fences for image refs (in order)
    n = {"i": 0}
    def repl_mermaid(*_):
        n["i"] += 1
        return f"![Diagram {n['i']}]({rendered[n['i']-1]}){width_attr}"
    text = mermaid_re.sub(repl_mermaid, text)

    # 3. resolve relative image refs to absolute + width-constrain.
    #    Leave absolute paths and URLs alone (only rewrite if the resolved file exists).
    def repl_img(m):
        alt, target = m.group(1), m.group(2).strip()
        if target.startswith(("http://", "https://", "/")) or target.startswith("/tmp/"):
            # already absolute or remote: just ensure width attr
            return f"![{alt}]({target}){width_attr}"
        resolved = (src_dir / target).resolve()
        if resolved.exists():
            return f"![{alt}]({resolved}){width_attr}"
        return m.group(0)  # unknown ref, leave untouched
    text = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", repl_img, text)

    out_md = out_dir / f"{src.stem}.pandoc.md"
    out_md.write_text(text, encoding="utf-8")

    leftover = text.count("```mermaid")
    if leftover:
        sys.exit(f"unexpected: {leftover} mermaid fences remain after substitution")

    # 4. pandoc -> docx
    out_docx = out_dir / f"{src.stem}.docx"
    r = subprocess.run(["pandoc", str(out_md), "-o", str(out_docx)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"pandoc failed:\n{r.stderr}")

    # sanity: embedded media count should equal image refs
    media = subprocess.run(["unzip", "-l", str(out_docx)],
                           capture_output=True, text=True).stdout
    media_count = media.count("word/media/")
    img_refs = len(re.findall(r"!\[[^\]]*\]\(", text))
    print(f"image refs: {img_refs}; embedded media in docx: {media_count}", file=sys.stderr)

    print(str(out_docx))  # last line = the artifact path


if __name__ == "__main__":
    main()
