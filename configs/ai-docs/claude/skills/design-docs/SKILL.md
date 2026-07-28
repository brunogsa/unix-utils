---
name: design-docs
description: "USE PROACTIVELY when authoring an ADR, HLD, LLD, RFC, design doc, tech design, spec_<slug>.md, plan_<slug>.md, or payload schema — routes to templates, rules, and worked examples."
user-invocable: false
---

# Design & Build Docs — ADR / HLD / LLD / spec / plan

How the five docs divide work, so each one is written faster and none re-derives another.

This skill picks *which* doc to write and routes you to its template and a worked example. Two companion skills carry the quality bar — load them alongside this one:

- **`doc-standards`** — prose, comment, and density rules for the words inside any of these docs (also runs the density check).
- **`mermaid-diagrams`** — for every diagram you embed: validation, the target renderer version, and the common parse traps.

The toolbox: **ADR, HLD, LLD** (durable, committed in `docs/`) and **the spec, the plan** (throwaway, untracked, deleted after the PR).

The split that matters most is **purpose**: HLD, LLD, and ADR are **decision & alignment** docs (for humans aligning); spec and plan are **AI-build** docs (spec-driven), fed from them.

So durable docs carry tests, tasks, and launch at **alignment altitude** — strategy, titles, cross-team deps — while the plan carries the **concrete** version — commit-tasks, file paths, test titles.

The spec/plan workflow — interviewing, drafting, refining — lives in the `brainstorm` skill, and their conventions and self-review gates in the `spec-driven-development` library; this skill only covers their shape and altitude.

## Who owns what (single source of truth)

When two docs could carry the same thing, this table says which one owns the full version; the others recap + link instead of repeating.

| Concern | Owner | Others |
|---|---|---|
| Why / business context | HLD (epic) · the spec (feature) | recap + link |
| Decision + alternatives | ADR; or HLD/LLD decision section / spec·plan log (minor) | recap + link the ADR |
| Structure, contracts, data model, de/para | LLD | recap + link the LLD |
| Diagrams — big-picture (C4L1, architecture; high-level flow/sequence/state) | HLD | recap + link, don't redraw |
| Diagrams — detailed (code/component design, data-model & endpoint schemas, detailed flow/sequence/state, corner/failure) | LLD | recap + link, don't redraw |
| Success metrics, UAT, test & launch strategy — high-level | HLD / LLD | spec/plan recap + link |
| Task breakdown — titles only (estimates, parallelization, cross-team deps) | HLD / LLD | plan expands to commit-tasks |
| Concrete testable acceptance criteria | the spec | HLD/LLD keep the high-level version + link |
| Test titles, commit-sized tasks, file paths, commit sketch | the plan | — |

Diagram *type* isn't the discriminator — altitude is: the same flow/sequence/state diagram can serve an HLD at big-picture level and an LLD at detail level.

## Relating docs: recap + link by file, let sections flex

When two docs relate, the referencing doc points to the other by **file path, URL, or named anchor — never by a section or page number**.

It adds a **brief recap** of what's there.

The recap is enough to read standalone; the link is the drill-down for readers who want the full detail.

Recap *and* link, never link alone and never a bare number.

A `§X` pointer rots when the target renumbers and forces a jump to understand; the inline recap keeps each doc readable on its own.

So related sections are **elastic**:

- References an upstream that already answers a section (context, requirements, a decision) → that section shrinks to *recap + link*. An LLD that references an HLD is smaller.

- Self-contained, no related upstream → those sections grow to carry the full content. An LLD with no HLD has a fuller Context and Requirements.

Applies to every pair that relates: HLD↔ADR, HLD↔LLD, LLD↔LLD, LLD↔ADR, HLD↔spec, LLD↔plan, spec↔plan.

## Within a doc: sections reference only what the reader already read

The rule above covers doc→doc pointers, which may point anywhere. This one covers section→section pointers inside a single doc, where reading is linear.

- **A section may reference only earlier sections** — the reader has read them; a forward reference demands a jump into unread territory mid-sentence.

- **The appendix is the only exception**: it is optional-reading lookup material, so any section may reference it.

- **Token refs count as references** — `(OQ-17)` / `(R-11)` may only be cited after their registry section; before it, state the fact inline without the token.
  - Item-to-item token refs inside the same registry section are fine: the section's roadmap already introduced every item.

- **Order sections knowns-first so refs flow backward**: Context → Requirements → Premises → Decisions → Risks → Open Questions → core solution (design, mappings, flows) → Appendix.
  - Unknowns cite the knowns that spawned them; the core solution cites everything; the HLD/LLD templates encode this order.

- **Circular pairs** (a premise and the risk it creates, an open question and its risk): the earlier item keeps only the inline recap — no token.
  - The later item carries the backward token.

- **A forward pointer must be linkless**: "detalhado adiante" / "detailed ahead" with no anchor, token, or section number — it signals detail is coming without demanding the jump.

- Applies to all five docs — ADR, HLD, LLD, spec, plan.

