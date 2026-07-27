---
name: mermaid-diagrams
description: "Best practices for writing Mermaid diagrams. Use when writing, reviewing, or editing any Mermaid diagram — sequence diagrams, flowcharts, C4 context diagrams, or any architecture/flow diagram."
---

# Mermaid Diagrams

## Validate before paste — non-negotiable

Mermaid has subtle syntax traps the eye misses.

- A broken diagram renders as plain text in GitHub/GitLab/Jira and most previewers — silent doc degradation, no error.
- **Run every diagram through `mmdc` before pasting into any `.md`, PR, ticket, wiki, or chat.**
- No exceptions, even one-liners — the trap is usually a one-char typo that looks fine.

```bash
# Single diagram saved to a .mmd file:
mmdc -i /tmp/d.mmd -o /tmp/d.svg
echo "exit: $?"   # non-zero = parse error; read the message, fix, re-run.

# Validate every block already inside a markdown file (use this BEFORE you commit / open the PR):
awk '/^```mermaid/{f=1; n++; out="/tmp/d"n".mmd"; next} /^```$/{if(f){f=0; close(out)}} f{print > out}' file.md
for f in /tmp/d*.mmd; do
  printf "%s: " "$(basename "$f")"
  mmdc -i "$f" -o "${f%.mmd}.svg" >/dev/null 2>&1 && echo OK || echo FAIL
done
```

Install if missing: `npm i -g @mermaid-js/mermaid-cli`.

Validate each fenced block independently — one broken block doesn't fail-fast the renderer for the others.

### Target renderer

Author against the locally-installed `mmdc` (`mmdc --version`); validate every diagram with it before committing.

