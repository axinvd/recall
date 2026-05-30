---
trigger: "Read when working on the memory system itself — node conventions, trigger writing, node size, Pareto, compaction"
title: Memory workflow
tags: [memory, meta]
type: reference
---

# Memory workflow

How the triggered-markdown memory works. This node is itself memory — read it when
writing/curating nodes or changing the system.

## Layout

- **global** — `<memory-repo>/memory/*.md` — cross-project knowledge (tooling, methods,
  patterns useful in any repo). Versioned in this repo.
- **local** — `<project>/docs/*.md` — project-scoped designs, decisions, specs. Versioned
  with the project's code.
- **chats** — raw transcripts, auto-imported. Not nodes; grep fallback only.

A note belongs in `local` by default. Promote to `global` only when it generalizes.

## Node format

```
---
trigger: "Use when ... / Read when ... (≤200 chars; pick one prefix)"
---

# Human-readable H1

Body. Inline links: [label](other-node.md) or [label](~/abs/path.md) cross-vault.
```

- `trigger` is the only required, enforced field — it's the load-or-skip signal the agent
  reads from the index. Always double-quote it (YAML breaks on unquoted colons).
- H1 required. kebab-case filenames. One concept per node (atomicity).
- Aim for ≥2 outgoing links — dense linking helps traversal.

## Trigger writing

A trigger is a load-or-skip signal. Two rules:

1. **Covers every topic in the body.** If the body drifts past what the trigger predicts,
   widen the trigger or split the node.
2. **Specific enough to match real prompts.** Include the distinctive nouns/file/component
   names the node actually contains. Too generic fires on everything; too narrow is abandoned.

Structure: `<prefix> <action or situation> — <key topics>`
- `Use when` — action/task triggers (implementing, debugging, scoping).
- `Read when` — context/reference triggers (understanding, onboarding).

## What to document (Pareto)

Memory holds what's **hard to recover from code**. Fix what code can't tell you:
- **Do:** decisions + rationale, trade-offs, non-obvious invariants, rejected approaches.
- **Do NOT:** anything obvious from code, trivial changes, formatting, temporary workarounds.

The 80/20: a reader + a couple of prompts should reproduce most of a project's value from
nodes alone.

## Verified only

Memory is ground truth, not a scratchpad. Write **only verified information** — confirmed
by running it, reading the code, or stated by the user. No guesses, hypotheses, or hasty
conclusions. Ideas, hunches, and speculation are written **only on the user's explicit
request**, and then labelled as such (e.g. an `ideas-backlog` node). When unsure whether
something is verified, don't write it.

## Writing cadence — write yourself

Memory maintains itself: **write proactively, without being asked.** At the end of any
substantive work — a decision made, a non-obvious fix, a rejected approach, a gotcha hit —
capture it into the right node (global or local `docs/`) directly, applying the two gates
above. There is no manual "save" step and no approval gate; you are the one who keeps the
graph current as you work. The chat archive is imported automatically by the SessionStart
hook. The **only manual memory command is `/mem:compact`** — it optimizes the graph (below).

## Node size & compaction

Soft limit ~150 body lines (`memory validate` warns above). A node that outgrows its
trigger is a split candidate. But the deeper move is **compaction**: once something is
*implemented and plainly readable from the code*, downgrade the node to a **link-stub** —
trigger + one or two lines of durable essence + a link to the code. Run `/mem:compact` to
do this retroactively across a vault. Prefer stubbing/splitting over endless appending.

## CLI

- `memory status` — where memory lives + node counts. Single overview.
- `memory index [vault]` — every node with trigger, outgoing, incoming.
- `memory validate [vault]` — frontmatter / H1 / dead-link / size checks.
- `memory dump [vault]` — JSON of all nodes (feeds `/mem:compact`).

The SessionStart hook regenerates the index into `/tmp/memory-index-<project>.md` and
prints a pointer — read that file before grep when a question touches a past decision.

## Never do

- Don't delete/overwrite a node without asking.
- Don't append past a node's trigger — split or stub instead.
