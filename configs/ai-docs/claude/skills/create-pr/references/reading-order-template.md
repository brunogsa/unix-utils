# Reading Order Template

Used by:

- `code-review-pipeline` — English, in `auto-review.md` output.
- `create-pr` — Portuguese, in PR descriptions as `Guia de review`.

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

### English -- used by `code-review-pipeline` local mode (`auto-review.md`)

```markdown
<details>
<summary><strong>Recommended Reading Order</strong> (estimated: {min}-{max} min)</summary>

**Essential** (~{min}min):
1. PR description (business context + decisions)
2. `{controller_file}` — {brief role}
3. `{use_case_file}` — business logic
4. Test titles in `{unit_test_file}` ({N} tests)
5. Test titles in `{integration_test_file}` ({N} tests)

**Complete** (+{extra}min):
6. Test bodies (unit)
7. Test bodies (integration)
8. Types/models in `{types_path}`

</details>
```

### Portuguese -- used by `create-pr` (PR description "Guia de review")

```markdown
### Guia de review

Tempo estimado: {min}-{max} min

**Essencial** (~{min}min):
1. Descrição do PR (contexto de negócio + decisões)
2. `{controller_file}` — {brief role}
3. `{use_case_file}` — regra de negócio
4. Títulos dos testes em `{unit_test_file}` ({N} testes)
5. Títulos dos testes em `{integration_test_file}` ({N} testes)

**Completo** (+{extra}min):
6. Corpo dos testes unitários
7. Corpo dos testes de integração
8. Types/models em `{types_path}`
```

## Label Translations

When generating one variant from the other, use these label mappings:

| English | Portuguese |
|---|---|
| Recommended Reading Order | Guia de review |
| estimated | Tempo estimado |
| Essential | Essencial |
| Complete | Completo |
| PR description | Descrição do PR |
| business context + decisions | contexto de negócio + decisões |
| business logic | regra de negócio |
| Test titles in | Títulos dos testes em |
| tests | testes |
| Test bodies (unit) | Corpo dos testes unitários |
| Test bodies (integration) | Corpo dos testes de integração |
