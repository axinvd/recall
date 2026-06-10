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

(`~/vault/permanent` is a symlink to this repo's `memory/` — Obsidian sees the global
nodes; the repo stays the single source.)

No embeddings, no Qdrant, no running service. Flat markdown + a tiny Python CLI. At the
scale a personal memory vault operates (hundreds of nodes), a trigger-index that's
*actually loaded every session* beats heavier semantic machinery — see `docs/` for the
reasoning.

## How it solves the three pains

1. **Index wasn't being loaded.** A **SessionStart hook** now regenerates the index into
   `/tmp/memory-index-<project>.md` and prints a one-line pointer. The agent is told where
   memory is on every session start — it no longer depends on remembering to run a command.
   (Index goes to a file because the hook's stdout is capped ~10 KB.)
2. **Memory only grew.** **`/mem:optimize all`** applies the Pareto principle *retroactively*:
   verbose nodes are tightened, nodes that became derivable from the code are downgraded to
   **link-stubs** (trigger + essence + pointer to code), duplicates merged or decomposed,
   stale flagged — with a plan you approve.
3. **Memory was scattered.** This repo is a **Claude Code plugin** (hook + commands in
   `.claude-plugin/`) and the **home of global memory** (`memory/`). One place.

## CLI

```
memory status             where memory lives + node counts (start here)
memory index [vault]      every node: trigger, outgoing links, incoming count
memory validate [vault]   frontmatter / H1 / dead-link / size checks
memory dump [vault]       JSON of all nodes (feeds /mem:optimize all)
```

Vaults resolve from the environment: `global` = `<repo>/memory` (override `MEMORY_GLOBAL`),
`local` = `$CLAUDE_PROJECT_DIR/docs`. No hand-maintained vault registry.

## Commands & cadence

- **Writing is automatic, after the task is confirmed done.** The assistant maintains memory
  proactively — once the user confirms the work is complete it writes verified, durable
  knowledge into nodes itself (verified-only + Pareto gates from `guide/workflow.md`) and
  offers to commit. Nothing is written mid-task while facts are in flux.
- `/mem:optimize` — the **one manual command**: optimize memory in light of this session.
  Writes the session's verified knowledge, surfaces borderline candidates (ideas, options
  discussed, hypotheses) as an interactive pick-list, and reconciles the nodes the session
  touched (tighten / stub / merge / flag stale). Plan → approval → apply.
- `/mem:optimize all [global]` — the same pass vault-wide: full Pareto compaction of the
  graph (derivable nodes → link-stubs, duplicates merged/decomposed, stale flagged).
- **Chat archive is automatic.** The SessionStart hook incrementally imports session
  transcripts (subagent sessions are skipped — `--include-subagents` to pull them too).

## Layout

```
.claude-plugin/   plugin.json (SessionStart hooks) + marketplace.json
bin/              memory (CLI wrapper) + session-start.sh (hook)
src/memory.py     the engine (index/validate/status/dump, multi-vault)
commands/         slash commands: optimize.md
scripts/          chat-import pipeline (claude_to_obsidian.py + sync wrapper)
guide/workflow.md the memory conventions — force-read by the hook, NOT a vault node
memory/           GLOBAL MEMORY — cross-project nodes
docs/             this project's own memory + design rationale
```

Start at `guide/workflow.md` for node conventions, or run `memory status`.

## Install (live, no copy)

Marketplace install **copies** the plugin into `~/.claude/plugins/cache/...`, which freezes
the bundled `memory/` data and breaks "the repo is the home of memory". Instead, load it
live (shows up as `mem@inline`) so `${CLAUDE_PLUGIN_ROOT}` points at this repo:

```
claude --plugin-dir ~/projects/memory
```

This is the method actually in use — wrap it in a shell alias so every session gets it.
The engine then reads/writes the live `~/projects/memory/memory`, not a cache copy.
`bin/` is also on `PATH`, which is what makes the bare `memory` CLI work.

## Config

`config.toml` (repo root) holds the node-size limits. Nothing lives under `~/.config` —
the config travels with the repo. Vaults are resolved from the environment, not registered.

## Status

Done: engine, SessionStart hooks (index→file + intro; async chat import), plugin manifest,
`/mem:optimize` (session-delta save + candidate surfacing; `all` = vault-wide compaction —
absorbed the former `/mem:save` and `/mem:compact`), chat-import pipeline with subagent
filtering, global notes moved into `memory/` (`~/vault/permanent` is now a symlink here),
config in-repo. Loaded live via `--plugin-dir` (`mem@inline`). `/mem:import` was dropped —
the hook imports automatically; force a resync with `scripts/sync_claude_obsidian.sh --full`.
