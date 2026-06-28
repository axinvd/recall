---
description: Vault-wide Pareto compaction — re-verify every node against the code; tighten the verbose, stub the derivable, merge duplicates, flag the stale. Plan → approval → apply. Never deletes without confirmation.
allowed-tools: Bash(memory:*), Bash(git:*), Bash(ls:*), Bash(rg:*), Bash(grep:*), Bash(python3:*), Read, Edit, Write, Agent, AskUserQuestion
argument-hint: "[global|local] (default: local)"
---

You are running the **vault-wide memory compaction** — the full retroactive Pareto pass
over every node. Memory should hold what is *hard to recover from code*; this command
tightens what's bloated and removes what's dead, graph-wide. Where the assistant's live
autowrite keeps individual nodes current, this is the occasional whole-graph pass. Sibling:
`/mem:import` (harvest knowledge from archived chats).

**Before anything: Read `$CLAUDE_PLUGIN_ROOT/guide/workflow.md`** — the node conventions
(format, triggers, Pareto, verified-only) this command applies. It is not pre-loaded.

## Vault

`$ARGUMENTS`: `local` (default) / `global`. `global` is higher-stakes — only compact it
when explicitly asked.

## Steps

1. **Dump the nodes.** `memory dump <vault>` — JSON with each node's `trigger`, `h1`,
   `body`, `outgoing`, `incoming`, `abs_path`, `body_lines`. This is your worklist.

2. **Classify each node against the code.** For a small graph do it inline; for many nodes
   (>~8) dispatch **sonnet subagents in parallel**, one per node or small batch. Each node
   gets exactly one verdict (below).

3. **Verify code references before stubbing.** For every STUB/STALE verdict, actually open
   the referenced code (`Read`/`rg`) and confirm the body is genuinely derivable / stale.
   Do not stub on assumption. Capture the real file path for the stub link.

4. **Present the plan and STOP.** A table: `node | verdict | action | one-line reason`,
   then totals (`KEEP n / TIGHTEN n / STUB n / MERGE n → x / STALE n`). Show the proposed
   rewritten body for each STUB **and** each TIGHTEN inline so the user sees what survives.
   **Wait for explicit approval.**

5. **Apply approved actions.** Rewrite STUB and TIGHTEN bodies (Edit), fold+redirect MERGEs
   and decomposed duplicates, delete approved STALE/merged files. Keep every surviving
   node's `trigger` accurate to its new (smaller) body.

6. **Validate.** `memory validate <vault>`; fix any dead links the merges/deletes
   introduced. Re-run until clean.

7. **Report.** Nodes before → after, lines reclaimed, deletions made, and any node you were
   unsure about and left as KEEP for the user to review later.

## Verdicts

- **KEEP** — a decision, rationale, trade-off, non-obvious invariant, gotcha, or rejected
  approach; not recoverable from the code; already tight. Leave untouched.
- **TIGHTEN** — worth keeping, but verbose, restates what the code now shows, or duplicates
  another node. Rewrite down to its durable essence; fold shared content into the canonical
  node and link to it (decompose, don't copy).
- **STUB** — the body now mostly describes what the code plainly shows. Rewrite to: the
  `trigger`, the `# H1`, one–three lines of durable essence (the *why*, if any), and a
  verified link to the authoritative code. The literal "leave only the pointer" move.
- **MERGE** — substantially overlaps another node. Fold the durable content into the
  canonical node, rewrite inbound links, mark this one for deletion.
- **STALE** — contradicts current code or describes something abandoned. Flag for deletion
  with the reason.

A node is a STUB candidate when its body restates the implementation; it is KEEP the moment
it explains a choice the code can't justify on its own. When unsure, KEEP — an over-long
node costs a warning, a wrong deletion costs knowledge.

## Guardrails

- Never delete, blank, or overwrite a node without plan-stage approval.
- A STUB must carry a working link to the code it points at.
- Do not git-commit silently — offer, then act.
- If a node is already a tight KEEP, leave it — compaction is not rewriting for its own sake.
