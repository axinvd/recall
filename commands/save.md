---
description: End-of-session memory save — write this session's verified knowledge, surface unwritten candidates as a pick-list, reconcile the nodes the session touched. Plan → approval → apply. Never deletes without confirmation.
allowed-tools: Bash(memory:*), Bash(git:*), Bash(ls:*), Bash(rg:*), Bash(grep:*), Bash(python3:*), Read, Edit, Write, Agent, AskUserQuestion
argument-hint: "(no arguments — operates on this session's delta)"
---

You are running the **end-of-session memory save**. Memory should hold what is *hard to
recover from code* — decisions, rationale, trade-offs, non-obvious invariants, rejected
approaches (the Pareto + verified-only gates from `guide/workflow.md`). This command
captures the current session's delta. Siblings: `/mem:compact` (vault-wide maintenance),
`/mem:import` (the same harvest over archived chats).

## Steps

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
   changed. A handful, not the whole vault — that's what `/mem:compact` is for.

3. **Reconcile each touched node** against the session's outcome — the session may have
   made a node stale, derivable from new code, or duplicated by what you're about to
   write. Verdicts: KEEP / TIGHTEN / STUB / MERGE / STALE (full definitions live in
   `/mem:compact`'s doc; in short — tighten verbosity, stub what code now shows, merge
   overlaps, flag contradictions). New knowledge goes into existing nodes before new files.

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

## Guardrails

- Never delete, blank, or overwrite a node without plan-stage approval.
- Verified-only rules the prose: a CANDIDATE enters a node only if the user picked it, and
  only labelled as unverified.
- Do not git-commit silently — offer, then act.
- If a touched node is already a tight KEEP, leave it — this is not rewriting for its own sake.
