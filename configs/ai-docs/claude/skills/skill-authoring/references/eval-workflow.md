# Eval / improve workflow

Condensed from Anthropic's `skill-creator` plugin, adapted to this skill's local paths. Read this file only when actually running an eval loop — it's not needed to write or lightly edit a SKILL.md.

## Test cases

Write 2-3 realistic test prompts — what a real user would actually say — and save them to `evals/evals.json` next to the skill under test.
Don't write assertions yet; those come while runs are in flight.
Schema: `references/schemas.md` in this directory.

Before inventing prompts from scratch, mine real ones: grep `~/.claude/projects` transcripts (see the `usage-audit` skill) for candidates that plausibly should or shouldn't trigger this skill.
Hand-invented prompts encode the author's guess at real usage; transcripts are observed usage, free for the taking. This applies equally to trigger-eval queries (`## Description optimization` below).

## Running and grading

1. **Spawn all runs in the same turn.**
   - For each test case, spawn a with-skill subagent and a baseline subagent (no skill, or the pre-change skill snapshot) together — not with-skill first and baselines later.
   - Save outputs under `<skill-name>-workspace/iteration-<N>/eval-<id>/{with_skill,without_skill}/outputs/`.
2. **While runs are in flight, draft assertions** — objectively verifiable checks with descriptive names. Subjective qualities (style, tone) are better judged by the human reviewer than forced into an assertion.
3. **Capture timing from task notifications as they arrive** — `total_tokens` and `duration_ms` are only available in that notification, not persisted elsewhere; write them to `timing.json` in each run directory immediately.
4. **Grade each run** with the `agents/grader.md` prompt (this directory's parent `agents/`). Its `grading.json` output must use the exact field names `text`/`passed`/`evidence` — the viewer depends on them.
5. **Aggregate**: `python -m scripts.aggregate_benchmark <workspace>/iteration-N --skill-name <name>` (run from this skill's own directory so `scripts.*` resolves).
   Layout gotcha: `aggregate_benchmark.py` only counts a config dir as valid if it has a `run-N/` subdirectory nested inside it.
   It also reads pass/fail counts from a `summary` field in `grading.json` (not `expectations` alone) — add both before aggregating, or it silently reports all-zero stats.
6. **Launch the viewer**: `python eval-viewer/generate_review.py <workspace>/iteration-N --skill-name "<name>" --benchmark <workspace>/iteration-N/benchmark.json`.
   For headless/no-display environments: add `--static <output_path>` and read feedback back from the downloaded `feedback.json`.
7. **Read `feedback.json`** once the user is done reviewing — empty feedback means "fine as-is," focus improvements on entries with specific complaints.

## Improving the skill

- Generalize from feedback instead of overfitting to the handful of test cases in front of you.
  A skill run a million times across prompts you haven't seen needs the general fix, not a patch for today's example.
- Keep the prompt lean — read the transcripts, not just outputs, and cut instructions that make the model do unproductive work.
- Explain the *why* behind each instruction rather than issuing bare MUSTs — an ALL-CAPS directive with no reasoning is a sign the instruction should be reframed, not emphasized harder.
- If multiple test-run transcripts independently reinvent the same helper (e.g. every run hand-writes a similar parsing script), bundle it into `scripts/` once.
  This avoids leaving every future run to reinvent it.

After improving, rerun all test cases (including baselines) into a new `iteration-<N+1>/` directory and repeat.

## Description optimization

Trigger evals (`scripts/run_eval.py`, `scripts/run_loop.py`) run every query in an isolated sandbox — a fresh `CLAUDE_CONFIG_DIR` plus a temp project where the injected skill is the only one visible.
Why isolated: in a dense real environment (dozens of co-visible skill descriptions), headless proactive triggering floors at zero for every description, so a non-isolated eval measures the environment, not the description.
Auth: `ANTHROPIC_API_KEY` if set, else the subscription OAuth credential is copied into each sandbox (from the macOS Keychain or `~/.claude/.credentials.json`).
Needed because with `CLAUDE_CONFIG_DIR` set, claude only reads credentials from inside that dir.
With neither source available the scripts exit with a clear error instead of scoring silent zeros.

1. Generate ~20 trigger-eval queries, mixing should-trigger and should-not-trigger phrasings — mine real transcripts first, per `## Test cases` above.
2. Review them with the user via `assets/eval_review.html` (open directly, or serve locally) before running anything expensive.
3. Run the optimization loop from this skill's own directory: `python -m scripts.run_loop --eval-set <path> --skill-path <path> --model claude-sonnet-5 [--max-iterations N]`.
   It splits train/test, iterates description rewrites via `scripts/improve_description.py`, and picks the best iteration by *test* score to avoid overfitting the visible queries.
4. Apply the resulting `best_description` to the skill's frontmatter once the user signs off.

## Package and validate

`python -m scripts.package_skill <skill-path>` validates frontmatter (via `scripts/quick_validate.py`) and zips the skill folder, excluding `__pycache__`, `node_modules`, and the local `evals/` directory.
