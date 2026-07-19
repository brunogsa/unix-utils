# Mid-flight sub-steps — inserting into the checklist file

Detail for /implement's mid-flight sub-steps step (under sub-step decomposition). Load only when a helper or drift surfaces mid-task and the subagent needs to add sub-steps to its checklist file.

## Insertion rule

When a sub-step uncovers a new helper that needs its own test, insert a RED-helper / GREEN-helper pair into the checklist file **right after the current step**, before the later pending ones.

A markdown file preserves the order lines are written in, so insertion is positional: put the new lines where they belong and the rest stay put.
There is no ID-renumbering contract and no reordering dance — unlike a TaskList, whose display order the subagent cannot control.

## Keep the orchestrator's TaskList out of it

Mid-flight sub-steps are the subagent's business. The orchestrator's TaskList holds only the parent task, so the sole thing that changes there mid-task is the parent task's status — never the RED-GREEN granularity.
