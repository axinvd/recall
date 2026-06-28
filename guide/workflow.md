---
trigger: "Read when working on the memory system itself — node conventions, trigger writing, node size, Pareto, compaction"
title: Memory workflow
tags: [memory, meta]
type: reference
---

# Memory workflow

The write-side conventions of the triggered-markdown memory. The assistant applies them
**live** — writing verified nodes itself as a session produces durable knowledge (the
SessionStart hook carries the trigger to do so); `/mem:import` and `/mem:compact` load this
file before they touch nodes too. Read it also when changing the memory system itself.
Read-side rules (trigger matching, recall, the command list) live in the SessionStart hook
text and the index header — not here.

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

**Readable code and interfaces document themselves.** If a parameter's purpose, a flag's
effect, or a flow is already clear from the signature / type / interface, don't restate it
in memory — the Pareto gate is "would a competent reader of the code need this?", not "is it
true?". A project written in clean, self-explaining code may rightly have only an *overview*
node: what it is, why it exists, the few choices the code can't justify on its own.

**No duplication — decompose instead.** The same Pareto logic applies across nodes: if a
fact lives in the code, it doesn't belong in a doc; if it lives in one doc, it shouldn't be
copied into a second. When two nodes need the same content, factor it into one canonical
node and link to it. Duplication is debt — every copy is one more thing to drift.

The 80/20: a reader + a couple of prompts should reproduce most of a project's value from
nodes alone.

## Verified only

Memory is ground truth, not a scratchpad. Write **only verified information** — confirmed
by running it, reading the code, or stated by the user. No guesses, hypotheses, or hasty
conclusions. Ideas, hunches, and speculation are written **only on the user's explicit
request**, and then labelled as such (e.g. a clearly-marked ideas/backlog node). When unsure whether
something is verified, don't write it.

## Node size & compaction

Soft limit ~150 body lines (`memory validate` warns above). A node that outgrows its
trigger is a split candidate. But the deeper move is **compaction**: once something is
*implemented and plainly readable from the code*, downgrade the node to a **link-stub** —
trigger + one or two lines of durable essence + a link to the code.

Compaction is not only triage (which nodes to stub/merge/drop) — it also **optimizes the
surviving documents themselves**: tighten verbose prose to its durable essence, pull
duplicated content out into one canonical node and link to it (decompose, don't copy), and
trim anything the code now explains. Run `/mem:compact` to do this retroactively
across a vault. Prefer stubbing/splitting/decomposing over endless appending.

## When to write (autowrite)

Write verified durable knowledge into nodes **yourself**, at the natural close of the work
that produced it — don't wait to be asked, and don't batch it all to session end. The bar
is the Pareto + verified-only gates above: a decision and its *why*, a non-obvious
invariant, a rejected approach, a gotcha — not anything the code already shows. Prefer
updating an existing node (match its trigger) over spawning a near-duplicate.

## Never do

- Don't write anything **unverified** on your own — ideas, options weighed, hypotheses.
  Offer them to the user; they enter memory only if picked, and then labelled as unverified.
- Don't delete/overwrite a node, or fold/redirect one into another, without asking.
- Don't append past a node's trigger — split or stub instead.
