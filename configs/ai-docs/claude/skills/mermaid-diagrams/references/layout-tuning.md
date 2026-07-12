# Layout tuning — render both and pick

For any flowchart with subgraphs or more than ~6 nodes, layout is not a guess: render the alternatives and judge from the rendered PNG. Three axes, each cheap to try.

## Subgraphs help or hurt — it depends on what you want

A `subgraph` is a **hard containment box**: every node stays inside, so any edge crossing the boundary routes *around* the cluster wall instead of taking the shortest path.

That containment is exactly what you want sometimes — and exactly what fights you other times. Decide per diagram which you're optimizing for:

- **Keep subgraphs when grouping is the message.** If the reader must see "these systems share a domain or migration cohort", the box *is* the information — grouping outweighs longer edges.
- **Drop subgraphs when the message is the wiring.** On a dense graph with many cross-cluster edges, containment walls multiply bends; flattening lets ELK minimize crossings *globally* — often much cleaner.
- **Annotation boxes are the exception** — a `subgraph "Legend"` or "Open decisions" box with *no* edges to the main graph costs nothing, so keep those even when you flatten domain clusters.

[Why] The same node/edge set renders very differently with vs. without containment. On a dense graph, **render both flat and grouped and compare the PNGs** — the better layout is obvious.

## TD vs LR — render both and pick

For flowcharts with subgraphs or > 6 nodes, `TD` and `LR` produce meaningfully different auto-layouts. Render both and judge from rendered PNG:

```bash
cp diagram.mmd /tmp/td.mmd
sed 's/^flowchart TD/flowchart LR/' /tmp/td.mmd > /tmp/lr.mmd
mmdc -i /tmp/td.mmd -o /tmp/td.png -w 1600 -H 1200
mmdc -i /tmp/lr.mmd -o /tmp/lr.png -w 1600 -H 1200
# View both with the Read tool (Claude is multimodal).
```

Compare on rendered images:

- **Subgraph titles intact** — header overlap = wrong direction.
- **Edge crossings** — fewer is better; zero crossings reads ~2× faster.
- **Aspect ratio** — tall narrow scrolls badly; very wide gets squeezed by sidebars.
- **Pipeline alignment** — request→service→upstream reads as `LR`; sequential decisions as `TD`.
- **Loop compactness** — pick the direction keeping feedback edges (cache reads, retries) as short local arcs.

Heuristic (verify visually anyway):

| Shape of the system | Try first |
|---|---|
| Small ≤ 6 nodes, no subgraphs | `TD` |
| Sequential decision flow (yes/no branches) | `TD` |
| Layered request pipeline (UI → BFF → upstream), C4L2 with subgraphs | `LR` |
| Wide fan-out from one source to many siblings | `LR` |

## Dagre vs ELK — also render both for dense diagrams

For flowcharts beyond ~10 nodes with many cross-cluster edges, Mermaid's ELK renderer often beats the default dagre. Render both and judge visually (same workflow as TD vs LR).

Enable ELK by prepending an init directive to the diagram source:

~~~text
%%{init: {"flowchart": {"defaultRenderer": "elk"}}}%%
flowchart LR
  ...
~~~

**Use the init directive above — NOT the YAML frontmatter `config: layout: elk`.** They are two different mechanisms, and the frontmatter one fails silently on older renderers:

- **Init directive** `defaultRenderer: elk` — the ELK renderer built into mermaid core. Works across mermaid 10.x and 11.x, so it's the portable choice regardless of which version your `mmdc` ships.
- **Frontmatter** `config: layout: elk` — the pluggable layout-engine API added in mermaid **11**, needing `@mermaid-js/layout-elk` installed. On 10.x it is **silently ignored** (no error, exit 0) and falls back to dagre.
- **Tell them apart** — ELK routes edges as **orthogonal right-angle** segments; dagre uses **curved splines**. See curves when you asked for ELK? Check you used `defaultRenderer`, not `layout`.

Compare on rendered PNGs:

- **Edge crossings** — ELK typically wins on subgraph-heavy diagrams (orthogonal routing).
- **Subgraph compactness** — dagre often stretches subgraphs into long rows; ELK packs them tighter.
- **Cross-cluster edge routing** — ELK's orthogonal routing is easier to follow across multiple subgraphs.
- **Aspect ratio** — ELK usually gives a more balanced shape; dagre tends toward extreme widths or heights.

Caveats:

- GitHub's bundled Mermaid sometimes lags on ELK support. If a diagram renders worse on GitHub than locally, drop the init directive to fall back to dagre — treat ELK as opt-in.
- ELK can be slower for very large diagrams (>50 nodes); usually not noticeable in `mmdc` but worth knowing if you script bulk renders.
