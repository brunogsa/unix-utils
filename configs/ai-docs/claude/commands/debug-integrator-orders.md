# Debug Integrator Orders

Trace one or more orders through Integrator by externalId or externalOrderId, checking all stages from ingestion through invoice delivery.

## Usage

`/debug-integrator-orders <order-ids...>`

Where `<order-ids...>` is one or more order identifiers, space-separated. Accepted formats:
- Prefixed: `SAE-ESKOLARE-967006100948-02`
- Numeric: `967006100948-02`

## Skills (auto-loaded)

- @integrator-architecture -- log groups, filtering syntax, downstream calls
- @arco-architecture -- brands, order/invoice flows per brand
- @integrator-debug -- interaction model, self-improvement protocol

---

## Execution Steps

### Identify Order Format and Brand

For each provided ID, determine:
- Is it an `externalId` (prefixed, e.g., `SAE-ESKOLARE-967006100948-02`)?
- Is it an `externalOrderId` (numeric, e.g., `967006100948-02`)?
- Extract brand from prefix if available (SAE, SAS, IS, etc.)
- Based on brand, determine which flows Integrator handles (see @arco-architecture order/invoice flows)

### Search Core Logs by Order ID

For each order, search core logs using substring match on the identifier:

```bash
aws-get-cloudwatch-logs \
  --log-group '/aws/ecs/integrator-core-service/core' \
  --filter '{ $.* = %<order-id>% }' \
  --stdout
```

**Note:** Substring match (`%value%`) is acceptable here because order IDs are long enough to avoid false positives. If the ID is short, prefer exact field match: `{ $.externalId = "<id>" }` or `{ $.externalOrderId = "<id>" }`.

**Quote the matching log entries.** From results, extract:
- `transactionId` for each occurrence
- `flow` name
- Status and error messages (quote the exact error payloads)
- Timestamps

### Identify Flow and Queue

Based on log entries, determine:
- Which flow handled this order
- Which queue/topic was involved
- Whether the order was processed synchronously or asynchronously

### Trace Each Transaction

For each unique `transactionId` found in the core logs, delegate to `/debug-integrator-tid` for the full cross-layer lifecycle (API GW, middleware, core, async lambdas).

If multiple orders share the same transactionId, note this (batch processing).

### Check Invoice Leg

Orders have a return path: OMS sends invoices back through Integrator to legacy ERPs.

- **SAS:** OMS -> Integrator -> Protheus SAS
- **NSE:** OMS -> Integrator -> SAP1
- **SAE:** OMS -> SAP4 directly (no Integrator involvement)

If the brand involves Integrator for invoices, search for invoice-related logs:

```bash
aws-get-cloudwatch-logs \
  --log-group '/aws/ecs/integrator-core-service/core' \
  --filter '{ $.* = %<order-id>% && $.* = %invoice% }' \
  --stdout
```

### Check for DLQ Messages

If the order appears to have failed at any stage, check related DLQs:

```bash
aws-get-dlq-summary --queue-name <dlq-name> --peek 5
```

Search the output for the order ID. If DLQ investigation is needed, suggest delegating to `/debug-integrator-dlq`.

### Analyze and Present Findings

Follow the findings summary template from @integrator-debug. For each order, additionally report:

- **Order stage:** ingested / delivered to OMS / invoice received / invoice delivered to ERP / failed at [stage]
- **Timeline:** ingestion -> OMS delivery -> invoice receipt -> ERP delivery (or failure point)
- **Invoice status:** delivered / pending / failed / N/A (SAE)
- **Related orders:** if batch, list all orders in the same batch

---

## Self-Improvement

Follow the self-improvement protocol from @integrator-debug. During order tracing, watch for:
- Order ID format patterns per brand
- Flow name -> order type mappings
- Invoice flow patterns and log fields
- Common order/invoice failure patterns
