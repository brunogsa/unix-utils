<!--

TEMPLATE LEGEND - drop every HTML comment, this one included. Keep headings and fixed PT-BR sentences verbatim, in order. Fill every slot but {EST1} and {EST2}, which the stamp script fills.

- {PR_NUMBER}: the PR number.
- {SHORT_SHA}: the head commit's first 7 characters.
- {COMMIT_URL}: https://github.com/<owner>/<repo>/pull/<number>/commits/<short_sha>.
- {BLOB}: https://github.com/<owner>/<repo>/blob/<short_sha>, every code link's prefix.
- {PATH}, {FILE}, {LINE}: a repo-relative path, its basename, a line at the head commit.
- {STACK_GOAL}, {STACK_GOAL_URL}: the whole stack's business goal, and its own source.
- {BUSINESS_GOAL}: why the business wants this PR - the outcome, not the code.
- {GOAL_URL}: the goal's source - the ticket or its project, or the PR for its body or title.
- {SOURCES_READ}: every source read, each linked.
- {STACK_PR_NUMBER}, {STACK_PR_TITLE}: one stacked PR, base first.
- {PARENT_BRIEF}: the parent PR in one or two sentences.
- {DELIVERABLE}: the technical deliverable.
- {RISK_LEVEL}: Baixo, Médio or Alto; {RISK_EVIDENCE}: one sentence, 200 characters at most.
- {CHANGE_SUMMARY}: what changes; {CHANGE_FACT}: one counted fact.
- {ENTRADA_SAIDA}: HTTP, DB, queue, topic and cache touched, or "nenhum".
- {TERM}, {CODE_NAME}, {DEFINITION}, {DETAIL}: a PT-BR term, its code name, meaning, optional detail.
- {ENTRYPOINT_SENTENCE}: the entry points or their absence; {READ_FROM}: where to start reading.
- {FLAG_NAME}, {FLAG_ON}, {FLAG_OFF}: a flag, and the behavior on and off.
- {TESTS_RUN}, {TEST_SCOPE}, {NOT_RUN}: the metrics run's test count, scope, kinds not run.
- {PATH_TITLE}: input → steps → output; {PATH_CONTRACT}: throws or returns errors.
- {FLOW_NUMBER}, {FLOW_TITLE}: the flow's number in its path, its purpose.
- {FLOW_TEST_COUNT}, {CATEGORY_COUNT}: test cases, it.each expanded.
- {SPEC_FILE}, {SPEC_PATH}, {DESCRIBE_PATH}: a spec's name, path, and describe titles joined by " › ".
- {TEST_TITLE}: a title, verbatim.
- {EACH_REST}, {EACH_TOTAL}, {EACH_LINE}: unlisted cases, all cases, the it.each line.
- {SHARED_STEPS}, {EARLIER_PATH}, {EARLIER_FLOW_NUMBER}: the shared code and the flow testing it.
- {FLOW_INPUT}, {FLOW_OUTPUT}: what enters and leaves the diagram.
- {NODE_ID}, {FUNCTION}, {PARAMS}, {RETURN_TYPE}, {NODE_DOES}: a code node.
- {EXTERNAL_SYSTEM}, {PROTOCOL}, {CALLS}: a system outside the repo.
- {EDGE_LABEL}: what an edge carries, in PT-BR.
- {METRIC}, {VALUE}, {LIMIT}, {UNTESTED_LINES}: a metric over its limit, or untested lines.

-->
# Guia de review: PR #{PR_NUMBER}

Snapshot gerado sobre o commit [`{SHORT_SHA}`]({COMMIT_URL}).

<!-- STACK BLOCK: only when the base branch is not the default branch. Omit it otherwise. Keep one goal line, chosen as for the business goal. -->

**Pilha de PRs.** {STACK_GOAL} ([fonte]({STACK_GOAL_URL}))

**Pilha de PRs (objetivo incerto).** {STACK_GOAL} ([fonte]({STACK_GOAL_URL})). A fonte só sugere esse objetivo, sem declará-lo.

**Pilha de PRs.** Objetivo da pilha não encontrado nas fontes lidas: {SOURCES_READ}.

1. #{STACK_PR_NUMBER} {STACK_PR_TITLE}
2. #{STACK_PR_NUMBER} {STACK_PR_TITLE} ◀ este PR
3. #{STACK_PR_NUMBER} {STACK_PR_TITLE}

<!-- Parent brief: only when it helps situate this PR. -->

{PARENT_BRIEF}

<!-- END STACK BLOCK -->

## ⏱ Camada 1 · o essencial {EST1}

<!-- BUSINESS GOAL: always present; keep one line - the 1st when a source states the goal, the 2nd when one only hints at it, the 3rd when none does. Never invent one. Stacked: only this PR's share. -->

**Objetivo de negócio.** {BUSINESS_GOAL} ([fonte]({GOAL_URL}))

**Objetivo de negócio (incerto).** {BUSINESS_GOAL} ([fonte]({GOAL_URL})). A fonte só sugere esse objetivo, sem declará-lo.

**Objetivo de negócio.** Não encontrado nas fontes lidas: {SOURCES_READ}.

<!-- END BUSINESS GOAL -->

**Entregável.** {DELIVERABLE}

