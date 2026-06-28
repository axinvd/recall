---
trigger: "Read when learning the node format — what a global memory node looks like, how triggers/links work (copy into memory/ as a starter)"
title: Example global node
tags: [memory, example]
type: reference
---

# Example global node

A sample node showing the format. Copy it into your **global** vault (`memory/`) as a
starting point, then replace it with real nodes. The global vault holds cross-project
knowledge — tooling, methods, patterns useful in any repo; project-scoped notes live in that
project's `docs/` instead (the **local** vault). `memory/` is gitignored by this repo, so
keep your global nodes as their own private git repo nested in that folder, or point
`MEMORY_GLOBAL` elsewhere.

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
