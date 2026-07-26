# Research — CLAUDE.md size budgets

Citations behind the two CLAUDE.md size numbers: 260 non-blank lines, and 32 words per line.

The instruction-count and CRITICAL-ratio budgets are separate — see [`research-instruction-load-budgets.md`](research-instruction-load-budgets.md).

[`research.md`](research.md) indexes all three files and carries the summary table.

## CLAUDE.md length

**Budget: 260 non-blank lines**

### Marker-convention re-derivation (200 → 260)

The 200 below was anchored on "a line roughly equals an instruction" — true for the pre-marker imperative style.

The marker convention broke that 1:1 mapping: every `[Instruction]` now carries a `[Why]` line beneath it, plus optional `[Example]` lines.

So ~100 instructions cost ~200 non-blank lines as instruction+why pairs alone, before any header or the Counting-conventions meta section.

That makes the 100-instruction budget and a 200-line budget mathematically incompatible — you cannot use the full instruction budget without breaching 200 lines.

The fix keeps instruction *count* (≤100) as the real adherence gate and re-derives the line cap to **260** = ~200 (pairs at full instruction budget) + ~60 (current header/meta/example overhead).

The line budget now guards only marker-overhead bloat, not instruction load — the count budget already does the latter.

### Jaroslawicz et al. 2025 — instruction adherence peaks at 150–200

*How Many Instructions Can LLMs Follow at Once?* arXiv:2507.11538
https://arxiv.org/abs/2507.11538

IFScale benchmark across 20 frontier models. Key findings:

- "Mid-range peaks around 150–200 instructions" before selective attention degrades.
- Best models drop to 68% accuracy at 500 instructions.
- Reasoning models hold up better through 100–250.

**Implication:** the 150–200 peak applies to *instruction count*, which the marker convention now measures directly (≤100 budget). The line cap (260) is a separate marker-overhead guard — see the re-derivation above.

### Community consensus — 200 ideal, 300 ceiling

- HumanLayer, *Writing a good CLAUDE.md* — https://www.humanlayer.dev/blog/writing-a-good-claude-md
- anthropics/claude-code#5502 — community report of CLAUDE.md adherence decay — https://github.com/anthropics/claude-code/issues/5502

### arXiv 2603.13351 — context interference

*Prompt Complexity Dilutes Structured Reasoning* — https://arxiv.org/html/2603.13351v1

A STAR task scored 100% on an isolated prompt, but 0–30% when surrounded by competing instructions. Supports trimming CLAUDE.md aggressively even when under the line budget.

### Anthropic — Claude Code best practices

https://code.claude.com/docs/en/best-practices — "Keep CLAUDE.md short and human-readable." No numeric cap; informs the "keep lean" stance rather than a specific number.

---

## CLAUDE.md words per line

**Budget: 32 words per line**

No external source. User preference backing the "Prefer scannable shape" principle in CLAUDE.md.

Acts as a prose-bloat guard:

- 32 words is ~2 full sentences or ~200 characters — the upper edge of comfortable scanning.
- Most principles should come in well under.
- The budget is a ceiling, not a target.