**Risco de mudança: {RISK_LEVEL}.**

<!-- Up to 4 bullets, in order: callers of the new code, changed existing functions, who reaches them, other existing-file changes. -->

- {RISK_EVIDENCE}
  - [{FILE}:{LINE}]({BLOB}/{PATH}#L{LINE})

**O que muda.** {CHANGE_SUMMARY} Os termos em itálico estão definidos no Glossário logo abaixo.

<!-- One bullet per counted fact: files, lines, tests. -->

- {CHANGE_FACT}

- Entrada / Saída: {ENTRADA_SAIDA}.

**Glossário.** As abstrações do código que o resto do guia usa, na ordem em que o fluxo passa por elas.

<!-- Repeat per term, in flow order. The sub-bullet is optional. -->

- *{TERM}* (`{CODE_NAME}`, [{FILE}:{LINE}]({BLOB}/{PATH}#L{LINE})): {DEFINITION}

  - {DETAIL}

**Entrypoints.** {ENTRYPOINT_SENTENCE}

- {READ_FROM} ([{FILE}:{LINE}]({BLOB}/{PATH}#L{LINE})).

## ⏱ Camada 2 · fluxos: comportamento pelos testes, depois o diagrama {EST2}

<!-- FEATURE FLAGS BLOCK: only when the changed code reads a flag; one bullet per flag. -->

Feature flags lidas:

- `{FLAG_NAME}` ([{FILE}:{LINE}]({BLOB}/{PATH}#L{LINE}))
  - Ligada: {FLAG_ON}

  - Desligada: {FLAG_OFF}

<!-- END FEATURE FLAGS BLOCK -->

Cada fluxo abaixo traz primeiro os seus testes, depois o seu diagrama. Cada teste aparece uma vez, no primeiro fluxo que o executa; um fluxo que reusa o mesmo código aponta para lá.

<!-- METRICS LEGEND: only when a diagram node carries a ⚠️. -->

Um ⚠️ numa caixa de diagrama marca uma métrica no limite ou acima dele, ou linhas que nenhum dos {TESTS_RUN} testes de {TEST_SCOPE} executa. {NOT_RUN}

<!-- END METRICS LEGEND -->

<!-- USE-CASE PATH: repeat this ### section per use-case path. -->

### {PATH_TITLE}

{PATH_CONTRACT}

<!-- FLOW: repeat this #### section per flow inside the path. -->

#### Fluxo {FLOW_NUMBER}: {FLOW_TITLE}

<!-- BACK-REFERENCE: only when an earlier flow tested this code; plain text, no anchor link. -->

{SHARED_STEPS} são os mesmos de {EARLIER_PATH} · Fluxo {EARLIER_FLOW_NUMBER}, então os testes de lá valem aqui também. Abaixo, só o que é próprio deste fluxo.

<!-- END BACK-REFERENCE -->

**Testes deste fluxo ({FLOW_TEST_COUNT}).**

<!-- CATEGORY: repeat as ✅ Happy, 🔶 Corner, ❌ Failure, 📝 Logs, in that order, each with its count. Omit one with 0 tests. Keep the blank line after <summary>. -->

<details><summary>✅ Happy ({CATEGORY_COUNT})</summary>

<!-- At most 4 PT-BR key points, before any title. -->

- {KEY_POINT}

<!-- SPEC: repeat this line and its titles per spec file and describe path. -->

📄 [`{SPEC_FILE}`]({BLOB}/{SPEC_PATH}) › {DESCRIBE_PATH}

- `{TEST_TITLE}`

<!-- IT.EACH: past 3 cases, at most 3 sample titles, then the "e mais" line. -->

- `{TEST_TITLE}`

- … e mais {EACH_REST} casos do mesmo `it.each` ({EACH_TOTAL} no total), [no spec]({BLOB}/{SPEC_PATH}#L{EACH_LINE})

</details>

<!-- END CATEGORY -->

<!-- DIAGRAM: one flowchart per flow; split past about 10 nodes. ⚠️ lines only where metrics flag that node. -->

```mermaid
flowchart TD
  input(("{FLOW_INPUT}")):::ioIn
  {NODE_ID}["{FUNCTION}<br/>({PARAMS}) → {RETURN_TYPE}<br/><br/>{NODE_DOES}<br/><br/>⚠️ {FUNCTION}: {METRIC} {VALUE}/{LIMIT}<br/>⚠️ {FUNCTION}: L{UNTESTED_LINES} sem teste"]
  ext{{"{EXTERNAL_SYSTEM} « {PROTOCOL} »<br/><br/>{CALLS}"}}
  out(("{FLOW_OUTPUT}")):::ioOut
  err(("Erro<br/>lançado")):::ioOut

  input -->|"1. {EDGE_LABEL}"| {NODE_ID}
  {NODE_ID} -->|"2. {EDGE_LABEL}"| ext
  {NODE_ID} -->|"3. {EDGE_LABEL}"| out
  {NODE_ID} -.->|"{EDGE_LABEL}"| err
  classDef ioIn fill:#000000,color:#ffffff,stroke:#000000
  classDef ioOut fill:#ffffff,color:#000000,stroke:#000000,stroke-width:2px
```

<!-- END FLOW -->

<!-- END USE-CASE PATH -->
