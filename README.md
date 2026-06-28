# memory

Persistent, self-maintaining memory for Claude Code — and the single place where
cross-project memory actually lives. Successor to the semi-manual `memgraph` +
chat-import setup.

The whole point: **one repo you can open to see how memory is wired**, instead of
spelunking through `~/.claude`, `~/scripts`, and a global config.

## The three layers

| Layer | What | Where | Retrieval |
|-------|------|-------|-----------|
| **Triggered nodes** | curated decisions, designs, gotchas | `memory/` (global, in this repo) + `<project>/docs/` (local) | trigger-index, loaded on demand |
| **Chat archive** | raw session transcripts | `chats/` (in this repo, gitignored — data, not versioned) | grep fallback |

(Both the nodes and the chat archive live in this repo — one place. The archive is
`.gitignore`d, so it stays out of version control while still travelling with the code.)

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
   verbose nodes are tightened, nodes that became derivable from the code are downgraded to
   **link-stubs** (trigger + essence + pointer to code), duplicates merged or decomposed,
   stale flagged — with a plan you approve.
3. **Memory was scattered.** This repo is a **Claude Code plugin** (hook + commands in
   `.claude-plugin/`), the **home of global memory** (`memory/`), and the **chat archive**
   (`chats/`, gitignored). One place.

## CLI

```
memory status             where memory lives + node counts (start here)
memory index [vault]      every node: trigger, outgoing links, incoming count
memory validate [vault]   frontmatter / H1 / dead-link / size checks
memory dump [vault]       JSON of all nodes (feeds /mem:compact)
```

Vaults resolve from the environment: `global` = `<repo>/memory` (override `MEMORY_GLOBAL`),
`local` = `$CLAUDE_PROJECT_DIR/docs`. No hand-maintained vault registry.

## Writing & cadence

- **Autowrite.** The assistant writes verified durable knowledge into nodes *itself*, as a
  session produces it — no command to run. Two gates bind (from `guide/workflow.md`):
  only *verified* facts are written, and *unverified* ideas/options/hypotheses are never
  self-promoted — they're offered to you and land labelled. (Earlier this was a manual
  `/mem:save`; restored to autowrite 2026-06-28 — history in `docs/vault-mem-namespace.md`.)
- Two slash commands remain, **named for when you call them**:
  - `/mem:compact [global]` — occasional vault maintenance: full Pareto compaction of the
    graph (derivable nodes → link-stubs, duplicates merged/decomposed, stale flagged).
  - `/mem:import <project|transcript> [N]` — recovery from the archive: mines a past
    transcript (or a project's N most recent) for knowledge that never reached nodes —
    sessions that died mid-task, or projects being onboarded into memory.
- **Chat archive is automatic.** The SessionStart hook incrementally imports session
  transcripts into `chats/`, stitching compaction/continuation chains into one file per
  logical session (subagent sessions are skipped — `--include-subagents` to pull them too).

## Layout

```
.claude-plugin/   plugin.json (SessionStart hooks) + marketplace.json
bin/              memory (CLI wrapper) + session-start.sh (hook)
src/memory.py     the engine (index/validate/status/dump, multi-vault)
commands/         slash commands: compact.md, import.md
scripts/          chat-import pipeline (claude_to_obsidian.py + sync wrapper)
guide/workflow.md the write-side conventions — applied live by the assistant + loaded by the /mem: commands; NOT a vault node
memory/           GLOBAL MEMORY — cross-project nodes
chats/            chat archive (gitignored data) — auto-imported session transcripts
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

Live-reload nuance (verified): command markdown is read at invocation time, so edits to
`commands/*.md` apply immediately even mid-session; the SessionStart hook has already run,
so hook/index changes only take effect on the next session.

## Config

`config.toml` (repo root) holds the node-size limits. Nothing lives under `~/.config` —
the config travels with the repo. Vaults are resolved from the environment, not registered.

## Status

Done: engine, SessionStart hooks (index→file + intro; async chat import), plugin manifest,
**autowrite** (the assistant writes verified nodes itself; `/mem:save` was deleted), the two
commands — `/mem:compact` (vault-wide Pareto pass) and `/mem:import` (knowledge from archived
chats; the transcript *sync* stays automatic — force a resync with
`scripts/sync_claude_obsidian.sh --full`) — chat-import pipeline with subagent filtering and
**compaction/continuation stitching** (one file per logical session), the chat archive moved
**into the repo** at `chats/` (gitignored; `~/vault` retired), config in-repo. Loaded live
via `--plugin-dir` (`mem@inline`). Write-path history (the `/mem:optimize` merge+reversal,
and autowrite drop+restore) is in `docs/vault-mem-namespace.md`.
