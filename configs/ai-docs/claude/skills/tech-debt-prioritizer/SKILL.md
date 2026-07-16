---
name: tech-debt-prioritizer
description: >-
  Classify and set the priority of Jira Tech Debt cards using the Integrations team's objective
  rubric (Highest/High/Medium/Low/Lowest), then post a Portuguese rationale comment and apply a
  label. Use this whenever the user asks to prioritize, triage, (re)classify, or "refine" one or
  more Tech Debt tickets against the team's definition — even if they only say "set the priority on
  these debts", "refina esses débitos", or paste tickets and ask which priority they should be.
  Also use when a card's priority needs justification a reviewer can audit.
compatibility: Requires the jira-cli skill (Jira REST API v3 helpers) and its env vars.
---

# Tech Debt Prioritizer

Turn a Tech Debt Jira card into a defensible, labeled priority decision. The output a human
reviews is threefold: the **priority field**, a **Portuguese comment** explaining the call, and a
**label** marking it as triaged.

## Why this exists

Priority on a debt card is only useful if the next person can audit *why*. A bare "Medium" tells
them nothing; "Medium because the acute failure is already mitigated and what remains is regression
risk in a frequently-touched read path" lets them agree or push back. This skill enforces that the
rationale is written down, and that it argues against the adjacent levels — the boundary calls are
where classification actually goes wrong.

## The rubric

Classify against *objective criteria* (is there active production evidence? is the area frequently
modified? is it being sunset?), not a gut sense of importance — the boundary between levels is
precise and easy to misremember, so always check against the definitions below, never from memory.

Fonte canônica da definição de prioridade de Débito Técnico usada pelo Time de Integrações.
Classifique sempre pelo **critério objetivo**, não pela "sensação" de importância. Se o débito
já causou um incidente mas o incidente **já foi mitigado**, ele deixa de ser iminente — reclassifique
pelo risco residual (normalmente regressão → Medium), não pela gravidade do incidente passado.

### Highest

**Definição:** débito que, se não resolvido, causa incidente iminente. Risco técnico crítico com evidência concreta em produção.

**Critério objetivo:** existe evidência em logs/métricas de que o débito **já está** causando falhas ou dados incorretos, com tendência de agravamento em < 2 sprints.

**Exemplos:**
- Validar dados mandatórios vindos dos legados (dados inválidos já passando e gerando NF com erro — X ocorrências no último mês).
- Pool de conexões do banco sem limite — em pico de volume, o Integrador vai parar.
- Credenciais hardcoded em código — risco de segurança com exposição iminente.

**SLA esperado:** resolução na sprint corrente.
**Benchmark:** Google trata tech debt com risco de outage como P1; Spotify usa "code red" para débitos críticos.

### High

**Definição:** débito que degrada observabilidade, segurança ou confiabilidade. Impede o time de detectar ou reagir a problemas.

**Critério objetivo:** o débito cria ponto cego operacional (alerta que não funciona, log que não existe, dashboard incompleto) ou risco de segurança sem exploração ativa conhecida.

**Exemplos:**
- Novo threshold para alarmes de latência (alarmes ruidosos = time ignora alertas reais).
- Endpoint sem rate limiting — funciona hoje, mas qualquer spike derruba.
- Ausência de tracing distribuído no fluxo de devolução — impossível debugar em produção.

**SLA esperado:** resolução em 1-2 sprints.
**Benchmark:** Google trata observability debt como P2; AWS Well-Architected resolve gaps de "operational excellence" em 1-2 ciclos.

### Medium

**Definição:** débito que reduz a velocidade do time ou aumenta o risco de bugs em futuras entregas.

**Critério objetivo:** aumenta o tempo de desenvolvimento de novas features (> 20% de overhead estimado) **ou** aumenta o risco de regressão em áreas frequentemente modificadas.

**Exemplos:**
- Inclusão de KPIs de negócio no dashboard (time sem visibilidade = decisões no escuro).
- Módulo de mapeamento com 15 if/else aninhados — toda mudança gera bug.
- Testes de integração flaky que passam 70% das vezes — CI não confiável.

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
**Benchmark:** regra do Boy Scout — "leave the campground cleaner than you found it". Resolvido quando há PR na área.

### Lowest

