# Rubrica de prioridade — Débito Técnico

Fonte canônica da definição de prioridade de Débito Técnico usada pelo Time de Integrações.
Classifique sempre pelo **critério objetivo**, não pela "sensação" de importância. Se o débito
já causou um incidente mas o incidente **já foi mitigado**, ele deixa de ser iminente — reclassifique
pelo risco residual (normalmente regressão → Medium), não pela gravidade do incidente passado.

## Highest

**Definição:** débito que, se não resolvido, causa incidente iminente. Risco técnico crítico com evidência concreta em produção.

**Critério objetivo:** existe evidência em logs/métricas de que o débito **já está** causando falhas ou dados incorretos, com tendência de agravamento em < 2 sprints.

**Exemplos:**
- Validar dados mandatórios vindos dos legados (dados inválidos já passando e gerando NF com erro — X ocorrências no último mês).
- Pool de conexões do banco sem limite — em pico de volume, o Integrador vai parar.
- Credenciais hardcoded em código — risco de segurança com exposição iminente.

**SLA esperado:** resolução na sprint corrente.
**Benchmark:** Google trata tech debt com risco de outage como P1; Spotify usa "code red" para débitos críticos.

## High

**Definição:** débito que degrada observabilidade, segurança ou confiabilidade. Impede o time de detectar ou reagir a problemas.

**Critério objetivo:** o débito cria ponto cego operacional (alerta que não funciona, log que não existe, dashboard incompleto) ou risco de segurança sem exploração ativa conhecida.

**Exemplos:**
- Novo threshold para alarmes de latência (alarmes ruidosos = time ignora alertas reais).
- Endpoint sem rate limiting — funciona hoje, mas qualquer spike derruba.
- Ausência de tracing distribuído no fluxo de devolução — impossível debugar em produção.

**SLA esperado:** resolução em 1-2 sprints.
**Benchmark:** Google trata observability debt como P2; AWS Well-Architected resolve gaps de "operational excellence" em 1-2 ciclos.

## Medium

**Definição:** débito que reduz a velocidade do time ou aumenta o risco de bugs em futuras entregas.

**Critério objetivo:** aumenta o tempo de desenvolvimento de novas features (> 20% de overhead estimado) **ou** aumenta o risco de regressão em áreas frequentemente modificadas.

**Exemplos:**
- Inclusão de KPIs de negócio no dashboard (time sem visibilidade = decisões no escuro).
- Módulo de mapeamento com 15 if/else aninhados — toda mudança gera bug.
- Testes de integração flaky que passam 70% das vezes — CI não confiável.

**SLA esperado:** resolução em 2-4 sprints.
**Benchmark:** Spotify coloca "health check items" com impacto em velocity no próximo quarter; Google planeja P3 tech debt em OKRs trimestrais.

## Low

**Definição:** débito em área estável, sem impacto na velocidade corrente. Melhoria arquitetural de longo prazo.

**Critério objetivo:** código funciona e é testado, mas não segue o padrão atual do time. Área raramente modificada (< 1 PR/mês).

**Exemplos:**
- Migrar módulo X de callback para async/await (funciona, estilo antigo).
- Consolidar dois clientes HTTP que fazem a mesma coisa em uma abstração única.
- Adicionar tipagem forte em módulo legado que já tem testes cobrindo.

**SLA esperado:** backlog priorizado, resolução oportunística (ex.: quando já estiver mexendo na área).
**Benchmark:** regra do Boy Scout — "leave the campground cleaner than you found it". Resolvido quando há PR na área.

## Lowest

**Definição:** débito em código legado em descomissionamento ou em área que raramente muda e não impacta o time.

**Critério objetivo:** ROI mínimo dado o roadmap. Módulo/sistema com data de sunset definida, ou código sem PR há > 6 meses.

**Exemplos:**
- Refatorar testes de endpoint SAP que será descontinuado em 2 meses.
- Melhorar naming de variáveis em script de migração que já rodou.
- Atualizar dependência em serviço legado que será substituído.
