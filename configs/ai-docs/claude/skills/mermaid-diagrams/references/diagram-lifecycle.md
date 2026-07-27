# Lifecycle convention for to-be / migration diagrams

When a diagram shows a **target ("to-be") or migration state** — not just what exists today — encode lifecycle status so the reader can tell *what's real now* from *what's planned*.

This is the one case where extra color earns its keep — the whole point of a to-be diagram is the gap between current and target.

A field-tested convention (orthogonal axes — node = what a thing's status is, edge = what a relationship's status is):

| Marker | Meaning |
|---|---|
| **Green node fill** | will be created — does not exist yet |
| **Yellow node fill** | undecided / unsure (may already exist; we just haven't committed) |
| **Dashed node border** | second, redundant marker that the system doesn't exist yet (pairs with green; a yellow node can *also* take it when it's both unsure *and* nonexistent) |
| **Solid edge** | integration that **already exists** |
| **Dashed edge** | integration that exists **but is intended to be deprecated/removed** |

The load-bearing subtlety: **node markers carry "doesn't exist yet," edge markers carry "exists or not."**

So a *future* integration (into a green/dashed node that isn't built) is drawn as a **solid** edge — the green node already tells the reader it's not real.

Don't dash a future edge: dashed means "exists today, kill it later," the opposite message.

- **State the convention in-diagram, not just in your head.** Put it in a `subgraph "Legend"` with one swatch per marker, or a `%%` comment block.
  - An unexplained red/green is a claim the reader can't verify. Copying a diagram's colors without knowing their meaning ("is green *new* or *good*?") — decode or ask first.

- **Don't invent markers the source doesn't define.** If a diagram uses only the five above, don't add a sixth (e.g. a "problem" red) on a hunch.
  - Express "this should go away" with the tools you have — a dashed (deprecate) edge — not a new color.

- `classDef` recipe:
  ~~~text
  classDef willCreate  fill:#d5e8d4,stroke:#82b366,stroke-dasharray:5 5
  classDef unsure      fill:#fff2cc,stroke:#d6b656
  classDef unsureMissing fill:#fff2cc,stroke:#d6b656,stroke-dasharray:5 5
  ~~~
