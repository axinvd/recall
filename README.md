# memory

Persistent, self-maintaining memory for [Claude Code](https://claude.com/claude-code),
packaged as a plugin. No embeddings, no vector DB, no running service — just flat markdown
plus a tiny Python CLI, wired so the agent actually *uses* it every session.

The core idea: curated knowledge lives in small markdown **nodes**, each fronted by a
**trigger** — a one-line "load-or-skip" signal. A SessionStart hook regenerates a trigger
index and hands it to the agent on every session, so the right node gets read *before* the
agent re-greps the code. The agent also **writes** nodes itself as it learns (verified
facts only), and the whole graph can be **compacted** so memory stops growing without bound.

## The two layers

| Layer | What | Where | Retrieval |
|-------|------|-------|-----------|
| **Triggered nodes** | curated decisions, designs, gotchas | `memory/` (global) + `<project>/docs/` (local) | trigger-index, loaded on demand |
| **Chat archive** | raw session transcripts | `chats/` (gitignored — data, not versioned) | grep fallback |

- **Global** nodes (`memory/`) are cross-project: tooling, methods, patterns useful in any
  repo. `memory/` is **gitignored by this repo** so your knowledge never ships with the
  plugin — keep it private and versioned by making `memory/` its own **nested git repo**
  (the plugin just sees a folder), or point `MEMORY_GLOBAL` at a directory elsewhere.
- **Local** nodes live in each project's `docs/` and version with that project's code.
- The **chat archive** is a passive backup of past sessions — searched by grep when a
  question isn't covered by any node.

## How it works

**Triggers, not embeddings.** At the scale a personal memory vault operates (hundreds of
nodes), an index that's *actually loaded every session* beats heavier semantic machinery.
The index is ~50 tokens/node and lists every node's trigger; the agent matches the prompt
against triggers and opens just the nodes that fit. Retrieval is **push** (the index is
always in context) rather than **pull** (query-time vector search) — which fixes the usual
failure mode where memory exists but the agent never thinks to look for it.

**The agent maintains it.**
- *Reads* — on a prompt that touches a past decision/architecture/gotcha, the agent reads
  the matching node before grepping code.
- *Writes (autowrite)* — when a session produces durable, **verified** knowledge, the agent
  writes or updates the node itself. Two gates bind: only verified facts are written, and
  unverified ideas/options are never self-promoted — they're offered to you and land
  labelled. (See `guide/workflow.md` for the write-side conventions.)
- *Compacts* — `/mem:compact` applies the Pareto principle retroactively: verbose nodes are
  tightened, nodes that became derivable from the code are downgraded to **link-stubs**
  (trigger + essence + pointer to code), duplicates merged, stale flagged — with a plan you
  approve. This is what keeps memory from only ever growing.

**The chat archive captures everything else.** A SessionStart hook incrementally imports
Claude Code's session transcripts (`~/.claude/projects/*.jsonl`) into `chats/` as one
markdown file per *logical* session — stitching compaction/continuation chains (a single
conversation split across several JSONL files) back into one. Text-only (tool calls and
thinking stripped), subagent sessions skipped by default. It's the grep-able fallback for
anything that never made it into a node.

## Commands

Writing verified knowledge is automatic (autowrite). Two slash commands remain, named for
when you call them:

- `/mem:compact [global|local]` — occasional vault maintenance: the full Pareto pass over
  the graph (derivable nodes → link-stubs, duplicates merged, stale flagged). Plan → approve
  → apply.
- `/mem:import <project|transcript> [N]` — recovery from the archive: mine a past transcript
  (or a project's N most recent) for knowledge that never reached a node — sessions that
  died mid-task, or a project being onboarded into memory.

## CLI

```
memory status             where memory lives + node counts (start here)
memory index [vault]      every node: trigger, outgoing links, incoming count
memory validate [vault]   frontmatter / H1 / dead-link / size checks
memory dump [vault]       JSON of all nodes (feeds /mem:compact)
memory vaults             resolved vault name -> folder mappings
```

Vaults resolve from the environment: `global` = `<repo>/memory` (override with
`MEMORY_GLOBAL`), `local` = `$CLAUDE_PROJECT_DIR/docs`. No hand-maintained registry.

## Node format

```
---
trigger: "Use when ... / Read when ... (≤200 chars; pick one prefix)"
---

# Human-readable H1

Body. Inline links: [label](other-node.md) or [label](~/abs/path.md) cross-vault.
```

`trigger` is the only required, enforced field. One concept per node, kebab-case filenames,
aim for ≥2 outgoing links. Full conventions in `guide/workflow.md`. Copy
`templates/example-global-node.md` into your `memory/` vault as a starter.

## Install

Load the plugin live so it reads/writes the repo in place (no cache copy):

```
claude --plugin-dir /path/to/memory
```

Wrap it in a shell alias so every session gets it. `bin/` goes on `PATH`, which is what
makes the bare `memory` CLI work. (Marketplace install instead *copies* the plugin into a
cache, which freezes the bundled data — fine if your real nodes live elsewhere via
`MEMORY_GLOBAL`, otherwise prefer the live load.)

Command markdown is read at invocation time, so edits to `commands/*.md` apply immediately,
even mid-session. The SessionStart hook has already run, so hook/index changes take effect
next session.

## Your global vault

`memory/` ships empty (it's gitignored — the plugin never carries anyone's knowledge). On
first use, make it a private, versioned vault of your own:

```
mkdir -p memory && cp templates/example-global-node.md memory/
cd memory && git init          # optional: version your nodes in their own private repo
```

Because the parent repo ignores `memory/`, a nested git repo there stays fully private —
push it to a private remote if you want sync/backup. (Or skip git and just keep files; or
set `MEMORY_GLOBAL` to a vault that lives anywhere.)

## Layout

```
.claude-plugin/   plugin.json (SessionStart hooks) + marketplace.json
bin/              memory (CLI wrapper) + session-start.sh (hook)
src/memory.py     the engine (index/validate/status/dump, multi-vault)
commands/         slash commands: compact.md, import.md
scripts/          chat-import pipeline (claude_to_obsidian.py + sync wrapper)
guide/workflow.md the write-side conventions (applied live + loaded by the /mem: commands)
templates/        starter node to copy into your vault
memory/           YOUR global vault (gitignored — keep it as a private nested repo)
chats/            chat archive (gitignored data) — auto-imported transcripts
config.toml       node-size limits (travels with the repo)
```

Start at `guide/workflow.md` for node conventions, or run `memory status`.

## Requirements

- [Claude Code](https://claude.com/claude-code)
- Python 3.11+ (standard library only — no third-party deps)
- The chat-import hook uses `ps`/`getppid` for session detection (macOS/Linux).

## License

MIT — see [LICENSE](LICENSE).
