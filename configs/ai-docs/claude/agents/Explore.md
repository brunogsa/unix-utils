---
name: Explore
description: Read-only search agent for broad fan-out searches — when answering means sweeping many files, directories, or naming conventions and you only need the conclusion, not the file dumps. Specify search breadth ("medium" or "very thorough").
model: sonnet
effort: low
maxTurns: 32
---

## Shadows

Shadows Claude Code's built-in `Explore` agent, overriding only
`model: sonnet` so exploration never inherits a pricier session
model — this pin measurably cut average cost per run from $2.33 to
$1.17 (n=21→36, −50%). Keep behavior otherwise equivalent to the
built-in: read-only search, no editing or judgment.
