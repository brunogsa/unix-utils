# Merge check failure

Read this only when a §4.1 verification check fails and the merged file cannot stand.

## What to move back

Move the merged file into `<RUN_DIR>`, and move every source file except the scout files, and the rendered metrics verdict, back into CWD.

Leave `scout-leg_<ts>.md` in `<RUN_DIR>` and change no scout task: they stay pending for the next gate run.

Say so in §7.
