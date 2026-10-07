# Research - CLAUDE.md size budgets

Citations behind the three CLAUDE.md size numbers: 260 non-blank lines, 40,000 characters, and 32 words per line.

The instruction-count and CRITICAL-ratio budgets are separate - see [`research-instruction-load-budgets.md`](research-instruction-load-budgets.md).

[`research.md`](research.md) indexes all three files and carries the summary table.

## CLAUDE.md length

**Budget: 260 non-blank lines**

### Marker-convention re-derivation (200 → 260)

The 200 below was anchored on "a line roughly equals an instruction" - true for the pre-marker imperative style.

The marker convention broke that 1:1 mapping: every `[Instruction]` now carries a `[Why]` line beneath it, plus optional `[Example]` lines.

So ~100 instructions cost ~200 non-blank lines as instruction+why pairs alone, before any header or the Counting-conventions meta section.

That makes the 100-instruction budget and a 200-line budget mathematically incompatible - you cannot use the full instruction budget without breaching 200 lines.

The fix keeps instruction *count* (≤100) as the real adherence gate and re-derives the line cap to **260** = ~200 (pairs at full instruction budget) + ~60 (current header/meta/example overhead).

The line budget now guards only marker-overhead bloat, not instruction load - the count budget already does the latter.

### Jaroslawicz et al. 2025 - instruction adherence peaks at 150-200

*How Many Instructions Can LLMs Follow at Once?* arXiv:2507.11538
https://arxiv.org/abs/2507.11538

IFScale benchmark across 20 frontier models. Key findings:

- "Mid-range peaks around 150-200 instructions" before selective attention degrades.
- Best models drop to 68% accuracy at 500 instructions.
- Reasoning models hold up better through 100-250.

**Implication:** the 150-200 peak applies to *instruction count*, which the marker convention now measures directly (≤100 budget). The line cap (260) is a separate marker-overhead guard - see the re-derivation above.

### Community consensus - 200 ideal, 300 ceiling

- HumanLayer, *Writing a good CLAUDE.md* - https://www.humanlayer.dev/blog/writing-a-good-claude-md
- anthropics/claude-code#5502 - community report of CLAUDE.md adherence decay - https://github.com/anthropics/claude-code/issues/5502

### arXiv 2603.13351 - context interference

*Prompt Complexity Dilutes Structured Reasoning* - https://arxiv.org/html/2603.13351v1

A STAR task scored 100% on an isolated prompt, but 0-30% when surrounded by competing instructions. Supports trimming CLAUDE.md aggressively even when under the line budget.

### Anthropic - Claude Code best practices

https://code.claude.com/docs/en/best-practices - "Keep CLAUDE.md short and human-readable." No numeric cap; informs the "keep lean" stance rather than a specific number.

---

## CLAUDE.md chars

**Budget: 40,000 characters**

### Claude Code binary - the "Large CLAUDE.md" warning

Source: the Claude Code 2.1.292 binary (`~/.local/share/claude/versions/2.1.292`, extracted 2026-10-07).

- Function `S7e` computes the per-file instruction limit as `max(40000, round(contextWindow * 0.05 * charsPerToken))`.
- `charsPerToken` is 4 for pre-Claude-5 models and 3 otherwise.
- So 40,000 is the floor, and it binds on 200k-context models: 200000 * 0.05 * 3 = 30,000, raised to the 40,000 floor.
- A 1M-context model gets 150,000.
- Warning text: "Large <file> will impact performance (<n> chars > <limit>)".
- `<n>` is the file's JS string length, which equals characters for non-astral text.
- `check.sh` counts code points with a locale-free `tr -d '\200-\277' | wc -c`.

Why 40,000 rather than the model-specific limit: it is the strictest value across every model, so a CLAUDE.md that passes never triggers the warning.

Known non-gate: a second warning, "Instruction files will impact performance: N files, X chars in total > Y".

- Y = `max(120000, per-file limit)`, summed over all loaded instruction files (user, project and local CLAUDE.md, plus rules dirs).
- `check.sh` does not gate this total, because it depends on which project the session runs in.

Official doc: https://code.claude.com/docs/en/memory does not state 40k. It says "target under 200 lines per CLAUDE.md file" (see [CLAUDE.md length](#claudemd-length)) and "Claude Code skips a file over 4 MiB" (the binary has `CB=4194304`).

Re-derive: when a Claude Code release changes the warning, byte-search the current binary for `will impact performance`, then read the limit function that warning calls. Minified names like `S7e` change every release, so search by the warning text, not the name.

---

## CLAUDE.md words per line

**Budget: 32 words per line**

No external source. User preference backing the "Prefer scannable shape" principle in CLAUDE.md.

Acts as a prose-bloat guard:

- 32 words is ~2 full sentences or ~200 characters - the upper edge of comfortable scanning.
- Most principles should come in well under.
- The budget is a ceiling, not a target.

