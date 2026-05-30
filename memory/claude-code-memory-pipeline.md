---
trigger: "Read when designing Claude Code memory — chat archive, concept notes, project CLAUDE.md, vault layers"
title: Claude Code memory pipeline
tags: ["permanent", "claude-code", "obsidian", "memory", "tooling"]
created: 2026-04-25
updated: 2026-04-25
status: active
type: permanent
---

# Claude Code memory pipeline

Local Obsidian vault at `~/vault` is the persistent-memory store for Claude Code sessions across projects. Four layers, each with a distinct role.

## Layers

- **`logs/`** — short structured session logs written by `/mem:save`. The active read path on `/mem:resume`.
- **`permanent/`** — Zettelkasten concept notes. Distilled long-term knowledge, dense wikilinks, one concept per note. This is what survives across months.
- **`chats/code/`** — passive archive of every meaningful Claude Code session. Refreshed by `/mem:import`. Searchable backup, not auto-loaded.
- **`graphify/<project>/`** — codebase knowledge graph per project. Lets Claude understand structure without re-reading source files.

## Source of truth for chats

Sessions are read **directly from `~/.claude/projects/<encoded-cwd>/[<branch>/]<uuid>.jsonl`**, not via `claude-extract`. The extractor names files `claude-conversation-{YYYY-MM-DD}-{shortid}.md` and silently collides on agent-dispatch days (loses ~50% of sessions). JSONL has UUID-named files in project-encoded directories — no collisions, plus the path encodes project membership.

## What gets written to `chats/code/`

For each JSONL session: filename `<date>-<project>-<full-uuid>.md`. Body keeps **only**:

- real user prompts (excluding `tool_result` events that come back as `type: user`)
- assistant `text` blocks

Dropped: `tool_use`, `tool_result`, `thinking`, `attachment`, `file-history-snapshot`, `permission-mode`, `system`. Reduces 433 MB raw JSONL to 18 MB markdown — same content set as `claude-extract`. Tool args/results would balloon archive 10× with mostly noise; not worth it.

Filtered: sessions with fewer than `--min-messages 3` total or `--min-user 1` real user prompts are skipped (~5% of sessions are agent-dispatch noise).

## Active vs passive memory

`chats/` is **passive**. Claude does not auto-load it on session start. It serves three uses:

1. Obsidian Graph View / Calendar / full-text search — when user remembers "we discussed X around February" and wants to find it.
2. Grep target — `grep -l 'project: myProject' ~/vault/chats/code/*.md`.
3. On-demand retrieval — Claude reads a specific archive file when asked.

**Active memory** = `[vault-mem-namespace](vault-mem-namespace.md)` commands writing to `logs/` + concept notes in `permanent/` + project-level `CLAUDE.md`. The chat archive is fallback, not primary.

## Trade-offs encoded in this design

- No tool_use/tool_result preservation — saves disk + readability, loses fine-grained "what bash command did I run" recall.
- No cron — `/mem:import` on demand. Avoids Full Disk Access setup, but archive can drift if user forgets.
- `chats/` not auto-queried — keeps context window small; relies on user discipline to use `/mem:save` and `permanent/` for what matters.

## Related
- [vault-mem-namespace](vault-mem-namespace.md)
- [claude-code-jsonl-format](claude-code-jsonl-format.md)
