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

Validate each fenced block independently — a broken diagram earlier in the file does not fail-fast the renderer for later blocks; the reader just sees garbled text on the broken one.

### Common parse traps that pass eyeball review but fail `mmdc`

- **Unquoted parens / brackets inside pipe-delimited edge labels** — `A -->|label (with parens)| B` fails: mermaid reads `(` as the start of a node shape.
  - Fix: quote the whole label — `A -->|"label (with parens)"| B`.
  - Applies to `()`, `[]`, `{}`, and `(())` inside any pipe label.
- **Special characters in node display text** — `:` `(` `)` `&` `/` are usually fine inside `["..."]` but break inside bare `[...]`.
  - When in doubt, wrap node text in double quotes: `node["Foo: Bar (v2)"]`.
- **Reserved words as participant ids** — `end`, `note`, `loop` confuse the parser. Alias them: `participant E as end-state`.
- **`<br/>` line breaks** — only work inside quoted strings. Bare `[Foo<br/>Bar]` fails; `["Foo<br/>Bar"]` works.

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

## Edge semantics — source must be the actor

`A --> B` reads as "A performs an action that affects B" — the source must be the **agent doing the work**, not the data origin.

Flowcharts (unlike sequence diagrams) don't enforce this, so it's the most common architecture-diagram bug.

It hits hardest in client-side caching (TanStack Query, SWR, RTK Query, Apollo) and any framework that intercepts on the receiver side.

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
- Use `subgraph` to group related components, not just for visual decoration.
- Direction: default to `TD` (top-down) for small flowcharts. For larger / subgraph-heavy flowcharts, **render both `TD` and `LR` and pick the easier-to-read one** (workflow below). Don't guess.
- Omit flows that are obvious and add noise without adding insight.

### TD vs LR — render both and pick

For any flowchart with subgraphs or > 6 nodes, `TD` and `LR` produce meaningfully different auto-layouts. Don't pick on feel — render both as PNG and judge the rendered output:

```bash
cp diagram.mmd /tmp/td.mmd
sed 's/^flowchart TD/flowchart LR/' /tmp/td.mmd > /tmp/lr.mmd
mmdc -i /tmp/td.mmd -o /tmp/td.png -w 1600 -H 1200
mmdc -i /tmp/lr.mmd -o /tmp/lr.png -w 1600 -H 1200
# Then view both with the Read tool (Claude is multimodal — PNGs work).
```

What to compare on the rendered images:

- **Subgraph titles intact** — header overlapped by a contained node = wrong direction for this graph.
- **Edge crossings** — fewer is better; zero crossings reads almost twice as fast.
- **Aspect ratio fits the medium** — tall narrow scrolls badly in PR descriptions; very wide gets squeezed by sidebars.
- **Pipeline alignment** — request → service → upstream pipelines mirror naturally as `LR`; sequential decision flows read better as `TD`.
- **Loop compactness** — pick the direction that keeps feedback edges (cache reads, retries) as short local arcs.

Heuristic to start from (verify with the visual check anyway):

| Shape of the system | Try first |
|---|---|
| Small ≤ 6 nodes, no subgraphs | `TD` |
| Sequential decision flow (yes/no branches) | `TD` |
| Layered request pipeline (UI → BFF → upstream), C4L2 with subgraphs | `LR` |
| Wide fan-out from one source to many siblings | `LR` |

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

- **Numbers (`1`, `2`, `3`)** mark sequence: step 2 cannot start until step 1 finishes.
- **Letters (`1a`, `1b`, `1c`)** mark sibling sub-steps of one parent step: they may execute in parallel, or in any order within that step.
- **Phase prefixes** (`1a`, `1b`, …, `2a`, `2b`, …) work well when the diagram contains two or more discrete flows triggered by different events (e.g., "on Apply" vs. "on tab switch").
  - The phase number is the major identifier; sub-letter is the within-phase order.
