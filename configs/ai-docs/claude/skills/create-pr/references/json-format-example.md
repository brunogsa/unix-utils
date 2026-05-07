# JSON snippet format (referenced by SKILL.md "JSON snippets" rule)

Use `JSON.stringify(obj, null, 2)` style: each key on its own line, 2-space indentation, every nested object/array expanded vertically — including single-key objects. Only empty `[]` may stay on one line.

## Right shape

```json
{
  "data": [
    {
      "entity": "sales_agreement_product",
      "externalId": "all_skus-MTEST-EI-SAPB1-9961-2026-04-29",
      "payload": [
        {
          "salesAgreementId": "MTEST-EI-SAPB1-9961"
        }
      ]
    }
  ],
  "pagination": {
    "totalItems": 1
  }
}
```

## Wrong shapes (never inline objects)

- `{ "sku": "X" }` — single-key inline
- `{ "sku": "X", "id": "Y" }` — multi-key inline
- `"payload": [{ "sku": "X" }]` — inline inside array

Reviewers read top-down, not horizontally. Vertical expansion makes diffs reviewable line-by-line.
