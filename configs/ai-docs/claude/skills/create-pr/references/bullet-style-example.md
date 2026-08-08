# Bullet style (referenced by writing-style.md's "Bullets" rule)

## Hard to scan

```markdown
- Fix lib test failures by changing build:deps from selective to full tsc -b
- Auto-create .env from .env.local.example for seamless git worktree support
  - New setup:env script in core/package.json
- Apply Prisma migrations to test DB (port 5433)
  - Fixes 40 pre-existing failures (test DB was never migrated)
```

## Better

```markdown
- **Lib test fix** -- `build:deps` → full `tsc -b`
- **Worktree support** -- `setup:env` auto-creates `.env` from example
- **Test DB migrations** -- new `dbtest:migrate` for port 5433
  - Fixes 40 pre-existing failures (test DB was never migrated)
```

The reviewer scans the bold prefixes (`Lib test fix` / `Worktree support` / `Test DB migrations`) and skips the body of any topic they don't need to dig into.
