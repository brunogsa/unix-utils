---
name: integrator-architecture
description: "Integrator architecture reference. USE when debugging Integrator routes/auth/downstream calls, looking up log groups or DBs, or answering any Integrator-internal question."
user-invocable: false
---

# Integrator Architecture

Integrator-specific architecture reference. This skill grows incrementally during debug sessions.

See also: @arco-architecture for the broader Arco ecosystem context.

---

## Repository

- **GitHub:** `arco-cv/arco2-integrator`
- **Local path:** `~/workspace/code/team-engineering/arco2-integrator`
- **Smoke tests:** `scripts/smoke-tests/`
- **OpenAPI specs:** `docs/integrator/`

---

## Request Routing

| Method | Path | Route |
|--------|------|-------|
| GET | Facade endpoints | API GW -> core (HTTP_PROXY + VPC Link, **middleware bypassed**) |
| POST | Facades, webhooks, invoices, cancellations | API GW -> middleware -> core (HTTP integration) |

**Consequence:** GET facade endpoints (kits, segmentos, xFiliais, WsTransportadoras, statusPedidos, etc.) have **no middleware logs** -- trace only in core.

---

## Authentication

- **100% at API Gateway level** (API key validation)
- Middleware does NOT perform auth
- If `integrationLatency` is `-` and `apiKey` is `-`: request rejected at API GW (no key provided)
- If `integrationLatency` > 0 and `apiKey` present: passed API GW auth, reached backend

---

## Downstream Calls

| Type | Mechanism |
|------|-----------|
| GET to legacy systems (Protheus) | **Synchronous** -- direct HTTP call from core |
| POST to legacy systems | **Asynchronous** -- via `integrator-http-caller-prod` Lambda |
| GET to OMS | **Synchronous** -- direct HTTP call from core |
| POST to OMS | **Asynchronous** -- via `integrator-sf-http-caller-prod` Lambda |

---

## TransactionId Mapping

- When caller omits `x-transaction-id` header, API GW `requestId` becomes `transactionId` in core/middleware logs
- Use this to trace requests across layers: API GW `requestId` = core `transactionId`

---

## Known Log Groups

| Log Group | Layer | Purpose |
|-----------|-------|---------|
| `API-Gateway-Execution-Logs_1ciiwix04k/prod` | 1st | API GW access logs. JSON: `status`, `resourcePath`, `path`, `httpMethod`, `ip`, `userAgent`, `apiKey`, `responseLatency`, `integrationLatency`. Check FIRST for HTTP status alarms. |
| `/aws/ecs/integrator-middleware-service/middleware` | 2nd (POST only) | Schema validation, forwards to core, logs request/response with transactionId. GET endpoints bypass this entirely. |
| `/aws/ecs/integrator-core-service/core` | 3rd | Business logic. GET requests to legacy made synchronously here. Trace by `transactionId`. |
| `/aws/lambda/integrator-http-caller-prod` | async | POST/async requests to legacy systems. GET requests do NOT appear here. |
| `/aws/lambda/integrator-sf-http-caller-prod` | async | POST/async requests to OMS. |
| `/aws/lambda/integrator-sf-notifier-prod` | async | Sales agreements and products synced to Salesforce (all Arco brands). |

---

## Log Filtering

**CloudWatch filter syntax (used by `--filter` in `aws-get-cloudwatch-logs`):**

- Exact match on JSON field: `{ $.status = 401 }`
- Substring match on any field: `{ $.* = %some-value% }` -- WARNING: matches ANY field, can produce false positives
- Combine conditions: `{ $.level = "error" && $.transactionId = "abc-123" }`
- String values need double quotes: `{ $.flow = "my-flow" }`
- Numeric values are bare: `{ $.status = 401 }`

**Filtering strategies per log group:**

- **API Gateway:** `{ $.status = 401 }`, `{ $.resourcePath = "/v1/..." }`, or combine
- **Middleware:** `{ $.level = "error" }`, `{ $.originPath = %endpoint% }`, or `{ $.transactionId = "id" }`
- **Core/Lambda:** `{ $.level = "error" }` as baseline, combine with `{ $.transactionId = "id" }`
- **sf-notifier:** look for agreement/product identifiers in message body

**Avoid:** `{ $.* = %value% }` with short numbers (like `401`, `500`) -- too many false positives.

---

## Progressive Time Window Strategy

Omit `--start-date` from `aws-get-cloudwatch-logs` to activate progressive mode automatically. It tries windows of 15m, 1h, 2h, 4h, 8h, 1d, 2d, 1w, 2w, 4w anchored from `--end-date` (or now), stopping at the first window with results.

---

## Known API Key Names

| Key Name | Caller |
|----------|--------|
| `integrator_api_plataforma_pedidos_api_key` | PDP (Plataforma de Pedidos) |

*More keys will be added as we discover them during debug sessions.*

---

## Databases

- **RDS / PostgreSQL** -- details to be filled
- **DynamoDB** -- details to be filled

---

## Known DLQ Names and Flows

*To be filled as we discover them during debug sessions.*
