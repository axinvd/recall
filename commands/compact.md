---
description: Pareto-compact the memory — tighten verbose nodes, downgrade nodes that became derivable from code into link-stubs, merge/decompose duplicates, flag stale. Plan → approval → apply. Never deletes without confirmation.
allowed-tools: Bash(memory:*), Bash(git:*), Bash(ls:*), Bash(rg:*), Bash(grep:*), Read, Edit, Write, Agent
argument-hint: "[global|local] (default: local — the current project's docs/)"
---

You are running the **Pareto compaction** pass over the memory. Memory should hold
what is *hard to recover from code* — decisions, rationale, trade-offs, non-obvious
invariants, rejected approaches. Anything now plainly readable from the implementation
(including what a clean signature or interface already makes obvious) should shrink to a
**link-stub**: a trigger + one or two lines of essence + a pointer to the code. The goal is
a smaller, denser graph, not deletion for its own sake.

Compaction is two jobs, not one. **Triage** decides each node's fate (keep / stub / merge /
drop). But it also **optimizes the surviving documents themselves**: tighten verbose prose
to its durable essence, and pull content duplicated across nodes into one canonical node
that the others link to (decompose, don't copy). A node can be worth keeping yet still be
bloated or redundant — fix that too.

## Scope

`$ARGUMENTS` selects the vault: `local` (default — the current project's `docs/`) or
`global` (cross-project memory). Compacting `global` is rarer and higher-stakes — only
do it when explicitly asked.

## Steps

1. **Dump the nodes.** Run `memory dump <scope>` — JSON with each node's `trigger`,
   `h1`, `body`, `outgoing`, `incoming`, `abs_path`, `body_lines`. This is your worklist.

2. **Classify each node against the code.** For a small graph do it inline; for many
   nodes (>~8) dispatch **sonnet subagents in parallel**, one per node or small batch.
   Each node gets exactly one verdict:

   - **KEEP** — contains a decision, rationale, trade-off, non-obvious invariant, gotcha,
     or rejected approach. Not recoverable by reading the code. Already tight. Leave untouched.
   - **TIGHTEN** — the knowledge is worth keeping, but the body is verbose, restates parts
     the code now shows, or duplicates content held in another node. Rewrite it down to its
     durable essence; if the duplication is the problem, fold the shared part into the
     canonical node and link to it (decompose, don't copy). The node survives — leaner.
   - **STUB** — the body now mostly *describes what the code plainly shows* (how a
     function works, current field names, a flow that's obvious from the source). Rewrite
     it down to: the kept frontmatter `trigger`, the `# H1`, **one–three lines of the
     durable essence** (the *why*, if any), and a link to the authoritative code
     (``[impl](path/to/file.ts)`` — use real repo-relative paths you verified). This is
     the literal "leave only the pointer" move.
   - **MERGE** — substantially overlaps another node. Fold the durable content into the
     canonical node, rewrite inbound links to point there, then mark this one for deletion.
   - **STALE** — contradicts the current code or describes something abandoned. Flag for
     deletion with the reason.

   A node is a STUB candidate when its body restates the implementation; it is KEEP the
   moment it explains a choice the code can't justify on its own. When unsure, KEEP — the
   cost of an over-long node is a warning, the cost of a wrong deletion is lost knowledge.

3. **Verify code references before stubbing.** For every STUB/STALE verdict, actually open
   the referenced code (`Read`/`rg`) and confirm the body is genuinely derivable / stale.
   Do not stub on assumption. Capture the real file path for the stub link.

4. **Present the plan and STOP.** A table: `node | verdict | action | one-line reason`,
   then totals (`KEEP n / TIGHTEN n / STUB n / MERGE n → x / STALE n`). Show the proposed
   rewritten body for each STUB **and** each TIGHTEN inline so the user sees what survives.
   **Wait for explicit approval.**
   Honor the standing rule: never delete or overwrite a node without confirmation.

5. **Apply approved actions.** Rewrite STUB and TIGHTEN bodies (Edit), fold+redirect MERGEs
   and decomposed duplicates, delete approved STALE/merged files. Keep every surviving
   node's `trigger` accurate to its new (smaller) body — if a rewrite no longer covers the
   old trigger, tighten the trigger too.

6. **Validate.** Run `memory validate <scope>`; fix any dead links the merges/deletes
   introduced (rewrite or remove them). Re-run until clean.

7. **Report.** One short block: nodes before → after, lines reclaimed, deletions made,
   and any node you were unsure about and left as KEEP for the user to review later.

## Guardrails

- Default scope is `local`. Touch `global` only when asked.
- Never delete or blank a node without step-4 approval.
- A STUB must still carry a working link to the code it points at — a stub with a dead
  link is worse than the original node.
- Do not git-commit. Leave the working tree for the user to review.
- If a node is already a tight KEEP, leave it — compaction is not rewriting for its own sake.
