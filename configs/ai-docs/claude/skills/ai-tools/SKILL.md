---
description: "AI-powered shell scripts for changelogs, commit messages, code review bundles, clipboard context, and command generation"
user-invocable: false
---

# AI Tools

Shell scripts at `~/oh-my-zsh/func-utilities/` that use OpenAI/Anthropic APIs.

## Scripts

### ai-request
Core API caller. Sends prompt to OpenAI (default: o4-mini), falls back to Anthropic Claude Sonnet on quota exhaustion.
```
ai-request "<prompt>" [model]
```
Env: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`

### ai-changelog
Generates changelog bullet points from a git diff/show via AI.
```
git show HEAD~1 | ai-changelog
git diff HEAD~1 | ai-changelog
```

### aigitcommit
Generates a conventional commit message from staged changes, opens editor for review before committing.
```
aigitcommit [--no-verify]
```

### aicmd
Generates a shell command from a natural language prompt, copies it to clipboard.
```
aicmd 'recursively find and delete all .DS_Store files'
```

### aireview
Prepares a comprehensive code review bundle (diff, file contents, repo map, conventions, PR/Jira context) and copies to clipboard.
```
aireview main feature/new-api
aireview --github https://github.com/owner/repo/pull/123
aireview --github <pr-url> --jira <jira-url>
```
Requires: git repo, SSH access. Optional: `gh` CLI, Jira env vars, `aider` (for repo map).

### aicopy
Copies file names and contents to clipboard. Accepts file paths via args or stdin.
```
aicopy file1.ts file2.ts
rg --files | aicopy
```

### aiyank
Converts file paths to git-root-relative paths, copies to clipboard.
```
aiyank fileA.yaml fileB.json
ls | aiyank
```

### aiappend
Appends clipboard content or last command output to `~/.claude/CLAUDE.md` (AI shared context).
```
aiappend --clipboard
aiappend --output
```

### estimate_tokens
Estimates token count for a file (conservative: max of chars/4 and words*0.75).
```
estimate_tokens <file>
```
