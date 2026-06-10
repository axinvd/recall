#!/usr/bin/env bash
# SessionStart hook. Regenerates the memory index into a file and prints a short
# pointer to stdout. We do NOT inline the index/guide into the output: SessionStart
# output is capped (~10 KB) and would be truncated-to-file at ~20-50 nodes anyway.
# So we control the files ourselves and direct the agent to Read them up front — the
# index (all nodes) and the workflow guide — before it starts on the user's request.
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
  echo "Consult these nodes before grep/re-reading code when a question touches a"
  echo "past decision, architecture, or known gotcha. Match the trigger, then Read"
  echo "the node. global = cross-project memory; local = this project's docs/."
  echo
  echo "$INDEX"
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

FIRST, before starting on the user's request, Read both files in full:
  1. ${OUT}
     — the freshly regenerated index: every memory node with its trigger + links.
  2. ${ROOT}/guide/workflow.md
     — the guide for reading, writing and curating memory.

Then, as you work (details in the guide):
- READ: when a question or task touches a past decision / architecture / gotcha, match a
  node's trigger from the index and Read that node before grep/re-reading code — at
  startup AND mid-session.
- WRITE: after the user confirms the task done, capture verified durable knowledge into
  nodes yourself (Pareto, verified-only); offer to commit.
- RECALL: past work not in any node — grep the chat archive ~/vault/chats/code/*.md
  (filter by \`project: <name>\` in frontmatter), then Read the matching transcript.
- /mem:optimize tunes memory for this session (save + surface unwritten candidates +
  reconcile touched nodes); /mem:optimize all = vault-wide compaction.
  CLI: \`memory status | index | validate\`.
EOF
exit 0
