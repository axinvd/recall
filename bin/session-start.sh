#!/usr/bin/env bash
# SessionStart hook. Regenerates the memory index into a file and prints a short
# pointer to stdout. We do NOT inline the index/guide into the output: SessionStart
# output is capped (~10 KB) and would be truncated-to-file at ~20-50 nodes anyway.
# So we control the files ourselves and direct the agent to Read them up front — the
# index (all nodes) and the workflow guide — before it starts on the user's request.
set -uo pipefail

ROOT="${CLAUDE_PLUGIN_ROOT:-"$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"}"

PROJECT="norepo"
if [[ -n "${CLAUDE_PROJECT_DIR:-}" ]]; then
  PROJECT="$(basename "$CLAUDE_PROJECT_DIR")"
fi
OUT="/tmp/memory-index-${PROJECT}.md"

{
  echo "# Memory index — ${PROJECT} — refreshed at $(date '+%Y-%m-%d %H:%M')"
  echo
  echo "Consult these nodes before grep/re-reading code when a question touches a"
  echo "past decision, architecture, or known gotcha. Match the trigger, then Read"
  echo "the node. global = cross-project memory; local = this project's docs/."
  echo
  python3 "$ROOT/src/memory.py" index 2>/dev/null
} > "$OUT" 2>/dev/null

# Compact intro + mandatory read directive (well under the hook output cap). This is the
# only memory guidance injected per session — full conventions live in guide/workflow.md
# (a plugin doc, force-read above; deliberately NOT a vault node, so it stays out of the index).
cat <<EOF
[memory] This session uses the \`mem\` plugin — persistent memory as triggered markdown nodes.

FIRST, before starting on the user's request, Read both files in full:
  1. ${OUT}
     — the freshly regenerated index: every memory node with its trigger + links.
  2. ${ROOT}/guide/workflow.md
     — the guide for reading, writing and curating memory.

Then, as you work:
- READ relevant nodes (at startup AND mid-session): the moment a question or task touches a
  past decision / architecture / known gotcha, match a node's trigger from the index and
  Read that node before grep/re-reading code — a node can become relevant later, not just at
  startup. global = cross-project memory; local = this project's docs/.
- WRITE (yourself, no command) — but only AFTER the user confirms the task is done: then
  proactively capture VERIFIED, durable knowledge into nodes (Pareto — decisions, rationale,
  trade-offs, gotchas; nothing recoverable from code or obvious from an interface). No
  guesses — ideas only on explicit request. Offer to commit the changes at that point.
- RECALL a past session: if the user refers to earlier work and it is NOT in any node, the
  chat archive is a lightweight grep fallback (processed transcripts, not auto-loaded) —
  search ~/vault/chats/code/*.md (filter by \`project: <name>\` in frontmatter), then Read
  the matching transcript.
- /mem:compact optimizes the graph. CLI: \`memory status | index | validate\`.
EOF
exit 0
