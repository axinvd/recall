#!/bin/bash
# Chat-import pipeline. Reads ~/.claude/projects/*.jsonl and writes one markdown
# per session into <vault>/chats/code/. Location-independent: resolves its own dir.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VAULT_DIR="$HOME/vault"          # chats live outside the repo (data, not versioned)
LOG="$SCRIPT_DIR/sync.log"

# keep the log bounded — it appends on every SessionStart
if [ -f "$LOG" ] && [ "$(wc -l < "$LOG")" -gt 400 ]; then
  tail -n 200 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
fi

echo "[$(date)] Sync started" >> "$LOG"

python3 "$SCRIPT_DIR/claude_to_obsidian.py" \
    --vault-dir "$VAULT_DIR" \
    "$@" 2>> "$LOG"

echo "[$(date)] Sync completed" >> "$LOG"
