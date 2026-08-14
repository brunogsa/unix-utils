#!/usr/bin/env python3
# check-uncollected-background-output.py - block a subagent's
#   stop when its run ends with a backgrounded command whose
#   output it never read.
#
# Usage (Claude Code SubagentStop hook):
#   check-uncollected-background-output.py
#
# stdin: the SubagentStop hook payload, as JSON
# stdout: {"decision": "block", "reason": "..."} when a
#   background job was left uncollected, nothing otherwise
# exit: always 0.
#
# Why this guard is a SubagentStop gate.
#
# A subagent has no event loop. Ending its turn IS ending its
# run, and a background job a subagent owns is killed when it
# gives its final response.
#
# So a subagent that yields to "wait for the notification"
# dies idle, its result a sentence about waiting, recoverable
# only by a manual SendMessage from the orchestrator.
#
# A PreToolUse deny on run_in_background would catch only
# half of that.
#
# A command can also reach the background without the agent
# choosing anything, when the runner auto-backgrounds it on
# timeout -- and at PreToolUse time that call still reads as
# a foreground one.
#
# The defect is also yielding while a job is uncollected, not
# backgrounding, which is legitimate on its own.
#
# Detection covers both entry paths.
#
# The runner prints one of two announcements, and they share
# exactly one literal -- "Output is being written to: <path>."
# That literal is what this keys on, so the agent-initiated and
# the auto-backgrounded case are detected by the same rule.
#
# The payload's own background_tasks array is not used: it
# holds only work still in flight, so it drops a job that
# finished before the stop and whose output was still never
# read -- a dead run just the same.
#
# What counts as collected.
#
# Any later Read of the output path, any later Bash command
# naming that path or the job id, and any later poll of the id.
# All three return the job's bytes, and the concern is whether
# the result was consumed, not which tool consumed it.
#
# Whether the read was COMPLETE is deliberately not judged.
# Doing so would re-implement the runner's completion
# semantics inside a stop hook, and would block the read-the-
# tail-and-move-on flow the slow-command rule asks for.
#
# Posture splits by what the evidence supports.
#
# Fail OPEN when the transcript cannot be read at all, and
# when the payload names none. With no evidence of a job, a
# block is not one extra turn -- it is a demand the agent has
# no way to satisfy, repeated at every stop.
#
# Fail CLOSED inside a readable transcript: a job with no
# later read blocks, because a false block costs one turn
# while a false pass costs a dead run and a manual rescue.
#
# An unparseable LINE is skipped rather than abandoning the
# scan, so a transcript truncated mid-write still gets its
# complete lines checked.
#
# Known limits, stated rather than designed around, because a
# guard trusted past its range is worse than one that names
# its holes:
#
# - A bare `cmd &` inside a Bash command is invisible here.
#     It produces no runner announcement to key on.
#
# - A long-lived process started on purpose and never meant
#     to be collected -- a dev server -- trips this.
#
# - A poll that returned only partial output counts as
#     collected, per the deliberate non-judgment above.
#
import json
import re
import sys

# The two announcements this has to cover:
#   agent-initiated
#     "Command running in background with ID: <id>."
#
#   harness-initiated, on a foreground command's timeout
#     "Command did not complete within its <n>s timeout and
#      was moved to the background (ID: <id>)."
OUTPUT_PATH_PATTERN = re.compile(r"Output is being written to: (\S+)")
JOB_ID_PATTERN = re.compile(r"(?:with ID: |\(ID: )([A-Za-z0-9_-]+)")

# A later call to one of these can hand the agent the job's
# own bytes. Anything else only mentions the path.
COLLECTING_TOOLS = ("Read", "Bash", "BashOutput", "TaskOutput")


