#!/usr/bin/env bash
# SessionStart hook. Builds one file the agent must Read, then prints a short pointer to it.
# The file = the regenerated node index + the full memory guide (guide/workflow.md, appended
# with its frontmatter stripped). All behavioural rules — read, recall, write, commit,
# maintain — live in the guide; the hook only generates the index, wires in the live paths,
# and tells the agent to read the file. (We write to a file, not stdout: SessionStart output
# is capped ~10 KB. The guide is the single source of truth — the hook never restates it.)
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
  echo "# Memory — ${PROJECT} — refreshed at $(date '+%Y-%m-%d %H:%M')"
  echo
  echo "The live index of memory nodes is below; after it, the guide for using and"
  echo "maintaining memory — read both. Vaults: global = ${ROOT}/memory, local ="
  echo "${PROJECT_DIR}/docs. Chat archive (grep fallback): ${ROOT}/chats/code. Each index"
  echo "line shows a node's trigger (the load-or-skip signal), → outgoing links and ←"
  echo "incoming count; node bodies are not loaded — Read the node file when a trigger matches."
  echo
  echo "$INDEX"
  echo
  echo "---"
  echo
  # Append the guide minus its YAML frontmatter (keep the body from its first H1 on).
  awk 'NR==1 && /^---/ {f=1; next} f && /^---/ {f=0; next} !f' "$ROOT/guide/workflow.md"
} > "$OUT"

if [[ "$INDEX_STATUS" == "failed" ]]; then
  echo "[memory] WARNING: index generation failed — ${OUT} contains the error output."
  echo "Run \`memory status\` to diagnose. Memory nodes are still on disk:"
  echo "  global: ${ROOT}/memory/   local: ${PROJECT_DIR}/docs/"
  echo "Read ${ROOT}/guide/workflow.md for the memory conventions."
  exit 0
fi

cat <<EOF
[memory] This session uses the \`mem\` plugin — persistent memory as triggered markdown nodes.

Before starting the user's request, Read ${OUT} in full: the live node index plus the guide
for using, writing, committing, and maintaining memory. Re-check it as the topic shifts —
this is your standing instruction for how memory works, not a one-time startup note.
EOF
exit 0
