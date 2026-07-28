# import-tasklist — flow overview

Human-facing overview for auditing the flow at a glance. Non-authoritative — the numbered steps in [`../SKILL.md`](../SKILL.md) win on any conflict. Regenerate this file whenever the skill's flow changes.

Two renderings of the same flow, kept cross-checkable on purpose. The `# N` comments in the pseudo-code are the diagram's node ids, so an id with no matching comment is drift.

## Pseudo-code

Python-shaped for readability only; nothing here runs, and the function names stand for steps this skill performs, not real APIs.

```python
# 1 · Entry: /import-tasklist [local-id...]
def import_tasklist(local_ids):
    if not exists("tasklist.md"):                           # 2
        return stop("nothing to import")                    # 2a

    # 3 · Step 2 — split on the "### <id>. [" header line;
    #     no args = every entry, named ids = exact local-id match
    #     (an unresolved name is skipped and reported, not an error).
    entries = apply_scope_rule(split_entries(read("tasklist.md")), local_ids)
    if not entries:                                          # 4
        return stop("nothing selected")                      # 4a

    for e in entries:
        # 5 · Step 3 — Depends-on titles split on "; "; description
        #     captured verbatim with the one trailing blank-line
        #     separator stripped off, byte-identical to the original.
        e.depends_on, e.description = extract_fields(e)

        e.task_id = task_create(e.subject_header, e.description)   # 6 · Step 4

        # 7 · Step 5 — fold the subject in to "[#<id>]"; inspect
        #     success rather than trusting a thrown error alone.
        e.fold_ok = task_update(e.task_id, subject=folded(e)).success

    # 8 · Step 6 — only entries where BOTH calls succeeded are
    #     eligible for step 7's resolution and step 8's removal list.
    tracked = [e for e in entries if e.task_id and e.fold_ok]

    # 9 · Step 7a — one fresh TaskList call, made after every entry
    #     was attempted, already covers this batch's own new tasks.
    title_to_ids = build_title_map(task_list())

    for e in tracked:
        for title in e.depends_on:                          # 10 · once per title
            ids = title_to_ids.get(title, [])
            if len(ids) != 1:                                # 10
                report_unresolved(e, title, ids)              # 10a · 0 = gone, 2+ = ambiguous
                continue
            task_update(e.task_id, add_blocked_by=ids[0])    # 11

    # 12 · Step 8 — spawn once, passing step 6's successful ids
    #     as the already-imported removal list.
    dispatch("tasklist-sweeper", background=True,
             remove=[e.local_id for e in tracked])

    return report(tracked, entries)
```

## Flowchart

```mermaid
flowchart TD
  n1(["1. /import-tasklist [local-id...]"]):::start
  n2{"2. Step 1 · tasklist.md exists in CWD?"}
  n2a(["2a. Stop: nothing to import"])
  n3["3. Step 2 · Read file, split into entries<br/>on the header line; apply scope rule<br/>(no args = every entry; named ids = exact<br/>local-id match, unresolved ones reported)"]
  n4{"4. Selection empty?"}
  n4a(["4a. Report and stop"])
  n5["5. Step 3 · Per selected entry, extract<br/>Depends-on titles (split on '; ') and<br/>description (trailing blank-line separator<br/>stripped, byte-identical to the original)"]
  n6["6. Step 4 · TaskCreate each entry<br/>(subject = header remainder,<br/>description = extracted text)"]:::state
  n7["7. Step 5 · TaskUpdate to fold the subject<br/>in to [#&lt;returned-id&gt;] shape;<br/>inspect every result's success field"]
  n8["8. Step 6 · Track the local id of every entry<br/>where TaskCreate AND its fold-in TaskUpdate<br/>both succeeded"]

  n9["9. Step 7a · Build one title→id-list map<br/>from a single fresh TaskList call, made after<br/>every selected entry has been attempted"]

  subgraph resolve["Step 7b-c · Per Depends-on title of each Step-6-tracked entry"]
    direction TB
    n10{"10. Title resolves to exactly one id?"}
    n10a["10a. Unresolved (0 matches) or ambiguous<br/>(2+ matches) — name it in the report,<br/>never guess"]
    n11["11. TaskUpdate addBlockedBy on<br/>the entry's own task id"]:::state
  end

  n12["12. Step 8 · Dispatch tasklist-sweeper<br/>(agent-pinned · background), passing<br/>Step 6's ids as the already-imported<br/>removal list"]:::dispatch

  n1 --> n2
  n2 -->|"no"| n2a
  n2 -->|"yes"| n3 --> n4
  n4 -->|"yes"| n4a
  n4 -->|"no"| n5 --> n6 --> n7 --> n8 --> n9 --> n10
  n10 -->|"no"| n10a
  n10 -->|"yes"| n11
  n10a --> n12
  n11 --> n12

  classDef start fill:#fef3c7,stroke:#d97706,stroke-width:2px
  classDef gate fill:#fee2e2,stroke:#dc2626,stroke-width:2px
  classDef dispatch fill:#dbeafe,stroke:#2563eb,stroke-width:2px
  classDef state fill:#dcfce7,stroke:#16a34a,stroke-width:2px
  classDef skill fill:#f3e8ff,stroke:#9333ea,stroke-width:2px
  classDef hook fill:#e5e7eb,stroke:#4b5563,stroke-width:2px
```
