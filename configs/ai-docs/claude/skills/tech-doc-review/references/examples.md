# Exemplos inventados

Achados de exemplo para calibrar o tom, as faixas e os extras de domínio. Todos são inventados: o contrato, os campos e os valores não existem.

- **Regra:** nunca copie um exemplo do documento revisado para um relatório; use estes só como referência de tom e de cobertura.

## Tom

- **Escreva para alguém de produto:** a primeira frase de cada campo não tem jargão; nome de campo, tipo e código vão num sub-bullet.

- **Lacuna vista de quem consome:** "o que a consulta devolve quando a nota não existe?", e não "faltou documentar os erros".

- **Exemplo que mostra o problema acontecendo:** "uma nota que não existe e um sistema fora do ar recebem a mesma resposta".

- **O custo de deixar como está, em uma frase:** o que o nosso time não consegue fazer, ou o que pode sair errado, sem impor a solução.

- **Em Bloqueia, nomeie a etapa travada:** "não conseguimos ligar cada nota aos seus itens", e não só "isso bloqueia a integração".

- **Caso concreto:** cite o campo, a aba e o valor que não fecha, no lugar de um "há inconsistências".

- **Cobertura:** cada seção do documento termina em algo que quem consome precisa saber para implementar.

## Achados de um contrato de notas fiscais

Um time de faturamento expõe 3 consultas numa planilha: "Notas por CNPJ", "Itens da nota" e "Status do pedido", mais uma aba "exemplo".

Formato: faixa e título; depois o que falta, o exemplo, o que bloqueia (ou o custo de deixar como está), o item e onde.

- **Bloqueia:** "Um mesmo dado aparece com nomes diferentes entre as abas".

  - O que falta: um nome único para a chave da nota em todas as abas. O detalhe: `accessKey` numa aba e `invoiceKey` na outra.

  - Exemplo: o nosso time lê a nota numa aba e não acha os itens dela na outra, porque procura pelo nome errado.

  - O que bloqueia: ligar cada nota aos seus itens, o primeiro passo da conferência.

  - Item: Consistência interna. Onde: Notas por CNPJ, Itens da nota.

- **Bloqueia:** "A data de alteração não tem hora, e nenhuma data tem fuso".

  - O que falta: a hora da alteração e o fuso horário das datas. O detalhe: `updatedAt` traz só a data, e o exemplo mostra o número serial `45352`.

  - Exemplo: uma nota alterada às 23h em Brasília aparece como do dia seguinte para quem lê em UTC.

  - O que bloqueia: buscar só o que mudou desde a última leitura; sem a hora, toda leitura traz o dia inteiro de novo.

  - Item: Datas e fuso. Onde: Notas por CNPJ, Itens da nota, exemplo.

- **Bloqueia:** "Nenhuma consulta diz o que devolve quando falha".

  - O que falta: a resposta de cada consulta quando algo dá errado. O detalhe: não diz se uma nota que não existe devolve 404 ou 200 com lista vazia.

  - Exemplo: uma nota que não existe e um sistema fora do ar recebem a mesma resposta.

  - O que bloqueia: decidir quando tentar de novo e quando avisar quem pediu a nota.

  - Item: Caminhos de erro. Onde: Notas por CNPJ, Itens da nota, Status do pedido.

- **Bloqueia:** "A consulta de notas por CNPJ devolve tudo de uma vez".

  - O que falta: paginação (devolver a lista em partes, página a página).

  - Exemplo: um emissor com 10 mil notas devolve todas numa resposta só, cada uma com o PDF inteiro.

  - O que bloqueia: consultar os emissores grandes, cuja resposta passa do tempo limite.

  - Item: Paginação. Onde: Notas por CNPJ.

- **Gera dúvida:** "Status sem a lista de valores".

  - O que falta: a lista fechada dos status possíveis. O detalhe: o status traz um código interno do sistema de origem.

  - Exemplo: chega o status `Z7`, e o nosso time não sabe se a nota foi cancelada ou aprovada.

  - Se não for resolvido: cada time interpreta o código de um jeito, e uma nota cancelada pode seguir como aprovada.

  - Item: Enumerações. Onde: Status do pedido.

- **Gera dúvida:** "Casas decimais dos valores em aberto".

  - O que falta: quantas casas decimais têm os valores em dinheiro. O detalhe: "a definir" numa aba e 2 casas na outra.

  - Exemplo: R$ 10,005 arredondado de dois jeitos dá um centavo de diferença por item.

  - Se não for resolvido: totais que não batem entre os sistemas, descobertos só na conferência.

  - Item: Precisão decimal. Onde: Notas por CNPJ, Itens da nota.

- **Gera dúvida:** "A aba exemplo traz valores que não fecham".

  - O que falta: um exemplo coerente. O detalhe: o total da nota (150.00) difere da soma dos itens (140.00).

  - Exemplo: o nosso time não sabe se a diferença de 10.00 é frete, imposto ou erro.

  - Se não for resolvido: os testes comparam contra um valor que pode estar errado.

  - Item: Consistência interna. Onde: exemplo.

- **Boa prática:** "Nomes de campo fora do padrão".

  - O que falta: um padrão único de escrita para os nomes de campo. O detalhe: `itemCategory` numa aba e `items[].itemcategory` na outra.

  - Exemplo: quem copia o nome de uma aba para a outra recebe o campo vazio.

  - Se não for resolvido: erros pequenos e repetidos, achados só nos testes.

  - Item: Nomes de campos. Onde: Notas por CNPJ, Itens da nota.

## Verificações fiscais

Extras de domínio para contratos de nota fiscal brasileira.

- **Chave de acesso da NF-e:** formato e tamanho únicos em todas as abas, com o padrão `^[0-9]{6}[A-Z0-9]{12}[0-9]{26}$`.

- **CNPJ:** um tamanho e um formato por dado, com `^[A-Z0-9]{12}[0-9]{2}$`, que aceita o CNPJ alfanumérico.

- **CFOP:** código de 4 dígitos, como `type: string` com `pattern: '^[0-9]{4}$'`.

- **Valores em dinheiro:** casas decimais definidas, e total da nota coerente com a soma dos itens.

- **Data de emissão da nota:** campo definido na aba que o devolve, com fuso.

- **PDF da nota (DANFE em Base64):** paginação ou limite, pois cada nota carrega o PDF inteiro.
