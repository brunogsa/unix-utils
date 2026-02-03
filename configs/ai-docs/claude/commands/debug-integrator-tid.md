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

### Search Core Logs

Start with core -- this is where business logic and downstream calls live:

```bash
aws-get-cloudwatch-logs \
  --log-group '/aws/ecs/integrator-core-service/core' \
  --filter '{ $.transactionId = "<id>" }' \
  --stdout
```

**Quote the log entries found.** Then extract:
- Request method, path, flow
- Downstream calls and their responses (quote status codes and error payloads)
- Error messages, status codes
- Timestamps for timeline

### Search API Gateway Logs

If not found in core, or to get the entry point details:

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

### Search Middleware Logs (POST endpoints only)

Only if the endpoint uses POST routing (API GW -> middleware -> core):

```bash
aws-get-cloudwatch-logs \
  --log-group '/aws/ecs/integrator-middleware-service/middleware' \
  --filter '{ $.transactionId = "<id>" }' \
  --stdout
```

**Skip this for GET endpoints** -- they bypass middleware entirely (see @integrator-architecture routing).

### Search Async Lambda Logs

If the request triggered async downstream calls (POST to legacy or OMS):

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
