---
description: "AWS CloudWatch log fetching utility with pagination, filtering, and multiple output modes"
user-invocable: false
---

# AWS Tools

Shell scripts at `~/oh-my-zsh/func-utilities/` for AWS operations.

## Scripts

### aws-get-cloudwatch-logs
Fetches and paginates CloudWatch logs with filtering support.

```
AWS_PROFILE=<profile> aws-get-cloudwatch-logs \
  --log-group <name> \
  --start-date <utc-iso8601> \
  [--end-date <utc-iso8601>] \
  [--filter <pattern>] \
  [--output <file>] \
  [--stdout]
```

**Parameters:**
- `--log-group` (required) -- CloudWatch log group name
- `--start-date` (required) -- UTC ISO8601 (e.g., `2025-01-15T10:30:00Z`)
- `--end-date` -- defaults to now
- `--filter` -- CloudWatch filter pattern (e.g., `{ $.level = "error" }`)
- `--output <file>` -- append results to specific file
- `--stdout` -- print to stdout only, no debug info

**Environment:** `AWS_PROFILE` (required)

**Examples:**
```bash
AWS_PROFILE=arco-stage aws-get-cloudwatch-logs \
  --log-group '/aws/ecs/my-service/core' \
  --start-date '2025-01-15T10:00:00Z' \
  --end-date '2025-01-15T12:00:00Z' \
  --filter '{ $.flow = "my-flow" && $.level = "error" }'
```
