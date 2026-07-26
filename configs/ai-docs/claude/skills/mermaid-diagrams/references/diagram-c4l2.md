# C4L2 Container Diagram

The right level for a plan / tech-design architecture flowchart.

Don't redraw the C4L1 from scratch — **build on it**:

- Copy the actor + system-under-design boxes + external systems from the spec's L1.
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

## Conventions

- One `subgraph` per system-under-design box L1 had. External systems stay opaque (no subgraph).
- Re-use L1 box title verbatim as subgraph title so the L1↔L2 correspondence is visible.
- Containers follow naming rules: real module/service/store names, never "Component A".
- Cross-boundary edges terminate at the inner container, not the wrapper: `Browser --> Auth`, not `Web --> API`.
- Aim for ≤ 4 containers per subgraph; more = the subgraph deserves its own L3.
- Keep total count of subgraphs + external boxes + actors ≤ 6. More = split into two L2 diagrams scoped differently.
