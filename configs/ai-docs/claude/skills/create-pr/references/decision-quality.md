# Decision quality — examples

Examples for the create-pr SKILL.md rules covering decision titles, consequence sub-bullets, reuse rationale, and language consistency.

## Decision titles — user-visible surprise, not internal mechanism

Bad title (mechanism — describes how it works internally):

```
**Eager fetch of SKUs in helper**
```

Good title (user-visible behavior the reader needs to know):

```
**SKUs are loaded even when operator never opens the "Products" tab**
```

Internal-mechanism details belong in sub-bullets, not the title.

## Decisions — spell out the consequence if reversed

When the rationale isn't self-evident from the title, add a sub-bullet describing what degrades or breaks if the decision is reversed:

```
- **1 request to Integrator per tab** — simpler, scales, preserves pagination.
  - Calling errors_callback with >1 entity forces a SCAN in the DB (risk of Integrator degradation).
```

Without that sub-bullet, the decision reads as style preference; with it, the reader sees the constraint.

## Reuse rationale — ONE concrete future use, not a speculative list

Bad (three speculative uses look weaker than one):

```
Future reuse: drill-down screens, store-readiness gate, debug tools
```

Good (one concrete use the reviewer can verify):

```
Future reuse: determine whether a Store is "data-clean" enough to open, in TICKET-XYZ
```

## Section names AND body prose in the PR's primary language

Translate not just section headers but recurring body terms.

- **Section names** (Portuguese team example): `Evidences` → `Evidências`, `References` → `Referências`, `Changes` → `Mudanças`.
- **Body prose** (verbs and structural words): `Apply` → `Aplicar`, `Browse` → `Navegação`, `sibling` → `irmã`, `nested` → `aninhada`.
- **Keep English**: engineering jargon (`passthrough`, `fan-out`, `trade-off`, `deploy`, `follow-up`, `default`, `cache`, `tab`).

Inconsistent language across the ToC and body reads as imported boilerplate; mid-prose English code-switching breaks scanning.

## Reading guide — qualitative, not taxonomic

Each file entry describes what the reviewer *learns* there ("BFF contract", "passthrough mode + helpers", "self-contained, no URL state"), not just role labels ("controller", "use case").

Layout:

- **Open** — one paragraph explaining the reading order's rationale (why these files in this order — typically "feature X enables feature Y" or "contract first, consumers second").
- **Bold the densest file** — e.g., `**The densest piece of this PR**`.
- **Close** — minimum-viable-read shortcut: `If time is short, focus on N, M, K`.
- **Translate the body** to the team's language at render time per the language rule.
