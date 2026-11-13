# Launching a learn run in a lateral session

`to-spec`, `to-plan`, `address-verdicts` and `address-pr-comments` read this file by path, each time the human's feedback should teach the rules.

The goal is that the human never repeats a correction: lessons reach the global `CLAUDE.md` and skills while the caller keeps working.

## Launch rules

- Launch by default and never ask.
  - Why: the user set this as a standing rule on 2026-11-03, and the per-item approval in `improve-from-user` step 7, in the new window, is the human's only gate.

- Carry on in the same message as the launch (the editor dispatch, the apply loop), and never read the window back.
  - Why: waiting would serialize work the user wants in parallel.

- Launch once per round, where a round is one human message or one `AskUserQuestion` call's answers - never once per correction. `address-pr-comments` launches once per run.

- A learn run also never runs in main or in a subagent.
  - Why: `improve-from-user` asks per-item approval and its edits need permission prompts, which only render in a main session, and a separate window keeps its reads out of the caller's context.

## What counts as a correction (to-spec, to-plan)

- The human corrects, rejects, rewords, or adds to the written document, or rejects the recommended option.
- An open-question answer that picks the recommended option is not a correction.
- A round with no correction launches nothing.

## The source

- Chat feedback (to-spec, to-plan): write `<scratchpad>/feedback_<slug>_<N>.md` in the caller's own scratchpad, N being the round number from 1, holding:
  - `Document: <absolute path of the spec or plan>`
  - `Repo: <absolute path of main's repo>`
  - `References:` absolute paths the learn session may open to dig deeper (the document, `notes.md`, the briefs) - paths only, never pasted contents.
    - Why: pasted contents would grow the caller's context.

  - The items, in `improve-from-user`'s unified item format.
    - **Verbatim** is the human's exact words.
    - **Lesson drawn** is the caller's first draft, which the learn session's step 2 challenges.

- Verdict marks (address-verdicts): write no feedback file; the source is Mode D over the absolute paths of the verdict files.
  - The caller launches nothing when any of those files already carries a `[Done]` heading.
  - Why: an earlier run likely mined its marks, so a second launch would propose the same lesson as if the human had repeated it.
- PR comments (address-pr-comments): write no feedback file; the source is Mode B over the repo-qualified PR `<owner>/<repo>#<n>`, using step 2's `OWNER_REPO`.
  - Why: the learn session runs in `~/unix-utils`, so a bare PR number would resolve against the wrong repo.

## The launch

Write a prompt file in the caller's own scratchpad, then run:

```bash
~/.claude/skills/lateral-session/scripts/lateral-session.sh ~/unix-utils <prompt-file>
```

- The repo dir is always `~/unix-utils`.
  - Why: the user wants the lessons in the global `CLAUDE.md` and global skills.

- The prompt file says to run `/improve-from-user feedback in <absolute feedback file>`.
  - For PR comments it says `/improve-from-user PR <owner>/<repo>#<n>` instead.
  - For verdict marks it says `/improve-from-user verdict marks on <absolute paths>` instead.

- It also says the human decides in that window which proposals to apply.
- It also says a lesson fitting only the work repo is listed with that repo's name and not written.

- When main's own repo is `~/unix-utils`, the prompt also carries `lateral-session`'s worktree lines (own worktree, merge back, remove it).
  - Why: main may check out or commit in that tree while the learn session edits it.

## Launch refused

- When `lateral-session.sh` exits 2 (for example, not inside tmux), tell the user in one line with the exact command to run later from `~/unix-utils`, and carry on.

- Never fall back to running `improve-from-user` in main.
  - Why: its reads would land in main's context.