**Definição:** débito em código legado em descomissionamento ou em área que raramente muda e não impacta o time.

**Critério objetivo:** ROI mínimo dado o roadmap. Módulo/sistema com data de sunset definida, ou código sem PR há > 6 meses.

**Exemplos:**
- Refatorar testes de endpoint SAP que será descontinuado em 2 meses.
- Melhorar naming de variáveis em script de migração que já rodou.
- Atualizar dependência em serviço legado que será substituído.

## The one judgment call that trips people up

A debt that **already caused an incident** feels like Highest. But Highest requires the failure to
be *active and worsening*. If a fix has already mitigated the incident, the imminent-failure
criterion no longer holds — reclassify by the **residual** risk. Usually that residual is "this
coupling/pattern will bite again on the next change here", which is Medium's regression criterion,
not Highest. State this explicitly in the comment when it applies, because it's the most common
place a reviewer will disagree.

## Workflow

Assume one or more Jira card keys (e.g. `ITGD-3160`). For each card:

1. **Read the card.** Pull its summary + description so the rationale is grounded in what the card
   actually says, not a guess. Use the jira-cli skill:
   ```bash
   source ~/.claude/skills/jira-cli/scripts/jira-utilities.sh
   get-jira-issue ITGD-3160 "summary,description,priority,labels"
   ```

2. **Classify** against the rubric above. Pick the level whose *objective criterion*
   the card meets. Identify the adjacent level(s) you're ruling out — you'll justify against them.

3. **Confirm the field values with the target Jira** before writing (priority names and the label
   spelling can differ per instance):
   ```bash
   jira-api-request GET "/rest/api/3/priority"   # confirm Highest/High/Medium/Low/Lowest exist
   ```

4. **Set the priority:**
   ```bash
   update-jira-issue ITGD-3160 '{"priority":{"name":"Medium"}}'
   ```

5. **Post the rationale comment (Portuguese).** Write the comment to a markdown file, convert to
   ADF (Jira v3 needs ADF, not markdown), and POST it. See the comment structure below.
   ```bash
   adf=$(md-to-adf /tmp/comment.md)
   body=$(python3 -c "import sys,json; print(json.dumps({'body': json.load(open(sys.argv[1]))}))" <(printf '%s' "$adf"))
   jira-api-request POST "/rest/api/3/issue/ITGD-3160/comment" "$body"
   ```

6. **Add the label last** (the user's convention is to label *after* the rationale is recorded, so
   the label means "triaged with justification"). Default label: `pre-refined-ai`. Preserve existing
   labels — read them in step 1 and re-send the full list, since `update` replaces the array:
   ```bash
   update-jira-issue ITGD-3160 '{"labels":["kit1:1","pre-refined-ai"]}'
   ```

7. **Verify** priority + labels landed, and report each card's final state back to the user.

When several cards are in play, do them in one pass and present a short table (key → priority →
one-line reason) so the user can sanity-check the whole batch at a glance.

## Comment structure

Portuguese, brief but complete. The shape that makes it auditable:

```markdown
## Prioridade: <Nível>

**Classificação:** <Nível> — <critério objetivo em uma linha>.

**Por que não <nível acima>:** <por que o critério do nível superior não é atendido>.

**Por que não <nível abaixo>:** <por que este débito é mais grave que o nível inferior>.

**Por que <Nível> (critério objetivo):** <a evidência concreta do card que ancora a escolha>. SLA esperado: <do rubric>.

_Referência: definição de prioridade de Débito Técnico (pré-refino AI)._
```

You don't always need both "por que não" blocks — include the boundary(ies) that are genuinely
close. A Lowest call rarely needs "por que não Highest". Argue the neighbors that a reviewer might
actually propose instead.

## Notes

- **Labels are literal.** This Jira accepts colons (`kit1:1`); other instances may reject colons or
  spaces. If `update` errors on the label, report it and fall back to a hyphenated form rather than
  silently dropping it.
- **Spikes need a due date** in this project (Tech Spike / Functional Spike). Tech Debt does not —
  but if you ever set priority on a Spike here and creation/edit fails on `duedate`, that's why.
- **Don't invent evidence.** If the card doesn't state occurrence counts or production signals, say
  the classification is based on the described risk, and flag the missing evidence as a `Dúvida` for
  the user rather than fabricating a number.