- `mmdc` exit 0 is necessary but only sufficient when your publish target renders the same Mermaid version as your local `mmdc`.
- A different target (e.g. GitHub's pinned version) can still reject what passed locally.
- Prefer conservative forms that render identically across versions: quote every node and edge label, and use `<br/>` (never `\n`) for line breaks.
- Bare `\n` renders as the literal characters `\n` on older renderers.

### Common parse traps that pass eyeball review but fail `mmdc`

- **Unquoted parens / brackets inside pipe-delimited edge labels** — `A -->|label (with parens)| B` fails: mermaid reads `(` as the start of a node shape.
  - Fix: quote the whole label — `A -->|"label (with parens)"| B`.
  - Applies to `()`, `[]`, `{}`, and `(())` inside any pipe label.

- **Special characters in node display text** — `:` `(` `)` `&` `/` are usually fine inside `["..."]` but break inside bare `[...]`.
  - When in doubt, wrap node text in double quotes: `node["Foo: Bar (v2)"]`.

- **Reserved words as participant ids** — `end`, `note`, `loop` confuse the parser. Alias them: `participant E as end-state`.
- **`<br/>` line breaks** — only work inside quoted strings. Bare `[Foo<br/>Bar]` fails; `["Foo<br/>Bar"]` works.
- **Bare `%%` separator lines spawn a phantom node** — a line that is *only* `%%` renders as a stray node labelled `%%`, and passes `mmdc` with exit 0 (no error).
  - It's a junk box floating in the diagram — give every comment content (`%% --`, `%% ----`), never a lone `%%`.

- **Arrow tokens inside `%%` comments leak into the parse** — a comment like `%% solid (-->) vs dashed (-.->)` emits a phantom `%%` node; the stripper misfires on `-->`/`-.->`.
  - Keep arrow syntax out of comment text — write "solid vs dashed", not the literal arrows.
  - Detection for both: after rendering, `grep -c 'nodeLabel">%%' out.svg` — must be `0`. Exit code alone won't catch these; they're silent.

When `mmdc` reports `Parse error on line N` with a caret:

- The caret points at the first token the parser couldn't accept.
- The actual cause is usually one or two characters before it (the unbalanced `(`, the reserved word, etc.).
- Read the line right-to-left from the caret.

## Naming

Every node, box, or actor must name the actual component it represents — never generic labels.

- **Architecture / context diagrams** — name the actual system, service, or data store.
  - Good: `Integrator API`, `Arco SAS`, `Postgres: users_db`, `Redis cache`
  - Bad: `Service A`, `Backend`, `DB`

- **Flow / sequence diagrams** — name the actual module, class, function, or service.
  - Good: `UserController`, `AuthService`, `Kafka: order-events`
  - Bad: `Module A`, `Handler`, `Queue`

## Rich node labels — separate the header from the body with a blank line

When a node carries more than its name — vendor tag, responsibilities, status notes, bullets — split the label into a **header** (identity) and a **body** (details) with a blank line: `<br/><br/>`.

- **Header** = what the node *is*: the name, plus an optional `« Vendor »` tech tag on its own line and/or a short alias like `(SeFaz)` / `(Configurador)`.

- **Body** = what it *does* or what's notable: responsibilities, bullets, caveats, migration intent.

- Put the blank line after the **whole** header block (name + vendor + alias), before the first detail.

~~~text
oms["OMS<br/>« Salesforce »<br/><br/>• Orquestração: Pedidos, Invoice<br/>Atenção: acoplado à nuvem SF"]
cgi["CGI (Cadastro Global)<br/><br/>Fonte da Verdade: Escolas, Faculdades<br/>expõe eventos + API"]
~~~

[Why] The header answers "what is this?", the body "what does it do?". The blank line lets the eye grab the name first and drop into details only when needed.



- Without the break the name blurs into the bullets — costs one `<br/>`, saves a re-scan per node.
- **Identity-only nodes get no break.** A bare name, or name + short alias (`Receita Federal<br/>(SeFaz)`), has no body to separate — a blank line just floats a lonely subtitle.
  - Apply the break only where a real details/responsibilities block exists.

- A single parenthetical that *renames or expands* the node (`(Loja B2C 2.0)`, `(Sistema Produção Gráfica)`) is part of the header, not the body — it stays attached, no break.
  - A parenthetical that *describes behavior* (a note, a sentence with a verb) is body — break before it.

## Diagram titles — scannable summaries

Pack the title (in `<details><summary>` or heading) with mechanism + payload + flow direction so readers can pre-read and skip the body when not needed.

Pattern + examples: see [`references/diagram-titles.md`](references/diagram-titles.md).

## Edge semantics — source must be the actor

`A --> B` reads as "A performs an action that affects B" — the source must be the **agent doing the work**, not the data origin.

Flowcharts (unlike sequence diagrams) don't enforce this, so it's the most common architecture-diagram bug.

It hits hardest in client-side caching and any framework that intercepts on the receiver side.

The origin can't reach the destination directly — some other actor puts the data there.

```text
Bad   (says "the BFF reaches into the browser cache"):
  GSA --> Cache

Good  (the UI's useQuery hook caches the response it received from GSA):
  UI -->|"useQuery caches the envelope returned by GSA"| Cache
```

Same issue, different domains:
- **Apollo / RTK Query / SWR** — the *client* normalizes/caches; the GraphQL server / REST endpoint never touches the cache.
- **Webhooks landing in a queue** — the HTTP handler (not the external sender) is what enqueues; arrow source is the handler.
- **Database triggers writing audit rows** — the *trigger* is the actor, not the original `INSERT` caller.

When in doubt, **write the sequence diagram first**.

- Lifelines force each message between actually-connected participants.
- If you can't draw `GSA → Cache` directly there, you can't shortcut it in the flowchart either.
- Mirror the sequence's arrow sources into the flowchart.

Reviewer checklist:

- For every edge `X --> Y`, ask: *does X execute the code that affects Y?* If "X provides data some other component then puts into Y", it's mis-sourced.

- Cross-check against any sibling sequence diagram — if the sequence has `A->>B: data; B->>C: write`, the flowchart edge is `B --> C`, not `A --> C`.

## Diagram Type Selection

| Goal | Diagram type |
|------|-------------|
| System boundaries and external actors | `flowchart TD` (C4L1 style) |
| What runs *inside* each system box | `flowchart TD` with `subgraph` (C4L2 style) |
| Step-by-step interaction between components | `sequenceDiagram` |
| Decision flow / branching logic | `flowchart TD` |
| State transitions | `stateDiagram-v2` |

## Readability Rules

- One diagram = one question answered. Don't try to show everything in one diagram.
- Aim for 5–10 nodes. More than 15 usually means it should be two diagrams.
- Label edges when the relationship isn't obvious from node names alone.
- Use `subgraph` to group related components, not just for visual decoration — but on dense graphs grouping is a trade-off (see Layout below).

- Direction: default to `TD` (top-down) for small flowcharts. For larger / subgraph-heavy flowcharts, **render both `TD` and `LR` and pick the easier-to-read one** (see Layout below). Don't guess.

- Omit flows that are obvious and add noise without adding insight.

### Layout: render alternatives and pick — don't guess

For subgraph-heavy or > 6-node flowcharts, the same nodes and edges render very differently across layout choices. Render the alternatives and judge from the PNG, never guess.

Load [`references/layout-tuning.md`](references/layout-tuning.md) — covers the subgraph keep-vs-flatten trade-off, TD vs LR, and dagre vs ELK (init directive, not frontmatter), each with a render-both-and-compare workflow.

## Reading start point and flow ordering

A static architecture diagram is read like a map: the reader needs to know **where to enter** and, when a flow has multiple steps, **what order to follow them in**.

Two cheap conventions handle both — apply them whenever a reader could otherwise follow the wrong edge first.

### Mark the start point with `classDef`

Highlight the entry actor (or the first system the reader should look at) with a distinct fill color so the reader's eye lands there first.

Re-use the class name `start` across diagrams for consistency:

~~~mermaid
flowchart TD
  user(["End User"]):::start
  api["API"]
  user --> api

  classDef start fill:#fef3c7,stroke:#d97706,stroke-width:2px
~~~

The actor shape `(["…"])` already says "person" semantically; the highlight reinforces "this is where you start reading."

### Number the flow when ordering matters

If the diagram describes a multi-step flow (Apply → derive → cache → query, login → fetch → render), prefix edge labels with `1.`, `2.`, `3.` so the reading order is unambiguous.

Use letters (`1a`, `1b`, `1c`) for siblings inside a step that fan out in parallel or whose internal order doesn't matter — they all "happen as part of step 1":

~~~mermaid
flowchart TD
  user(["End User"]):::start
  ui["React UI"]
  api["API"]
  db[("Postgres")]
  cache[("Redis")]

  user -->|"1. submits form"| ui
  ui -->|"2. POST /orders"| api
  api -->|"3a. write order"| db
  api -->|"3b. invalidate cached list"| cache

  classDef start fill:#fef3c7,stroke:#d97706,stroke-width:2px
~~~

Conventions:

- **Numbers (`1`, `2`, `3`)** mark sequence: step 2 starts after step 1 finishes.
- **Letters (`1a`, `1b`, `1c`)** mark sibling sub-steps of one parent: parallel or any order within that step.
- **Phase prefixes** (`1a`...`2a`...) when the diagram contains 2+ discrete flows triggered by different events (e.g., "on Apply" vs "on tab switch"). Phase number = major identifier; sub-letter = within-phase order.

- **Dashed alternative within a step** — `"1c (fallback). on X failure"` signals alternative path within step 1c.

- **Skip numbers** for pure-structure diagrams or tiny ones; numbers earn their place when there are ≥3 directed edges or branching.

### Don't over-color

One `classDef start` + default styling is usually enough. Data stores get cylinder shape `[(…)]`; external nodes get `"…<br/>external"` in the label. Every extra color is one more thing the reader decodes.

### Lifecycle convention for to-be / migration diagrams

When showing a **target ("to-be") or migration state**, encode lifecycle status so the reader tells *what's real now* from *what's planned* — the one case extra color earns its keep.

Load [`references/diagram-lifecycle.md`](references/diagram-lifecycle.md) — covers the node/edge marker convention (green/yellow/dashed), the future-edge-stays-solid subtlety, the state-it-in-diagram rule, and the `classDef` recipe.

## C4L1 Context Diagram

System under design + external actors. High-level, `flowchart TD`.

Load [`references/diagram-c4l1.md`](references/diagram-c4l1.md) when drawing one — a minimal example, edge-incidence, abstraction level (roles not fields), uniform-pattern for N entities in one role.

It routes on to [`references/diagram-c4l1-strangler-fig-example.md`](references/diagram-c4l1-strangler-fig-example.md) only for a busy diagram — many third-party systems, or a legacy-vs-target split.

## C4L2 Container Diagram

Right level for a plan / tech-design flowchart. Build on the L1, don't redraw from scratch.

Load [`references/diagram-c4l2.md`](references/diagram-c4l2.md) when drawing one — covers example, build-on-L1 rule, and full convention list (subgraph-per-system, naming, cross-boundary edges, container/box caps).

## Sequence Diagram

Execution path at module/function level. Actors must be actual code components. Always `autonumber`; split if >5 lanes.

Load [`references/diagram-sequence.md`](references/diagram-sequence.md) when drawing one — covers examples and the fan-out / filter-parameter / external-hop rules for implementation contracts.
