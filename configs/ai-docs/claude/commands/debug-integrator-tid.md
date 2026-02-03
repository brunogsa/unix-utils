# Debug Integrator Transaction

Trace a single request's full lifecycle across all Integrator layers using a transactionId or API Gateway requestId.

## Usage

`/debug-integrator-tid <transaction-id-or-request-id>`

Where `<transaction-id-or-request-id>` is either:
- A `transactionId` from core/middleware logs
- An API Gateway `requestId` (same value when caller omits `x-transaction-id`)

Both formats accepted -- they map to the same identifier (see @integrator-architecture TransactionId Mapping).

## Skills (auto-loaded)

- @integrator-architecture -- routing, log groups, transactionId mapping
- @arco-architecture -- brands, systems context
- @integrator-debug -- interaction model, self-improvement protocol

---

## Execution Steps

### Search All Layers at Once

Start with a cross-service search to get the full picture:

```bash
AWS_PROFILE=arco-prod aws-get-integrator-logs \
  --filter '{ $.transactionId = "<id>" || $.requestId = "<id>" }' \
  --stdout
```

This fetches from all 6 Integrator log groups in parallel, merges by timestamp, and injects `__source` per entry. **Quote the merged output.**

Extract from results:
- Which layers were involved (`__source` field)
- Request method, path, flow
- Downstream calls and their responses (quote status codes and error payloads)
- Error messages, status codes
- Timestamps for timeline

### Drill Into Specific Layers

If the cross-service search is too broad or you need more context around specific entries, drill into individual log groups:

**Core** (business logic and downstream calls):
```bash
aws-get-cloudwatch-logs \
  --log-group '/aws/ecs/integrator-core-service/core' \
  --filter '{ $.transactionId = "<id>" }' \
  --stdout
```

**API Gateway** (entry point details -- uses `requestId`, not `transactionId`):
```bash
aws-get-cloudwatch-logs \
  --log-group 'API-Gateway-Execution-Logs_1ciiwix04k/prod' \
  --filter '{ $.requestId = "<id>" }' \
  --stdout
```

Extract: `status`, `resourcePath`, `httpMethod`, `apiKey`, `integrationLatency`, `ip`. **Quote the API GW log entry.**

If `apiKey` is present, identify the caller:
```bash
aws-get-api-keys --suffix '<last6chars>'
```

**Middleware** (POST endpoints only -- skip for GET, see @integrator-architecture routing):
```bash
aws-get-cloudwatch-logs \
  --log-group '/aws/ecs/integrator-middleware-service/middleware' \
  --filter '{ $.transactionId = "<id>" }' \
  --stdout
```

**Async Lambdas** (if request triggered downstream calls):
```bash
# Legacy systems
aws-get-cloudwatch-logs \
  --log-group '/aws/lambda/integrator-http-caller-prod' \
  --filter '{ $.transactionId = "<id>" }' \
  --stdout

# OMS (Salesforce)
aws-get-cloudwatch-logs \
  --log-group '/aws/lambda/integrator-sf-http-caller-prod' \
  --filter '{ $.transactionId = "<id>" }' \
  --stdout
```

### Reconstruct Timeline

Build a chronological timeline of the request:

1. API Gateway entry (timestamp, caller, endpoint)
2. Middleware processing (if POST)
3. Core processing (business logic, downstream calls)
4. Async Lambda execution (if applicable)
5. Final response / error

Present the timeline with quoted evidence (log lines, status codes, error messages) at each step. Highlight where things went wrong.

### Codebase Investigation

If the error is unclear from logs alone, follow the codebase investigation from @integrator-debug. Search for:
- The endpoint handler
- The downstream client making the failed call
- Error handling and retry logic
- Configuration and secrets involved

### Analyze and Present Findings

Follow the findings summary template from @integrator-debug.

---

## Self-Improvement

Follow the self-improvement protocol from @integrator-debug. During transaction tracing, watch for:
- New log patterns or fields
- New transactionId propagation paths
- Retry behavior patterns
