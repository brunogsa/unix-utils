# Density rules — caps & rewrite patterns

The rule (verbatim from CLAUDE.md `DOC` section):

- Every prose line, bullet, and sub-bullet stays **≤256 chars or ≤32 words**.
- Over the cap → split into more (shorter) paragraphs *or* convert to bullets+sub-bullets.
- Never drop information.

Verify with `~/.claude/skills/doc-standards/scripts/check-density.sh <file>`.

## Why bullets, not just shorter prose

- Long prose paragraphs compress the writer's reasoning into one breathless run.
- Bullets force expansion of the structure the writer used internally — exactly what readers need to scan.
- Reach for bullets first; reach for "more paragraphs" only when the content genuinely flows as continuous reasoning (rare in PR/spec/plan docs).

## What the script excludes (and why)

- **Fenced code blocks** (``` … ```) — code has its own length norms; mermaid blocks are diagrams.
- **Blank lines** — separators carry no content.
- **Table rows** (lines starting with `|`) — tables wrap visually; raw markdown is wide by format.
- **HTML-tag-only lines** (`<details>`, `</details>`, `<summary>…</summary>`) — structural wrappers, not content.
- **Link-only lines** — a single `[text](url)` with optional list/quote marker is a citation pointer, not prose.

Char/word measurement strips `(https://…)` URL portions and remaining `[`/`]` brackets first, so `[label](url)` measures as `label` — the rendered density a reader actually sees.

## Rewrite patterns

### Dense paragraph → bullets + sub-bullets

Bad — 470 chars / 60 words in one breath:

```markdown
DBMA-841 (BFF) introduces a new procedure `getSchoolsAgreementsAndSkus` (sibling of `errorCallbacks.*`) that returns the active agreements per school (one per brand via `getMostRecentContractPerBrand`) and their SKUs, allowing the front-end to filter agreements and SKUs through `errorCallbacks.{list,summary}` in passthrough mode (still accepts CNPJ as a parameter for backward compatibility), and adds a guard preventing multi-entity passthrough on the same request.
```

Good — same information, scannable:

```markdown
- **DBMA-841 (BFF)** — new procedure + passthrough on the read endpoints.
  - **`contractValidation.getSchoolsAgreementsAndSkus`** (NEW, sibling of `errorCallbacks.*`).
    - Returns active agreements per school (one per brand via `getMostRecentContractPerBrand`) and their SKUs.
  - **`errorCallbacks.{list,summary}` passthrough mode** — accept `salesAgreementId[]` / `sku[]` directly, forward to Integrator.
    - Still accepts CNPJ for backwards compatibility.
  - **Guard** — rejects multi-entity passthrough on the same request (preserves Integrator index usage).
```

### Long bullet → bullet + sub-bullets

Bad — 320 chars / 40 words in one bullet:

```markdown
- **Eager fetch de SKUs no helper** — sempre busca SKUs para todo agreement sobrevivente, independente de qual aba o operador vai abrir, porque o resultado é cacheado no browser e reusado em todas as 3 abas; uma busca lazy "skip SKUs unless entity=product" forçaria re-derivação ao trocar de aba e derrotaria a arquitetura de cache.
```

Good — split the rationale:

```markdown
- **Eager fetch de SKUs no helper** — sempre busca SKUs para todo agreement sobrevivente, independente de qual aba o operador vai abrir.
  - O resultado é cacheado no browser e reusado em todas as 3 abas.
  - Lazy fetch ("skip SKUs unless entity=product") forçaria re-derivação ao trocar de aba e derrotaria a arquitetura de cache.
```

## Exceptions (single connective sentence between bulleted blocks)

- A short prose sentence connecting two bulleted blocks is fine — often clearer than forcing it into a bullet.
- Keep that sentence ≤256 chars / ≤32 words.
- The script flags any line over the cap regardless of role; resolve those by splitting, not by exception.

Example — acceptable connective sentence:

```markdown
- **Phase 1 (Apply)** — derive agreements + SKUs once, cache the envelope.
- **Phase 2 (Browse)** — read cache, flatten by entity, passthrough to Integrator.

Phase 1 runs once per Apply; Phase 2 runs on every tab/filter/page interaction.

- **Cache miss** — re-Apply invalidates the key and re-derives.
- **Failed brands** — non-blocking warning banner, partial render.
```
