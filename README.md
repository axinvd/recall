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

**The agent maintains it.** It reads the matching node before grepping, writes verified nodes
itself as it learns (autowrite — unverified ideas are never self-promoted), commits each one,
and periodically compacts the graph so it stops growing. All the operational rules for this
live in one place — **[`guide/workflow.md`](guide/workflow.md)** (reading & recall, node
format, the verified-only / Pareto gates, autowrite, commit-after-write, compaction) — which
the SessionStart hook puts in front of the agent every session, so it's followed, not just
documented.

**The chat archive captures everything else.** A SessionStart hook incrementally imports
Claude Code's session transcripts (`~/.claude/projects/*.jsonl`) into `chats/` as one
markdown file per *logical* session — stitching compaction/continuation chains (a single
conversation split across several JSONL files) back into one. Text-only (tool calls and
thinking stripped), subagent sessions skipped by default. It's the grep-able fallback for
anything that never made it into a node.

## Commands

Writing is automatic (autowrite) — no command for it. Two slash commands remain for
maintenance, both documented under **[Maintenance commands](guide/workflow.md#maintenance-commands)**
in the guide: `/mem:compact` (vault-wide Pareto pass) and `/mem:import` (mine archived chats
for knowledge that never reached a node — interrupted sessions, onboarding).

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

A node is markdown with a one-line `trigger` in YAML front matter and an `# H1` heading; the
`trigger` is the only required field. The full rules — trigger writing, links, size limits —
are in **[the guide](guide/workflow.md#node-format)**. Copy `templates/example-global-node.md`
into your `memory/` vault as a working starter.

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
guide/workflow.md the operational guide (read/write/commit/maintain) — injected every session
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
