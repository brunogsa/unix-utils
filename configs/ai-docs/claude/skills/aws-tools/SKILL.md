---
description: "AWS shell utilities: CloudWatch logs, API Gateway distribution, API key lookup, DLQ summary"
user-invocable: false
---

# AWS Tools

Shell scripts at `~/oh-my-zsh/func-utilities/` for AWS operations.

## Scripts

### aws-get-cloudwatch-logs
Fetches and paginates CloudWatch logs with filtering support. Supports progressive time windows when `--start-date` is omitted.

```
AWS_PROFILE=<profile> aws-get-cloudwatch-logs \
  --log-group <name> \
  [--start-date <utc-iso8601>] \
  [--end-date <utc-iso8601>] \
  [--filter <pattern>] \
  [--output <file>] \
  [--stdout]
```

**Parameters:**
- `--log-group` (required) -- CloudWatch log group name
- `--start-date` -- UTC ISO8601 (e.g., `2025-01-15T10:30:00Z`). When omitted, uses progressive mode: tries 15m, 1h, 2h, 4h, 8h, 1d, 2d, 1w, 2w, 4w windows anchored from `--end-date` (or now), stopping at the first window with results.
- `--end-date` -- defaults to now
- `--filter` -- CloudWatch filter pattern (e.g., `{ $.level = "error" }`)
- `--output <file>` -- append results to specific file
- `--stdout` -- print to stdout only, no debug info

**Environment:** `AWS_PROFILE` (required)

**Examples:**
```bash
# Explicit time range:
AWS_PROFILE=arco-stage aws-get-cloudwatch-logs \
  --log-group '/aws/ecs/my-service/core' \
  --start-date '2025-01-15T10:00:00Z' \
  --end-date '2025-01-15T12:00:00Z' \
  --filter '{ $.flow = "my-flow" && $.level = "error" }'

# Progressive mode (auto-finds the right time window):
AWS_PROFILE=arco-prod aws-get-cloudwatch-logs \
  --log-group '/aws/ecs/integrator-core-service/core' \
  --filter '{ $.level = "error" }' \
  --stdout
```

### aws-get-status-distribution-api-gw
Fetches API Gateway logs and outputs a distribution table grouped by endpoint, HTTP status, and caller (API key).

```
AWS_PROFILE=<profile> aws-get-status-distribution-api-gw \
  --log-group <name> \
  [--start-date <utc-iso8601>] \
  [--end-date <utc-iso8601>] \
  [--status <code>] \
  [--path <resource-path>]
```

**Parameters:**
- `--log-group` (required) -- API Gateway log group name
- `--start-date` -- UTC ISO8601 (defaults to start of today UTC)
- `--end-date` -- defaults to now
- `--status` -- filter by HTTP status code (e.g., `401`)
- `--path` -- filter by resourcePath (exact match)

**Environment:** `AWS_PROFILE` (required)

**Output:** aligned table with columns `METHOD`, `PATH`, `STATUS`, `API_KEY` (last 6 chars), `COUNT`, sorted by count descending.

**Helper:** `apigw-distribution-table.js` (same directory) -- Node.js script that parses JSONL and produces the table.

**Examples:**
```bash
AWS_PROFILE=arco-prod aws-get-status-distribution-api-gw \
  --log-group 'API-Gateway-Execution-Logs_1ciiwix04k/prod' \
  --status 401

AWS_PROFILE=arco-prod aws-get-status-distribution-api-gw \
  --log-group 'API-Gateway-Execution-Logs_1ciiwix04k/prod' \
  --status 401 --path '/v1/facades/sae/protheus/kits'
```

### aws-get-api-keys
Lists API Gateway API keys with their last 6 characters. Optionally filters by key value suffix.

```
AWS_PROFILE=<profile> aws-get-api-keys [--suffix <last-N-chars>]
```

**Parameters:**
- `--suffix` -- filter keys by value suffix (e.g., last 6 chars from API GW logs)

**Environment:** `AWS_PROFILE` (required). Requires `jq`.

**Output:** table with columns `NAME`, `LAST_6_CHARS`, `DESCRIPTION`.

**Examples:**
```bash
AWS_PROFILE=arco-prod aws-get-api-keys
AWS_PROFILE=arco-prod aws-get-api-keys --suffix 'xY3k9z'
```

### aws-get-dlq-summary
Gets DLQ queue attributes and peeks at messages with automatic identifier extraction. Handles both standard and FIFO queues (FIFO limited to 1 message peek). SNS-wrapped messages are automatically unwrapped.

```
AWS_PROFILE=<profile> aws-get-dlq-summary \
  --queue-url <url> | --queue-name <name> \
  [--peek <N>]
```

**Parameters:**
- `--queue-url` -- full SQS queue URL (mutually exclusive with `--queue-name`)
- `--queue-name` -- SQS queue name, resolved to URL internally
- `--peek <N>` -- number of messages to peek (default: 1, max: 10; FIFO: always 1)

**Environment:** `AWS_PROFILE` (required). Requires `jq`.

**Output:** queue attributes (message count, in-flight, oldest age in human-readable format) + per message: full JSON payload and extracted identifiers (`transactionId`, `externalId`, `externalOrderId`, `docNumber`, `flow`).

**Examples:**
```bash
AWS_PROFILE=arco-prod aws-get-dlq-summary --queue-name 'my-service-dlq'
AWS_PROFILE=arco-prod aws-get-dlq-summary --queue-url 'https://sqs.us-east-1.amazonaws.com/123456789/my-dlq' --peek 5
```
