# Memory — using & maintaining

The one guide for this triggered-markdown memory: how to read it, write it, and keep it
healthy. The SessionStart hook puts this in front of you every session (writing is automatic
and can happen in any session); `/mem:import` and `/mem:compact` load it too. Everything
operational lives here.

## Using memory (read & recall)

- **Read on match.** When a prompt touches what a node's trigger covers — a past decision,
  an architecture, a known gotcha — Read that node *before* grepping or re-reading code. All
  session long, not just at startup: re-check triggers as the topic shifts, and follow the
  `→` links. The index is the load-or-skip layer; the node file is the content.
- **Recall the archive.** For past work captured in no node, grep the chat archive
  (`<plugin>/chats/code/*.md`, filtered by `project: <name>` in frontmatter) and Read the
  match. The archive is the grep-fallback; curated nodes are primary memory.

## Layout

- **global** — `<repo>/memory/*.md` — cross-project knowledge. **local** —
  `<project>/docs/*.md` — project-scoped designs/decisions. **chats** — auto-imported
  transcripts, grep fallback only (not nodes).
- A note is `local` by default; promote to `global` only when it generalizes.

## Node format

```
---
trigger: "Use when ... / Read when ... (≤200 chars; pick one prefix)"
---

# Human-readable H1

Body. Inline links: [label](other-node.md) or [label](~/abs/path.md) cross-vault.
```

`trigger` is the only required field — the load-or-skip signal in the index; always
double-quote it (YAML breaks on unquoted colons). H1 required, kebab-case filename, one
concept per node, aim for ≥2 outgoing links.

## Trigger writing

A load-or-skip signal. Two rules: (1) **covers the whole body** — if the body drifts past
what the trigger predicts, widen it or split the node; (2) **specific to real prompts** —
include the distinctive nouns/files/components the node actually contains (too generic fires
on everything; too narrow is abandoned). Structure: `<prefix> <action/situation> — <key
topics>`, where `Use when` = action/task triggers and `Read when` = context/reference.

## What to document (Pareto)

Memory holds what's **hard to recover from code**: decisions + rationale, trade-offs,
non-obvious invariants, rejected approaches — NOT what's obvious from code, trivial changes,
formatting, or temporary workarounds. The gate is "would a competent reader of the code need
this?", not "is it true?": if a parameter's purpose, a flag's effect, or a flow is already
clear from the signature/type/interface, don't restate it. Clean, self-explaining code may
rightly have only an *overview* node — what it is, why it exists, and the few choices the code
can't justify on its own. **No duplication — decompose instead:** if a fact lives in the code
it isn't a doc; if it lives in one node it isn't copied into a second — factor shared content
into one canonical node and link to it. Duplication is debt: every copy is one more thing to
drift. The 80/20: a reader + a few prompts should reproduce most of a project's value from
nodes alone.

## Verified only

Memory is ground truth, not a scratchpad. Write **only verified facts** — confirmed by
running it, reading the code, or stated by the user. No guesses or hypotheses. Ideas and
speculation go in **only on the user's explicit request**, labelled as such (e.g. a
clearly-marked ideas/backlog node). If unsure it's verified, don't write it.

## When to write (autowrite)

Write verified durable knowledge into nodes **yourself**, at the natural close of the work
that produced it — don't wait to be asked, and don't batch it to session end. The bar is the
Pareto + verified gates above. Prefer updating an existing node (match its trigger) over
spawning a near-duplicate.

## Commit after writing

A write isn't done until it's committed — version nodes immediately, don't leave them dirty:

- **Global** → commit in the vault's own repo: `git -C <memory-vault> add -A && git -C
  <memory-vault> commit` (default vault is `memory/`, a private git repo nested in the plugin,
  which the plugin repo gitignores).
- **Local** → commit in that project's repo, with the code change the note describes.

This is the one place "commit only when asked" is pre-authorized — but only the node file(s):
stage just those, never sweep unrelated changes into the commit. Keep the message short (what
knowledge changed, not how).

## Node size & compaction

Soft limit ~150 body lines (`memory validate` warns above). A node that outgrows its trigger
is a split candidate. The deeper move is **compaction**: once something is implemented and
plainly readable from the code, downgrade the node to a **link-stub** — trigger + a line or
two of durable essence (the *why*, if any) + a link to the code. Compaction is not only triage
(which nodes to stub/merge/drop): it also optimizes the survivors — tighten verbose prose to
its durable essence, pull duplicated content into one canonical node and link to it, and trim
anything the code now explains. Prefer stubbing/splitting/decomposing over endless appending.

## Maintenance commands

- `/mem:compact [global|local]` — vault-wide Pareto pass: re-verify each node against the
  code, then tighten / stub / merge / flag stale. Plan → approval → apply.
- `/mem:import <project|transcript> [N]` — mine archived chats for knowledge that never
  reached a node (sessions that died mid-task, or a project being onboarded).
- CLI: `memory status | index | validate | dump`.

## Never do

- Don't write anything **unverified** on your own — offer it to the user; it enters memory
  only if picked, and then labelled as unverified.
- Don't delete/overwrite a node, or fold/redirect one into another, without asking.
- Don't append past a node's trigger — split or stub instead.
