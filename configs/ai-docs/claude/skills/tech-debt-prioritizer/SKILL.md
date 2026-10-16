---
name: tech-debt-prioritizer
description: >-
  Prioritize, triage, or (re)classify issues in Jira OR Linear against the Integrations team's
  objective rubric (Highest/High/Medium/Low/Lowest), set the priority, and post a PT-BR rationale
  comment. Use for "prioriza", "triar", "refina esses débitos", "set the priority on these",
  "review the priorities of this project", or pasted Jira keys / Linear issue ids or URLs. Covers
  Tech Debt and also Support / Toil / Bug tickets.
compatibility: Jira needs the jira-cli skill; Linear needs the Linear MCP plugin (mcp__plugin_linear_linear__*).
---

# Tech Debt Prioritizer

Turn an issue into a defensible, labeled priority decision, on Jira or Linear. The output a human reviews is threefold: the **priority field**, a **Portuguese comment** explaining the call, and a **triaged marker** (the `pre-refined-ai` label where the platform has it).

## Why this exists

Priority on a debt card is only useful if the next person can audit *why*. A bare "Medium" tells
them nothing; "Medium because the acute failure is already mitigated and what remains is regression
risk in a frequently-touched read path" lets them agree or push back. This skill enforces that the
rationale is written down, and that it argues against the adjacent levels - the boundary calls are
where classification actually goes wrong.

## The rubric

Classify against *objective criteria* (is there active production evidence? is the area frequently
modified? is it being sunset?), not a gut sense of importance - the boundary between levels is
precise and easy to misremember, so always check against the definitions below, never from memory.

Fonte canônica da definição de prioridade de Débito Técnico usada pelo Time de Integrações.
Classifique sempre pelo **critério objetivo**, não pela "sensação" de importância. Se o débito
já causou um incidente mas o incidente **já foi mitigado**, ele deixa de ser iminente - reclassifique
pelo risco residual (normalmente regressão → Medium), não pela gravidade do incidente passado.

### Highest

**Definição:** débito que, se não resolvido, causa incidente iminente. Risco técnico crítico com evidência concreta em produção.

**Critério objetivo:** existe evidência em logs/métricas de que o débito **já está** causando falhas ou dados incorretos, com tendência de agravamento em < 2 sprints.

**Exemplos:**
- Validar dados mandatórios vindos dos legados (dados inválidos já passando e gerando NF com erro - X ocorrências no último mês).
- Pool de conexões do banco sem limite - em pico de volume, o Integrador vai parar.
- Credenciais hardcoded em código - risco de segurança com exposição iminente.

**SLA esperado:** resolução na sprint corrente.
**Benchmark:** Google trata tech debt com risco de outage como P1; Spotify usa "code red" para débitos críticos.

### High

**Definição:** débito que degrada observabilidade, segurança ou confiabilidade. Impede o time de detectar ou reagir a problemas.

**Critério objetivo:** o débito cria ponto cego operacional (alerta que não funciona, log que não existe, dashboard incompleto) ou risco de segurança sem exploração ativa conhecida.

**Exemplos:**
- Novo threshold para alarmes de latência (alarmes ruidosos = time ignora alertas reais).
- Endpoint sem rate limiting - funciona hoje, mas qualquer spike derruba.
- Ausência de tracing distribuído no fluxo de devolução - impossível debugar em produção.

**SLA esperado:** resolução em 1-2 sprints.
**Benchmark:** Google trata observability debt como P2; AWS Well-Architected resolve gaps de "operational excellence" em 1-2 ciclos.

### Medium

**Definição:** débito que reduz a velocidade do time ou aumenta o risco de bugs em futuras entregas.

**Critério objetivo:** aumenta o tempo de desenvolvimento de novas features (> 20% de overhead estimado) **ou** aumenta o risco de regressão em áreas frequentemente modificadas.

**Exemplos:**
- Inclusão de KPIs de negócio no dashboard (time sem visibilidade = decisões no escuro).
- Módulo de mapeamento com 15 if/else aninhados - toda mudança gera bug.
- Testes de integração flaky que passam 70% das vezes - CI não confiável.

**SLA esperado:** resolução em 2-4 sprints.
**Benchmark:** Spotify coloca "health check items" com impacto em velocity no próximo quarter; Google planeja P3 tech debt em OKRs trimestrais.

### Low

**Definição:** débito em área estável, sem impacto na velocidade corrente. Melhoria arquitetural de longo prazo.

**Critério objetivo:** código funciona e é testado, mas não segue o padrão atual do time. Área raramente modificada (< 1 PR/mês).

**Exemplos:**
- Migrar módulo X de callback para async/await (funciona, estilo antigo).
- Consolidar dois clientes HTTP que fazem a mesma coisa em uma abstração única.
- Adicionar tipagem forte em módulo legado que já tem testes cobrindo.

