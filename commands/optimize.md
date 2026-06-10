---
description: Optimize the memory — by default in light of this session (write new verified knowledge, surface unwritten candidates, reconcile the nodes the session touched), or vault-wide with `all` (the full Pareto compaction). Plan → approval → apply. Never deletes without confirmation.
allowed-tools: Bash(memory:*), Bash(git:*), Bash(ls:*), Bash(rg:*), Bash(grep:*), Bash(python3:*), Read, Edit, Write, Agent, AskUserQuestion
argument-hint: "[all] [global|local] (default: this session's delta, local vault)"
---

You are running the **memory optimization** pass. Memory should hold what is *hard to
recover from code* — decisions, rationale, trade-offs, non-obvious invariants, rejected
approaches (the Pareto + verified-only gates from `guide/workflow.md`). This command brings
memory to that state: writing what's missing, tightening what's bloated, removing what's
dead. One command, two scopes.

## Scope

`$ARGUMENTS` selects scope and vault:

- *(empty)* — **session scope** (default): this session's new knowledge + only the nodes
  this session touched.
- `all` — **vault scope**: the full retroactive pass over every node.
- `local` (default) / `global` — which vault. `global` is higher-stakes — only optimize it
  vault-wide when explicitly asked.

## Session scope — steps

1. **Harvest the session** into two buckets, applying the Pareto gate (skip anything
   recoverable from code or obvious from an interface):

   - **VERIFIED** — decisions + rationale, trade-offs, gotchas hit, rejected approaches;
     confirmed by running it, reading the code, or stated by the user. This is what
     autonomous post-task writing would capture anyway.
   - **CANDIDATE** — ideas, options weighed but not decided, hypotheses, half-verified
     observations. You would NOT write these on your own; surface them here because the
     user invoked the command explicitly.

2. **Collect the touched nodes.** From `memory index`: nodes you Read this session, nodes
   whose triggers match what the session worked on, nodes covering code the session
   changed. A handful, not the whole vault — that's what `all` is for.

3. **Reconcile each touched node** against the session's outcome using the verdicts below —
   the session may have made a node stale, derivable from new code, or duplicated by what
   you're about to write. New knowledge goes into existing nodes before new files.

4. **Present the plan and STOP.**
   - New/updated nodes + a verdict table for touched nodes (`node | verdict | one-line reason`).
   - Offer the CANDIDATEs via **AskUserQuestion** (multiSelect; batch into questions of ≤4
     options, label = short name, description = one line + why you didn't dare write it).
     With more than ~12 candidates, fall back to a numbered list.
   - Wait for explicit approval of the rest of the plan.

5. **Apply.** Write per the conventions in `guide/workflow.md` (quoted `trigger` covering
   the body, H1, links to related nodes). Picked CANDIDATEs land clearly labelled as
   unverified (an `## Ideas / unverified` section or an `ideas-backlog` node) — never mixed
   into verified prose.

6. **Refresh this session's chat archive** (best-effort):
   `python3 "$CLAUDE_PLUGIN_ROOT/scripts/claude_to_obsidian.py" --vault-dir ~/vault --current`
   If session detection fails, say so and continue — the SessionStart hook catches up next time.

7. **Validate and offer to commit.** Run `memory validate`; fix what it flags. Offer to
   commit the node changes — never commit without the user's go-ahead.

## Vault scope (`all`) — steps

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
- Verified-only rules the prose: a CANDIDATE enters a node only if the user picked it, and
  only labelled as unverified.
- A STUB must carry a working link to the code it points at.
- Do not git-commit silently — offer, then act.
- If a node is already a tight KEEP, leave it — optimization is not rewriting for its own sake.
