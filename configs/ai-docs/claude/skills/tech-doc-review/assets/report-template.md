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

- Todo termo técnico que o relatório usa entra no "Glossário" do resumo, com uma explicação simples.

- Ruim: "`updatedAt` é DATS, sem fuso". Bom: "A data de alteração não traz a hora nem o fuso horário", com `updatedAt` e DATS num sub-bullet.

Menos é mais:

- Uma linha opcional ("Exemplo", "Sugestão") só entra quando diz algo que as outras linhas do achado não dizem.

- O relatório não mostra o item do checklist de cada achado: ele serve à revisão, não a quem lê.

-->

**Fonte revisada:** <ID do arquivo no Drive, ou caminho local do arquivo>

**Resolvidos desde o último relatório:** <N> achados corrigidos: <título 1>; <título 2>; <título 3>.

<!-- Sem relatório anterior, ou com 0 corrigidos, a linha não existe. -->

Olá, time! Segue a revisão do documento. Começa por um resumo, com o contexto e um glossário; os detalhes vêm depois, em 3 faixas, do que mais nos trava ao que é só boa prática. Cada achado diz o que falta e o que acontece se ficar como está. A decisão de como resolver é de vocês.

## Resumo executivo

**Contexto:** <o que o documento define, quem o escreveu e para quem, em 1 a 3 frases sem jargão.>

**Demandas:** <as demandas que o documento define, uma por bullet.>

- **<Nome da demanda>:** <o que ela entrega e para quê. Exemplo: "Notas por CNPJ: lista as notas fiscais emitidas para um cliente.">

**Veredito:** <uma frase sem jargão. Exemplo: "Ainda não dá para começar a integração: 4 definições travam o desenvolvimento.">

- **Bloqueia (<N>):** o que impede o nosso time de começar ou terminar a integração.

  - <Título do achado>: impede <a etapa que não começa ou não termina>.

- **Gera dúvida (<N>):** <uma frase sobre o que esses achados têm em comum>.

- **Boa prática (<N>):** <uma frase sobre o que esses achados têm em comum>.

**Glossário:**

- **<Termo>:** <o que significa, em uma frase simples. Exemplo: "Paginação: devolver uma lista longa em partes, página a página.">

<!--

- No resumo, ser fácil de entender vale mais que ser curto: prefira uma frase a mais a um termo sem explicação.

- Fora do glossário, o resumo não traz nome de campo nem detalhe técnico.

- Uma demanda é cada consulta, operação ou evento que o documento define. Use o nome que o documento dá a ela.

- O glossário traz só os termos técnicos que o relatório usa, inclusive siglas do domínio (como CNPJ ou NF-e). Sem nenhum, ele não aparece.

- Um sub-bullet por achado de Bloqueia, com no máximo 12 palavras sobre o que ele impede.

- Uma faixa sem achados não aparece no resumo. Os números batem com os achados abaixo, depois dos cortes por tamanho.

-->

## Bloqueia

<!-- Sem isso, o nosso time não consegue começar ou terminar uma etapa da integração. Mais lugares afetados primeiro; empate segue a ordem do checklist. -->

### <Título curto, em linguagem simples> [recorrente]

- **O que falta:** <o que falta ou está ambíguo no documento, numa frase sem jargão>.

  - <Um detalhe técnico por sub-bullet: campo, aba, tipo, valor.>

- **O que bloqueia:** <a etapa do nosso time que não começa ou não termina, e por quê>.

- **Exemplo (opcional):** <um caso concreto do que dá errado se a lacuna ficar>.

- **Sugestão (opcional):** <como poderia ficar: um exemplo inventado e genérico, ou o trecho do contrato de referência>.

- **Onde:** <aba, seção ou operação 1>; <aba, seção ou operação 2>

- **Etiqueta:** já reportado - <link do comentário ou da mensagem onde foi levantado>

<!--

- "Exemplo" mostra, com valores inventados, o custo de deixar a lacuna como está. Só entra quando "O que bloqueia" sozinho não deixa alguém de produto imaginar esse custo.

  - Ruim, pois só repete a lacuna: "Exemplo: a data vem sem fuso horário."

  - Bom, pois mostra o custo: "Uma nota alterada às 23h59 fica fora da leitura do dia seguinte, e a alteração nunca chega até nós."

- "O que bloqueia" existe só nesta faixa. Nas outras, o mesmo lugar se chama "Se não for resolvido".

- "Sugestão" mostra uma forma clara, sem impor a solução, e só entra quando ajuda o time a decidir. Nunca é copiada do documento revisado.

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

- **Se não for resolvido:** <o custo de deixar como está: o que o nosso time precisa adivinhar, e o risco de adivinhar errado>.

- **Exemplo (opcional):** <...>

- **Sugestão (opcional):** <...>

- **Onde:** <...>

## Boa prática

### <Título curto, em linguagem simples>

- **O que falta:** <...>

- **Se não for resolvido:** <...>

- **Exemplo (opcional):** <...>

- **Sugestão (opcional):** <...>

- **Onde:** <...>