**SLA esperado:** backlog priorizado, resolução oportunística (ex.: quando já estiver mexendo na área).
**Benchmark:** regra do Boy Scout - "leave the campground cleaner than you found it". Resolvido quando há PR na área.

### Lowest

**Definição:** débito em código legado em descomissionamento ou em área que raramente muda e não impacta o time.

**Critério objetivo:** ROI mínimo dado o roadmap. Módulo/sistema com data de sunset definida, ou código sem PR há > 6 meses.

**Exemplos:**
- Refatorar testes de endpoint SAP que será descontinuado em 2 meses.
- Melhorar naming de variáveis em script de migração que já rodou.
- Atualizar dependência em serviço legado que será substituído.

## Applying the rubric to non-debt tickets (Support / Toil / Bug)

Use the same criteria, reading "o débito" as "o problema que o ticket descreve". No new criteria beyond these:

- Active production failure or incorrect data now → Highest.
- Unmonitored failure, reliability or security risk, or a costly manual workaround → High.
- Slows the team or is recurring toil → Medium.
- One-off request with no stated deadline or impact, in a stable area → Low.
- Obsolete system or no activity for more than 6 months → Lowest, and raise a `Dúvida` asking whether to cancel the ticket instead.

## The one judgment call that trips people up

A debt that **already caused an incident** feels like Highest. But Highest requires the failure to
be *active and worsening*. If a fix has already mitigated the incident, the imminent-failure
criterion no longer holds - reclassify by the **residual** risk. Usually that residual is "this
coupling/pattern will bite again on the next change here", which is Medium's regression criterion,
not Highest. State this explicitly in the comment when it applies, because it's the most common
place a reviewer will disagree.

## Choosing the platform

Decide by evidence, never by key shape: `ITGD-3160` (Jira) and `CDPI-399` (Linear) look the same.

- A `linear.app` URL, or the user naming Linear → Linear.
- An `*.atlassian.net` URL, or the user naming Jira → Jira.
- A key whose team prefix was already resolved earlier in the session → that platform.
- Otherwise, ask the user which platform.

Then read only the matching reference file: `references/jira.md` or `references/linear.md`. Only one is needed per run, so never open the other.

## Workflow

Assume one or more issue keys or ids. Each step below names what to do; the platform reference holds the exact call. For each issue:

1. **Read the issue and its comments.** Ground the rationale in what the issue actually says, not a guess. Use the platform reference for the exact call.

2. **Classify** against the rubric above. Pick the level whose *objective criterion* the issue meets. Name the adjacent level(s) you're ruling out - you'll justify against them.

3. **Confirm the priority values** with the target platform before writing, since names and numeric codes differ per platform. The platform reference holds the exact call and the level mapping.

4. **Set the priority.** The platform reference holds the exact call.

5. **Post the rationale comment (Portuguese)** using the structure below. The platform reference holds the exact call and format.

6. **Mark as triaged**, last, so the marker means "triaged with justification". The platform reference holds the exact call and how to preserve existing labels.

7. **Verify** priority and marker landed, and report each issue's final state back to the user.

When several issues are in play, do them in one pass and present a table (key → current → proposed → one-line reason) so the user can sanity-check the whole batch at a glance.

In batch mode, add one step before any write (steps 4-6): present the proposals, changes first and unchanged issues listed compactly, and write only what the user approves.

## Comment structure

Portuguese, brief but complete. The shape that makes it auditable:

```markdown
## Prioridade: <Nível>

**Classificação:** <Nível> - <critério objetivo em uma linha>.

**Por que não <nível acima>:** <por que o critério do nível superior não é atendido>.

**Por que não <nível abaixo>:** <por que este débito é mais grave que o nível inferior>.

**Por que <Nível> (critério objetivo):** <a evidência concreta do card que ancora a escolha>. SLA esperado: <do rubric>.

_Referência: critérios de prioridade do Time de Integrações (pré-refino AI)._
```

The heading shows the rubric level, plus the platform value when it differs, e.g. `## Prioridade: Lowest (Linear: Low)`.

You don't always need both "por que não" blocks - include the boundary(ies) that are genuinely
close. A Lowest call rarely needs "por que não Highest". Argue the neighbors that a reviewer might
actually propose instead.

## Notes

- **Don't invent evidence.** If the card doesn't state occurrence counts or production signals, say
  the classification is based on the described risk, and flag the missing evidence as a `Dúvida` for
  the user rather than fabricating a number.
- Platform-specific notes live in the platform reference.

[`assets/flowchart.md`](assets/flowchart.md) is a human-facing overview of this flow - do NOT load it.
