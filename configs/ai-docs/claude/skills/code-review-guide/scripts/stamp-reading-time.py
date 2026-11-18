#!/usr/bin/env python3
# stamp-reading-time.py - Fill a review guide's reading times.
#
# Usage:
#   stamp-reading-time.py <guide.md>
#   stamp-reading-time.py --help
#
# stdin: unused
# stdout: one line per layer, e.g.
#   camada1 words=201 diagrams=1 minutes=3
#
# The guide is rewritten in place: {EST1} and {EST2} become
# "(~N min)", N = ceil(words / 200) + 1 per mermaid diagram.
#
# exit: 0 stamped, 1 bad input (message on stderr): file
#   unreadable, or a placeholder or layer heading missing.
import math
import re
import sys
from pathlib import Path

WORDS_PER_MINUTE = 200
MINUTES_PER_DIAGRAM = 1

LAYER_1_HEADING = re.compile(r"(?m)^## .*Camada 1\b")
LAYER_2_HEADING = re.compile(r"(?m)^## .*Camada 2\b")
MERMAID_BLOCK = re.compile(r"(?ms)^```mermaid.*?^```")
MERMAID_OPENING = re.compile(r"(?m)^```mermaid")
LINK_URL = re.compile(r"\]\([^)]*\)")


class GuideError(Exception):
    pass


def split_layers(text):
    """Return the text of layer 1 and of layer 2."""
    layer_1_start = LAYER_1_HEADING.search(text)
    layer_2_start = LAYER_2_HEADING.search(text)
    if layer_1_start is None or layer_2_start is None:
        raise GuideError("Camada 1 or Camada 2 heading is missing")
    layer_1 = text[layer_1_start.start():layer_2_start.start()]
    layer_2 = text[layer_2_start.start():]
    return layer_1, layer_2


def count_words(layer_text):
    """Count words, skipping mermaid source and link URLs."""
    prose = MERMAID_BLOCK.sub(" ", layer_text)
    prose = LINK_URL.sub("]", prose)
    return len(prose.split())


def estimate_layer(layer_text):
    words = count_words(layer_text)
    diagrams = len(MERMAID_OPENING.findall(layer_text))
    reading_minutes = math.ceil(words / WORDS_PER_MINUTE)
    minutes = reading_minutes + diagrams * MINUTES_PER_DIAGRAM
    return words, diagrams, minutes


def stamp(text):
    """Return the stamped text and one report line per layer."""
    for placeholder in ("{EST1}", "{EST2}"):
        if placeholder not in text:
            raise GuideError(f"placeholder {placeholder} is missing")
    layers = split_layers(text)
    report = []
    for number, (placeholder, layer) in enumerate(
        zip(("{EST1}", "{EST2}"), layers), start=1
    ):
        words, diagrams, minutes = estimate_layer(layer)
        text = text.replace(placeholder, f"(~{minutes} min)")
        report.append(
            f"camada{number} words={words} "
            f"diagrams={diagrams} minutes={minutes}"
        )
    return text, report


def print_header_comment(script_path):
    """Print the leading comment block, minus the shebang."""
    for line in Path(script_path).read_text().splitlines()[1:]:
        if not line.startswith("#"):
            break
        print(line.removeprefix("# ").removeprefix("#"))


def main(argv):
    if argv[1:] in (["-h"], ["--help"]):
        print_header_comment(argv[0])
        return 0
    if len(argv) != 2:
        print("usage: stamp-reading-time.py <guide.md>", file=sys.stderr)
        return 1
    guide_path = Path(argv[1])
    try:
        text = guide_path.read_text(encoding="utf-8")
        stamped, report = stamp(text)
    except (OSError, UnicodeDecodeError) as error:
        print(f"error: cannot read {guide_path}: {error}", file=sys.stderr)
        return 1
    except GuideError as error:
        print(f"error: {guide_path}: {error}", file=sys.stderr)
        return 1
    guide_path.write_text(stamped, encoding="utf-8")
    print("\n".join(report))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
