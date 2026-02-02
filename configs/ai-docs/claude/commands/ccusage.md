# Claude Code Usage Analysis

Fetch usage data for the current session using the `ccusage` CLI, interpret the results, and propose improvements to reduce cost and token usage.

## Usage

`/ccusage`

## Process

### 1. Identify Current Session

The current session is the most recently modified `.jsonl` file in the project directory:

```bash
# Get project dir name (replace / with -)
project_dir=$(echo "$PWD" | sed 's|^/||; s|/|-|g')

# Get most recent session ID
session_id=$(ls -t ~/.claude/projects/"$project_dir"/*.jsonl 2>/dev/null | head -1 | xargs basename | sed 's/\.jsonl$//')

echo "Session ID: $session_id"
```

If no session is found, inform the user and stop.

### 2. Fetch Usage Data

```bash
ccusage session -i "$session_id" --json --breakdown --no-color
```

### 3. Interpret the Data

Analyze the JSON output and present a summary:

- **Total cost** (USD)
- **Total tokens** (input, output, cache creation, cache read)
- **Cache hit ratio** -- `cacheReadTokens / (cacheReadTokens + inputTokens + cacheCreationTokens)` -- higher is better
- **Model breakdown** -- cost and tokens per model used
- **Turn count** -- number of entries (API round-trips)
- **Average cost per turn**
- **Most expensive turns** -- identify outliers (turns with unusually high token counts)

### 4. Propose Improvements

Based on the analysis, suggest actionable improvements when applicable:

- **High cache creation, low cache read** → context is being rebuilt too often; suggest shorter prompts or fewer tool calls that reset context
- **High output tokens** → responses may be too verbose; suggest more targeted prompts
- **Many turns with low output** → possible retry loops or failed tool calls; identify the pattern
- **Expensive model on simple tasks** → suggest using haiku for straightforward tasks (search, simple reads)
- **High total cost** → break down where the cost comes from and suggest specific reductions
- **Low cache hit ratio** → conversation context isn't being reused efficiently

If no improvements are obvious, say so -- don't fabricate suggestions.
