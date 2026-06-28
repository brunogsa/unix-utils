---
name: design-docs
description: "USE PROACTIVELY when authoring or revising an ADR, HLD, LLD, RFC, design doc, tech design, spec.md, plan.md, or a payload schema as JSONC. Routes you to the right doc, its template, a worked example, and the rules that keep them from overlapping."
user-invocable: false
---

# Design & Build Docs — ADR / HLD / LLD / spec / plan

How the five docs divide work, so each one is written faster and none re-derives another.

This skill picks *which* doc to write and routes you to its template and a worked example. Two companion skills carry the quality bar — load them alongside this one:

- **`doc-standards`** — prose, comment, and density rules for the words inside any of these docs (also runs the density check).
- **`mermaid-diagrams`** — for every diagram you embed: validation, the target renderer version, and the common parse traps.

The toolbox: **ADR, HLD, LLD** (durable, committed in `docs/`) and **spec.md, plan.md** (throwaway, untracked, deleted after the PR).

The split that matters most is **purpose**: HLD, LLD, and ADR are **decision & alignment** docs (for humans aligning); spec and plan are **AI-build** docs (spec-driven), fed from them.

So durable docs carry tests, tasks, and launch at **alignment altitude** — strategy, titles, cross-team deps — while the plan carries the **concrete** version — commit-tasks, file paths, test titles.

The spec.md/plan.md workflow — interviewing, drafting, refining — lives in the `spec-driven-development` skill; this skill only covers their shape and altitude.

## Who owns what (single source of truth)

When two docs could carry the same thing, this table says which one owns the full version; the others recap + link instead of repeating.

| Concern | Owner | Others |
|---|---|---|
| Why / business context | HLD (epic) · spec.md (feature) | recap + link |
| Decision + alternatives | ADR; or HLD/LLD decision section / spec·plan log (minor) | recap + link the ADR |
| Structure, contracts, data model, de/para | LLD | recap + link the LLD |
| Diagrams — big-picture (C4L1, architecture; high-level flow/sequence/state) | HLD | recap + link, don't redraw |
| Diagrams — detailed (code/component design, data-model & endpoint schemas, detailed flow/sequence/state, corner/failure) | LLD | recap + link, don't redraw |
| Success metrics, UAT, test & launch strategy — high-level | HLD / LLD | spec/plan recap + link |
| Task breakdown — titles only (estimates, parallelization, cross-team deps) | HLD / LLD | plan expands to commit-tasks |
| Concrete testable acceptance criteria | spec.md | HLD/LLD keep the high-level version + link |
| Test titles, commit-sized tasks, file paths, commit sketch | plan.md | — |

Diagram *type* isn't the discriminator — altitude is: the same flow/sequence/state diagram can serve an HLD at big-picture level and an LLD at detail level.

## Relating docs: recap + link by section, let sections flex

When two docs relate, the referencing doc points to the other by **filepath or URL at the section level**, with a **brief recap** of what's there.

The recap is enough to read standalone; the link is the drill-down for readers who want the full detail.

Recap *and* link, never link alone: a bare "see §X" rots when the target moves and forces a jump to understand, whereas the inline recap keeps each doc readable on its own.

So related sections are **elastic**:

- References an upstream that already answers a section (context, requirements, a decision) → that section shrinks to *recap + link*. An LLD that references an HLD is smaller.

- Self-contained, no related upstream → those sections grow to carry the full content. An LLD with no HLD has a fuller Context and Requirements.

Applies to every pair that relates: HLD↔ADR, HLD↔LLD, LLD↔LLD, LLD↔ADR, HLD↔spec, LLD↔plan, spec↔plan.

## RFC is a status, not a doc

An RFC is a doc *circulating for comments*, not a sixth document.

Put it as a `Status` on an HLD or ADR (`Draft → RFC / In Review → Accepted`) while you gather feedback.

