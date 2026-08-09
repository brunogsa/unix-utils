# Reading Order Template

Used by `create-pr`, in PR descriptions as the review guide. Portuguese is the default; the English variant below covers teams whose PR language is English.

Both templates are the *contents* of that block, never the block itself: `references/pr-template.md` owns the collapsed `<details>` wrapper, its `Review guide` label, and the estimated-time line inside its `<summary>`.

That split is what keeps the guide costing 1 rendered line — a variant carrying its own heading or its own wrapper either renders expanded or nests a second `<details>`.

Generate a **specific** reading order from the diff -- list real file paths, not generic placeholders.

## Time-Estimate Heuristic

- **Essential**: ~5 min base + ~1 min per 50 lines of core implementation
- **Complete**: Essential + ~1 min per 100 lines of remaining diff

## File-Role Order

Order files most → least important for the reviewer. Infer roles from paths.

1. **Controller / consumer** -- orchestration, I/O entry
2. **Use case / shared / pure function** -- business logic
3. **Test titles** (`*.spec.*`) -- behavior documentation, with test count
4. **Test bodies** -- implementation details (Complete tier)
5. **Types / models / schemas** -- supporting (Complete tier)
6. **Config** -- supporting (Complete tier)

Path heuristics: `controller/`, `consumer/` → orchestration. `use-case/`, `shared/` → business logic. `*.spec.*` → tests. `types/`, `models/` → supporting.

## Templates

The roles above rank the files; they never become the entry text.

Each entry says what the reviewer *learns* there, per `SKILL.md`'s qualitative-not-taxonomic rule — the placeholders below are prompts to fill, not labels to paste.

### English -- when the team's PR language is English

```markdown
**Essential** (~{min}min):
1. PR description (business context + decisions)
2. `{controller_file}` — {what the reviewer learns here}
3. `{use_case_file}` — {what the reviewer learns here}
4. Test titles in `{unit_test_file}` ({N} tests)
5. Test titles in `{integration_test_file}` ({N} tests)

**Complete** (+{extra}min):
6. Test bodies (unit)
7. Test bodies (integration)
8. Types/models in `{types_path}`
```

### Portuguese -- the default (PR description "Guia de review")

```markdown
**Essencial** (~{min}min):
1. Descrição do PR (contexto de negócio + decisões)
2. `{controller_file}` — {o que o revisor aprende aqui}
3. `{use_case_file}` — {o que o revisor aprende aqui}
4. Títulos dos testes em `{unit_test_file}` ({N} testes)
5. Títulos dos testes em `{integration_test_file}` ({N} testes)

**Completo** (+{extra}min):
6. Corpo dos testes unitários
7. Corpo dos testes de integração
8. Types/models em `{types_path}`
```

## Label Translations

When generating one variant from the other, use these label mappings:

The first two rows translate `references/pr-template.md`'s `<summary>`; the rest translate the contents below it.

| English | Portuguese |
|---|---|
| Review guide | Guia de review |
| estimated time | tempo estimado |
| Essential | Essencial |
| Complete | Completo |
| PR description | Descrição do PR |
| business context + decisions | contexto de negócio + decisões |
| business logic | regra de negócio |
| Test titles in | Títulos dos testes em |
| tests | testes |
| Test bodies (unit) | Corpo dos testes unitários |
| Test bodies (integration) | Corpo dos testes de integração |
