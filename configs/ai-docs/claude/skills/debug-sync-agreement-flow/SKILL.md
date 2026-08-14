---
name: debug-sync-agreement-flow
description: Trace a contract through the PIC → ERP sales-agreement sync, fetch its CloudWatch payloads into one CWD notes file, and optionally post it as a Jira comment. Use for /debug-sync-agreement-flow, a contract that failed to sync, or an ITGD sync ticket.
---

# Debug Sync Agreement Flow

Traces one contract through the PIC → ERP sales-agreement sync and fetches the payloads each hop
exchanged, so the failure can be read off the wire instead of inferred.

```
/debug-sync-agreement-flow <contractId>
```

`<contractId>` is any id that appears in the log lines — the PIC contract `id`, a `versaoId`, or the
ERP `absID`/`idContratoERP`. It is a discovery key for a substring filter, not a lookup key, so an id
from any hop works.

**The deliverable is one notes file in the repo root**, written for the user to read, not a temp
scratch dump. Posting it to Jira is a separate, opt-in step (see near the end).

This skill is a *process*, not a knowledge base of this flow's internals. It does not catalog log
message strings, queue names, or error classes — those live in the code and are cheap to grep fresh
each run; baking them in here would just go stale the next time the code changes. You are in the repo
with the source available, so read it directly whenever a payload needs explaining.

## General shape (stable enough to state, not so detailed it goes stale)

```
PIC  --webhook-->  integrator-middleware (validates against OpenAPI)
                        │
                        ▼
                     core: sync-sales-agreement-pic (routes by brand to an ERP target)
                        │
                        ▼
                  ERP-specific SQS queue
                        │
                        ▼
        core: sync-sales-agreement-pic-<erp> consumer/use-case
              (translates the payload, calls the ERP, then calls PIC back)
```

Every ERP target (SAP B1, Oracle EBS, Raízes, SGE, ...) follows this same shape; only the outbound
call, its error shape, and the field mapping differ. When you need those specifics for the ERP you're
debugging, grep `core/src/modules/sales-agreements/sync-sales-agreement-pic-<erp>/` and
`core/src/modules/sales-agreements/shared/pic/erp-target.resolver.ts` — don't rely on a doc to have
kept up.

## Scope

Run from the integrator repo root — the skill invokes a repo script.

First time only: `cd scripts/rotation-support/aws/logs && yarn install`.

## Procedure

### 1. Resolve inputs

**Ask which AWS profile to use. Never assume one.** Profile names vary per machine — the project docs
say `<env>.CLOUD_ADMIN`, but this machine uses `arco-stage`/`arco-qa`/`arco-prod`. Offer what is
actually configured, and confirm which environment it points at:

```bash
aws configure list-profiles
aws sts get-caller-identity --profile <profile>   # fails ⇒ aws sso login --profile <profile>
```

Also settle the time window. If the user gives none, default to the last 7 days and say so — a window
that silently excludes the failure looks identical to a contract that never synced.

Ask for `<contractId>` if the invocation omitted it.

### 2. Fetch one CSV per log group

Query wide on `<contractId>` — you do not know the `transactionId` yet.

```bash
AWS_PROFILE=<profile> node scripts/rotation-support/aws/logs/get-logs-from-insights.js \
  --log-groups "/aws/ecs/integrator-core-service/core" \
  --query "fields @timestamp, @message, @log, level, message, transactionId | filter @message like /<contractId>/" \
  --start-date "<utc-iso8601>Z" --end-date "<utc-iso8601>Z" \
  --output-csv core.csv
```

Repeat for `/aws/ecs/integrator-middleware-service/middleware` into a separate CSV — the inbound PIC
webhook payload lives there, not in core. The outbound request/response to the ERP 1.0 and the PIC
callback both live in core. Write both CSVs outside the repo (they're working files, not the
deliverable).

### 3. Discover the transaction ids

```bash
~/.claude/skills/debug-sync-agreement-flow/scripts/extract-payloads.py \
  --csv core.csv --list-transactions --grep <contractId>
```

One failure usually spans several transactions — the create that succeeded and the update that failed
are separate webhooks with separate ids. Notes covering only the failing one hide when the divergence
was introduced, so carry every transaction that bears on the conclusion. Expect noise: a wide substring
match can catch unrelated flows that happen to share digits with `<contractId>` — cross-check each hit
against a field that's actually specific (e.g. `idContratoERP`) before trusting it.

### 4. Extract each transaction's payloads

