#!/usr/bin/env python3
"""Render Mermaid blocks in a markdown file,
then build a pandoc .docx ready for Google Docs.

Why a .docx (and not HTML or paste-from-markdown):
  Google Drive turns an uploaded .docx into a native Google Doc.
  The conversion keeps full fidelity AND keeps embedded images,
  because a .docx carries images as real media parts.
  Google's HTML import, by contrast,
  silently strips inline/base64 images.
  HTML therefore loses every diagram.
  Only the .docx path preserves images through the conversion.

What this does:
  1. Find every ```mermaid fenced block,
     render each to a PNG via mmdc.
  2. Resolve every relative image reference to an absolute path.
     Example: ./assets/x.png.
     The base is the markdown file's own directory.
     Pandoc then finds the files from any working directory.
  3. Width-constrain every image.
     Wide diagrams would otherwise overflow the page.
  4. Run pandoc to emit a .docx with all images embedded.

Usage:
  render_and_build.py <input.md>
      [--out-dir DIR] [--width 6in] [--scale 2]

It prints the path of the generated .docx.
That path is the last line of stdout.
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

MERMAID_RE = re.compile(r"```mermaid\n(.*?)\n```", re.DOTALL)

# Group 3 captures an attribute block already trailing the ref
# (e.g. {width=3in} or {#fig .wide}), so it is kept as-is
# instead of a second block being appended after it.
IMAGE_REF_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)(\{[^}]*\})?")


def rewrite_image_refs(text, rendered_pngs, src_dir, width_attr):
    """Return text with mermaid fences swapped for image refs.
    Every image ref is width-constrained.

    rendered_pngs holds one PNG path per mermaid fence,
    in fence order.
    """

    # 2. swap mermaid fences for image refs (in order)
    n = {"i": 0}
    def repl_mermaid(*_):
        n["i"] += 1
        return f"![Diagram {n['i']}]({rendered_pngs[n['i']-1]}){width_attr}"
    text = MERMAID_RE.sub(repl_mermaid, text)

    # 3. resolve relative image refs to absolute +
    # width-constrain.
    #    Leave absolute paths and URLs alone (only rewrite if
    #    the resolved file exists).
    def repl_img(m):
        alt, target = m.group(1), m.group(2).strip()
        attr = m.group(3) or width_attr
        if target.startswith(("http://", "https://", "/")) or target.startswith("/tmp/"):
            # already absolute or remote: just ensure width attr
            return f"![{alt}]({target}){attr}"
        resolved = (src_dir / target).resolve()
        if resolved.exists():
            return f"![{alt}]({resolved}){attr}"
        return m.group(0)  # unknown ref, leave untouched
    return IMAGE_REF_RE.sub(repl_img, text)


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("input_md")
    ap.add_argument("--out-dir", default=None,
                    help="work/output dir (default: /tmp/md2gdoc/<stem>)")
    ap.add_argument("--width", default="6in",
                    help="max image width as a pandoc attr (page text width ~6.5in)")
    ap.add_argument("--scale", default="2",
                    help="mmdc render scale; 2 = crisp text without huge files")
    return ap.parse_args()


def render_mermaid_blocks(text, render_dir, scale):
    """Render every mermaid fence in text to a PNG.

    Return the PNG paths in fence order.
    """
    blocks = MERMAID_RE.findall(text)
    print(f"mermaid blocks: {len(blocks)}", file=sys.stderr)
    rendered = []
    for i, code in enumerate(blocks, 1):
        mmd = render_dir / f"mermaid_{i:02d}.mmd"
        png = render_dir / f"mermaid_{i:02d}.png"
        mmd.write_text(code + "\n", encoding="utf-8")
        r = subprocess.run(
            ["mmdc", "-i", str(mmd), "-o", str(png), "-b", "white", "-s", str(scale)],
            capture_output=True, text=True,
        )
        if r.returncode != 0 or not png.exists():
            sys.exit(f"mmdc failed on block {i}:\n{r.stderr}")
        rendered.append(png)
        print(f"  rendered block {i} -> {png.name}", file=sys.stderr)
    return rendered


def write_pandoc_md(text, out_md):
    """Write text to out_md; fail if a mermaid fence remains."""
    out_md.write_text(text, encoding="utf-8")

    leftover = text.count("```mermaid")
    if leftover:
        sys.exit(f"unexpected: {leftover} mermaid fences remain after substitution")


def build_docx(out_md, out_docx):
    """Run pandoc on out_md to emit out_docx."""

    # -raw_html: the docx writer drops raw HTML, so `<valor>`
    # placeholders would vanish. -implicit_figures: caption
    # paragraphs keep-with-next, so Google Docs pushes diagrams
    # to the next page.
    r = subprocess.run(["pandoc", "-f", "markdown-implicit_figures-raw_html",
                        str(out_md), "-o", str(out_docx)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"pandoc failed:\n{r.stderr}")


def report_media_counts(text, out_docx):
    """Print image refs vs embedded media in the docx."""
    media = subprocess.run(["unzip", "-l", str(out_docx)],
                           capture_output=True, text=True).stdout
    media_count = media.count("word/media/")
    img_refs = len(re.findall(r"!\[[^\]]*\]\(", text))
    print(f"image refs: {img_refs}; embedded media in docx: {media_count}", file=sys.stderr)


def main():
    args = parse_args()

    src = Path(args.input_md).resolve()
    if not src.exists():
        sys.exit(f"input not found: {src}")

    out_dir = Path(args.out_dir) if args.out_dir else Path("/tmp/md2gdoc") / src.stem
    render_dir = out_dir / "rendered"
    render_dir.mkdir(parents=True, exist_ok=True)

    text = src.read_text(encoding="utf-8")

    # 1. render mermaid blocks
    rendered = render_mermaid_blocks(text, render_dir, args.scale)

    text = rewrite_image_refs(text=text, rendered_pngs=rendered,
                              src_dir=src.parent,
                              width_attr="{width=%s}" % args.width)

    out_md = out_dir / f"{src.stem}.pandoc.md"
    write_pandoc_md(text, out_md)

    # 4. pandoc -> docx
    out_docx = out_dir / f"{src.stem}.docx"
    build_docx(out_md, out_docx)

    # sanity: embedded media count should equal image refs
    report_media_counts(text, out_docx)

    print(str(out_docx))  # last line = the artifact path

    # -raw_html: the docx writer drops raw HTML, so `<valor>`
    # placeholders would vanish. -implicit_figures: caption
    # paragraphs keep-with-next, so Google Docs pushes diagrams
    # to the next page.
    r = subprocess.run(["pandoc", "-f", "markdown-implicit_figures-raw_html",
                        str(out_md), "-o", str(out_docx)],
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