def iter_content_blocks(transcript_path):
    """Yield every message content block in the transcript, in
    file order. A line that does not parse is skipped, never
    fatal, so a transcript truncated mid-write still yields the
    complete lines that precede the truncation."""
    with open(transcript_path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            message = entry.get("message")
            if not isinstance(message, dict):
                continue
            content = message.get("content")
            if not isinstance(content, list):
                continue
            for block in content:
                if isinstance(block, dict):
                    yield block


def parse_background_job(block):
    """Return the (output path, job id) a backgrounded command's
    tool_result announces, or None when block announces none.
    The job id is "" when the announcement carries no id."""
    if block.get("type") != "tool_result":
        return None
    content = block.get("content")
    if not isinstance(content, str):
        return None
    path_match = OUTPUT_PATH_PATTERN.search(content)
    if path_match is None:
        return None
    id_match = JOB_ID_PATTERN.search(content)
    output_path = path_match.group(1).rstrip(".")
    return output_path, (id_match.group(1) if id_match else "")


def get_collection_probe_text(block):
    """Return the searchable text of a tool call that could have
    returned a background job's output, or None when the block
    is not such a call. The whole input is searched, so a path
    reaches this wherever the tool happens to carry it."""
    if block.get("type") != "tool_use":
        return None
    if block.get("name") not in COLLECTING_TOOLS:
        return None
    return json.dumps(block.get("input", {}), sort_keys=True)


def is_collected(job_position, output_path, job_id, probes):
    """Return whether some probe AFTER job_position names this
    job. Position matters: a read of the same path from before
    the command was backgrounded read the previous contents,
    not this job's."""
    for probe_position, probe_text in probes:
        if probe_position <= job_position:
            continue
        if output_path in probe_text:
            return True
        if job_id and job_id in probe_text:
            return True
    return False


def find_uncollected_output_paths(transcript_path):
    """Return each background job's output path that no later
    tool call read, in the order the jobs were announced."""
    jobs = []
    probes = []
    for position, block in enumerate(iter_content_blocks(transcript_path)):
        job = parse_background_job(block)
        if job is not None:
            output_path, job_id = job
            jobs.append((position, output_path, job_id))
            continue
        probe_text = get_collection_probe_text(block)
        if probe_text is not None:
            probes.append((position, probe_text))

    uncollected = []
    for position, output_path, job_id in jobs:
        if is_collected(position, output_path, job_id, probes):
            continue
        if output_path not in uncollected:
            uncollected.append(output_path)
    return uncollected


def build_block_reason(output_paths):
    """Compose the block message. It names the way out, not
    just the ban, because an agent told only what it may not do
    yields again for want of an alternative."""
    listed = "\n".join(f"  - {path}" for path in output_paths)
    return (
        "This run is ending with a backgrounded command whose output was "
        "never read:\n"
        f"{listed}\n\n"
        "A subagent has no event loop: ending your turn IS ending your run. "
        "A background job you own is terminated when you give your final "
        "response, so no completion notification can ever reach you -- the "
        "run dies idle and needs a manual rescue from the orchestrator.\n\n"
        "Two ways to finish holding the result:\n"
        "  1. Read the output path above. It is a plain file on disk, "
        "readable right now, whether or not the command has finished.\n"
        "  2. Re-run the command in the foreground with its output "
        "redirected to a file, then read that file's tail (CLAUDE.md's "
        "slow-command rule).\n\n"
        "Never end your turn waiting for a background notification."
    )


def main():
    try:
        payload = json.load(sys.stdin)
    except (ValueError, OSError):
        return
    if not isinstance(payload, dict):
        return

    if payload.get("stop_hook_active"):
        return

    transcript_path = payload.get("agent_transcript_path")
    if not isinstance(transcript_path, str) or not transcript_path:
        return

    try:
        uncollected = find_uncollected_output_paths(transcript_path)
    except OSError:
        return

    if not uncollected:
        return

    print(
        json.dumps(
            {"decision": "block", "reason": build_block_reason(uncollected)}
        )
    )


if __name__ == "__main__":
    main()
