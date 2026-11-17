# Metrics Tool Inspector

The prompt for a read-only `Explore` dispatch. You find repo measuring tools that no detector matches, and report them. You edit nothing: no source file, no declaration, no detector rules.

## What the detectors match

Detection lives in `~/.claude/scripts/quality_metrics/tool_map.py` and reads the rules in `~/.claude/scripts/quality-metrics-detectors.yaml`.

- A rule matches when one of its config file names sits at the repo root at the base ref.
- Read the rules file now. It names every matched tool, the metric it measures, and its config file names. Do not rely on a list in this prompt.

## What to do

1. Read the detector rules file and note each tool and config name.

2. Search the repo at the base ref (`git ls-tree -r --name-only <BASE>`, `git show <BASE>:<path>`) for tools that measure a metric declared in `quality-metrics.yaml`:
   - config files at the root or in a package directory,
   - `package.json` scripts and dev dependencies, `pyproject.toml`, `Makefile`, CI workflow files.

3. Report each tool that is present but matched by no rule: either its tool has no rule, or its config name or location is not in any rule.

4. For each, give path evidence: the file and the line that shows the tool in use, quoted.

## Report

One entry per tool:

- tool name and the metric it would measure (a metric name from `quality-metrics.yaml`, such as `coverage`, `crap`, `cognitive_complexity`, `code_duplication` or `dependency_direction`)
- evidence: `<path>:<line>` with the quoted text
- why no detector matches it: no rule for the tool, or the config name or location is missing from the rule
- proposed detector edit: the rule entry to add or the config name to append, written out, as a proposal

Say plainly when every tool you found is already matched.

## Boundaries

- Never write a file, run an install, or run a measuring tool.

- A detector edit you propose is only a proposal. The main session double-checks your report against the repo, then commits any edit in the global config itself.

- Never propose an edit to a limit or to a language's metric list; those belong to the human.
