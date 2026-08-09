#!/usr/bin/env python3
"""check-rule-citations.py - flag cross-file rule citations that don't resolve.

These docs deliberately don't restate rules; each one points at whichever file
authors the rule ("the rule is canonical; do not restate it here"). That only
holds if the pointer resolves. When it names the wrong file the reader follows
it, finds nothing, and re-derives the rule locally - recreating exactly the
duplication the pointer exists to prevent. A wrong pointer is worse than none,
because it looks satisfied.

Four citation forms are recognised, three of them quoting the rule by name:

  A  the "Context section" rule in writing-style.md
  B  writing-style.md's "Bullets"
  D  SKILL.md "JSON snippets" rule
  C  pr-page-budget.md's altitude rule          <- descriptive slug, not a name

A/B/D are checked STRICTLY: every significant word of the quoted name must
appear in one bold span (`- **Bullets** -- ...`) or heading (`## the one-page
goal`) of the cited file - the two forms a rule is authored in. Word-set
containment rather than substring, because a correct citation may compress the
authored name: "Section names in the PR's primary language" is authored as
**Section names AND body prose in the PR's primary language**.

C is checked WEAKLY - its words need only appear somewhere in the cited file.
The slug is a paraphrase, so there is no name to match; absent words still prove
the citation wrong, present ones prove nothing. This one-sided check is
deliberate: restricting C to bold spans would flag correct citations of CLAUDE.md,
whose rules are often not bolded, and a check that cries wolf gets ignored.

C gets one extra hop. When the cited file does mention the slug, but every line
mentioning it also names ANOTHER .md, that file is a signpost rather than the
author and the citation should have named whatever it points at. A slug the cited
file authors as a bold span or heading is its own, however many example files
those lines link out to.

A cited filename that doesn't resolve is SKIPPED, not reported - example content
legitimately names files from other projects, and there is nothing to verify.

AI-consumed output (compact, parseable - mirrors check-density.sh):
  == <filename>                          header, per file with hits
  <line>:unresolved-rule:<file>:"<name>" quoted name is authored nowhere in <file>
  <line>:unknown-topic:<file>:<slug>     slug's words appear nowhere in <file>
  <line>:forwarded:<file>:<other>        <file> only forwards the slug to <other>

The fix is the same for every hit: retarget the citation at the file that really
authors the rule, or - if the rule is stated in more than one place - delete the
extra homes so there is one owner to cite.

Usage:
  check-rule-citations.py <file> [<file>...]
  find ~/.claude/skills \\( -name '*.md' -o -name '*.sh' -o -name '*.py' \\) \\
    -print0 | xargs -0 check-rule-citations.py

Exit codes:
  0  clean
  1  citations found that don't resolve
  2  usage error
"""

import re
import sys
from functools import lru_cache
from pathlib import Path

FENCE = re.compile(r"^\s*(```|~~~)")
FRONTMATTER = re.compile(r"^---\s*$")

MD_FILE = r"[A-Za-z0-9_./-]+\.md"
QUOTED = r'"([^"]{3,80})"'
APOS = r"['’]s"
RULE_NOUN = r"(?:rule|section|invariant|convention|goal|order|budget)"

# A: the "X" rule in Y.md  ->  (name, file)
FORM_QUOTED_IN_FILE = re.compile(rf"{QUOTED}\s+{RULE_NOUN}s?\s+in\s+({MD_FILE})")
# B: Y.md's "X"  ->  (file, name)
FORM_FILE_OWNS_QUOTED = re.compile(rf"({MD_FILE}){APOS}\s+{QUOTED}")
# D: Y.md "X"  ->  (file, name)
FORM_FILE_THEN_QUOTED = re.compile(rf"({MD_FILE})\s+{QUOTED}")
# C: Y.md's altitude rule  ->  (file, slug). The noun rides along in the slug:
# "one-page goal" identifies a topic where the bare adjective "one-page" doesn't.
FORM_FILE_OWNS_SLUG = re.compile(
    rf"({MD_FILE}){APOS}\s+([a-z][a-z' ’-]{{2,40}}?\s+{RULE_NOUN})\b"
)

BOLD_SPAN = re.compile(r"\*\*(.+?)\*\*")
HEADING = re.compile(r"^#+\s+(.*)$")

# Words carrying no identifying signal; dropped before comparing a cited name to
# an authored one, so a citation may compress or expand the connective tissue.
# "rule" is here because it names the act of citing, not the thing cited - unlike
# "goal", "invariant", or "budget", which do narrow which rule is meant.
STOPWORDS = {
    "the", "and", "for", "its", "it", "in", "on", "of", "to", "or", "is", "as",
    "at", "by", "with", "from", "that", "this", "not", "never", "only", "per",
    "a", "an", "be", "are", "but", "into", "over", "own", "all", "any", "one",
    "rule", "rules",
}


def significant_words(phrase):
    """Identifying words of a rule name - lowercased, stripped of punctuation."""
    raw = re.split(r"[^A-Za-z0-9]+", phrase.lower())
    return {word for word in raw if len(word) >= 3 and word not in STOPWORDS}


