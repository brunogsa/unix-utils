---
description: "AWS shell utilities: CloudWatch logs, API key lookup, DLQ summary, Integrator cross-service logs"
user-invocable: false
---

# AWS Tools

Shell scripts at `~/oh-my-zsh/commands/` for AWS operations.

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

### jsonl-distribution-table.js
Generic JSONL distribution table. Groups entries by caller-specified fields, outputs an aligned table with a COUNT column sorted by count descending.

```bash
node ~/oh-my-zsh/commands/jsonl-distribution-table.js --fields field1,field2,... [file]
```

Reads from `/dev/stdin` when no file is given. Composable via pipe:
```bash
AWS_PROFILE=arco-prod aws-get-cloudwatch-logs \
  --log-group 'API-Gateway-Execution-Logs_1ciiwix04k/prod' \
  --filter '{ $.status = 401 }' \
  --stdout \
| node ~/oh-my-zsh/commands/jsonl-distribution-table.js --fields httpMethod,resourcePath,status,apiKey
```

### jsonl-merge-and-sort-by-field.js
Generic JSONL merge and sort. Reads multiple JSONL files, sorts all entries by a specified field, outputs merged JSONL to stdout.

```bash
node ~/oh-my-zsh/commands/jsonl-merge-and-sort-by-field.js --sort-field <field> [--desc] <file1> [file2] ...
```

Handles numeric, ISO8601, and string values. Entries missing the sort field are placed at the end.

```bash
node ~/oh-my-zsh/commands/jsonl-merge-and-sort-by-field.js --sort-field timestamp f1.jsonl f2.jsonl
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

### aws-get-integrator-logs
Fetches logs from all 6 Integrator log groups in parallel, merges results into a single JSONL output sorted by timestamp. Each entry gets an injected `__source` field with the log group label.

```
AWS_PROFILE=<profile> aws-get-integrator-logs \
  [--start-date <utc-iso8601>] \
  [--end-date <utc-iso8601>] \
  [--filter <pattern>] \
  [--output <file>] \
  [--stdout] \
  [--exclude <label>...]
```

**Parameters:**
- `--start-date` -- UTC ISO8601. When omitted, uses progressive mode (same as `aws-get-cloudwatch-logs`)
- `--end-date` -- defaults to now
- `--filter` -- CloudWatch filter pattern
- `--output <file>` -- write merged output to file
- `--stdout` -- print merged JSONL to stdout
- `--exclude` -- skip specific log groups by label (space-separated)

**Log group labels:** `apigw`, `middleware`, `core`, `http-caller`, `sf-http-caller`, `sf-notifier`

**Environment:** `AWS_PROFILE` (required). Requires `node.js`.

**Helpers:** `jsonl-merge-and-sort-by-field.js` (merge + sort), `jq` (injects `__source` label per log group).

**Examples:**
```bash
# Trace a transactionId across all layers:
AWS_PROFILE=arco-prod aws-get-integrator-logs \
  --filter '{ $.transactionId = "abc-123" || $.requestId = "abc-123" }' \
  --stdout

# Skip API GW and sf-notifier:
AWS_PROFILE=arco-prod aws-get-integrator-logs \
  --filter '{ $.transactionId = "abc-123" }' \
  --exclude apigw sf-notifier \
  --stdout
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
