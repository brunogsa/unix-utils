# Changes Digest Format

This is the return format for the step-1 gathering subagent.

1. **Planned vs discovered** -- bullets under `Planned:` / `Discovered along the way:`, each tagged with the files it touches.
2. **Per-file reading-guide notes** -- one line per touched file: what the reviewer *learns* there; flag the densest file; suggest a read order.
3. **Decision list** -- one entry per non-obvious decision: user-visible surprise (title), mechanism (sub-note), consequence if reversed.
4. **Other authoring inputs**:
    - Business-context signals from commit bodies.
    - New API/method names with how they differ from existing ones.
    - Operational-risk items worth a `WARNING:` prefix.
    - Incidentals that changed shared state (docs/conventions/infra).
