---
description: "Brainstorm and refine ideas into a structured spec.md. Use when user says 'brainstorm', 'let's brainstorm', 'brainstorm with me', or is exploring a feature, problem, or design before implementation."
disable-model-invocation: false
---

# Brainstorm

Help the user explore and refine an idea into a structured spec.md.

## Usage

`/brainstorm [path/to/spec.md]`

Examples:
- `/brainstorm spec.md` -- refine an existing spec the user wrote
- `/brainstorm features/auth-spec.md` -- custom path
- `/brainstorm` -- no file: use session context, check for ./spec.md

## Process

### 1. Gather starting context

**If a file path is provided**: read it and use as the starting point.
**If no file path**: check if `./spec.md` exists and read it.
**If nothing exists**: use the current session context (conversation history,
codebase understanding) to seed the brainstorm.

### 2. Interview the user

Ask clarifying questions (Socratic style). Focus on:
- What problem are we solving? (Background)
- Who benefits and how? (User Stories)
- What does success look like? (Acceptance Criteria)
- What constraints exist? (Non-Functional Requirements)
- What's unclear? (mark with `[NEEDS CLARIFICATION]`)

Use Mermaid diagrams (rendered via `render-ascii-mermaid`) to visualize
architecture, data flow, or state when it aids understanding.

Ask 2-3 questions per round. Don't overwhelm.

### 3. Generate/update spec.md

Write to the provided file path, or `./spec.md` by default.
Use the template from the `spec-driven-development` skill.
If the file already exists, update it in place (preserve user content,
fill gaps, restructure into the template).

### 4. Present for review

Show the spec summary. Ask if anything is missing or wrong.
Iterate until the user is satisfied.
