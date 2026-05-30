---
trigger: "Read when designing vault commands — /mem:save, /mem:import, process-tree session detection, mtime fallback"
title: Vault /mem: namespace — slash commands for persistent memory
tags: ["permanent", "claude-code", "obsidian", "memory", "tooling", "slash-commands"]
created: 2026-04-25
updated: 2026-04-25
status: active
type: permanent
---

# Vault /mem: namespace — slash commands for persistent memory

Three Claude Code slash commands (`/mem:save`, `/mem:resume`, `/mem:import`) that turn `~/vault/` into an active memory layer across sessions. Definitions live in `~/.claude/commands/mem/{save,resume,import}.md` — installed once, available globally in every Claude Code session.

## /mem:resume — start of session

Inputs: optional project name (overrides auto-detection).

Steps the command instructs Claude to do:
1. Detect project from `git rev-parse --show-toplevel` basename, fall back to `general`.
2. Read project-level `CLAUDE.md` (if in a repo).
3. Read last 3 logs in `~/vault/logs/` scoped by `<project>-` filename prefix; fall back to overall recents if none.
4. Survey `~/vault/permanent/` for notes tagged `project-<name>`; read titles + first paragraph of up to 5.
5. List (don't read bodies of) recent chat archives in `~/vault/chats/code/`.
6. Output a structured brief: stack & conventions, last sessions with takeaways, active concept notes, aggregated TODOs, suggested next step.

Read-only — never modifies vault.

## /mem:save — end of session

Inputs: optional slug (e.g. `mem-setup`); else Claude infers a 2-4 word slug from the session topic.

Steps:
1. Detect project (same as resume).
2. **Archive the live chat.** Calls `python3 ~/scripts/claude_to_obsidian.py --vault-dir ~/vault --current` which detects this session's JSONL via parent-process tree (see [claude-code-jsonl-format](claude-code-jsonl-format.md)) and writes `~/vault/chats/code/<date>-<project>-<uuid>.md`. Min-message filters bypassed.
3. Build log filename `~/vault/logs/<date>-<project>-<slug>.md` (with `-2`, `-3` suffix on collision).
4. Synthesize from the conversation: what was done, decisions, gotchas, pending TODOs, next entry point.
5. Write the log with frontmatter (`chat_archive`, `session_id`, `tags`).
6. Propose 0-3 concept notes for `permanent/`. **Does not create them automatically** — user picks which to promote.

## /mem:import — refresh chat archive

Bulk-refreshes `~/vault/chats/code/` from `~/.claude/projects/`. Idempotent by session UUID. Forwards `$ARGUMENTS` to the script (e.g. `--min-messages 5`).

Used rarely — typically only after pulling sessions from another machine or recovering from a broken archive. Per-session archiving happens automatically inside `/mem:save`.

## Design choices

**`mem:` namespace.** Audited plugin commands across `~/.claude/plugins/` before picking the prefix; it does not collide with `superpowers:`, `figma:`, `commit-commands`, or any other installed plugin. Future plugins are unlikely to claim `mem:`.

**Project detection via git.** `git rev-parse --show-toplevel` is the cheapest deterministic project boundary. No fuzzy matching, no config file. If not in a repo, `general` is the bucket.

**No auto-git-commit.** Logs live in `~/vault/`, separate from project repos. Original reference design (`lucasrosati/claude-code-memory-setup`) had `/save` auto-push to origin — too invasive, removed.

**Concept-note proposals are not auto-promoted.** `/mem:save` lists 0-3 candidates with one-line purposes. The user explicitly picks which to write. This keeps `permanent/` curated rather than letting it drift into a session-log dump.

**Chat archive linked from log frontmatter.** `chat_archive: chats/code/<file>` in the log YAML lets future sessions trace back to the full transcript when the log's distillation isn't enough. The wikilink in `## Related` is the user-facing path.

**Process-tree session detection over mtime.** See [claude-code-jsonl-format](claude-code-jsonl-format.md) for why mtime fails with parallel sessions and subagents.

## Files involved

- `~/.claude/commands/mem/save.md` — slash command body (instructions to Claude)
- `~/.claude/commands/mem/resume.md`
- `~/.claude/commands/mem/import.md`
- `~/scripts/claude_to_obsidian.py` — JSONL converter, supports `--current`, `--session-jsonl PATH`, full sync
- `~/scripts/sync_claude_obsidian.sh` — thin wrapper for `/mem:import`, logs to `~/scripts/sync.log`
- `~/vault/CLAUDE.md` — vault rules; lists the `/mem:` commands

## What this layer does NOT do

- It does not auto-load chat archives into Claude's context. `chats/` is passive (search/grep target). Active context = logs/ + permanent/ + project CLAUDE.md.
- It does not enforce `/mem:save` discipline. If the user forgets, the chat still ends up in `~/.claude/projects/` (Claude Code's own JSONL store) and can be recovered later via `/mem:import` — but no log will exist to summarize it.
- It does not run on a cron. On-demand only.

## Related
- [claude-code-memory-pipeline](claude-code-memory-pipeline.md) — the four-layer architecture this namespace operates on
- [claude-code-jsonl-format](claude-code-jsonl-format.md) — what /mem:save and /mem:import actually parse
