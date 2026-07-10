# Decisions, Premises, Risks, Open Questions Structure

The durable docs (HLD, LLD) carry numbered Decisions, Premises, Risks, and Open Questions. Keep those four sections clean with these rules.

- **One item, one sub-section — never a flat bullet list.** Give each Decision/Premise/Risk/Open-Question its own markdown heading, with the entry's body beneath it.
  - Applies uniformly to all four sections — don't leave one as a bullet list and another as sub-sections.
  - **The heading title is a scannable summary.** A reader skims the outline and opens a body only for details — so the title must carry the gist, not just the token.
  - Format: `### <TOKEN> — <summary>`, e.g. `### OQ-08 — Preço do item: unitário vs total`.
  - Keep the stable `<TOKEN>` (OQ-/PR-/D-/R-N) in the heading as the cross-reference anchor.
  - Cross-reference these items only by their stable `<TOKEN>`, never a `§N.M`-number.
    - Items get added/removed and `§`-numbers churn, while the token is a named anchor that tracks the item.
  - Tokens obey the reading-order rule above: cite them only from text after their registry section; earlier text recaps inline without the token.

- **Label by what you actually know.** A fact you've validated or assume true is a *Premise*; a genuine unknown is an *Open Question*.
  - Don't dress an unknown as a Premise, nor prematurely close a question you can't yet answer — both directions matter.

- **An unknown that would block execution becomes a provisional Premise + Risk, not an Open Question.**
  - Assume the most reasonable default, write it as a Premise flagged provisional (e.g. "Provisória — confirmar com o time X").
  - Register what breaks if the assumption is wrong as a Risk that cites the Premise back.
  - This keeps the build moving on the assumed default while the real answer is chased in parallel — reserve Open Questions for unknowns that don't gate work already in flight.
  - Since Risks (section 5) follows Premises (section 3), the Premise points forward with a linkless phrase ("risco ... registrado adiante"); the Risk then carries the backward token once both entries exist.

- **A fact already stated in Context isn't a Premise**, even if later sections cite it often or in a specific way.
  - Recap the Context fact inline instead of minting or reviving a registry token for it.

- **Each fact lives once.** When a question is answered, move the answer into *Decisions*; don't leave decided content embedded inside the *Open Question*.
  - Drop any Open Question that a Premise already settles — no duplicate item across sections.

- **Open Questions is a burn-down list — its goal is "Nenhuma".** It records only what is *still* unknown, not a history of what got resolved.
  - When a question closes, **relocate** its content to the right home — a *Premise*, *Decision*, *Risk*, or embedded directly in the solution/mapping — and **remove** it from the Open Questions list.
  - Never leave a "[RESOLVIDA]" / "resolved" stub sitting in the Open Questions section — that defeats the burn-down and clutters the list.
  - When relocating, keep cross-references intact: repoint any `OQ-N` pointer to the item's new home (or state the fact inline), then grep the doc for dangling `OQ-/PR-/D-/R-` tokens before calling it done.

- **One logical decision, one Decision.** Consolidate; don't fragment a single choice across several `D-` items. Rejected options belong as *"discarded alternatives"* sub-bullets under the decision they lost to, not separate entries.

- **Trade-offs as sub-bullets, not a table.** For a decision's pros/cons, nest bullets under each option — more scannable and easier to keep inside the density cap than a markdown table.

- **Cluster items by theme, then order the clusters along one stable narrative.** Don't leave the four sections in the accidental order the tokens were minted.
  - Pick a narrative the whole doc already follows and reuse it in every section — e.g. the payload/call flow (source-of-truth → header → items → response → read-back), or foundational-scope-first.
  - Reorder freely: the stable `<TOKEN>` is a named anchor, so moving a `### OQ-08` block never breaks a `(OQ-08)` cross-reference elsewhere.
  - **Never renumber a token to fit the new order** — that *does* break every reference.
  - Open the section with a **roadmap** naming each cluster and listing its tokens in reading order (one cluster per line), then order the `###` items to match.
  - The roadmap gives the reader the map before the details.
  - Prefer the roadmap over per-cluster headings — a heading with a single item under it violates the "never a one-item heading" rule, and singleton clusters are common.
