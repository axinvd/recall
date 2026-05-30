#!/usr/bin/env bash
# SessionStart hook. Regenerates the memory index into a file and prints a short
# pointer to stdout. We do NOT print the index itself: SessionStart output is
# capped (~10 KB) and would be truncated-to-file at ~20-50 nodes anyway. So we
# control the file ourselves and tell the agent where to read it on demand.
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

# Compact intro + pointer (well under the hook output cap). This is the only memory
# guidance injected per session — full conventions live in memory/_workflow.md.
cat <<EOF
[memory] Persistent memory is available as triggered markdown nodes.
- READ: before grep or re-reading code on a past decision / architecture / known gotcha,
  read ${OUT} (the refreshed index), match a node's trigger, then Read that node.
  global = cross-project memory; local = this project's docs/.
- WRITE (do this yourself, no command): at the end of substantive work, proactively write
  VERIFIED, durable knowledge into nodes (Pareto — decisions, rationale, trade-offs,
  gotchas; nothing recoverable from code). No guesses — ideas only on explicit request.
- /mem:compact is the one manual command — it optimizes the graph.
- CLI: \`memory status | index | validate\`. Full conventions: memory/_workflow.md.
EOF
exit 0
