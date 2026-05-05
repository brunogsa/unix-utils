---
name: mermaid-diagrams
description: "Best practices for writing Mermaid diagrams. Use when writing, reviewing, or editing any Mermaid diagram — sequence diagrams, flowcharts, C4 context diagrams, or any architecture/flow diagram."
---

# Mermaid Diagrams

## Naming

Every node, box, or actor must name the actual component it represents — never generic labels.

- **Architecture / context diagrams** — name the actual system, service, or data store.
  - Good: `Integrator API`, `Arco SAS`, `Postgres: users_db`, `Redis cache`
  - Bad: `Service A`, `Backend`, `DB`
- **Flow / sequence diagrams** — name the actual module, class, function, or service.
  - Good: `UserController`, `AuthService`, `Kafka: order-events`
  - Bad: `Module A`, `Handler`, `Queue`

## Diagram Type Selection

| Goal | Diagram type |
|------|-------------|
| System boundaries and external actors | `flowchart TD` (C4L1 style) |
| Step-by-step interaction between components | `sequenceDiagram` |
| Decision flow / branching logic | `flowchart TD` |
| State transitions | `stateDiagram-v2` |

## Readability Rules

- One diagram = one question answered. Don't try to show everything in one diagram.
- Aim for 5–10 nodes. More than 15 usually means it should be two diagrams.
- Label edges when the relationship isn't obvious from node names alone.
- Use `subgraph` to group related components, not just for visual decoration.
- Always use `TD` (top-down) direction — vertical scrolling is easier to read than horizontal.
- Omit flows that are obvious and add noise without adding insight.

## C4L1 Context Diagram

Shows the system under design and its external actors. Keep it high-level — no internal implementation details. Use `flowchart TD` with clear node shapes to distinguish actors from systems.

~~~mermaid
flowchart TD
  user(["End User"])
  api["Integrator API"]
  arco["Arco SAS\nexternal"]

  user -->|HTTP requests| api
  api -->|Fetches pricing| arco
~~~

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