## RFC is a status, not a doc

An RFC is a doc *circulating for comments*, not a sixth document.

Put it as a `Status` on an HLD or ADR (`Draft → RFC / In Review → Accepted`) while you gather feedback.

Don't create a separate RFC artifact; it would duplicate the HLD.

## Rules of thumb

- **Durable docs carry only the alignment altitude** — task *titles*, test/launch *strategy*, success metrics — for estimates, parallelization, and cross-team deps.

- **File paths, commit-sized tasks, and concrete test titles live only in the throwaway plan** — they rot, and they belong with the build (plan + TaskList).

- **Code bodies live in neither** the design nor the plan — they live in the repo. The LLD holds interfaces/schemas (the contract); the plan holds file paths and tasks.

- **A decision you'll argue again in 6–12 months → ADR.** A minor one → a line in the spec/plan decision log; graduate it to an ADR if it grows teeth.

## Decisions, Premises, Risks, Open Questions — how to structure them

Durable docs (HLD, LLD) carry numbered Decisions, Premises, Risks, and Open Questions — use tokens (`D-`, `PR-`, `R-`, `OQ-`) as stable cross-reference anchors.
One item per heading, cluster by theme before ordering.

See [`references/dpro-structure.md`](./references/dpro-structure.md) for detailed rules on labeling, token ordering, burn-down lists, and roadmaps.

## The five docs at a glance

Shared mental model for which doc is which — not a step you need help running.

| Doc | Lifespan | Job |
|---|---|---|
| **ADR** | Durable | Decide — one significant decision + alternatives |
| **HLD** | Durable | Design (system / epic) — what & why across alternatives |
| **LLD** | Durable | Design (one component) — structure, contracts, data, de/para |
| **Spec** | Throwaway | Why / What — requirements + acceptance criteria, one feature |
| **Plan** | Throwaway | Build — tasks, files, commits, test titles, one feature |

**Significant** = hard to reverse OR cross-team blast radius.

Not significant (cheap to reverse AND contained) → skip durable docs, go straight to the spec → the plan.

Significant → write the durable doc, then still produce the spec → the plan downstream to execute.

```mermaid
flowchart TD
  start(["Change to make"]):::start
  q1{"Significant?<br/>hard to reverse OR cross-team blast radius"}
  q2{"What are you capturing?"}

  adr["ADR — one decision + alternatives<br/>(standalone if significant, else a section)"]
  hld["HLD — system / epic design<br/>what & why across alternatives"]
  lld["LLD — one component<br/>structure, contracts, data, de/para, diagrams"]

  spec["Spec (throwaway)<br/>why / what + acceptance criteria"]
  plan["Plan (throwaway)<br/>tasks, files, commits, test titles"]
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

- LLD — start from `assets/template-lld.md` (one component, implementation-ready: code design, data model, contracts, de/para mappings, error/concurrency, observability).
  - See `references/example-good-lld.md` for a full worked example (numbered premises/decisions/risks/open-questions with `PR-`/`D-`/`R-`/`OQ-` tokens, de/para mappings as the core, call-sequence diagram, source/destination schemas in the appendix).

  - The top comment block holds the HLD↔LLD boundary rule.

- The spec — do **not** improvise from this skill's altitude/ownership notes.
  - Read `~/.claude/skills/spec-driven-development/SKILL.md` (by path — it is not Skill-invocable) and populate its `assets/spec-template.md`.
  - Sections, in order: Background/Context, Goals and Success Metrics/KPIs, Context Diagram, User Stories.

  - Then Non-Functional and Technical Requirements, Testable Acceptance Criteria (`### AC-N:` BDD entries plus boundary/failure checklists), Open Questions, Functional Decisions log.

  - This skill owns only the spec's *altitude and ownership*; the section structure and self-review gates live in that library, and the interview workflow in `brainstorm`.

- The plan — same rule: read that same library by path and populate its `assets/plan-template.md`.
  - Sections: Technical Approach & High Level Architecture, General Flow, Test Design with its AC → test coverage list, structured Task Breakdown, PR Breakdown, Open Questions, Technical Decisions log.

  - Authoring a spec/plan from the altitude notes above instead of these templates is the known failure mode this route exists to prevent.

- Schema as JSONC — render request/response/event payloads as annotated JSONC (real values, each field tagged with type/required/constraints/description); copy `references/example-good-schema.jsonc`.
  See [`references/schema-jsonc-rules.md`](./references/schema-jsonc-rules.md) for line-length, description, and enum formatting rules.

- de/para (from → to) mapping — qualify every field by its system.
  - Prefix each field with its source/destination system (`pic.`, `sge.`, `hub.`, `crm.`, or `const` for a literal), so provenance stays clear when systems share field names.

  - Validate the mapping against a real production payload, not just the vendor's example — real data stress-tests edge cases the example misses before you finalize.

  - **If a field has no destination because that concept doesn't apply on the destination side, say so plainly — don't call it a gap.**
