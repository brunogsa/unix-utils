# Exemplos inventados

Achados de exemplo para calibrar o tom, as faixas e os extras de domínio.

- **Regra:** nunca copie um exemplo do documento revisado para um relatório; use estes só como referência de tom e de cobertura.

## Tom

- **Escreva para alguém de produto:** a primeira frase de cada campo não tem jargão; nome de campo, tipo e código vão num sub-bullet.

- **Lacuna vista de quem consome:** "o que a consulta devolve quando a nota não existe?", e não "faltou documentar os erros".

- **O custo de deixar como está, em uma frase:** o que o nosso time não consegue fazer, ou o que pode sair errado, sem impor a solução.

- **Em Bloqueia, nomeie a etapa travada:** "não conseguimos ligar cada nota aos seus itens", e não só "isso bloqueia a integração".

- **Exemplo só quando precisa:** ele mostra o custo de deixar a lacuna como está, nunca repete a lacuna.

  - Ruim: "Exemplo: o status vem como um código interno." Bom: "Uma nota cancelada segue como aprovada, e o pedido é entregue sem cobrança."

- **Caso concreto:** cite o campo, a aba e o valor que não fecha, no lugar de um "há inconsistências".

- **Cobertura:** cada seção do documento termina em algo que quem consome precisa saber para implementar.

## Resumo executivo de exemplo

- **Contexto:** o time de faturamento descreve, numa planilha, 3 consultas que vai abrir para o nosso time conferir as notas fiscais emitidas.

- **Demandas:** "Notas por CNPJ" lista as notas de um cliente; "Itens da nota" traz os produtos de cada nota; "Status do pedido" diz em que etapa o pedido está.

- **Veredito:** ainda não dá para começar: 4 definições travam a conferência das notas.

- **Glossário:** "fuso horário" é a região do horário de uma data, como Brasília ou UTC; "paginação" é devolver uma lista longa em partes.

## Achados de um contrato de notas fiscais

Um time de faturamento expõe 3 consultas numa planilha: "Notas por CNPJ", "Itens da nota" e "Status do pedido", mais uma aba "exemplo".

Formato: faixa e título; depois o que falta, o que bloqueia (ou o custo de deixar como está), o exemplo quando ele ajuda, e onde.

- **Bloqueia:** "Um mesmo dado aparece com nomes diferentes entre as abas".

  - O que falta: um nome único para a chave da nota em todas as abas. O detalhe: `accessKey` numa aba e `invoiceKey` na outra.

  - O que bloqueia: ligar cada nota aos seus itens, o primeiro passo da conferência.

  - Onde: Notas por CNPJ, Itens da nota.

- **Bloqueia:** "A data de alteração não tem hora, e nenhuma data tem fuso".

  - O que falta: a hora da alteração e o fuso horário das datas. O detalhe: `updatedAt` traz só a data, e o exemplo mostra o número serial `45352`.

  - O que bloqueia: buscar só o que mudou desde a última leitura.

  - Exemplo: uma nota alterada às 23h59 fica fora da leitura do dia seguinte, e a alteração nunca chega até nós.

  - Onde: Notas por CNPJ, Itens da nota, exemplo.

- **Bloqueia:** "Nenhuma consulta diz o que devolve quando falha".

  - O que falta: a resposta de cada consulta quando algo dá errado. O detalhe: não diz se uma nota que não existe devolve 404 ou 200 com lista vazia.

  - O que bloqueia: decidir quando tentar de novo e quando avisar quem pediu a nota.

  - Exemplo: o nosso sistema tenta de novo, a cada minuto, buscar uma nota que nunca vai existir, ou desiste de uma que só estava fora do ar.

  - Onde: Notas por CNPJ, Itens da nota, Status do pedido.

- **Bloqueia:** "A consulta de notas por CNPJ devolve tudo de uma vez".

  - O que falta: paginação, ou um limite de notas por resposta.

  - O que bloqueia: consultar um cliente com 10 mil notas, cada uma com o PDF, cuja resposta passa do tempo limite e não traz nenhuma.

  - Onde: Notas por CNPJ.

- **Gera dúvida:** "Status sem a lista de valores".

  - O que falta: a lista fechada dos status possíveis. O detalhe: o status traz um código interno do sistema de origem.

  - Se não for resolvido: cada time interpreta o código de um jeito, e uma nota cancelada pode seguir como aprovada.

  - Onde: Status do pedido.

- **Gera dúvida:** "Casas decimais dos valores em aberto".

  - O que falta: quantas casas decimais têm os valores em dinheiro. O detalhe: "a definir" numa aba e 2 casas na outra.

  - Se não for resolvido: totais que não batem entre os sistemas, descobertos só na conferência.

  - Exemplo: R$ 10,005 arredondado de dois jeitos dá um centavo por item; em 10 mil itens, R$ 100 que ninguém sabe explicar.

  - Onde: Notas por CNPJ, Itens da nota.

- **Gera dúvida:** "A aba exemplo traz valores que não fecham".

  - O que falta: um exemplo coerente. O detalhe: o total da nota (150.00) difere da soma dos itens (140.00).

  - Se não for resolvido: os testes comparam contra um valor que pode estar errado.

  - Onde: exemplo.

- **Boa prática:** "Nomes de campo fora do padrão".

  - O que falta: um padrão único de escrita para os nomes de campo. O detalhe: `itemCategory` numa aba e `items[].itemcategory` na outra.

  - Se não for resolvido: erros pequenos e repetidos, achados só nos testes.

  - Onde: Notas por CNPJ, Itens da nota.

## Verificações fiscais

Extras de domínio para contratos de nota fiscal brasileira.

- **Chave de acesso da NF-e:** formato e tamanho únicos em todas as abas, com o padrão `^[0-9]{6}[A-Z0-9]{12}[0-9]{26}$`.

- **CNPJ:** um tamanho e um formato por dado, com `^[A-Z0-9]{12}[0-9]{2}$`, que aceita o CNPJ alfanumérico.

- **CFOP:** código de 4 dígitos, como `type: string` com `pattern: '^[0-9]{4}$'`.

- **Valores em dinheiro:** casas decimais definidas, e total da nota coerente com a soma dos itens.

- **Data de emissão da nota:** campo definido na aba que o devolve, com fuso.

- **PDF da nota (DANFE em Base64):** paginação ou limite, pois cada nota carrega o PDF inteiro.
