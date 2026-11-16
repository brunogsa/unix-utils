#!/usr/bin/env python3
# test_render_and_build.py: tests the image-ref rewrite and
# the .docx pandoc builds.
#
# Usage:
#   python3 test_render_and_build.py
#   pytest test_render_and_build.py
#
# stdout: unittest results
# exit: 0 when every test passes, 1 otherwise
import base64
import importlib.util
import re
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

# Load the script by path: pytest's importlib mode puts no
# scripts dir on sys.path, so a plain import fails there.
SCRIPT = Path(__file__).resolve().parent / "render_and_build.py"
_spec = importlib.util.spec_from_file_location("render_and_build", SCRIPT)
if _spec is None or _spec.loader is None:
    raise ImportError(f"cannot load {SCRIPT}")
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
rewrite_image_refs = _module.rewrite_image_refs

WIDTH_ATTR = "{width=6in}"
DIAGRAM_PNG = "/tmp/md2gdoc/doc/rendered/mermaid_01.png"
MARKDOWN = """# Doc

```mermaid
graph TD
  A --> B
```

![Logo](./x.png)

![Chart](./chart.png){width=3in}
"""


class RewriteImageRefsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.src_dir = Path(self.tmp.name).resolve()
        (self.src_dir / "x.png").write_bytes(b"png")
        (self.src_dir / "chart.png").write_bytes(b"png")
        self.output = rewrite_image_refs(
            text=MARKDOWN, rendered_pngs=[Path(DIAGRAM_PNG)],
            src_dir=self.src_dir, width_attr=WIDTH_ATTR)

    def tearDown(self):
        self.tmp.cleanup()

    def test_never_places_two_attribute_blocks_side_by_side(self):
        self.assertNotIn("}{", self.output)

    def test_mermaid_diagram_gets_one_page_width_attribute(self):
        self.assertIn(f"![Diagram 1]({DIAGRAM_PNG}){{width=6in}}\n", self.output)

    def test_relative_image_resolves_to_absolute_with_one_page_width_attribute(self):
        self.assertIn(f"![Logo]({self.src_dir / 'x.png'}){{width=6in}}\n", self.output)

    def test_image_with_its_own_width_keeps_it_instead_of_the_page_width(self):
        chart_refs = re.findall(r"!\[Chart\]\([^)]*\)\S*", self.output)
        self.assertEqual(len(chart_refs), 1)
        self.assertTrue(chart_refs[0].endswith(")" + "{width=3in}"), chart_refs[0])

    def test_relative_image_with_its_own_width_still_resolves_to_absolute(self):
        self.assertIn(f"![Chart]({self.src_dir / 'chart.png'}){{width=3in}}\n", self.output)


# A valid 1x1 PNG, so pandoc embeds a real image instead of
# falling back to alt text.
ONE_PIXEL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==")


class BuildDocxTest(unittest.TestCase):
    """Runs the whole script on a tiny markdown.

    It reads back the .docx that pandoc produced.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name).resolve()
        (self.dir / "x.png").write_bytes(ONE_PIXEL_PNG)

    def tearDown(self):
        self.tmp.cleanup()

    def build(self, markdown):
        src = self.dir / "doc.md"
        src.write_text(markdown, encoding="utf-8")
        out_dir = self.dir / "out"
        run = subprocess.run([sys.executable, str(SCRIPT), str(src), "--out-dir", str(out_dir)],
                             capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        return zipfile.ZipFile(out_dir / "doc.docx")

    def test_keeps_angle_bracket_placeholder_text_outside_code(self):
        docx = self.build("| Campo | Data |\n|---|---|\n| inicio | **<data a definir>** |\n")
        self.assertIn("&lt;data a definir&gt;", docx.read("word/document.xml").decode())

    def test_image_alone_in_a_paragraph_gets_no_figure_or_caption_paragraph(self):
        docx = self.build("Texto antes.\n\n![Diagram 1](x.png)\n\nTexto depois.\n")
        document = docx.read("word/document.xml").decode()
        self.assertIn("<w:drawing>", document)
        self.assertNotIn("ImageCaption", document)
        self.assertNotIn("CaptionedFigure", document)

    def test_link_with_angle_bracket_destination_stays_a_hyperlink_to_that_url(self):
        docx = self.build("[t](<https://example.com/a b>)\n")
        self.assertIn("<w:hyperlink", docx.read("word/document.xml").decode())
        self.assertIn('Target="https://example.com/a%20b"',
                      docx.read("word/_rels/document.xml.rels").decode())


if __name__ == "__main__":
    unittest.main()
