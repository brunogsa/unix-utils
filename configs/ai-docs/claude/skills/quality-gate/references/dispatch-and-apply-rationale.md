# Dispatch and apply rationale

The reasoning behind two routing rules in `SKILL.md`. The rules themselves live there and bind without this file; read this only when someone questions why a leg or the apply step is shaped this way.

## Why each leg never spawns a nested reviewer

Each leg already is the fresh-context reviewer that the `refactor`, `auto-review`, and `test-sdd` skills would otherwise dispatch.

Nesting a reviewer inside it would spend one of the harness's three nesting levels on a second opinion nobody asked for.

The skills a leg invokes describe dispatching a reviewer, so without the explicit override the leg would follow that text literally. That is why `SKILL.md` tells the dispatcher to state the override in every leg's prompt.

## Why a flagged run never prompts on a multi-match

Either `--auto-solve` or `--report-only` marks a skill-dispatched run with nobody standing by. That is the same premise `SKILL.md` §6 uses to force `--no-ask`.

A prompt on a multi-match would stall the `/implement` tail indefinitely, so the run proceeds without that kind, exactly as a zero match resolves.

## Why applying belongs to `/address-verdicts`

`/address-verdicts` is the apply step for every `verdict_*.md` on disk, whoever wrote it. This skill decides which findings deserve a fix, and that skill owns how every fix lands.

Duplicating its loop here would let two copies of the lens routing, commit rule, and annotation format drift apart. A human could then no longer tell which copy their report followed.

## Why `/address-verdicts` runs in this session, not a subagent

This skill sits in `/implement`'s main session for the same reason.

`/address-verdicts` commits the `refactor` agent's work, and a permission prompt only renders in the main session. Its per-lens apply agents are already fresh-context subagents.

Wrapping it in another subagent would spend one of the three nesting levels on a layer that decides nothing.
