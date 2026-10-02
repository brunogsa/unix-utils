# Wave 2 fan-out path

Read this only when `SKILL.md`'s Wave 2 path selection chose the fan-out path. The inline path never opens it.

## Dispatch the lenses

Dispatch, in one message, in the background, one `agent(subAgent=code-reviewer, title=Review lens <name>)` per remaining lens. Each prompt carries:

- the resolved preamble placeholders: `diff_path`, `changed_files_path`, `commentable_lines_path`, `repo_root`, `mode`.
  - The `pr_context` file paths: `pr.json`, `commit-messages.txt`, `issue-context.md` when non-empty; the spec and plan paths in local mode.

- the single rubric path `references/specialists/<name>.md`, with the instruction to read `references/common-preamble.md` first, invoke `code-standards`, and honor the preamble's lazy triggers;
- the output path `$work_dir/wave2-lens-<name>.json`, holding the JSON array (an empty array when the lens finds nothing);
- the return contract: one line — output path and finding count — never the findings themselves.

On attempts ≥ 2, run `ListAgents` before dispatching and skip every lens that already has a live `Review lens <name>` agent.

A compaction during the wait leaves those agents running while their files are still missing, so a blind re-dispatch reviews the same lens twice.

When github mode also needs the guide (see "Guide writer on the fan-out path" below), its agent goes in the same dispatch message; it depends on Wave 1's files, not on the findings.

The orchestrator never reads the diff on this path; the lens agents do, each in its own window.

## Verify the lens files

Once every completion notification is in, verify each expected file exists and parses: `jq -e 'type=="array"' "$work_dir/wave2-lens-<name>.json"`.

For a missing or unparsable lens, first check `ListAgents` for a live agent with that title — a compaction mid-fan-out cannot tell running from dead — and only then re-dispatch it, once. A second failure aborts Wave 2 naming the lens.

## Merge

Merge, once every lens has a file:

```bash
n=$(ls "$work_dir"/wave2-lens-*.json 2>/dev/null | wc -l | tr -d ' ')
[ "$n" -eq 8 ] || { echo "wave2: expected 8 lens outputs, found $n"; exit 1; }
jq -s 'add' "$work_dir"/wave2-lens-*.json > "$work_dir/wave2-findings.json"
```

The count guard is the point of that block: an absent file and an empty array are indistinguishable downstream.

Without it, a lens skipped by mistake reads as a rubric that found nothing.

Dedup is **not** done here. Eight lenses over the same diff can still flag one defect twice under two `scope_tag`s, so Wave 3 resolves overlaps with the full merged list in hand.

## Guide writer on the fan-out path

Applies in github mode with `tiny_pr=false`. Dispatch `agent(subAgent=general-purpose, title=Write review guide, model=opus)` in the background — in the lens dispatch message when both go out together —

- telling it to read `references/guide-writer.md`, resolve its placeholders against the Wave 1 files, write the guide to `$work_dir/wave2-guide.md`, and return one line.
- `guide-writer.md` takes the diff as input, so running it inline re-reads the whole diff the fan-out exists to keep out of this window.
  - `general-purpose` has no frontmatter, so the model is named on the call and effort inherits — acceptable for prose.

- After the lens verification, if `$work_dir/wave2-guide.md` is still missing, give it the lens treatment: check `ListAgents` for a live `Write review guide` agent, then re-dispatch once.
  - On a second failure write the 2-sentence summary inline instead of aborting — the guide is context for the human, not a gate the findings depend on.
