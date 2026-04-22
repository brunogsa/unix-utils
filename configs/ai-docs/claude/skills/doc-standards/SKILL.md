---
description: "Documentation examples and anti-patterns covering a broad range of topics; headliners include commenting the why not the what, preferring tests and logs over comments, and self-documenting code through explicit names — this list is illustrative, not exhaustive. USE PROACTIVELY when writing or reviewing comments, docstrings, READMEs, module docs, or commit messages — the skill often has relevant guidance beyond what the headliners above suggest."
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
