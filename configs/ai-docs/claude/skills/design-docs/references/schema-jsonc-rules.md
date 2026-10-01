# Schema as JSONC — Formatting Rules

When a doc shows a request/response/event payload, render it as one annotated JSONC object, not a field table; copy `references/example-good-schema.jsonc`.

"Schema as jsonc" means that file's style: real values, each field tagged `type | required|optional | constraints | description`, optional fields shown, nested objects in full, quirks inline.

Keep every line ≤80 chars: short annotations stay inline.

- The example file itself keeps the repo's 64-char source-comment cap (the comment-format gate lexes `.jsonc`); schemas rendered in a markdown doc keep the 80-char guidance.

- When a full annotation would push the field line past 80, move the comment above the field (wrapped, multi-line), preceded by a blank line so it hugs its field.

- The only allowed shorthand for a nested object is "same shape as X", for a sub-object whose schema is shown elsewhere; never drop a field to shorten.
  - Wrap a long `/* ... */` placeholder inside its braces; it is a value, not a trailing annotation, so it is not moved above.

- List every enum value inline; when the enum is huge (~60), say so and give the rule instead.

- When the *value* is long (two origin paths in one de/para value), keep the leaf field in the value and move the container path up into the comment — never truncate.

- When an enum has several long or multi-word values, list one value per line (`// enum:` header, then `//   - value` per line).
  - This avoids wrapping inline `enum [a, b, c]` mid-value across lines.

- Never leave an orphaned continuation fragment (a lone trailing word) when wrapping.
  - Either fit the whole clause on one line.
  - Or split at a real idea boundary (e.g. a semicolon joining two clauses) so every resulting line stands complete on its own.

- Measure before wrapping (`wc -c` on the line).
  - A line that looks long by eye often already fits within 80 chars.
  - Needless splitting adds noise.

**The description segment is optional** — include it only when it adds real information beyond the name and type; otherwise omit it rather than forcing one.

- A phrase that just unpacks the identifier is not a description: `"modular"` → `// indica se é de modelo modular`, `"dataFimVigencia"` → `// data de término da vigência`.
  - Both examples above restate the name and teach the reader nothing new.

- A description earns its place when it decodes a magic value/enum, states a unit, or names a business rule/quirk: `"tipoEndereco": 1  // fixo 1 = Faturamento conforme doc`.

- When a description does earn its place, keep it one short clause — never a paragraph.
  - This is a content rule, distinct from the ≤80-char line cap above: a description can fit inside the cap and still be over-elaborate.
  - "Every field needs a description" is license to cover more fields, never to write more per field.
  - The fix for a useless description is to delete or tighten it, not expand it.
