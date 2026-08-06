# Entity Relationship Diagram

Shows the data model: entities (tables/collections), the attributes that carry a decision, and the cardinality between them.

~~~mermaid
erDiagram
  CUSTOMER ||--o{ ORDER : places
  ORDER ||--|{ ORDER_LINE : contains
  PRODUCT ||--o{ ORDER_LINE : "appears in"

  CUSTOMER {
    uuid id PK
    string email UK
    string name
  }
  ORDER {
    uuid id PK
    uuid customer_id FK
    timestamp placed_at
    string status
  }
  ORDER_LINE {
    uuid order_id PK, FK
    uuid product_id PK, FK
    int quantity
    decimal unit_price
  }
  PRODUCT {
    uuid id PK
    string sku UK
    string name
  }
~~~

## Cardinality glyphs — each side describes the entity it touches

Both halves are independent: the left glyph states how many `LEFT` rows relate to one `RIGHT` row, and the right glyph states the reverse.

The crow's foot (`{` / `}`) always points outward, away from the line.

| Left | Right | Means |
|------|-------|-------|
| `\|o` | `o\|` | zero or one |
| `\|\|` | `\|\|` | exactly one |
| `}o` | `o{` | zero or more |
| `}\|` | `\|{` | one or more |

[Instruction] **Read the glyph nearest an entity as the count of *that* entity.** In `CUSTOMER ||--o{ ORDER`, the `o{` next to `ORDER` means one customer has zero or more orders.

[Why] The instinct is to read the pair left-to-right as one phrase, which inverts the relationship on every asymmetric edge — the most common ERD bug, and one no parser catches.

## Solid vs dotted — identifying vs non-identifying

[Instruction] Use `--` (solid) when the child cannot exist without the parent, because the parent's key is part of the child's primary key.

[Instruction] Use `..` (dotted) when the child stands on its own and the foreign key is optional or nullable.

[Why] The line style is the only place an ERD records whether deleting the parent must cascade — prose next to the diagram drifts, the glyph doesn't.

~~~mermaid
erDiagram
  ORDER ||--|{ ORDER_LINE : "contains"
  USER_ACCOUNT ||..o{ AUDIT_EVENT : "triggers"

  AUDIT_EVENT {
    uuid id PK
    uuid actor_id FK "nullable: system events have no actor"
    string action
  }
~~~

## Parse traps specific to `erDiagram`

- **The relationship label is mandatory.** `ORDER ||--o{ SHIPMENT` fails with `Expecting 'COLON', 'STYLE_SEPARATOR', got 'NEWLINE'`.
  - Fix: give the verb — `ORDER ||--o{ SHIPMENT : fulfils`. Use `: ""` only when no verb is honest.
  - This is the one trap that bites hardest, because a labelled sibling edge on the line above makes the omission invisible to the eye.

- **Attribute lines are `type name key "comment"`, in that order** — the type comes first, unlike most schema languages.
- **Multiple keys on one attribute are comma-separated**: `uuid order_id PK, FK` for a composite-key join table.
- **The attribute comment is a quoted string at the end of the line** — it is the only place an ERD can carry a nullability or unit note.

## Scope — attributes that carry a decision, not the whole schema

[Instruction] Include primary keys, foreign keys, uniqueness constraints, and the fields the change actually touches — omit every other column.

[Why] The schema file and the ORM model already list every column and stay current for free, so a full dump in the diagram is a second copy that drifts.

It also buries the three fields the reader actually came for.

[Instruction] Keep the diagram to 5-10 entities; past that, split it by bounded context rather than shrinking the boxes.

[Why] Cardinality is the payload of an ERD, and past ~10 entities the edges cross enough that the reader can no longer trace any single one.
