---
name: doc-standards
description: "Doc and commit-message rules with examples. USE PROACTIVELY whenever writing or reviewing code comments, docstrings, READMEs, repo CLAUDE.md, or commit messages — including before adding any 'why' comment to code."
user-invocable: false
---

# Doc Standards -- Examples & Patterns

Reference examples for the DOC rules defined in CLAUDE.md.

---

## Prefer Tests & Logs over Comments

```ts
// Bad -- comments explaining what code does:
function createRecord(user, data) {
  // Check permissions
  if (!hasPermission(user)) return false;
  return db.insert(data);
}

// Good -- self-documenting code + logs + tests:
function createRecordIfUserHasPermission(user, data) {
  if (!validateUserPermissions(user)) {
    logger.info({ message: "Record creation rejected", userId: user.id });
    return false;
  }
  return db.insert(data);
}

test("rejects when user lacks permission", () => {
  expect(createRecordIfUserHasPermission(userWithoutPerms, data)).toBe(false);
});
```

---

## Code comments: WHY at most

A code comment's maximum scope is **why this code exists in its current shape** — a permanent invariant the next reader cannot infer from the code itself.

Anything narrower than WHY is wrong:

- **History** (PR numbers, "main used to", "the merge", "we previously did") → commit message body, not source. Rots the moment the next commit lands.
- **What the code does** → already shown by the code; rename or restructure instead.
- **How it works** → implementation detail; the next refactor falsifies it.

```ts
// Bad — history (rots on next commit):
// excludeFlowCodes overrides flowCode — replicates main's last-spread-wins (PR #2034).

// Bad — what the code does (the reader can see it):
// loop over the conditions and push to the array

// Good — WHY this exact shape is required, and only because the code can't show it:
// Prisma's typed builder emits `payload #> ARRAY[...]::jsonb`, which the planner
// cannot match to our partial expression index on `payload->0->>'externalId'`.
// Switching syntax silently degrades to Seq Scan on 1.2M rows.
```

If the explanation would survive any future refactor of the surrounding code, it's a WHY and probably belongs. Otherwise, delete.
