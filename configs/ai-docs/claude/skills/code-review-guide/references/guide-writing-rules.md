# Guide-writing rules

For the writer subagent: the rules the template and the example do not show.

## Inputs and output

- Read `../assets/guide-template.md` first: the literal skeleton, in output order.

- Read `example-pr2720.md` for tone and density, skipping its YAML frontmatter.

- Read the code only at the head commit: `git -C <clone> show <sha>:<path>`, and `<work_dir>/diff.patch` for the diff. Never read the working tree.
  - Take those values from the prompt, and put every scratch file in the scratch directory it names.

- Use the stack context, business-goal sources and metrics exactly as the orchestrator passed them. Never fetch a ticket, a PR or metrics yourself.

- Write `<work_dir>/guide.md`: the guide only, from `# Guia de review` on, with no `<details>` wrapper or footer; posting adds them.

## Filling the template

- Fill every `{UPPER_SNAKE}` placeholder except `{EST1}` and `{EST2}`, inside mermaid fences too.

- Delete every HTML comment of the template, the legend included.

- Omit a conditional block entirely when its condition fails: no heading, no empty line left behind, no "não se aplica" sentence.

## Language and proof

- Write prose in PT-BR. Test titles, code names and flag names stay verbatim, in the code's language.

- Back every factual claim with a link to the code that proves it. A claim you cannot link, drop.

- Pin every code link to the head commit with the 7-character SHA: `blob/<short_sha>/<path>#L<n>`. Never a 40-character SHA, never a branch name.

- Never write an in-page `](#...)` link: each run posts a new comment with the same headings, so an anchor jumps to the oldest one. Refer back in plain text.

- Label every code link `{file}:{line}`, as the template does, even where the example shortens it to `:95`.

- Set each glossary term in *italics* in prose outside the glossary only, never inside a code span, test title or mermaid label.

- Label a line-range link `file:10-20`, pinned with `#L10-L20`.

## Camada 1

- **Objetivo de negócio.** One sentence: the outcome the business wants for users or operations, never the code change.
  - Take it only from a source the orchestrator passed, in order: the linked ticket, then its project, then the PR body, then the PR title. Link that source.

  - Never infer a goal from the code. When a source only hints at one, use the template's "incerto" line.

  - When no source states one, use the "não encontrado" line.
  - In a stacked PR the stack block states the whole stack's goal in the same three forms; this line states only this PR's share.

- **Entregável.** One sentence: what the code now does.

- **Risco de mudança.** Baixo, Médio or Alto, with up to 4 evidence bullets in the template's order.
  - Count real callers by grepping at the head commit. "Nenhum chamador" is a claim and needs its link too.

- **O que muda.** Give counts, not adjectives: files, lines added and removed, tests.
  - Entrada / Saída names every HTTP call, database, queue, topic and cache the changed code touches, or says "nenhum".

- **Entrypoints.** Name the real entry points: controller route, consumer, cron, CLI.
  - When the PR adds none, say so and name the class and methods to start reading from.

## Camada 2: tests

- List each test once, in the first flow that runs it. A later flow reusing that code gets the template's back-reference sentence.

- Sort each test into one category:
  - ✅ Happy: the main path succeeds.

  - 🔶 Corner: an edge input still succeeds or is handled without error.

  - ❌ Failure: the code rejects, throws or returns an error.

  - 📝 Logs: the test asserts a log line.

- A back-reference to two earlier flows names both: `Fluxo 1 e Fluxo 3`, each with its own `path ·` when the paths differ.

- Count every case of an `it.each` in the category and flow counts.

- Open each category with at most 4 PT-BR key points: what the tests prove together, not a list of titles.

- Copy test titles verbatim from the spec at the head commit, in backticks, as plain bullets, never as links. For an `it.each`, substitute its parameters into the title.

- Show at most 3 titles of one `it.each`, chosen to show as many distinct parameter values as fit, then the "e mais N" line.
  - Write "caso" when N is 1, "casos" otherwise.

## Camada 2: diagrams

- Draw one `flowchart TD` per flow, never a sequence diagram. Split a flowchart that passes about 10 nodes into two flows.

- Write a code node label as `function<br/>(params) → ReturnType<br/><br/>what the code does there, in PT-BR`.

- Label a node grouping several functions with the group's name, then one `function(params) → ReturnType` line each.

- Escape generics as `#lt;` and `#gt;`, since raw angle brackets break the label.

- Number the solid edges in reading order (`"1. ..."`), with letters for branches (`"5a. ..."`). Leave a dashed `-.->` error edge unnumbered.

- Point each edge from the code that acts to what it affects, never from where the data came from.

- Quote every node and edge label, and never write a line that is only `%%`: it renders as a stray box.

## Metrics marks

- Add a ⚠️ line to a node only when the metrics show a problem in its function: a metric at or over its limit, or lines no test executes.

- Add the ⚠️ legend only when at least one node carries a ⚠️.

## Size

- The posted body, wrapper included, must stay at or under 65,536 characters, GitHub's hard limit.

- When it is over, shorten: fewer `it.each` samples, then tighter key points. Never split, drop a flow or truncate.

## Fix rounds

- The orchestrator returns `check-guide.py` violation lines verbatim, as `<line>: <rule>: <detail>`. Fix each one at that line of `guide.md` and change nothing else.

- The verifier returns mismatches with `path:line` evidence. Fix each one you confirm at the head commit.

- Dispute a verifier mismatch you cannot confirm, quoting the code that contradicts it.
