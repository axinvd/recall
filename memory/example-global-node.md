---
trigger: "Read when learning the node format — what a global memory node looks like, how triggers/links work (delete this once you have your own nodes)"
title: Example global node
tags: [memory, example]
type: reference
---

# Example global node

This is a sample node so the global vault isn't empty and the format is visible. The
**global** vault (`memory/` in this repo, or wherever `MEMORY_GLOBAL` points) holds
cross-project knowledge — tooling, methods, patterns useful in any repo. Project-scoped
notes live in that project's `docs/` instead (the **local** vault).

## What a node is

- The `trigger` (front-matter, ≤200 chars, always double-quoted) is the **only required
  field** — it's the load-or-skip signal the agent reads from the always-on index. Write it
  so it fires on the prompts this node should answer, and skips otherwise.
- One concept per file, kebab-case filename, an `# H1`, and ideally ≥2 inline Markdown
  links to sibling nodes (see the README for the link syntax).

## How retrieval works

Every session, a SessionStart hook regenerates a trigger index and tells the agent to read
it. When a prompt matches a trigger, the agent opens that one node before grepping code —
no embeddings, no running service, just markdown plus a tiny CLI. See the README for the
full picture, and `guide/workflow.md` for the write-side conventions.

Delete this node once you've written real ones.
