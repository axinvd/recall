# memory

Persistent, self-maintaining memory for Claude Code — and the single place where
cross-project memory actually lives. Successor to the semi-manual `memgraph` +
chat-import setup.

The whole point: **one repo you can open to see how memory is wired**, instead of
spelunking through `~/.claude`, `~/vault`, `~/scripts`, and a global config.

## The three layers

| Layer | What | Where | Retrieval |
|-------|------|-------|-----------|
| **Triggered nodes** | curated decisions, designs, gotchas | `memory/` (global, in this repo) + `<project>/docs/` (local) | trigger-index, loaded on demand |
| **Chat archive** | raw session transcripts | `~/vault/chats/` (data, not versioned here) | grep fallback |
| **Code graph** | structural code map | per-project (graphify) | on demand |

No embeddings, no Qdrant, no running service. Flat markdown + a tiny Python CLI. At the
scale a personal memory vault operates (hundreds of nodes), a trigger-index that's
*actually loaded every session* beats heavier semantic machinery — see `docs/` for the
reasoning.

## How it solves the three pains

1. **Index wasn't being loaded.** A **SessionStart hook** now regenerates the index into
   `/tmp/memory-index-<project>.md` and prints a one-line pointer. The agent is told where
   memory is on every session start — it no longer depends on remembering to run a command.
   (Index goes to a file because the hook's stdout is capped ~10 KB.)
2. **Memory only grew.** **`/mem:compact`** applies the Pareto principle *retroactively*:
   nodes that became derivable from the code are downgraded to **link-stubs** (trigger +
   essence + pointer to code), duplicates merged, stale flagged — with a plan you approve.
3. **Memory was scattered.** This repo is a **Claude Code plugin** (hook + commands in
   `.claude-plugin/`) and the **home of global memory** (`memory/`). One place.

## CLI

```
memory status             where memory lives + node counts (start here)
memory index [vault]      every node: trigger, outgoing links, incoming count
memory validate [vault]   frontmatter / H1 / dead-link / size checks
memory dump [vault]       JSON of all nodes (feeds /mem:compact)
```

Vaults resolve from the environment: `global` = `<repo>/memory` (override `MEMORY_GLOBAL`),
`local` = `$CLAUDE_PROJECT_DIR/docs`. No hand-maintained vault registry.

## Commands & cadence

- **Writing is automatic.** The assistant maintains memory proactively — at the end of
  substantive work it writes verified, durable knowledge into nodes itself (verified-only +
  Pareto gates from `memory/_workflow.md`). No manual save step.
- **Chat archive is automatic.** The SessionStart hook imports session transcripts.
- `/mem:compact [local|global]` — the **one manual command**: optimize the graph (downgrade
  derivable nodes to link-stubs, merge duplicates, flag stale). Plan → approval → apply.

## Layout

```
.claude-plugin/   plugin.json (SessionStart hook) + marketplace.json
bin/              memory (CLI wrapper) + session-start.sh (hook)
src/memory.py     the engine (index/validate/status/dump, multi-vault)
commands/         slash-command definitions
scripts/          chat-import pipeline
memory/           GLOBAL MEMORY — cross-project nodes (incl. _workflow.md)
templates/        node templates
docs/             this project's own memory + design rationale
```

Start at `memory/_workflow.md` for node conventions, or run `memory status`.

## Install (live, no copy)

Marketplace install **copies** the plugin into `~/.claude/plugins/cache/...`, which freezes
the bundled `memory/` data and breaks "the repo is the home of memory". Instead, load it
live so `${CLAUDE_PLUGIN_ROOT}` points at this repo:

```
# Persistent — symlink the repo into the skills dir (loads every session, no flag):
ln -s ~/projects/memory ~/.claude/skills/mem

# Or per-session, for development:
claude --plugin-dir ~/projects/memory
```

Both make the engine read/write the live `~/projects/memory/memory`, not a cache copy.
Run `/reload-plugins` or start a new session to activate.

## Config

`config.toml` (repo root) holds the node-size limits. Nothing lives under `~/.config` —
the config travels with the repo. Vaults are resolved from the environment, not registered.

## Status

Done: engine, SessionStart hook (index→file + intro), plugin manifest, `/mem:compact`,
`/mem:save`, `/mem:import`, chat-import pipeline, global notes moved into `memory/`
(`~/vault/permanent` is now a symlink here), config in-repo. Loaded live via skills-dir symlink.
