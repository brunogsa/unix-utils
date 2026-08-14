---
name: plan-status-markers
description: "Status-marker convention for a plan_<slug>.md task heading — [Doing]/[Done]/[Blocked]/[Deferred]/[Dropped]. Trigger: marking a plan task's progress, or asking what a marker means, in spec-driven-development, /implement, address-verdicts, or test-sdd"
disable-model-invocation: false
user-invocable: true
---

# Plan Status Markers

The status convention every `plan_<slug>.md` task heading follows — shared by `spec-driven-development`, `/implement`, `address-verdicts`, and `test-sdd`, so all four read and write the same marker.

## Placement

Status sits **right after the number, before any pre-existing tag** (e.g. a Jira ID): `### N. [Doing][JIRA-123] Title (...)`.

Omitted entirely in the initial (pending) state — a task with no marker hasn't started.

Single value, mutually exclusive — `[Blocked]` *replaces* `[Doing]`, never stacks with it.

Status is a file edit only, never committed — the plan stays session-scoped through implementation, per `spec-driven-development`.

## Semantics

- `[Doing]` — actively in progress this session (dispatched, not yet verified-done).
- `[Done]` — finished, verified, and committed.
- `[Blocked]` — external dependency unresolvable in this session. Pair with a `**QUESTION:**` marker naming what's needed to unblock.
- `[Deferred]` — deliberately postponed to a later session, but still planned.
- `[Dropped]` — decided not to do at all (scope reduction). Pair with `**DECISION (Task N):**` capturing the reason.

In all non-`[Done]` terminal states, do NOT leave partial code committed under a misleading status — either the commits stand as coherent work, or get reverted first.