def iter_prose_lines(path):
    """Yield (line_no, text) for lines outside code fences and frontmatter."""
    with open(path, encoding="utf-8") as fh:
        lines = fh.read().splitlines()

    in_fence = False
    in_frontmatter = bool(lines) and bool(FRONTMATTER.match(lines[0]))

    for index, line in enumerate(lines):
        if in_frontmatter:
            # The opening --- is line 0, so only a LATER --- closes the block.
            if index > 0 and FRONTMATTER.match(line):
                in_frontmatter = False
            continue

        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue

        yield index + 1, line


def find_skill_root(path):
    """Nearest ancestor directory holding a SKILL.md, or None outside a skill."""
    for parent in Path(path).resolve().parents:
        if (parent / "SKILL.md").is_file():
            return parent
    return None


def resolve_target(cited, citing_path, skill_root):
    """Filesystem path a cited filename names, or None when it names nothing here.

    SKILL.md means the citing file's own skill; CLAUDE.md means the config root
    two levels above a skill (~/.claude/CLAUDE.md). Anything else is searched in
    the citing file's directory, then the skill's usual subdirectories.
    """
    citing_dir = Path(citing_path).resolve().parent

    if cited == "SKILL.md":
        return skill_root / "SKILL.md" if skill_root else None

    if cited == "CLAUDE.md" and skill_root:
        candidate = skill_root.parent.parent / "CLAUDE.md"
        return candidate if candidate.is_file() else None

    search_dirs = [citing_dir]
    if skill_root:
        search_dirs += [skill_root, skill_root / "references", skill_root / "assets"]

    for directory in search_dirs:
        candidate = directory / cited
        if candidate.is_file():
            return candidate
    return None


@lru_cache(maxsize=None)
def authored_names(path):
    """Every bold span and heading in a file - the two forms a rule is authored in."""
    spans = []
    for _, line in iter_prose_lines(path):
        heading = HEADING.match(line)
        if heading:
            spans.append(heading.group(1))
        spans.extend(BOLD_SPAN.findall(line))
    return tuple(spans)


@lru_cache(maxsize=None)
def file_words(path):
    """Every significant word anywhere in a file, for the weak slug check."""
    with open(path, encoding="utf-8") as fh:
        return frozenset(significant_words(fh.read()))


def is_authored_in(name, target):
    """True when one bold span or heading of target carries every word of name."""
    wanted = significant_words(name)
    if not wanted:
        return True
    return any(wanted <= significant_words(span) for span in authored_names(target))


def is_mentioned_in(slug, target):
    """True when every word of a descriptive slug appears somewhere in target."""
    wanted = significant_words(slug)
    return not wanted or wanted <= file_words(target)


def forwarded_to(topic, target):
    """The file target hands `topic` off to, or None when target keeps it.

    Catches the one-hop-stale citation: target does mention the topic, but only
    on lines that name another file - so target is a signpost, not the author,
    and the citation should have named whatever it points at. A single mention
    that names nobody else means target really does carry the rule.
    """
    wanted = significant_words(topic)
    if not wanted:
        return None

    forwards = set()
    for _, line in iter_prose_lines(target):
        if not wanted <= significant_words(line):
            continue
        others = {name for name in re.findall(MD_FILE, line)
                  if Path(name).name != Path(target).name}
        if not others:
            return None
        forwards |= others

    return sorted(forwards)[0] if forwards else None


def cited_names(line):
    """Yield (cited_file, name, is_quoted) for every citation on one line."""
    for name, cited in FORM_QUOTED_IN_FILE.findall(line):
        yield cited, name, True
    for cited, name in FORM_FILE_OWNS_QUOTED.findall(line):
        yield cited, name, True
    for cited, name in FORM_FILE_THEN_QUOTED.findall(line):
        yield cited, name, True
    for cited, slug in FORM_FILE_OWNS_SLUG.findall(line):
        yield cited, slug.strip(), False


def check(path):
    """Report unresolved citations in one file; returns the violation count."""
    skill_root = find_skill_root(path)
    hits = []
    seen = set()

    for line_no, line in iter_prose_lines(path):
        for cited, name, is_quoted in cited_names(line):
            if (line_no, cited, name) in seen:
                continue
            seen.add((line_no, cited, name))

            target = resolve_target(cited, path, skill_root)
            if target is None or target.samefile(path):
                continue

            if is_quoted:
                if not is_authored_in(name, target):
                    hits.append((line_no, f'unresolved-rule:{cited}:"{name}"'))
                continue

            if not is_mentioned_in(name, target):
                hits.append((line_no, f"unknown-topic:{cited}:{name}"))
                continue

            # A rule authored in the target is the target's, however many example
            # files its own line links out to - only an unauthored topic forwards.
            if is_authored_in(name, target):
                continue

            signpost = forwarded_to(name, target)
            if signpost:
                hits.append((line_no, f"forwarded:{cited}:{signpost}"))

    if hits:
        print(f"== {path}")
        for line_no, detail in sorted(hits):
            print(f"{line_no}:{detail}")

    return len(hits)


def main(argv):
    files = [arg for arg in argv if not arg.startswith("-")]

    if not files or len(files) != len(argv):
        print("usage: check-rule-citations.py <file> [<file>...]", file=sys.stderr)
        return 2

    total = 0
    for path in files:
        try:
            total += check(path)
        except OSError as err:
            print(f"cannot read {path}: {err}", file=sys.stderr)
            return 2

    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
