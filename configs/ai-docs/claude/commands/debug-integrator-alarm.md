# Debug Integrator Alarm

Receive a Slack alarm text, validate environment, and systematically debug using AWS CLI and CloudWatch logs.

## Usage

`/debug-integrator-alarm <alarm-text>`

Where `<alarm-text>` is the full alarm message copied from Slack.

## Skills (auto-loaded)

- @integrator-architecture -- routing, auth, log groups, filtering syntax
- @arco-architecture -- brands, systems, sources of truth
- @integrator-debug -- interaction model, self-improvement protocol, common tools

---

## Execution Steps

### Identify the CloudWatch Alarm

Parse the alarm text to extract alarm name, metric, namespace, queue/topic/service references.

```bash
aws cloudwatch describe-alarms --state-value ALARM --output json
```

Cross-reference active alarms with the alarm text to identify which CloudWatch alarm we're dealing with. Present the match and explain reasoning. **Quote the matching alarm JSON.**

### Branch by Alarm Type

**If queue/topic related (SQS):**
- Inform which queue/topic is involved
- Get DLQ summary (attributes + peek):
  ```bash
  aws-get-dlq-summary --queue-name <dlq-name> --peek 5
  ```
- **Quote the output** (attributes and extracted identifiers from peeked messages).
- Share hypothesis before proceeding
- Suggest delegating to `/debug-integrator-dlq` if the DLQ investigation becomes the main focus

**If Lambda/ECS related:**
- Identify which Lambda/ECS service triggered the alarm
- Note the relevant log group from @integrator-architecture
- Explain what to expect in the logs

**If HTTP status code alarm (e.g., 401, 500, 4xx, 5xx):**
- Alarm names starting with `integrator-api-gw-prod-` are API Gateway metrics
- Identify endpoint path and HTTP status from alarm name/description
- Check OpenAPI in `docs/integrator/` for routing (HTTP_PROXY vs HTTP)

- **Step A -- Bird's-eye view:**
  ```bash
  AWS_PROFILE=arco-prod aws-get-status-distribution-api-gw \
    --log-group 'API-Gateway-Execution-Logs_1ciiwix04k/prod' \
    --status <code>
  ```
  Shows all affected endpoints and callers sorted by volume. Use to prioritize. **Quote the distribution table.**

- **Step B -- Drill into API Gateway logs:**
  - Filter: `{ $.status = <code> && $.resourcePath = "/v1/..." }`
  - Key fields: `apiKey` (caller), `integrationLatency` (did it reach backend?), `ip`, `userAgent`, `responseLength`. **Quote sample log entries showing these fields.**
  - If `integrationLatency` = `-`: API GW level rejection (see @integrator-architecture auth section)
  - If `integrationLatency` > 0: request reached backend, status came from downstream

- **Step C -- Identify caller by API key:**
  ```bash
  aws-get-api-keys --suffix '<last6chars>'
  ```

- **Step D -- Trace through core logs** (when `integrationLatency` > 0):
  - Filter core logs by transactionId (= API GW requestId, see @integrator-architecture)
  - Look for: downstream HTTP call errors, status codes, retry attempts
  - Suggest delegating to `/debug-integrator-tid` for deep tracing

- **401 interpretation:**
  - With `integrationLatency` > 0: downstream legacy auth failure (e.g., expired credentials in Secrets Manager like `PROTHEUS_SAE_AUTH`). Core retries with fresh token on 401; if both fail, secret is stale.
  - With `integrationLatency` = `-`: API GW auth issue (missing/invalid API key)
- **5xx interpretation:** look for transactionId in core logs for actual error

### Log Search with Progressive Windows

Omit `--start-date` to use progressive mode (auto-widens from 15m to ~1 month):

```bash
aws-get-cloudwatch-logs \
  --log-group '<log-group>' \
  --filter '{ $.level = "error" && $.transactionId = "<id>" }' \
  --stdout
```

- Always filter by `level = "error"` first
- Use identifiers from DLQ messages when available
- Search across relevant log groups (see @integrator-architecture)

### Check Recent Deployments

Follow the deployment check from @integrator-debug.

### Search the Codebase

Follow the codebase investigation from @integrator-debug.

### Analyze and Present Findings

Follow the findings summary template from @integrator-debug.

---

## Self-Improvement

Follow the self-improvement protocol from @integrator-debug. During this alarm investigation, watch for new insights about:
- API key -> caller mappings
- DLQ -> flow mappings
- Log patterns and filtering strategies
- Alarm-specific debugging shortcuts
