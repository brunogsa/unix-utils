# markdown-to-google-docs — flow overview

Human-facing overview for auditing the flow at a glance. Non-authoritative — the numbered steps in [`../SKILL.md`](../SKILL.md) win on any conflict. Regenerate this file whenever the skill's flow changes.

```mermaid
flowchart TD
  n1(["1. User wants a .md file published as a Google Doc"]):::start
  n2["2. Check dependencies: mmdc, pandoc, gcloud with Drive scope"]
  n3["3. Step 1 · Run render_and_build.py on the markdown.<br/>Renders each mermaid block to PNG, resolves relative images, runs pandoc.<br/>Confirm the embedded image count equals the expected diagram count"]
  n4{"4. Step 2 · Ask the user how to deliver"}:::gate
  n4a["4a. Fill an existing doc in place.<br/>Read the target first, since files.update replaces all content.<br/>Keep any header the user had"]
  n4b["4b. Create a new Doc"]
  n4c(["4c. Manual import: hand the user the .docx, they upload it to Drive.<br/>No auth, no further steps"]):::done
  n5{"5. Needs Drive auth and token errors?"}
  n5a["5a. Ask the user to run gcloud auth login --enable-gdrive-access.<br/>The assistant cannot do it for them"]:::gate
  n6["6. Step 3 · Verify conversion fidelity once on a throwaway doc:<br/>test, export, count img tags and heading styles, delete the scratch doc"]
  n7["7. Step 4 · Upload for real: gdoc_upload.py update with the fileId,<br/>or test to create a new doc and read its id"]:::dispatch
  n8["8. Step 5 · Export the final doc and confirm diagrams, headings, tables, key text.<br/>Count with grep -o piped to wc -l, never grep -c"]
  n9(["9. Delete any scratch docs created during verification"]):::done

  n1 --> n2 --> n3 --> n4
  n4 -->|"in place"| n4a --> n5
  n4 -->|"new doc"| n4b --> n5
  n4 -->|"zero setup"| n4c
  n5 -->|"yes"| n5a --> n6
  n5 -->|"no"| n6
  n6 --> n7 --> n8 --> n9

  classDef start fill:#d4edda,stroke:#28a745
  classDef gate fill:#fff3cd,stroke:#d39e00
  classDef dispatch fill:#d6e9f8,stroke:#2f7fc1
  classDef done fill:#d4edda,stroke:#28a745
```
