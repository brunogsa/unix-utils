# Reading start point and flow ordering

A static architecture diagram is read like a map: the reader needs to know **where to enter** and, when a flow has multiple steps, **what order to follow them in**.

Two cheap conventions handle both — apply them whenever a reader could otherwise follow the wrong edge first.

## Mark the start point with `classDef`

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

## Number the flow when ordering matters

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

## Don't over-color

One `classDef start` + default styling is usually enough. Data stores get cylinder shape `[(…)]`; external nodes get `"…<br/>external"` in the label. Every extra color is one more thing the reader decodes.

## Lifecycle convention for to-be / migration diagrams

When showing a **target ("to-be") or migration state**, encode lifecycle status so the reader tells *what's real now* from *what's planned* — the one case extra color earns its keep.

Load [`diagram-lifecycle.md`](diagram-lifecycle.md) — covers the node/edge marker convention (green/yellow/dashed), the future-edge-stays-solid subtlety, the state-it-in-diagram rule, and the `classDef` recipe.
