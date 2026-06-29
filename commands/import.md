---
description: Mine archived chat transcripts for knowledge that never reached memory — sessions that died mid-task, or projects being onboarded. The live knowledge-harvest, replayed over the archive. Plan → approval → apply.
allowed-tools: Bash(memory:*), Bash(git:*), Bash(ls:*), Bash(rg:*), Bash(grep:*), Bash(python3:*), Read, Edit, Write, Agent, AskUserQuestion
argument-hint: "<project>|<transcript.md> [N] (project name → its N most recent transcripts, default 1)"
---

You are running the **memory import from archived chats** — the same verified-knowledge
harvest the assistant does live, but the evidence is archived transcript(s) in
`$CLAUDE_PLUGIN_ROOT/chats/code/` instead of the current conversation. Typical uses: a
session that died before its knowledge was written (crash, API errors, closed laptop), or
onboarding a project whose sessions never fed memory. Note the transcript *sync* into the
archive is automatic (SessionStart hook) — this command extracts *knowledge* from the
archive into nodes.

**Before anything: Read `$CLAUDE_PLUGIN_ROOT/guide/workflow.md`** — the node conventions
(format, triggers, Pareto, verified-only) this command applies. It is not pre-loaded.

## Steps

1. **Resolve the transcripts.** `$ARGUMENTS`: a path is used as-is; a project name resolves
   to `$CLAUDE_PLUGIN_ROOT/chats/code/*-<project>-*.md` sorted by date, newest N (default 1). List what
   you picked before reading. If nothing matches, show the nearest project names from the
   archive and stop.

2. **Read each transcript and harvest** into VERIFIED / CANDIDATE buckets (the Pareto +
   verified-only gates from `guide/workflow.md`; CANDIDATE = ideas, options weighed,
   hypotheses you would not write on your own) — with two transcript-specific cautions:
   - Transcripts are text-only (no tool output). Treat a claim as VERIFIED only when the
     transcript says it was verified (tests run, committed, user confirmed) — and when it
     concerns code, re-check against today's code before writing; code may have moved
     since the chat.
   - **Check the tail.** If the transcript ends mid-task (API errors, an unanswered user
     request), report the interrupted work explicitly in the plan — it is a surfaced TODO,
     not memory.

3. **Collect and reconcile touched nodes** of the *target project's* vault plus global:
   nodes whose triggers match what the transcript worked on. Verdicts KEEP / TIGHTEN /
   STUB / MERGE / STALE (full definitions in `/recall:compact`'s doc).

4. **Route the knowledge.** Project-scoped findings go to that project's `docs/` — not the
   current repo's. If the target project has no `docs/` vault yet, creating it is an
   onboarding step: ask first. Generalizable findings go to the global vault as usual.

5. **Present the plan and STOP.**
   - New/updated nodes + the verdict table + any interrupted-tail TODOs.
   - Offer the CANDIDATEs via **AskUserQuestion** (multiSelect; batch into questions of ≤4
     options, label = short name, description = one line + why you didn't dare write it).
     With more than ~12 candidates, fall back to a numbered list.
   - Wait for explicit approval of the rest of the plan.

6. **Apply.** Write per the conventions in `guide/workflow.md`. Picked CANDIDATEs land
   clearly labelled as unverified — never mixed into verified prose.

7. **Validate and offer to commit.** Run `memory validate`; fix what it flags. Offer to
   commit in the target repo(s) — never commit without the user's go-ahead.

## Guardrails

- Never delete, blank, or overwrite a node without plan-stage approval.
- Verified-only rules the prose: a CANDIDATE enters a node only if the user picked it, and
  only labelled as unverified.
- Creating a `docs/` vault in another project is an explicit ask, not a side effect.
- Do not git-commit silently — offer, then act.
