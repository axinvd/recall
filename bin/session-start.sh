#!/usr/bin/env bash
# SessionStart hook. Regenerates the memory index into a file and prints a short
# pointer to stdout. We do NOT inline the index into the output: SessionStart
# output is capped (~10 KB) and would be truncated-to-file at ~20-50 nodes anyway.
# So we control the file ourselves and direct the agent to Read it up front. That
# file also carries the full write-side conventions (guide/workflow.md, appended
# below): writing to memory is now automatic, so the agent needs the conventions
# EVERY session — not only when a /mem: command happens to load them. The index
# header carries the read-side rules; the appended section carries the write-side.
set -uo pipefail

ROOT="${CLAUDE_PLUGIN_ROOT:-"$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"}"

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$PWD}"
PROJECT="$(basename "$PROJECT_DIR")"
# short path hash so same-named projects in different dirs don't share an index file
HASH="$(printf '%s' "$PROJECT_DIR" | cksum | cut -d' ' -f1)"
OUT="/tmp/memory-index-${PROJECT}-${HASH}.md"

INDEX_STATUS="ok"
if ! INDEX="$(python3 "$ROOT/src/memory.py" index 2>&1)"; then
  INDEX_STATUS="failed"
fi

{
  echo "# Memory index — ${PROJECT} — refreshed at $(date '+%Y-%m-%d %H:%M')"
  echo
  echo "This is the persistent memory: curated markdown nodes. global = cross-project"
  echo "knowledge (lives in the mem plugin repo); local = this project's docs/. Each"
  echo "entry below is one node: its trigger (the load-or-skip signal), outgoing links"
  echo "(→) and incoming count (←). Node BODIES are not loaded — only this index is."
  echo
  echo "How to use: the moment the conversation touches anything a trigger covers — a"
  echo "past decision, an architecture, a known gotcha — Read that node file before"
  echo "grep/re-reading code. That applies all session long, not only at startup:"
  echo "re-check the triggers when the topic shifts, and follow → links deeper."
  echo
  echo "$INDEX"
  echo
  echo "---"
  echo
  echo "## Write-side conventions (from guide/workflow.md)"
  echo
  echo "Writing to memory is automatic — apply these whenever you create or update a node"
  echo "this session, not only when a /mem: command runs. Source of truth: guide/workflow.md."
  echo
  # Inject the guide minus its YAML frontmatter (keep the body from its first H1).
  awk 'NR==1 && /^---/ {f=1; next} f && /^---/ {f=0; next} !f' "$ROOT/guide/workflow.md"
} > "$OUT"

if [[ "$INDEX_STATUS" == "failed" ]]; then
  echo "[memory] WARNING: index generation failed — ${OUT} contains the error output."
  echo "Run \`memory status\` to diagnose. Memory nodes are still on disk:"
  echo "  global: ${ROOT}/memory/   local: ${PROJECT_DIR}/docs/"
  echo "Read ${ROOT}/guide/workflow.md for the memory conventions."
  exit 0
fi

# Compact intro + mandatory read directive (well under the hook output cap). This is the
# only memory guidance injected per session — full conventions live in guide/workflow.md
# (a plugin doc, force-read above; deliberately NOT a vault node, so it stays out of the index).
cat <<EOF
[memory] This session uses the \`mem\` plugin — persistent memory as triggered markdown nodes.

FIRST, before starting on the user's request, Read ${OUT} in full — the freshly regenerated
memory index PLUS the write-side conventions. The header explains the index; the appended
section explains how to write & commit nodes (which you now do automatically — see WRITE).

Then, as you work:
- READ: when a question or task touches a past decision / architecture / gotcha, match a
  node's trigger from the index and Read that node before grep/re-reading code — at
  startup AND mid-session.
- WRITE: when the session produces durable, **verified** knowledge (a decision + its
  rationale, a non-obvious invariant, a rejected approach, a gotcha), write or update the
  node yourself — at the natural close of that piece of work, not only at session end —
  then **commit it immediately** (global nodes in the vault's own repo, e.g.
  \`git -C ${ROOT}/memory add -A && git -C ${ROOT}/memory commit\`; local nodes in the
  project repo). Stage only the node file(s), not unrelated changes. Two gates stay hard:
  write only *verified* facts (confirmed by running it, reading the code, or stated by the
  user), and never promote *unverified* ideas/options/hypotheses without asking the user
  first (offer them, land them labelled). Don't delete/overwrite a node, or append past its
  trigger, without the user's ok. The full conventions (format, trigger writing, Pareto,
  sizes) are in the write-side section of ${OUT} — skim them before your first write.
- RECALL: past work not in any node — grep the chat archive ${ROOT}/chats/code/*.md
  (filter by \`project: <name>\` in frontmatter), then Read the matching transcript.
- /mem:compact = vault-wide Pareto compaction; /mem:import <project|transcript> [N] = mine
  archived chats (interrupted sessions, onboarding). CLI: \`memory status | index | validate\`.
EOF
exit 0
