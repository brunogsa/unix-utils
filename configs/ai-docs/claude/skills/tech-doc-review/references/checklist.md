# Checklist de revisão de documento técnico

Cada item tem um nome estável.
Usam exatamente estes nomes: a correspondência com o relatório anterior (item do checklist mais lugar), a linha "Item do checklist" de cada achado e o prompt de verificação.

## Como aplicar

- Confira todos os itens abaixo. Quando o domínio do documento pede, some verificações específicas dele (por exemplo, um padrão de identificador próprio do setor).
  - Um achado específico de domínio é opcional: a verificação de olhos novos nem o exige nem o rejeita.

- Um item que não se aplica ao documento não gera achado. Diga ao engenheiro, no chat e fora do relatório, quais itens julgou não aplicáveis e por quê.
  - Exemplo: um documento em que toda operação é de leitura não gera achado de `Idempotência em escritas`.

- Agrupe antes de ranquear: duas lacunas formam um achado só quando têm o mesmo item e o mesmo pedido de correção. O achado nomeia todos os lugares.
  - Lacunas do mesmo item com correções diferentes são achados separados.
  - Um grupo assume a faixa mais alta entre os seus lugares.

- Regra do marcador aberto: todos os marcadores abertos do documento entram em um único achado, com um lugar por marcador.
  - Um campo que traz só um marcador ("a definir") não é vazio: ele entra neste achado, e não no de aba vazia.

- Regra da aba ou seção vazia: uma aba ou seção legível sem nenhuma linha de dados abaixo do cabeçalho vira um achado que a nomeia, e a revisão continua nas demais.
  - Vazia inclui só cabeçalho e só espaços em branco.

- Um contrato de referência, quando existe, fornece o exemplo dos achados que ele cobre.

## Itens para qualquer documento

1. **Caminho feliz** - endpoints, métodos, requisição e resposta.
2. **Caminhos de erro** - formato do corpo de erro e códigos 4xx (por exemplo 404 contra 500), não só 5xx.
   - A condição por trás de cada código e quais erros admitem nova tentativa.
3. **Autenticação**
4. **Ambientes** - hosts, caminhos base, URL do token e um ambiente de teste ou homologação.
5. **Filtros e parâmetros** - obrigatório ou opcional, tipos, restrições, comportamento com filtro vazio e como os filtros se combinam (E ou OU).
6. **Enumerações** - valores permitidos no lugar de texto livre.
7. **Tipos dos campos** - todo campo, de entrada e de saída, tem tipo JSON (string, number, integer, boolean, object, array) com suas restrições (tamanho, padrão, faixa).
   - Nunca um tipo próprio de fornecedor, nem texto no lugar de número ou booleano.

8. **Datas e fuso** - formato explícito e fuso explícito (por exemplo, ISO 8601 em UTC com `Z`).
9. **Precisão decimal** - número de casas explícito.
10. **Nomes de campos** - nomes óbvios, ou com descrição e exemplo de uso.
11. **Paginação** - listas e lotes paginados, com paginação estável sob alterações simultâneas.
12. **Idempotência em escritas** - escritas e atualizações dizem o que acontece quando o mesmo pedido chega duas vezes.
13. **Consistência interna** - um nome, um tamanho e um tipo por campo entre seções e entre consulta e resposta.
   - Nenhum título de seção ou aba que a descreva errado.
   - Nenhuma regra que contradiga outra.
14. **Limite de requisições** - `429` e `Retry-After`.
15. **Marcadores abertos** - "a definir", "a ser customizado", "faz sentido?" e similares, sem diferenciar maiúsculas de minúsculas, todos em um achado só.
16. **Aba ou seção vazia** - ver a regra acima.

## Itens só para evento

Para um evento (por exemplo, AsyncAPI), os 3 itens abaixo substituem os itens só de HTTP.

- Os itens só de HTTP são `Caminho feliz` na parte de endpoints e métodos, os códigos de status de `Caminhos de erro` e `Limite de requisições`.

- Os itens compartilhados (tipos, datas, enumerações, nomes de campos, exemplos, idempotência) continuam valendo.

- Nenhum achado só de HTTP é levantado.

17. **Garantia de entrega** - por exemplo, ao menos uma vez, o que obriga quem consome a descartar repetições.
18. **Ordem dos eventos** - se os eventos de uma mesma entidade chegam em ordem e qual chave os ordena.
19. **Versionamento do evento** - como o esquema evolui e como quem consome distingue versões.

## Exemplos genéricos para os achados

Exemplos inventados, só para mostrar o tom e o nível de detalhe. Não os copie para um relatório.

- Lacuna: "O documento não diz o que a consulta de uma reserva devolve quando ela não existe."
  - Por que isso importa: "Sem isso, quem consome não distingue 'a reserva não existe' de 'o sistema falhou', e não sabe se deve tentar de novo."

- Lacuna: "A data de devolução aparece como `12/03/2027`."
  - Exemplo: "`2027-03-12T00:00:00Z` deixa claro o formato e o fuso."
