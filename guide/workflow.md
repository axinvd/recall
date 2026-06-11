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
request**, and then labelled as such (e.g. an `ideas-backlog` node). When unsure whether
something is verified, don't write it.

## Reading cadence — not just at startup

Read nodes **whenever they become relevant, not only at session start.** The SessionStart
hook loads the index up front, but the trigger→Read move applies all session long: the
moment the work turns to a subsystem, decision, or gotcha a node covers, Read that node
before grep/re-reading code. A node that didn't look relevant at the start often becomes
relevant mid-task — match its trigger from the index and read it then.

## Writing cadence — only by command

Nodes change **only when the user runs a command** — never write or edit memory on your
own initiative. If the session produced something durable (a decision, a gotcha, a
rejected approach), say so and suggest `/mem:save`; the user decides when memory changes.
What an un-run save leaks, `/mem:import` recovers from the chat archive later. The chat
archive itself is imported automatically by the SessionStart hook.

**The commands — named for when you call them:**

- **`/mem:save`** — end of a session (or a mid-session checkpoint): writes the session's
  verified knowledge, **surfaces the borderline candidates** — ideas, options weighed,
  hypotheses you would not have dared write on your own — for the user to pick from
  (picked ones land clearly marked as unverified, never as truth), and reconciles the
  nodes the session touched (tighten / stub / merge / flag stale).
- **`/mem:compact`** — occasional vault maintenance: the same reconciliation vault-wide
  (below).
- **`/mem:import <project|transcript> [N]`** — recovery from the chat archive: the same
  harvest over past transcripts — sessions that died before their end-of-task write, or
  onboarding a project whose sessions never fed memory.

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

## CLI

- `memory status` — where memory lives + node counts. Single overview.
- `memory index [vault]` — every node with trigger, outgoing, incoming.
- `memory validate [vault]` — frontmatter / H1 / dead-link / size checks.
- `memory dump [vault]` — JSON of all nodes (feeds `/mem:compact`).

The SessionStart hook regenerates the index into `/tmp/memory-index-<project>.md` and
prints a pointer — read that file before grep when a question touches a past decision.

## Never do

- Don't write or edit nodes unprompted — memory changes only via `/mem:save` /
  `/mem:import` / `/mem:compact`.
- Don't delete/overwrite a node without asking.
- Don't append past a node's trigger — split or stub instead.