- **Dashed alternative within a step** — a fallback edge sharing a step number works as `"1c (fallback). on X failure"`.
  - Dashed line + parenthetical signals "alternative path within step 1c".
- **Skip the numbers** for diagrams that show pure structure (no flow), and for tiny one-or-two-edge diagrams where order is obvious.
  - Numbers earn their place when the diagram has ≥ 3 directed edges or any branching.

### Don't over-color

One `classDef start` plus the default styling for everything else is usually enough.

- Mermaid already gives data stores the cylinder shape `[(…)]`.
- External nodes can be marked in their label (`"…<br/>external"`).
- Resist the urge to invent palettes — every additional color is one more thing the reader has to decode.

## C4L1 Context Diagram

Shows the system under design and its external actors. Keep it high-level — no internal implementation details. Use `flowchart TD` with clear node shapes to distinguish actors from systems.

~~~mermaid
flowchart TD
  user(["End User"]):::start
  api["Integrator API"]
  arco["Arco SAS<br/>external"]

  user -->|"1. HTTP requests"| api
  api -->|"2. fetches pricing"| arco

  classDef start fill:#fef3c7,stroke:#d97706,stroke-width:2px
~~~

## C4L2 Container Diagram

The right level for a plan.md / tech-design architecture flowchart.

Don't redraw the C4L1 from scratch — **build on it**:

- Copy the actor + system-under-design boxes + external systems from the spec.md L1.
- Then expand each system-under-design box with a `subgraph` exposing its internal containers (services, caches, modules, queues).
- External systems stay opaque — their internals belong in *their* L2.

A reader who already saw the L1 should see the same outline (same actors, same external systems, same names) and just zoom into the boxes they care about. Redrawing breaks that continuity.

~~~mermaid
flowchart TD
  user(["End User"]):::start

  subgraph Web["Web App"]
    Browser["React UI"]
    Cache[("Browser cache")]
  end

  subgraph API["API Server"]
    Auth["AuthService"]
    Orders["OrdersController"]
  end

  ext["Stripe<br/>external"]

  user -->|"1. HTTP"| Browser
  Browser -->|"2a. tRPC"| Orders
  Browser -->|"2b. reads / writes"| Cache
  Orders -->|"3a. verifies token"| Auth
  Orders -->|"3b. charges card"| ext

  classDef start fill:#fef3c7,stroke:#d97706,stroke-width:2px
~~~

Conventions:

- One `subgraph` per system-under-design box that L1 had. Don't subgraph external systems — they stay opaque.
- Re-use the L1 box title verbatim as the subgraph title so a reader can spot the L1↔L2 correspondence at a glance.
- Containers inside the subgraph follow the same naming rule as everywhere else: name the actual module / service / store, never "Component A".
- Edges that cross the boundary terminate at the inner container, not the subgraph wrapper — `Browser --> Auth`, not `Web --> API`.
  - The wrapper exists to group; data still flows between the actual containers.
- Aim for ≤ 4 containers per subgraph.
  - If a subgraph has more, it likely deserves its own L3 diagram (zoom further into that one container) instead of growing this one.
- Keep the *count of subgraphs + external boxes + actors* ≤ 6.
  - The point is a single readable picture.
  - If you need more boxes, split into two L2 diagrams scoped to different parts of the L1.

## Sequence Diagram

Shows the execution path at module/function level. Actors must be actual code components.

- Always enable `autonumber` — it makes referencing steps in discussion and review much easier.
- If the diagram needs more than 5 participants (lanes), split it into smaller sub-diagrams, each covering one logical phase or interaction boundary.

~~~mermaid
sequenceDiagram
  autonumber
  participant C as UserController
  participant S as AuthService
  participant DB as Postgres: users_db

  C->>S: validateToken(token)
  S->>DB: findUser(userId)
  DB-->>S: User | null
  S-->>C: AuthResult
~~~
