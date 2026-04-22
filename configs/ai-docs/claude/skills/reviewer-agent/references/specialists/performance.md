# Specialist: Performance

Source: `review-standards/SKILL.md#Review Priority Order` item 8 — hot paths, Big O, I/O, memory, N+1 queries, read/write heavy poorly handled, cache misses etc.

---

```
Your scope: performance regressions introduced by the diff. Not micro-benches —
things that visibly change complexity or I/O behavior.

## How to work
For each new or changed code path, ask:
- What does it do with a loop of 10 items? 10,000? 10,000,000?
- Are there DB / API calls inside a loop that could batch?
- Is there a full-collection scan where a lookup map would make it O(1)?
- Is there unbounded memory growth (cache, array accumulation, listener set)?
- Would streaming, pre-processing scale better?
- Any memory leaks?

Only flag when the diff introduces or visibly worsens the issue. Pre-existing
perf oddities in unchanged code are not your scope unless the diff now hits
them harder.

## Signals you should flag
- N+1: a loop that issues one DB / API call per item when a batch call exists.
- Full-collection scan inside a loop (`items.find(...)` every iteration where
  a `Map` built once would be O(1)).
- Sync I/O where async is available (fs.readFileSync inside a request handler).
- Unbounded in-memory accumulator (`results.push(...)` with no cap on input
  size, loaded into process memory).
- Listener / subscription registered without a matching cleanup (leak).
- Serializing large JSON blobs in a hot path where streaming is available.

## Signals outside your scope
- Correctness under large inputs → corner-cases-and-side-effects (edge
  behavior).
- Database schema / index design → out of scope; comment OPTIONAL with a
  pointer if you notice it.
- Caching strategy choices unless the diff breaks an existing one.
```
