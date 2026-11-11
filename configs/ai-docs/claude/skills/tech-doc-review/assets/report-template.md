# Revisão técnica: <título do documento>

<!--

Modelo literal do relatório. O texto fora de comentários HTML é copiado; <...> é preenchido.

Regras que o script de verificação confere:

- Um único título `## Resumo executivo`, antes de qualquer faixa.

- Os outros títulos `## ` são só as 3 faixas abaixo, nesta ordem. Uma faixa sem achados é omitida.

- A linha "Resolvidos" tem menos de 30 palavras.

Regras que o script não confere:

- A linha "**Fonte revisada:**" vem logo depois do título. Uma nova execução a compara com a do relatório anterior.

- A linha "Resolvidos" e a marca "recorrente" só existem numa nova execução com relatório anterior.

- Cada bullet cabe em 32 palavras e 256 caracteres. Uma lacuna longa vira um bullet principal curto, com sub-bullets de um fato cada, separados por linha em branco.

Linguagem simples, sempre que possível:

- Escreva para que alguém de produto, sem formação técnica, entenda. Todo bullet principal começa por uma frase sem jargão.

- Nomes de campo, códigos de tabela do SAP, tipos e expressões regulares vão em sub-bullets, nunca na primeira frase.

- O primeiro uso de um termo técnico inevitável traz uma explicação de uma oração, como "paginação (devolver a lista em partes, página a página)".

- Ruim: "`updatedAt` é DATS, sem fuso". Bom: "A data de alteração não traz a hora nem o fuso horário", com `updatedAt` e DATS num sub-bullet.

-->

**Fonte revisada:** <ID do arquivo no Drive, ou caminho local do arquivo>

**Resolvidos desde o último relatório:** <N> achados corrigidos: <título 1>; <título 2>; <título 3>.

<!-- Sem relatório anterior, ou com 0 corrigidos, a linha não existe. -->

Olá, time! Segue a revisão do documento. Começa por um resumo; os detalhes vêm depois, em 3 faixas, do que mais nos trava ao que é só boa prática. Cada achado diz o que falta, dá um exemplo e o que acontece se ficar como está. A decisão de como resolver é de vocês.

## Resumo executivo

<Veredito em uma frase, sem jargão. Exemplo: "Ainda não dá para começar a integração: 4 definições travam o desenvolvimento.">

- **Bloqueia (<N>):** o que impede o nosso time de começar ou terminar a integração.

  - <Título do achado>: impede <a etapa que não começa ou não termina>.

- **Gera dúvida (<N>):** <uma frase sobre o que esses achados têm em comum>.

- **Boa prática (<N>):** <uma frase sobre o que esses achados têm em comum>.

<!--

- O resumo cabe em cerca de 200 palavras e não traz nome de campo nem detalhe técnico.

- Um sub-bullet por achado de Bloqueia, com no máximo 12 palavras sobre o que ele impede.

- Uma faixa sem achados não aparece no resumo. Os números batem com os achados abaixo, depois dos cortes por tamanho.

-->

## Bloqueia

<!-- Sem isso, o nosso time não consegue começar ou terminar uma etapa da integração. Mais lugares afetados primeiro; empate segue a ordem do checklist. -->

### <Título curto, em linguagem simples> [recorrente]

- **O que falta:** <o que falta ou está ambíguo no documento, numa frase sem jargão>.

  - <Um detalhe técnico por sub-bullet: campo, aba, tipo, valor.>

- **Exemplo:** <um caso concreto da lacuna acontecendo, que alguém de produto consiga imaginar>.

- **O que bloqueia:** <a etapa do nosso time que não começa ou não termina, e por quê>.

- **Sugestão (opcional):** <como poderia ficar: um exemplo inventado e genérico, ou o trecho do contrato de referência>.

- **Item do checklist:** <nome do item, igual ao de references/checklist.md>

- **Onde:** <aba, seção ou operação 1>; <aba, seção ou operação 2>

- **Etiqueta:** já reportado - <link do comentário ou da mensagem onde foi levantado>

<!--

- "Exemplo" é obrigatório e mostra o problema na prática. Exemplo de frase:

  "Uma nota emitida às 23h em Brasília aparece como do dia seguinte para quem lê em UTC."

- "O que bloqueia" existe só nesta faixa. Nas outras, o mesmo lugar se chama "Se não for resolvido".

- "Sugestão" mostra uma forma clara, sem impor a solução. Nunca é copiada do documento revisado.

- "[recorrente]" no título aparece só numa nova execução, quando o achado do relatório anterior continua sem correção.

  Num achado agrupado e corrigido em parte dos lugares, "Onde" lista só os lugares que restam.

- A linha "Etiqueta" é opcional e traz UMA das duas etiquetas, só quando o comentário ou a conversa tocou a lacuna:

  - já reportado - <link>

  - respondido fora do doc - <link>

- "respondido fora do doc" pede, com cordialidade, que o time escreva a resposta no documento. Exemplo de frase:

  "Vimos a resposta no link acima, obrigado! Podem escrevê-la também no documento? Assim ela fica valendo para todo mundo."

- Sem comentário nem conversa sobre a lacuna, o achado não leva a linha "Etiqueta".

-->

## Gera dúvida

### <Título curto, em linguagem simples>

- **O que falta:** <...>

- **Exemplo:** <...>

- **Se não for resolvido:** <o custo de deixar como está: o que o nosso time precisa adivinhar, e o risco de adivinhar errado>.

- **Sugestão (opcional):** <...>

- **Item do checklist:** <...>

- **Onde:** <...>

## Boa prática

### <Título curto, em linguagem simples>

- **O que falta:** <...>

- **Exemplo:** <...>

- **Se não for resolvido:** <...>

- **Sugestão (opcional):** <...>

- **Item do checklist:** <...>

- **Onde:** <...>
