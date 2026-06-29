#!/usr/bin/env bash
# SessionStart hook. Two parts, by size:
#   - the node index (variable, can be large) is written to a FILE — kept out of the capped
#     hook output so a big vault never overflows it and gets ignored; the agent Reads it when
#     it needs a trigger.
#   - the memory guide (guide/workflow.md, fixed ~6 KB) is printed INLINE — it's the standing
#     instruction for how to use/write/commit/maintain memory, so it's in front of the agent
#     every session with no Read. The guide is the single source of truth for behaviour; the
#     hook generates the index, wires in live paths, and never restates the guide.
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
  echo "The live node index. Each line is one node: its trigger (the load-or-skip signal),"
  echo "→ outgoing links and ← incoming count. Bodies are NOT here — Read a node file the"
  echo "moment its trigger matches the conversation. Vaults: global = ${ROOT}/memory, local ="
  echo "${PROJECT_DIR}/docs. Chat archive (grep fallback): ${ROOT}/chats/code."
  echo
  echo "$INDEX"
} > "$OUT"

if [[ "$INDEX_STATUS" == "failed" ]]; then
  echo "[memory] WARNING: index generation failed — ${OUT} has the error output."
  echo "Run \`memory status\` to diagnose. Nodes on disk: global ${ROOT}/memory/, local ${PROJECT_DIR}/docs/."
  echo "The memory guide is at ${ROOT}/guide/workflow.md."
  exit 0
fi

cat <<EOF
[memory] \`mem\` plugin — persistent triggered-markdown memory. The guide below is your
standing instruction for using, writing, committing, and maintaining memory this session
(writing is automatic — you do it yourself). The live node index for this project is in
${OUT} — Read it for the triggers, then open a node the moment one matches. Re-apply all of
this as the topic shifts, not just at startup.

EOF
cat "$ROOT/guide/workflow.md"
exit 0
