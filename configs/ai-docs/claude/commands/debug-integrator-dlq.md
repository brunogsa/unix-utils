# Debug Integrator DLQ

Investigate messages stuck in a Dead Letter Queue, extract identifiers, and trace the root cause.

## Usage

`/debug-integrator-dlq <dlq-name-or-url>`

Where `<dlq-name-or-url>` is either:
- Full SQS queue URL (e.g., `https://sqs.us-east-1.amazonaws.com/123456789/my-dlq`)
- DLQ name only (e.g., `my-dlq`) -- resolved to full URL internally

## Skills (auto-loaded)

- @integrator-architecture -- log groups, filtering syntax, known DLQs
- @arco-architecture -- brands, systems context
- @integrator-debug -- interaction model, self-improvement protocol

---

## Execution Steps

### Get DLQ Summary

Run a single command to get queue attributes and peek at messages (accepts name or URL):

```bash
aws-get-dlq-summary --queue-name <dlq-name> --peek 5
```

**Quote the full output** (attributes + peeked message payloads + extracted identifiers).

Share initial hypothesis based on the numbers and message patterns (same error? same flow? same time window?).

### Trace via Core Logs

For the most representative message(s), search core logs by transactionId (progressive mode auto-finds the time window):

```bash
aws-get-cloudwatch-logs \
  --log-group '/aws/ecs/integrator-core-service/core' \
  --filter '{ $.transactionId = "<id>" }' \
  --stdout
```

Also check the relevant Lambda log group if the flow is async:
- `integrator-http-caller-prod` for legacy system calls
- `integrator-sf-http-caller-prod` for OMS calls

### Check for Related Errors

Search for broader error patterns:

```bash
aws-get-cloudwatch-logs \
  --log-group '/aws/ecs/integrator-core-service/core' \
  --filter '{ $.level = "error" && $.flow = "<flow>" }' \
  --stdout
```

### Deeper Tracing

If individual transaction tracing is needed, suggest delegating to `/debug-integrator-tid` with the extracted transactionId.

### Analyze and Present Findings

Follow the findings summary template from @integrator-debug. Additionally report:
- Total messages affected
- Whether messages share a common cause
- Whether the source queue's consumer is still running
- Recommended action (redrive, fix and redrive, manual intervention)

---

## Self-Improvement

Follow the self-improvement protocol from @integrator-debug. During DLQ investigation, watch for:
- New DLQ name -> flow mappings
- Message body structure patterns
- Common root causes per DLQ