Don't create a separate RFC artifact; it would duplicate the HLD.

## Rules of thumb

- **Durable docs carry only the alignment altitude** — task *titles*, test/launch *strategy*, success metrics — for estimates, parallelization, and cross-team deps.

- **File paths, commit-sized tasks, and concrete test titles live only in the throwaway plan** — they rot, and they belong with the build (plan + TaskList).

- **Code bodies live in neither** the design nor the plan — they live in the repo. The LLD holds interfaces/schemas (the contract); the plan holds file paths and tasks.

- **A decision you'll argue again in 6–12 months → ADR.** A minor one → a line in the spec/plan decision log; graduate it to an ADR if it grows teeth.

## The five docs at a glance

Shared mental model for which doc is which — not a step you need help running.

| Doc | Lifespan | Job |
|---|---|---|
| **ADR** | Durable | Decide — one significant decision + alternatives |
| **HLD** | Durable | Design (system / epic) — what & why across alternatives |
| **LLD** | Durable | Design (one component) — structure, contracts, data, de/para |
| **spec.md** | Throwaway | Why / What — requirements + acceptance criteria, one feature |
| **plan.md** | Throwaway | Build — tasks, files, commits, test titles, one feature |

**Significant** = hard to reverse OR cross-team blast radius.

Not significant (cheap to reverse AND contained) → skip durable docs, go straight to `spec.md` → `plan.md`.

Significant → write the durable doc, then still produce `spec.md` → `plan.md` downstream to execute.

```mermaid
flowchart TD
  start(["Change to make"]):::start
  q1{"Significant?<br/>hard to reverse OR cross-team blast radius"}
  q2{"What are you capturing?"}

  adr["ADR — one decision + alternatives<br/>(standalone if significant, else a section)"]
  hld["HLD — system / epic design<br/>what & why across alternatives"]
  lld["LLD — one component<br/>structure, contracts, data, de/para, diagrams"]

  spec["spec.md (throwaway)<br/>why / what + acceptance criteria"]
  plan["plan.md (throwaway)<br/>tasks, files, commits, test titles"]
  build(["Build"])

  start --> q1
  q1 -->|"no"| spec
  q1 -->|"yes"| q2
  q2 -->|"a decision"| adr
  q2 -->|"a system / epic"| hld
  q2 -->|"one component"| lld
  hld -->|"per component"| lld
  adr --> spec
  lld --> spec
  spec --> plan
  plan --> build

  classDef start fill:#fef3c7,stroke:#d97706,stroke-width:2px
```

## Templates and worked examples — start here to write one

When authoring a design doc or ADR: copy the matching `assets/` template to start, then read the matching `references/` example to see it filled in.

Every diagram in these examples was validated with the `mermaid-diagrams` skill — load it before you paste your own.

- HLD — start from `assets/template-hld.md` (skeleton with TODOs + authoring notes); see `references/example-good-hld.md` for a full worked example (MoSCoW scope, numbered premises/decisions/risks, sequence + state diagrams, appendix).

- ADR — start from `assets/template-adr.md` (skeleton with TODOs); see `references/example-good-adr.md` for a worked example (decision + alternatives with +/-/~ trade-offs + consequences).

- LLD — start from `assets/template-lld.md` (one component, implementation-ready: code design, data model, contracts, de/para mappings, error/concurrency, observability). The top comment block holds the HLD↔LLD boundary rule. No worked example yet.

- Schema as JSONC — when a doc shows a request/response/event payload, render it as one annotated JSONC object, not a field table; copy `references/example-good-schema.jsonc`.
  - "Schema as jsonc" means that file's style: real values, each field tagged `type | required|optional | constraints | description`, optional fields shown, nested objects in full, quirks inline.
  - Keep every line ≤80 chars: short annotations stay inline.
    - When a full annotation would push the field line past 80, move the comment above the field (wrapped, multi-line), preceded by a blank line so it hugs its field.
