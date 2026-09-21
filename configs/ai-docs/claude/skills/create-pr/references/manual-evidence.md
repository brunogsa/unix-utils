# Manual evidence: paste the artifact, never narrate it

Read before writing any `<a id="scenario-N"></a>` block in `## Evidences`.

## The rule

- **CRITICAL: Every claim sits immediately next to the artifact that proves it** -- a claim is followed by the command and response that show it, never by a summary paragraph.
  - Bad: "Ran four kit-less-collection shapes against Oracle EBS and three against SGE on stage" followed by prose asserting what each ERP did.
  - That bad version shows no request, no response body, no timestamp -- the reviewer has to take the author's word for it.

- **CRITICAL: The command is pasted as issued, inside a fenced block** -- describing it in prose is not pasting it.
  - "ran four shapes against stage" is a claim, not a command.

- **The response is pasted verbatim**: status line plus body.
  - JSON is pretty-printed per [`json-format-example.md`](json-format-example.md).

- **N runs produce N request/response pairs** -- one bullet may never stand for several runs.
  - Four shapes run means four pairs pasted, not one paragraph summarizing four.

- **Each pair carries its timestamp (ISO-8601 with offset) and the target host or environment** -- e.g. `2026-09-18T14:32:07-03:00, stage.erp.example.com`.
  - A scenario with no timestamp or no host can't be re-dated or re-targeted by a later reader.

## Redaction and elision

- **Redaction is credential values only, replaced in place with a visible `<redacted>` marker** -- the header line stays, so the reader sees that auth was sent.
  - Good: `Authorization: Bearer <redacted>`.
  - Bad: deleting the whole `Authorization` line -- the reader can no longer tell whether the request carried auth.

- **Hosts and URLs are never redacted** -- redacting them destroys the reproducibility that is the artifact's whole job.
  - A scenario whose host is blacked out can't be re-run against the same environment.

- **Elision happens only inside an oversized payload, marked explicitly with what was removed and how much** -- e.g. `… 118 of 120 items elided …`.
  - Prose never replaces an artifact; eliding trims volume inside one, it doesn't summarize what ran.

## Length is never the reason to cut

- **A collapsed `<details>` costs exactly 1 rendered line of the PR body's 64-line budget**, whatever it holds.
  - `scripts/check-pr-page-fit.sh` charges a collapsed block only its `<summary>` line, then skips to `</details>`.
  - 200 lines of cURL and JSON inside cost the same 1 line a one-sentence summary would. There is no page-budget reason to ever summarize evidence.

- **The only real ceiling is GitHub's 65536-character body cap**, already guarded by `scripts/check-pr-body-size.sh`.
  - Pushing that cap means eliding inside the oversized payload per the rule above, never dropping the request or status line.

## No artifact, no scenario

- **CRITICAL: No artifact -> no scenario. Delete the bullet.** Never ship a claim with nothing behind it, and never write "TODO collect post-merge".
  - A PR that ships is a PR whose evidence already exists.
  - This is the remedy that makes `scripts/check-pr-evidence.sh` always satisfiable: that gate fails when a `<a id="scenario-N"></a>` block has no fenced code block and no image.

  - A scenario that can't produce one was never ready to be a scenario -- collect its artifact first, or delete it.

## Beyond HTTP

The exact-invocation-plus-exact-output shape generalizes past cURL:

- A DB query and its result rows.
- A CLI invocation and its stdout.
- A screenshot of a UI state, when the surface is visual rather than textual.

Whatever the surface, the rule is unchanged: paste the exact invocation and its exact output, not a description of either.

## Shape

    <a id="scenario-1"></a>
    <details>
    <summary>Scenario 1 — short description</summary>

    2026-09-18T14:32:07-03:00, stage.erp.example.com

    ```bash
    curl -sS -X POST https://stage.erp.example.com/v1/sales-agreements \
      -H "Authorization: Bearer <redacted>" \
      -H "Content-Type: application/json" \
      -d '{ "lines": [] }'
    ```

    `HTTP/1.1 422 Unprocessable Entity`

    ```json
    {
      "error": "lines must not be empty"
    }
    ```

    </details>
