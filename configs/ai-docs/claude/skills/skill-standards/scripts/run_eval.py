#!/usr/bin/env python3
"""Run trigger evaluation for a skill description.

Tests whether a skill's description causes Claude to trigger (read the skill)
for a set of queries. Outputs results as JSON.
"""

import argparse
import json
import os
import select
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from scripts.utils import parse_skill_md


def resolve_sandbox_auth() -> str | None:
    """Resolve authentication for the isolated sandbox config dirs.

    With CLAUDE_CONFIG_DIR set, claude reads credentials from a
    .credentials.json INSIDE that dir — never from the default store
    (macOS Keychain / ~/.claude/.credentials.json) — so a fresh sandbox
    is "Not logged in" unless a credential is materialized into it.

    Returns the subscription OAuth credential JSON to write into each
    sandbox, or None when ANTHROPIC_API_KEY is set (the subprocess env
    inherits it, no credential file needed). Exits with a clear error
    when neither auth source exists.
    """
    if os.environ.get("ANTHROPIC_API_KEY"):
        return None

    linux_credential_file = Path.home() / ".claude" / ".credentials.json"
    if linux_credential_file.exists():
        return linux_credential_file.read_text()

    try:
        keychain_lookup = subprocess.run(
            ["security", "find-generic-password", "-s", "Claude Code-credentials", "-w"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if keychain_lookup.returncode == 0 and keychain_lookup.stdout.strip():
            return keychain_lookup.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        pass

    print(
        "Error: no auth available for the isolated eval sandboxes. "
        "Set ANTHROPIC_API_KEY, or log in to Claude Code (subscription "
        "OAuth is read from the macOS Keychain or "
        "~/.claude/.credentials.json and copied into each sandbox).",
        file=sys.stderr,
    )
    sys.exit(1)


def run_single_query(
    query: str,
    skill_name: str,
    skill_description: str,
    timeout: int,
    model: str | None = None,
    credentials: str | None = None,
) -> bool:
    """Run a single query and return whether the skill was triggered.

    Runs `claude -p` in an isolated sandbox: a fresh CLAUDE_CONFIG_DIR
    (no user skills, CLAUDE.md, or plugins) and a temp project dir whose
    .claude/commands/ holds only the injected command file, so it is the
    single skill in Claude's available_skills list.

    Isolation is what makes the measurement discriminative: a dense user
    environment (dozens of co-visible skill descriptions) suppresses
    proactive skill triggering to near zero for EVERY description, so an
    eval run there measures the environment, not the description.

    Uses --include-partial-messages to detect triggering early from
    stream events (content_block_start) rather than waiting for the
    full assistant message, which only arrives after tool execution.
    """
    unique_id = uuid.uuid4().hex[:8]
    clean_name = f"{skill_name}-skill-{unique_id}"
    sandbox = Path(tempfile.mkdtemp(prefix="skill-trigger-eval-"))
    config_dir = sandbox / "config"
    project_root = sandbox / "project"
    command_file = project_root / ".claude" / "commands" / f"{clean_name}.md"

    try:
        config_dir.mkdir()
        if credentials:
            credential_file = config_dir / ".credentials.json"
            credential_file.write_text(credentials)
            credential_file.chmod(0o600)
        command_file.parent.mkdir(parents=True)
        # Use YAML block scalar to avoid breaking on quotes in description
        indented_desc = "\n  ".join(skill_description.split("\n"))
        command_content = (
            f"---\n"
            f"description: |\n"
            f"  {indented_desc}\n"
            f"---\n\n"
            f"# {skill_name}\n\n"
            f"This skill handles: {skill_description}\n"
        )
        command_file.write_text(command_content)

        cmd = [
            "claude",
            "-p", query,
            "--output-format", "stream-json",
            "--verbose",
            "--include-partial-messages",
        ]
        if model:
            cmd.extend(["--model", model])

        # Remove CLAUDECODE env var to allow nesting claude -p inside a
        # Claude Code session. The guard is for interactive terminal conflicts;
        # programmatic subprocess usage is safe.
        env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
        env["CLAUDE_CONFIG_DIR"] = str(config_dir)

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            cwd=str(project_root),
            env=env,
        )
        assert process.stdout is not None  # guaranteed by stdout=subprocess.PIPE above
        stdout = process.stdout

        triggered = False
        start_time = time.time()
        buffer = ""
        # Track state for stream event detection
        pending_tool_name = None
        accumulated_json = ""
        saw_json_event = False
        first_unparsed_line = None

        try:
            while time.time() - start_time < timeout:
                if process.poll() is not None:
                    remaining = stdout.read()
                    if remaining:
                        buffer += remaining.decode("utf-8", errors="replace")
                    break

                ready, _, _ = select.select([stdout], [], [], 1.0)
                if not ready:
                    continue

                chunk = os.read(stdout.fileno(), 8192)
                if not chunk:
                    break
                buffer += chunk.decode("utf-8", errors="replace")

                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        event = json.loads(line)
                        saw_json_event = True
                    except json.JSONDecodeError:
                        if first_unparsed_line is None:
                            first_unparsed_line = line
                        continue

                    # Early detection via stream events
                    if event.get("type") == "stream_event":
                        se = event.get("event", {})
                        se_type = se.get("type", "")

                        if se_type == "content_block_start":
                            cb = se.get("content_block", {})
                            if cb.get("type") == "tool_use":
                                tool_name = cb.get("name", "")
                                if tool_name in ("Skill", "Read"):
                                    pending_tool_name = tool_name
                                    accumulated_json = ""
                                else:
                                    # Not the tool we're watching for -- a Bash/Grep/etc
                                    # call earlier in the run doesn't rule out a Skill
                                    # or Read call later in the same run, so keep scanning
                                    # instead of deciding here.
                                    pending_tool_name = None

                        elif se_type == "content_block_delta" and pending_tool_name:
                            delta = se.get("delta", {})
                            if delta.get("type") == "input_json_delta":
                                accumulated_json += delta.get("partial_json", "")
                                if clean_name in accumulated_json:
                                    return True

                        elif se_type == "content_block_stop":
                            if pending_tool_name and clean_name in accumulated_json:
                                return True
                            pending_tool_name = None

                        # message_stop only ends the current assistant turn, not the
                        # whole `claude -p` run -- a later turn (after a tool result)
                        # can still call Skill/Read, so don't decide here either.

                    # Fallback: full assistant message
                    elif event.get("type") == "assistant":
                        message = event.get("message", {})
                        for content_item in message.get("content", []):
                            if content_item.get("type") != "tool_use":
                                continue
                            tool_name = content_item.get("name", "")
                            tool_input = content_item.get("input", {})
                            if tool_name == "Skill" and clean_name in tool_input.get("skill", ""):
                                triggered = True
                            elif tool_name == "Read" and clean_name in tool_input.get("file_path", ""):
                                triggered = True
                        if triggered:
                            return True

                    elif event.get("type") == "result":
                        return triggered
        finally:
            # Clean up process on any exit path (return, exception, timeout)
            if process.poll() is None:
                process.kill()
                process.wait()

        # A run with zero JSON events did not evaluate anything — plain-text
        # output like "Not logged in" would otherwise score as a silent
        # non-trigger and mask an auth failure as a description failure.
        if not saw_json_event:
            raise RuntimeError(
                f"claude -p produced no JSON events (auth failure or crash?); "
                f"first output line: {first_unparsed_line!r}"
            )
        return triggered
    finally:
        shutil.rmtree(sandbox, ignore_errors=True)


def run_eval(
    eval_set: list[dict],
    skill_name: str,
    description: str,
    num_workers: int,
    timeout: int,
    runs_per_query: int = 1,
    trigger_threshold: float = 0.5,
    model: str | None = None,
) -> dict:
    """Run the full eval set and return results."""
    results = []
    credentials = resolve_sandbox_auth()

    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        future_to_info = {}
        for item in eval_set:
            for run_idx in range(runs_per_query):
                future = executor.submit(
                    run_single_query,
                    item["query"],
                    skill_name,
                    description,
                    timeout,
                    model,
                    credentials,
                )
                future_to_info[future] = (item, run_idx)

        query_triggers: dict[str, list[bool]] = {}
        query_items: dict[str, dict] = {}
        for future in as_completed(future_to_info):
            item, _ = future_to_info[future]
            query = item["query"]
            query_items[query] = item
            if query not in query_triggers:
                query_triggers[query] = []
            try:
                query_triggers[query].append(future.result())
            except Exception as e:
                print(f"Warning: query failed: {e}", file=sys.stderr)
                query_triggers[query].append(False)

    for query, triggers in query_triggers.items():
        item = query_items[query]
        trigger_rate = sum(triggers) / len(triggers)
        should_trigger = item["should_trigger"]
        if should_trigger:
            did_pass = trigger_rate >= trigger_threshold
        else:
            did_pass = trigger_rate < trigger_threshold
        results.append({
            "query": query,
            "should_trigger": should_trigger,
            "trigger_rate": trigger_rate,
            "triggers": sum(triggers),
            "runs": len(triggers),
            "pass": did_pass,
        })

    passed = sum(1 for r in results if r["pass"])
    total = len(results)

    return {
        "skill_name": skill_name,
        "description": description,
        "results": results,
        "summary": {
            "total": total,
            "passed": passed,
            "failed": total - passed,
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Run trigger evaluation for a skill description")
    parser.add_argument("--eval-set", required=True, help="Path to eval set JSON file")
    parser.add_argument("--skill-path", required=True, help="Path to skill directory")
    parser.add_argument("--description", default=None, help="Override description to test")
    parser.add_argument("--num-workers", type=int, default=10, help="Number of parallel workers")
    parser.add_argument("--timeout", type=int, default=30, help="Timeout per query in seconds")
    parser.add_argument("--runs-per-query", type=int, default=3, help="Number of runs per query")
    parser.add_argument("--trigger-threshold", type=float, default=0.5, help="Trigger rate threshold")
    parser.add_argument("--model", default="claude-sonnet-5", help="Model to use for claude -p (default: claude-sonnet-5, for reproducible evals)")
    parser.add_argument("--verbose", action="store_true", help="Print progress to stderr")
    args = parser.parse_args()

    eval_set = json.loads(Path(args.eval_set).read_text())
    skill_path = Path(args.skill_path)

    if not (skill_path / "SKILL.md").exists():
        print(f"Error: No SKILL.md found at {skill_path}", file=sys.stderr)
        sys.exit(1)

    name, original_description, _ = parse_skill_md(skill_path)
    description = args.description or original_description

    if args.verbose:
        print(f"Evaluating: {description}", file=sys.stderr)

    output = run_eval(
        eval_set=eval_set,
        skill_name=name,
        description=description,
        num_workers=args.num_workers,
        timeout=args.timeout,
        runs_per_query=args.runs_per_query,
        trigger_threshold=args.trigger_threshold,
        model=args.model,
    )

    if args.verbose:
        summary = output["summary"]
        print(f"Results: {summary['passed']}/{summary['total']} passed", file=sys.stderr)
        for r in output["results"]:
            status = "PASS" if r["pass"] else "FAIL"
            rate_str = f"{r['triggers']}/{r['runs']}"
            print(f"  [{status}] rate={rate_str} expected={r['should_trigger']}: {r['query'][:70]}", file=sys.stderr)

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
