---
name: markdown-to-google-docs
description: >-
  Publish a Markdown file as a properly-formatted Google Doc with rendered Mermaid
  diagrams and embedded images. Use this whenever the user wants to get a .md file
  (design doc, HLD, RFC, README, spec, notes) into Google Docs — phrases like
  "publish this markdown to Google Docs", "turn this .md into a gdoc", "paste the HLD
  into the google doc with the diagrams rendered", "export this design doc to Docs",
  or "fill this google doc with the content of <file>.md". Triggers even when the
  user doesn't say "Mermaid" — it handles plain Markdown too, and renders any
  ```mermaid``` blocks and relative image references it finds. The output is a native
  Google Doc (headings, bold, lists, tables, code blocks) with every diagram as a real
  embedded image, created fresh or written into an existing doc in place.
---

# Markdown → Google Docs (with rendered Mermaid + images)

## What this solves and why the obvious paths fail

The goal: a Markdown file becomes a native Google Doc that looks hand-made —
real heading styles, tables, code blocks, and every diagram as an embedded image.

Three tempting shortcuts are dead ends; don't waste time rediscovering them:

- **Google Docs "Paste from Markdown" / HTML import** formats text well but **silently
  strips images**. An uploaded HTML with an inline/base64 `<img>` comes back with an
  empty `<img>` tag — every diagram is lost. Verified, not assumed.
- **The Google Drive MCP `create_file`** converts uploads to Docs, but only takes
  content *inline*. A real doc with ~10+ diagrams is a ~1 MB `.docx`; inlining ~1.4 M
  base64 chars is impractical and corrupts in transit. The MCP also has **no Docs edit
  API**, so it can't write into an existing doc or position images.
- **Hand-building the Doc via the Docs API** isn't available through the MCP either.

**The one path that works: render Mermaid → PNG, build a `.docx` with images embedded
(via pandoc), then upload the `.docx` from disk to the Drive REST API, which converts
it to a native Google Doc with images intact.** A `.docx` carries images as real media
parts, so they survive the conversion — unlike HTML.

## Dependencies (check first)

- `mmdc` — Mermaid CLI (`npm i -g @mermaid-js/mermaid-cli` or `brew install mermaid-cli`).
  Its bundled Chromium renders without a system Chrome.
- `pandoc` — Markdown → `.docx` with embedded media (`brew install pandoc`).
- `gcloud` — authenticated, **with Drive scope**. The default login has only
  `cloud-platform` scopes; minting a Drive token then fails with `invalid_scope`.
  The user must run this **once** (interactive, opens a browser):

  ```
  gcloud auth login --enable-gdrive-access
  ```

  This grants full `auth/drive`, which is required to write into a doc the user
  didn't create (`drive.file` would not cover that). If a step reports a token error,
  this re-auth is the fix — ask the user to run it; you can't do it for them.

## Workflow

### 1. Build the `.docx` (no auth needed — do this first)

```bash
python3 <skill>/scripts/render_and_build.py <input.md>
# prints the .docx path on the last stdout line
```

This renders every `​```mermaid​` block to PNG, resolves relative image refs (like
`./assets/x.png`) against the markdown's own directory, width-constrains images so wide
diagrams fit the page, and runs pandoc. It prints how many images it embedded — confirm
that equals the number of diagrams you expect.

### 2. Ask the user how to deliver (it's their call)

Filling an **existing** doc in place needs the Drive re-auth above; a zero-setup
fallback exists. Surface both:

- **Fill an existing doc in place** — same URL, sharing, and revision history are kept;
  the doc's content is replaced. Best when the user gave you a specific doc link.
  Needs the `--enable-gdrive-access` re-auth. **`files.update` replaces all content**,
  so check the target isn't holding work the user wants to keep (read it first; a
  placeholder with a "TODO: paste content" note is the green light). Preserve any small
  header the user had (e.g. a link to the canonical source) by injecting it near the top
  of the markdown before building.
- **Create a new Doc** — same re-auth, but leaves any existing doc untouched.
- **Manual import (zero setup)** — hand the user the `.docx`; they upload it to Drive and
  "Open with Google Docs", which auto-converts with images intact. Produces a new doc,
  no auth. Offer this when re-auth is unwelcome.

### 3. Verify conversion fidelity once (cheap insurance)

Before a big in-place overwrite, push the `.docx` through to a **throwaway** doc and
export it back, to confirm images + heading styles survive on this account:

```bash
python3 <skill>/scripts/gdoc_upload.py test <docx>            # -> {"id": ...}
python3 <skill>/scripts/gdoc_upload.py export <id> /tmp/check.html
grep -o '<img ' /tmp/check.html | wc -l                       # images embedded?
grep -oE '<h[12][^>]*font-size:[0-9]+pt' /tmp/check.html       # real heading styles?
python3 <skill>/scripts/gdoc_upload.py delete <id>            # clean up scratch
```

### 4. Upload for real

```bash
# fill an existing doc in place (same URL):
python3 <skill>/scripts/gdoc_upload.py update <fileId> <docx>

# or create a new doc:
python3 <skill>/scripts/gdoc_upload.py test <docx>   # returns the new doc id
```

Get `<fileId>` from the Google Doc URL: `.../document/d/<fileId>/edit`.

### 5. Verify the result and clean up

Export the final doc and confirm content landed — diagrams, headings, tables, key text:

```bash
python3 <skill>/scripts/gdoc_upload.py export <fileId> /tmp/final.html
grep -o '<img ' /tmp/final.html | wc -l          # = expected diagram count
grep -oE '<h[1-6]' /tmp/final.html | sort | uniq -c
grep -o '<table' /tmp/final.html | wc -l          # use -o | wc -l, NOT grep -c
```

Delete any scratch docs you created during verification so the user's Drive stays clean.

## Gotchas worth remembering

- **`grep -c` counts matching *lines*, not matches.** Google's HTML export is often one
  giant line, so `grep -c '<table'` reports `1` for a doc with many tables. Always use
  `grep -o PATTERN | wc -l` when counting things inside an exported Doc.
- **Width-constrain images.** Sequence/flow diagrams are wide; without a width attr they
  overflow the page. The build script applies `{width=6in}` by default; tune with
  `--width` if margins differ.
- **Image paths must resolve at pandoc time.** The build script rewrites relative refs to
  absolute paths so the working directory doesn't matter; keep that behavior if you edit it.
- **Code blocks** (including ```jsonc / unknown languages) render as a monospace style —
  expected, not a bug.
- **Scope matters for in-place edits.** Updating a doc the user didn't create needs full
  `auth/drive`, not `drive.file`. `--enable-gdrive-access` grants the former.
