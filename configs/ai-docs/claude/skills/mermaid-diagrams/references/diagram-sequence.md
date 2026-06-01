# Sequence Diagram

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

## Explicit fan-out, filter parameters, external hops

[Instruction] **Parallel calls render as separate arrows, not lumped.** N parallel calls = N arrows; `Note: in parallel` if useful.

[Instruction] **Filter parameters on the arrow label.** Write `summary(entity=X, resolved=false)`, not `summary call`.

[Instruction] **External-system hops are explicit.** Draw `BFF -> External` per call (or per batch with a note); don't hide the trust boundary.

[Why] Sequence diagrams are implementation contracts. Lumped nodes hide fan-out, filter shapes, and trust-boundary crossings — decisions reviewers need.

~~~mermaid
sequenceDiagram
    participant UI
    participant BFF
    participant Int as Integrator
    Note over UI,Int: Fan-out + filters per label + Integrator hop
    UI->>BFF: summary(entity=A, resolved=false)
    UI->>BFF: summary(entity=B, resolved=false)
    UI->>BFF: summary(entity=C, resolved=false)
    UI->>BFF: list(entity=active, resolved=false)
    Note right of UI: 4 calls in parallel
    BFF->>Int: 4 proxied GETs
    Int-->>BFF: typed responses
    BFF-->>UI: typed responses
~~~
