# Revisão técnica: <título do documento>

<!--

Modelo literal do relatório. O texto fora de comentários HTML é copiado; <...> é preenchido.

Regras que o script de verificação confere:

- Os únicos títulos `## ` são as 3 faixas abaixo, nesta ordem. Uma faixa sem achados é omitida.

- A linha "Resolvidos" tem menos de 30 palavras.

Regras que o script não confere:

- A linha "**Fonte revisada:**" vem logo depois do título. Uma nova execução a compara com a do relatório anterior.

- A linha "Resolvidos" e a marca "recorrente" só existem numa nova execução com relatório anterior.

- Cada bullet cabe em 32 palavras e 256 caracteres. Uma lacuna longa vira um bullet principal curto, com sub-bullets de um fato cada, separados por linha em branco.

-->

**Fonte revisada:** <ID do arquivo no Drive, ou caminho local do arquivo>

**Resolvidos desde o último relatório:** <N> achados corrigidos: <título 1>; <título 2>; <título 3>.

<!-- A linha "Resolvidos" tem menos de 30 palavras. Sem relatório anterior, ou com 0 corrigidos, a linha não existe. -->

Olá, time! Segue a revisão do documento. Os achados estão em 3 faixas, do que mais nos trava ao que é só boa prática. Cada um traz a lacuna, por que ela importa para quem consome e, quando ajuda, um exemplo. A decisão de como resolver é de vocês.

## Bloqueia

<!-- Sem isso, o time que consome não consegue seguir. Mais lugares afetados primeiro; empate segue a ordem do checklist. -->

### <Título curto do achado> [recorrente]

- **Lacuna:** <o que falta ou está ambíguo no documento, em uma ou duas frases>.

- **Por que isso importa:** <o que o time consumidor não consegue fazer, ou precisa adivinhar, por causa da lacuna; um caso concreto>.

- **Exemplo (opcional):** <um exemplo inventado e genérico do que seria claro; ou o trecho do contrato de referência, quando houver>.

- **Item do checklist:** <nome do item, igual ao de references/checklist.md>

- **Onde:** <aba, seção ou operação 1>; <aba, seção ou operação 2>

- **Etiqueta:** já reportado - <link do comentário ou da mensagem onde foi levantado>

<!--

- "[recorrente]" no título aparece só numa nova execução, quando o achado do relatório anterior continua sem correção.

  Num achado agrupado e corrigido em parte dos lugares, "Onde" lista só os lugares que restam.

- A linha "Etiqueta" é opcional e traz UMA das duas etiquetas, só quando o comentário ou a conversa tocou a lacuna:

  - já reportado - <link>

  - respondido fora do doc - <link>

- "respondido fora do doc" pede, com cordialidade, que o time escreva a resposta no documento. Exemplo de frase:

  "Vimos a resposta no link acima, obrigado! Podem escrevê-la também no documento? Assim ela fica valendo para todo mundo."

- Sem comentário nem conversa sobre a lacuna, o achado não leva a linha "Etiqueta".

- O primeiro uso de um termo técnico traz uma explicação de uma oração. Exemplo de frase:

  "paginação (devolver a lista em partes, página a página)".

-->

## Gera dúvida

### <Título curto do achado>

- **Lacuna:** <...>

- **Por que isso importa:** <...>

- **Exemplo (opcional):** <...>

- **Item do checklist:** <...>

- **Onde:** <...>

## Boa prática

### <Título curto do achado>

- **Lacuna:** <...>

- **Por que isso importa:** <...>

- **Exemplo (opcional):** <...>

- **Item do checklist:** <...>

- **Onde:** <...>
