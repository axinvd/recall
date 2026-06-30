# recall

**recall** is persistent, self-maintaining memory for [Claude Code](https://claude.com/claude-code).
Your agent remembers decisions, designs, and hard-won gotchas across sessions — and unlike
most agent-memory systems, everything it remembers is a **plain markdown file you can read,
edit, and commit to git**. No embeddings, no vector database, no API keys, no background
service. Just files, plus a tiny standard-library Python CLI, wired so the agent actually
*uses* the memory every session instead of forgetting it exists.

---

## Why recall is different

Most agent memory falls into three camps, and each gives something up:

- **Vector-DB / graph memory layers** — [mem0](https://github.com/mem0ai/mem0),
  [Letta](https://github.com/letta-ai/letta) (ex-MemGPT), [Zep/Graphiti](https://github.com/getzep/graphiti).
  An LLM extracts facts into a vector store or knowledge graph; retrieval is a similarity
  search at query time. Powerful, but the memory is rows in a database you read through an API, not
  text you can open — and they need an LLM/embeddings API key (Zep also a graph DB or its
  cloud).
- **Built-in assistant memory** — [ChatGPT memory](https://openai.com/index/memory-and-new-controls-for-chatgpt/),
  [Claude.ai memory](https://support.claude.com/en/articles/11817273). You *can* view and edit
  the summary now — but it's a vendor-hosted profile that lives in your account settings, not
  in your repo, gets silently re-synthesized in the background, and can't be diffed or shared
  with a team.
- **Coding-agent memory** — the closest cousins. [claude-mem](https://github.com/thedotmack/claude-mem)
  is the popular Claude Code plugin, but it's recall's architectural opposite: SQLite + a
  Chroma vector DB behind a background worker service, stored under `~/.claude-mem/`, recalled
  by semantic search. [Cursor](https://docs.cursor.com/) and
  [Windsurf](https://docs.devin.ai/) Memories, and Claude Code's own built-in auto-memory, are
  plain markdown you can edit — but all of them are **machine-local and not committed to your
  repo** by default, and none use an explicit, declared trigger.

recall makes a different trade: **plain text the agent treats as ground truth, versioned in
your repo.**

| | recall | Vector-DB layers (mem0/Letta/Zep) | Assistant memory (ChatGPT/Claude.ai) | Local agent memory (claude-mem, Cursor, CC built-in) |
|---|:---:|:---:|:---:|:---:|
| **Plain files you open & read** | ✅ markdown | ❌ DB rows via API | ⚠️ summary in settings | ⚠️ some markdown, some a DB |
| **Hand-edit / delete a fact** | ✅ edit the file | ⚠️ via API | ✅ in settings UI | ⚠️ varies |
| **Lives in your git repo / shared with the team** | ✅ committed | ❌ | ❌ | ❌ machine-local |
| **Diffable history / rollback** | ✅ git | ⚠️ audit log at best | ❌ silent re-synthesis | ❌ |
| **No embeddings · no API key · no service** | ✅ none | ❌ LLM/embeddings key | ✅ but vendor-hosted | ❌ (claude-mem: local vector DB + worker) |
| **Recall is reliable** | ✅ index in context every session | ⚠️ query-time search | ✅ auto-injected | ⚠️ search / judgment |

The headline trade: **you give up automatic semantic search; you get memory you can see,
correct, diff, and share like source code.** At the scale a personal vault runs (hundreds of
notes), an index that's genuinely loaded every session beats heavier machinery the agent has
to remember to query.

> **What about Claude Code's own built-in memory?** It's the nearest thing — also plain
> markdown, also an index loaded each session with topic files pulled in on demand. recall's
> difference is two-fold: its nodes live **in your repo and version with your code** (Claude
> Code's memory is machine-local under `~/.claude/`, never shared with a teammate), and each
> node carries an explicit **`trigger`** — a declared load-or-skip signal — instead of leaving
> the agent to guess which file to open.

---

## How you work with it

Day to day, you barely touch it — that's the point.

- **It writes itself.** As the agent learns something durable and verified — a decision and
  its rationale, a non-obvious invariant, an approach you rejected and why — it saves a note
  on its own at the natural close of that work, and commits it. You don't run a "save" command.
- **It reads itself.** Next time a prompt touches that topic, the agent loads the note
  *before* re-grepping the code, so it picks up where past-you left off instead of relearning.
- **You stay in control.** Memory is just files. Open one and read exactly what's remembered.
  Wrong? Edit the markdown. Stale? Delete it. Want to see how a decision evolved? `git log`
  the note. Reviewing a teammate's branch? Their project memory is right there in the diff.
- **It stays small.** Periodically you (or the agent, via `/recall:compact`) prune and tighten
  the vault — collapsing notes the code now explains, merging duplicates — so memory stops
  growing without bound.

The only rule the system holds itself to: **verified facts only.** The agent writes what it
confirmed by running, reading, or being told — never guesses. Speculation enters memory only
when you explicitly ask for it, clearly labelled.

---

## How it works

**Curated knowledge lives in small markdown *nodes*.** Each node is one concept, fronted by a
one-line **trigger** — a "load-or-skip" signal that says *when* this note is worth reading
(e.g. `"Use when deploying a static site to Dokploy — clean URLs, Nixpacks gotcha"`).

**A SessionStart hook builds a trigger index and hands it to the agent every session.** The
index lists every node's trigger and its links — about 50 tokens per node, bodies excluded.
The agent matches your prompt against the triggers and opens only the nodes that fit. This is
the crucial inversion: retrieval is **push** (the index is always in context) rather than
**pull** (a vector query the agent has to decide to run). It fixes the usual failure mode
where memory exists but the agent never thinks to look for it.

**The agent maintains the graph.** It reads matching nodes before grepping, writes verified
nodes itself as it learns, commits each one, follows `→` links between related notes, and
compacts the graph so it stops growing. All the operational rules — node format, the
verified-only and Pareto gates, autowrite, commit-after-write, compaction — live in one place,
**[`guide/workflow.md`](guide/workflow.md)**, which the hook puts in front of the agent every
session, so the conventions are *followed*, not just documented.

**A chat archive catches everything else.** The same hook incrementally imports Claude Code's
session transcripts into `chats/` as one clean markdown file per logical conversation
(stitching compaction/continuation chains back into one, stripping tool calls and thinking).
It's the grep-able fallback for anything that never made it into a curated node.

---

## The two layers

| Layer | What it holds | Where it lives | How it's retrieved |
|-------|------|-------|-----------|
| **Triggered nodes** | curated decisions, designs, gotchas | `memory/` (global) + `<project>/docs/` (local) | trigger index, loaded on demand |
| **Chat archive** | raw session transcripts | `chats/` (gitignored — data, not versioned) | grep fallback |

- **Global** nodes (`memory/`) are cross-project knowledge — tooling, methods, patterns useful
  in any repo. `memory/` is **gitignored by this repo** so your knowledge never ships with the
  plugin; keep it private by making `memory/` its own **nested git repo**, or point
  `MEMORY_GLOBAL` at a directory elsewhere.
- **Local** nodes live in each project's `docs/` and version with that project's code — so
  project memory is shared with anyone who clones the repo.
- The **chat archive** is a passive backup of past sessions, searched by grep only when a
  question isn't covered by any node.

---

## Commands

Writing is automatic — there's no command for it. Two slash commands remain for maintenance
(both documented under [Maintenance commands](guide/workflow.md#maintenance-commands)):

- **`/recall:compact`** — a vault-wide pass: re-verify each node against the code, tighten the
  verbose, stub what the code now explains, merge duplicates, flag the stale. Plan → approve →
  apply.
- **`/recall:import`** — mine the chat archive for knowledge that never reached a node
  (sessions that died mid-task, or a project you're onboarding).

---

## Install

Two ways — both reference this repo by path.

**Live load** — point Claude Code at a local clone so it reads/writes the repo in place:

```
claude --plugin-dir /path/to/recall
```

Best for hacking on the plugin or running your own copy. Wrap it in a shell alias so every
session gets it. `bin/` goes on `PATH`, which is what makes the bare `memory` CLI work. Command
markdown is read at invocation time, so edits to `commands/*.md` apply immediately; hook and
index changes take effect next session.

**Marketplace** — add the catalog repo, then install the plugin from it:

```
/plugin marketplace add axinvd/recall
/plugin install recall@axinvd
```

`recall@axinvd` reads as "the `recall` plugin from the `axinvd` catalog". Marketplace install
*copies* the plugin into a cache, which freezes the bundled folders — fine here, because your
real global nodes live outside the plugin (a nested private repo in `memory/`, or
`MEMORY_GLOBAL`).

### Your global vault

`memory/` ships empty (it's gitignored — the plugin never carries anyone's knowledge). On first
use, make it a private, versioned vault of your own:

```
mkdir -p memory && cp templates/example-global-node.md memory/
cd memory && git init          # optional: version your nodes in their own private repo
```

Because the parent repo ignores `memory/`, a nested git repo there stays fully private — push
it to a private remote for sync/backup. (Or skip git and just keep files; or set
`MEMORY_GLOBAL` to a vault anywhere.)

---

## Inspiration & prior art

recall stands on an idea that several people converged on in early 2026: stop doing
retrieval-over-embeddings, and instead let the agent **maintain its own linked-markdown wiki**.

- **Andrej Karpathy's ["LLM Wiki" gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)**
  (April 2026) is the clearest statement of the pattern: an LLM incrementally builds and
  cross-links a markdown knowledge base instead of querying a vector store — *"Obsidian is the
  IDE; the LLM is the programmer; the wiki is the codebase."*
- **[lucasrosati/claude-code-memory-setup](https://github.com/lucasrosati/claude-code-memory-setup)**
  turned that into a concrete Claude Code setup — Obsidian notes + [Graphify](https://github.com/safishamsi/graphify)
  code-graphs + a chat-import pipeline — and is the direct starting point recall grew from.

recall's contribution on top of that lineage is the missing retrieval half. In those setups
you pull context in by hand (a `/resume` command); recall replaces that with a **trigger index
that loads every session automatically**, so the right node surfaces without you asking — and
makes the whole vault **git-native** so memory versions and ships with your code, not in a
home-directory cache.

---

## Reference

### Node format

A node is markdown with a one-line `trigger` in YAML front matter and an `# H1` heading; the
`trigger` is the only required field. One concept per node, kebab-case filename, aim for a
couple of outgoing `→` links. The full rules — trigger writing, links, size limits — are in
**[the guide](guide/workflow.md#node-format)**. Copy `templates/example-global-node.md` into
your `memory/` vault as a working starter.

### CLI

```
memory status             where memory lives + node counts (start here)
memory index [vault]      every node: trigger, outgoing links, incoming count
memory validate [vault]   frontmatter / H1 / dead-link / size checks
memory dump [vault]       JSON of all nodes (feeds /recall:compact)
memory vaults             resolved vault name -> folder mappings
```

Vaults resolve from the environment: `global` = `<repo>/memory` (override with
`MEMORY_GLOBAL`), `local` = `$CLAUDE_PROJECT_DIR/docs`. No hand-maintained registry.

### Layout

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

### Requirements

- [Claude Code](https://claude.com/claude-code)
- Python 3.11+ (standard library only — no third-party deps)
- The chat-import hook uses `ps`/`getppid` for session detection (macOS/Linux).

## License

MIT — see [LICENSE](LICENSE).