```bash
~/.claude/skills/debug-sync-agreement-flow/scripts/extract-payloads.py \
  --csv core.csv --middleware-csv middleware.csv \
  --transaction-id <tid>
```

This prints one `###section###` header per payload with pretty JSON (`indent=2`) underneath — paste
each body straight into a fenced ` ```json ` block in the notes file, unedited.

Don't reach for `--trim-field` by default — it replaces a bulky array with a count note, and it's easy
to trim exactly the field the investigation is about. Only add it once you know a specific array is
irrelevant noise. A missing-section warning on stderr is signal: no `erp_response` is exactly what a
failed call looks like.

### 5. Read the code for the "why"

Once the payloads show *what* diverged (a field present on the webhook but absent from the ERP
request, an unexpected error body, etc.), find *why* by reading the actual module for that ERP target —
its mapper, use-case, and any custom error classes — plus `git log`/`git show` on the mapper if a
recent change looks implicated. Don't guess from memory or from a prior debug session; the code is
right there and it's the ground truth.

### 6. Write the notes file

Write one file to the repo root: `<contractId>-sync-notes.md`, or `<ticket>-log-evidence.md` when the
investigation came from a ticket. This is the deliverable — it belongs where the user will read it, not
in a temp directory, and it doesn't get a separate "polish" pass afterward.

Use the structure in [Notes file layout](#notes-file-layout).

### 7. Re-verify every load-bearing field against the raw CSV

Before showing anything, list every field the conclusion rests on, then re-read each one from the raw
CSV rather than from your own notes. Report the list and its outcome.

This step exists because it has already caught a wrong claim that was one approval away from being
permanent on a ticket: a notes file asserted a field was identical across two contract versions when
the raw payloads had it changing. Anything a reader would act on gets re-read.

Fixing the underlying bug, if one is confirmed, is a separate follow-up — not a step of this skill.

### 8. Offer the Jira post — opt-in

Hand over the notes file, then ask **once** whether to post it as a comment, and to which ticket.

Default to not posting. Stopping with the file is a complete outcome, not a partial one. A Jira
comment is visible to the whole team the moment it lands and cannot be unsent, so:

- Never post without an explicit yes.
- Approval to investigate is not approval to post.
- Approval on one ticket is not approval on the next.

If the answer is yes, check `JIRA_URL`, `JIRA_EMAIL` and `JIRA_API_TOKEN` are exported, then validate
the conversion before sending — a warning here means formatting would be silently lost:

```bash
~/.claude/skills/debug-sync-agreement-flow/scripts/post-jira-comment.sh <TICKET> <file>.md --dry-run
```

### 9. Post, then report

```bash
~/.claude/skills/debug-sync-agreement-flow/scripts/post-jira-comment.sh <TICKET> <file>.md
```

Report the comment id and URL it prints. On failure, report the HTTP status and body verbatim — never
retry silently.

## Notes file layout

Write it in the language of the ticket or the reader (Portuguese for ITGD tickets). This doubles as
the Jira comment body, so it must survive the ADF conversion — see the constraint below.

````markdown
# Evidências de logs (AWS <Env>) — causa raiz e payloads completos

## Causa raiz

<one paragraph: what the payloads show, which commit/PR if one is implicated, and why the symptom follows>

## Transação CREATE — <timestamp>, transactionId `<tid>`

**Payload recebido do PIC:**

```json
<pretty json>
```

**Requisição enviada ao <ERP>:**

```json
<pretty json>
```

**Resposta do <ERP>:**

```json
<pretty json>
```

**Callback enviado ao PIC:**

```json
<pretty json>
```

**Resposta do PIC ao callback:**

```json
<pretty json>
```

## Transação UPDATE — <timestamp>, transactionId `<tid>`

<same shape as CREATE — swap "Resposta do <ERP>" for "Erro retornado pelo <ERP>" when the call failed>

## Conclusão

<what the payloads prove, and what still needs deciding — never invent a fix that was not agreed>
````

### Why payloads are pretty JSON in fenced blocks

The Jira v3 API takes ADF. The bundled converter (`build-adf-payload.py`) turns a fenced ` ```json ` block into
a real ADF `codeBlock` node, so multi-line, indented JSON survives the conversion and renders as a
proper Jira code block — no manual minifying needed. Headings, paragraphs, bullet/numbered lists,
fenced code blocks, and inline `**bold**` / `` `code` `` / `[text](url)` are all supported; tables,
blockquotes, nested lists, and images still degrade to plain paragraphs **silently**, so keep the
notes file to the supported set.
