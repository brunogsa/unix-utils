# Diagram titles — examples

Pattern: `Diagram N — Stage X (Mechanism): What gets carried + How`.

## Bad — just a label

```
Diagram 2 — Phase 2 (Browse): cache hit on tab/filter/page change
```

Tells the reader nothing about what flows or how.

## Good — mechanism + payload + flow

```
Diagram 2 — Phase 2 (Navigation: cache + passthrough): Cache hit (CNPJ → Agreement IDs + SKUs) on tab change, filter via BFF (passthrough)
```

Reader sees four signals before opening the diagram:

- **Phase** — which phase of the flow.
- **Mechanism** — cache + passthrough.
- **Payload** — Agreement IDs + SKUs (and the source: CNPJ).
- **Flow direction** — through BFF as passthrough.

## When to apply

The pattern fits any title that precedes a diagram:

- `<details><summary>` text wrapping a fenced mermaid block.
- A heading (`###`) immediately above a fenced mermaid block.
- A figure caption when diagrams are referenced cross-section.

The title is the cheapest place to add reader value — it gets read 100% of the time; the diagram body only when the title justified the click.
