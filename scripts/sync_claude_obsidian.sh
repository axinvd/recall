#!/bin/bash
# Chat-import pipeline. Reads ~/.claude/projects/*.jsonl and writes one markdown
# per logical session into <repo>/chats/code/. Location-independent: resolves its own dir.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
VAULT_DIR="$REPO_DIR"            # chats live in the repo under chats/ (gitignored — data, not versioned)
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
