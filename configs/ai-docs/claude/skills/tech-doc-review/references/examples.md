# Exemplos inventados

Achados de exemplo para calibrar o tom, as faixas e os extras de domínio. Todos são inventados: o contrato, os campos e os valores não existem.

- **Regra:** nunca copie um exemplo do documento revisado para um relatório; use estes só como referência de tom e de cobertura.

## Tom

- **Lacuna vista de quem consome:** "o que a consulta devolve quando a nota não existe?", e não "faltou documentar os erros".

- **Por que isso importa, em uma frase:** diga o que o time consumidor não consegue fazer, sem impor a solução.

- **Caso concreto:** cite o campo, a aba e o valor que não fecha, no lugar de um "há inconsistências".

- **Cobertura:** cada seção do documento termina em algo que quem consome precisa saber para implementar.

## Achados de um contrato de notas fiscais

Um time de faturamento expõe 3 consultas numa planilha: "Notas por CNPJ", "Itens da nota" e "Status do pedido", mais uma aba "exemplo".

Formato: faixa e título; depois item do checklist, onde e caso concreto.

- **Bloqueia:** "Um mesmo dado aparece com nomes diferentes entre as abas".

  - Item: Consistência interna. Onde: Notas por CNPJ, Itens da nota.

  - Caso concreto: a chave de acesso da nota é `accessKey` numa aba e `invoiceKey` na outra.

- **Bloqueia:** "A data de alteração não tem hora, e nenhuma data tem fuso".

  - Item: Datas e fuso. Onde: Notas por CNPJ, Itens da nota, exemplo.

  - Caso concreto: `updatedAt` traz só a data, e o exemplo mostra uma data como número serial de planilha (`45352`).

- **Bloqueia:** "Nenhuma consulta diz o que devolve quando falha".

  - Item: Caminhos de erro. Onde: Notas por CNPJ, Itens da nota, Status do pedido.

  - Caso concreto: não diz se uma nota que não existe devolve 404 ou 200 com lista vazia.

- **Bloqueia:** "A consulta de notas por CNPJ não é paginada".

  - Item: Paginação. Onde: Notas por CNPJ.

  - Caso concreto: o filtro só por CNPJ pode devolver todas as notas do emissor, cada uma com o PDF em Base64.

- **Gera dúvida:** "Status sem a lista de valores".

  - Item: Enumerações. Onde: Status do pedido.

  - Caso concreto: o status traz um código interno do sistema de origem, sem a lista fechada de valores.

- **Gera dúvida:** "Casas decimais dos valores em aberto".

  - Item: Precisão decimal. Onde: Notas por CNPJ, Itens da nota.

  - Caso concreto: o tamanho dos valores em dinheiro está "a definir" numa aba e tem 2 casas na outra.

- **Gera dúvida:** "A aba exemplo traz valores que não fecham".

  - Item: Consistência interna. Onde: exemplo.

  - Caso concreto: o total da nota (150.00) difere da soma dos itens (140.00).

- **Boa prática:** "Nomes de campo fora do padrão".

  - Item: Nomes de campos. Onde: Notas por CNPJ, Itens da nota.

  - Caso concreto: `itemCategory` numa aba e `items[].itemcategory` na outra.

## Verificações fiscais

Extras de domínio para contratos de nota fiscal brasileira.

- **Chave de acesso da NF-e:** formato e tamanho únicos em todas as abas, com o padrão `^[0-9]{6}[A-Z0-9]{12}[0-9]{26}$`.

- **CNPJ:** um tamanho e um formato por dado, com `^[A-Z0-9]{12}[0-9]{2}$`, que aceita o CNPJ alfanumérico.

- **CFOP:** código de 4 dígitos, como `type: string` com `pattern: '^[0-9]{4}$'`.

- **Valores em dinheiro:** casas decimais definidas, e total da nota coerente com a soma dos itens.

- **Data de emissão da nota:** campo definido na aba que o devolve, com fuso.

- **PDF da nota (DANFE em Base64):** paginação ou limite, pois cada nota carrega o PDF inteiro.
