---
description: "Documentation standards with examples for comment discipline, test-driven docs, and logging as documentation"
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
