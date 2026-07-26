# Pre-flight — existing task state & TaskList items

Detail for /implement's pre-flight JSON state-file adoption step and its task/TaskList reconciliation step. Fires only on a resume or dirty run — a clean first run skips both sections.

## Session-level: JSON state-file adoption (§1.5)

When §1.5 finds an existing `/tmp/implement_*.json` whose `slug` AND `pr_label` both match this run's, adopt it instead of creating a new file.

No prompt: an existing file is itself the resume signal, mirroring the Stop hook's own escape hatch (deleting the file un-scopes the session).

Adoption is a rename plus two field patches, never a rewrite of its contents:

```bash
mv /tmp/implement_<old_session_id>.json /tmp/implement_<new_session_id>.json
jq --arg sid "<new_session_id>" \
  '.session_id = $sid | if .phase == "halted" then .phase = "tasks" else . end' \
  /tmp/implement_<new_session_id>.json \
  > /tmp/state.json && mv /tmp/state.json /tmp/implement_<new_session_id>.json
```

`tasks[]`, `attempts[]`, `gate_dispatches`, `tails`, `worktree`, `pr`, and `pr_label` all carry over verbatim.

A pre-change state file may still carry an `orchestration_review` key from before that step was removed — leave it untouched and ignore it; nothing reads it.

A pre-change state file predates `tails.wanted` and has no such key — treat its absence as `true`, matching the tails-mandatory behavior that file was created under.

A pre-change state file predates `pr_label` the same way — treat its absence as `""`, matching a plain task-id run (no `PR-N` label given).

§1.5's lookup filters on `pr_label`, so an adopted file's absent key must resolve to the same empty string the lookup itself defaults to. Otherwise adoption would never match a pre-change file.

`phase` carries over too, except `halted`, which resets to `tasks`: the verdict script fails loud on any phase other than `tasks`, so a resumed halted batch would crash its first verdict call.

The adopted phase decides where the resumed run re-enters:

- `tasks` → run the flow from §2 onward — re-seed any missing TaskList entries, then the task loop.
- `gates` → skip straight to the §8 batch test-presence gate; the task loop already ran.
- `tails` → skip straight to the §9 batch-end flow; check `.tails.*_report` for reports that already exist.

A budget-halted resume still halts again at that first verdict — the carried `attempts[]` already exceed the ceiling; delete the state file (below) to truly start over.

That alone restores every task's completed status and every attempt count: `implement-loop-state.sh` reads them the same way whether the run is fresh or resumed.

So finished tasks are never redispatched from a blank slate.

A task-id in this invocation with no matching `tasks[]` entry — e.g. a task added to the batch after the crash — gets appended when §1.6 first matches it.

The appended entry is `{"id": "<id>", "status": "pending"}`.

`tasks[].status` from the adopted file is authoritative over a stale `plan_<slug>.md` marker; §1.7's reconciliation resyncs the marker to match, not the other way around.

To discard a stale run entirely instead of resuming it, delete its state file before re-running `/implement` — that is the only supported way to force a clean slate.

## PR-level: branch resume on a PR-label run

Everything above already covers a PR-label run's *state file* — it's keyed on `(slug, pr_label)`, same adoption mechanics, no special case.
What's PR-specific is the **branch and manifest**, which live outside the state file entirely.

- **Re-invoking `/implement PR-N` while its PR is already open** — the state file adopts the same way (phase carries over per above).
  The branch itself: `references/pr-branch-creation.md`'s resume check (`git rev-parse --verify --quiet <feat_branch>/pr<N>`) finds it already exists.
  It runs a plain `git checkout` (never `-b`), and skips the dependency guard and parent-entry write — both already ran, and passed, the first time this branch was created.
  No second branch, no second PR: `gh pr create` in `references/batch-end-pr.md`'s "Draft PR" step hits the already-open-PR case and falls back to updating the existing PR's body instead of erroring.
- **Re-invoking `/implement PR-N` after a kill between `checkout -b` and its first task's commit.**
  The same resume check finds the branch — now real, with zero commits on it yet — and adopts it the same way.
  The state file's `tasks[]` shows every task still `pending` (or a lone `[Doing]` if the kill landed mid-dispatch — see "Handle existing task state" below).
  So §1.6–§1.7 dispatch the first task exactly as a fresh run would.
  Nothing here is a distinct recovery path: an empty branch is just a branch whose tasks haven't committed yet, and task-level resume already handles that.

## Task-level: plan_<slug>.md markers & TaskList items (§1.7)

These prompts fire only for state the adopted JSON doesn't already resolve.

That means a task whose `plan_<slug>.md` marker or TaskList entry disagrees with its JSON status, or a dirty run with no JSON file at all.

A task the JSON already marks `done`/`blocked` is skipped by the verdict script directly (§4-5) and never reaches this section.

That means an adopted `blocked` task is never re-offered for retry — its status carries over as terminal. To retry it after clearing the blocker, delete the state file and start clean.

### Handle existing task state

- **Already `[Done]`** → ask: re-execute / skip / abort.
- **Already `[Doing]`** → ask: resume / restart / abort. Multiple `[Doing]` tasks at once is a smell — flag it.
- **Already `[Blocked]` / `[Deferred]`** → ask: resume / abort.
  - Resume re-dispatches the task.
  - The fresh subagent picks up from its checklist file (§3) + `plan_<slug>.md` context.
  - The `[Doing]` flip happens on resume.
- **Already `[Dropped]`** → ask: revive (clear status, restart) / abort.

### Existing TaskCreate items

Run TaskList. If any items exist, list them **ON CHAT** and ask:

- Keep all
- Delete `completed` only
- Delete all
- Cancel `/implement`

Apply the choice before continuing — long lists may not fully render in the UI, so listing them in chat for explicit confirmation is part of the safety net.

Sub-steps are not in the TaskList — they live in each task's `/tmp` checklist file (§3), which a re-dispatch resumes from rather than overwrites, so no TaskList cleanup touches them.
