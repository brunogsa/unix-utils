# Light section set — the trimmed spec and plan

Read this only when the caller asks for the **light** section set. The default is the full templates in `assets/`, and a caller that says nothing gets those.

`brainstorm` resolves this choice in its pre-flight and passes it to the agent that writes each document, so this file is read inside that agent's context — never by the orchestrating session.

## The rule that decides membership

Light keeps every section a deterministic gate parses, plus the sections that carry decisions. It drops the sections that exist to brief a reader who doesn't already know the change.

Why that line and not a shorter one: the gates are what make a plan mechanically trustworthy, so trimming one turns a lean document into an unverified one.
The briefing sections are the ones a small, well-understood change can afford to lose, because the ACs and the task breakdown still say what to build.

## Omit the heading, don't write `N/A`

For a dropped section, leave the heading out of the file entirely — do not write the template's `N/A — <reason>` escape.

Why: the escape exists so a full document can record that a section was considered and didn't apply.
Light mode already declared that up front, so repeating it per section restores the very headings the mode was chosen to remove.

## spec_<slug>.md

**Keep**: Background / Context · Testable Acceptance Criteria (including both coverage checklists) · Open Questions · Functional Decisions.

**Drop**: Context Diagram · Goals and Success Metrics / KPIs · User Stories · Non-Functional and Technical Requirements.

Keep Background to a short paragraph — in light mode it absorbs whatever outcome or constraint the dropped sections would have carried.

**The two coverage checklists stay, fully instantiated.** They are the output of the interview's corner-case and failure-mode probing, so dropping them would discard the most expensive thing the interview produced.
Their existing per-checklist opt-out still applies on its own merits, and light mode is never a reason to reach for it.

## plan_<slug>.md

**Keep**: Technical Approach & High Level Architecture · Reuse report · Test Design · Task Breakdown · PR Breakdown · Open Questions · Technical Decisions.

**Drop**: General Flow · Side-effect report · Failure Handling & Consistency.

Technical Approach may run to a few lines with no diagram — its `N/A` escape for the diagram alone still applies, since the section itself is kept.

Keep the Reuse report even though no gate parses it: it is usually two bullets, and it is the only place the plan records what existing code was considered and rejected.

**PR Breakdown stays even when it only reads `Single PR.`** — `scripts/check-pr-dag.sh` needs that literal escape to pass, and a missing section is not the same thing.

## What light does not change

Every self-review gate still runs, deterministic and judged alike. Light removes prose a human reads, never a check.

The one adjustment belongs to the reviewer, not the author: a section this file drops is absent by design, so its absence is never a finding.
`references/self-review-checks.md` states that where the qualitative pass would otherwise flag it.
