# Manual verification — Task 26: rename guard wired as a blocking Stop hook

Scope: `configs/ai-docs/claude/hooks/claude-rename-guard-stop-hook.sh`, wired
into `configs/ai-docs/claude/hooks/claude-stop-orchestrator.sh`.

Design note (see report for full detail): `settings.json` itself is NOT
edited. `settings.json`'s `Stop` array already names
`claude-stop-orchestrator.sh`, and that orchestrator now dispatches the new
`claude-rename-guard-stop-hook.sh` wrapper, which invokes
`check-rename-references.py`. AC1 is satisfied via this resolved-path chain,
not by a second literal `Stop` entry in `settings.json` — see the commit
body and final report for why a second top-level entry was rejected.

## Part 1 — blocks on a deliberately-broken reference (isolated sandbox)

Sandbox built under `mktemp -d` (never inside this repo), with a
`settings.json` fixture referencing a script path that does not exist:

```
$ SANDBOX=$(mktemp -d)
$ mkdir -p "$SANDBOX/hooks"
$ cat > "$SANDBOX/settings.json" <<EOF
{
  "hooks": {},
  "note": "$SANDBOX/hooks/renamed-away-manual-check.sh"
}
EOF
```

Sandbox dir and settings.json content (verbatim):

```
=== Sandbox dir ===
/var/folders/g1/_9y09y6n0570c2ljsrmq02300000gq/T/tmp.5oT0jaLC0m
=== settings.json content ===
{
  "hooks": {},
  "note": "/var/folders/g1/_9y09y6n0570c2ljsrmq02300000gq/T/tmp.5oT0jaLC0m/hooks/renamed-away-manual-check.sh"
}
```

Command — invoke the REAL wrapper script (not the checker directly) with a
simulated Stop-event stdin, pointed at the sandbox via the same `--repo`/
`--settings` flags the wrapper forwards to the checker:

```
$ printf '%s' '{"session_id": "manual-verify-block", "stop_hook_active": false}' \
    | bash configs/ai-docs/claude/hooks/claude-rename-guard-stop-hook.sh \
        --repo "$SANDBOX" --settings "$SANDBOX/settings.json"
```

Raw output:

```
{
  "decision": "block",
  "reason": "check-rename-references.py found a dangling script reference -- FAIL: /private/var/folders/g1/_9y09y6n0570c2ljsrmq02300000gq/T/tmp.5oT0jaLC0m/hooks/renamed-away-manual-check.sh: referenced from /private/var/folders/g1/_9y09y6n0570c2ljsrmq02300000gq/T/tmp.5oT0jaLC0m/settings.json. Fix the reference, then confirm with: check-rename-references.py (exit 0 = clean)."
}
```

Exit code: `0` (the hook exits 0 either way — the block signal is the
`{decision:"block"}` JSON on stdout, per the orchestrator's own contract:
"Block detection is by a gate's JSON output, not its exit code").

Result: **blocks as expected** — the dangling reference is reported by
full path, and the reason names it and tells the fixer how to confirm the
fix.

## Part 2 — passes through on the real corpus (current ~243-WARN state)

Command — the REAL wrapper, with NO overrides, against this machine's real
unix-utils checkout (the corpus the checker's own 2-second-budget test also
exercises unmodified):

```
$ start2=$(date +%s.%N)
$ OUT2=$(printf '%s' '{"session_id": "manual-verify-passthrough", "stop_hook_active": false}' \
    | bash configs/ai-docs/claude/hooks/claude-rename-guard-stop-hook.sh)
$ exit_code2=$?
$ end2=$(date +%s.%N)
$ echo "stdout: [$OUT2]"
$ echo "exit code: $exit_code2"
$ echo "elapsed: $(awk -v s="$start2" -v e="$end2" 'BEGIN{printf "%.3f", e-s}')s"
```

Raw output:

```
stdout: []
exit code: 0
elapsed: 0.388s
```

Result: **silent pass-through as expected** — no `{decision:"block"}` JSON,
exit 0, well under the 2-second budget.

Direct checker confirmation of the same corpus, run separately to show the
FAIL/WARN split the wrapper's silence rests on:

```
$ python3 configs/ai-docs/claude/hooks/check-rename-references.py > /tmp/real-corpus-scan.txt 2>&1
$ echo "exit: $?"
$ echo "FAIL count: $(grep -c '^FAIL:' /tmp/real-corpus-scan.txt)"
$ echo "WARN count: $(grep -c '^WARN:' /tmp/real-corpus-scan.txt)"
```

Raw output:

```
exit: 0
FAIL count: 0
WARN count: 243
```

Note on the count: the plan's dispatch context measured 240 WARN at Task 6
landing time; this session measured 243. The delta is not from this task's
changes — this task adds no markdown, no install.sh, and no settings.json
content (the two new `.sh` files under `hooks/` are neither markdown nor
`install.sh`, so `run_scan` never reads them as a source at all). The one
pre-existing WARN this session's own new filenames incidentally surfaced in
a `grep` was a rename-list doc predating this task
(`configs/ai-docs/claude/skills/code-standards/references/rename-list.md`
referencing `claude-stop-orchestrator.sh`, which already existed before
Task 26). The +3 is attributed to concurrent sibling sessions' markdown
edits landing in this shared working tree during this task's execution, not
to anything Task 26 touched — 0 FAIL either way is the load-bearing number
for AC2.

## Part 3 — sandbox left no trace

```
$ rm -rf "/var/folders/g1/_9y09y6n0570c2ljsrmq02300000gq/T/tmp.5oT0jaLC0m"
$ ls "/var/folders/g1/_9y09y6n0570c2ljsrmq02300000gq/T/tmp.5oT0jaLC0m" 2>&1 || echo "sandbox removed, confirmed gone"
```

Raw output:

```
ls: /var/folders/g1/_9y09y6n0570c2ljsrmq02300000gq/T/tmp.5oT0jaLC0m: No such file or directory
sandbox removed, confirmed gone
```

Re-scanned the real repo immediately after cleanup, confirming the
deliberately-broken reference never touched the tracked tree and the real
corpus is still clean of FAIL findings:

```
$ python3 configs/ai-docs/claude/hooks/check-rename-references.py > /tmp/post-manual-verify-scan.txt 2>&1
$ echo "exit: $?"
$ echo "FAIL count: $(grep -c '^FAIL:' /tmp/post-manual-verify-scan.txt)"
$ echo "WARN count: $(grep -c '^WARN:' /tmp/post-manual-verify-scan.txt)"
```

Raw output:

```
exit: 0
FAIL count: 0
WARN count: 243
```

## Conclusion

Both AC2 halves are demonstrated with the real wrapper script, not by
reading the code: it blocks on a genuine dangling reference (Part 1) and
passes through silently on the current real corpus, including its
markdown-WARN findings (Part 2). No deliberately-broken reference was ever
committed or left in the tracked repo (Part 3).
