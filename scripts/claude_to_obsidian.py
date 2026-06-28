"""Convert Claude Code session JSONL files into Obsidian-friendly markdown.

Reads sessions from ~/.claude/projects/<encoded-project-path>/<uuid>.jsonl,
filters out low-value sessions, and writes one markdown file per *logical*
session into <vault>/chats/code/.

A "logical session" can span several JSONL files: when a conversation is
compacted (runs out of context) or resumed into a new session id, the
continuation file links back to its predecessor via a `parentUuid` / `leafUuid`
that lives in the earlier file. We follow those links, stitch the chain, and
render the whole thing as one markdown — see build_session_graph / render_chain.
In-file auto-compaction (`isCompactSummary`) keeps everything in one file
already; we drop the synthetic "session is being continued" summary when the
pre-compaction messages are present (deduplication), and keep it only when the
predecessor is missing (then it's the only record of the earlier context).
"""

import argparse
import fcntl
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

STATE_DIR = Path(__file__).resolve().parent  # repo/scripts — state lives next to the script
LAST_SYNC_FILE = STATE_DIR / ".last-sync-ts"
LOCK_FILE = STATE_DIR / ".sync.lock"

KEYWORD_TAG_MAP = {
    "python": "python",
    "react": "react",
    "supabase": "supabase",
    "deploy": "deploy",
    "bug": "debugging",
    "refactor": "refactoring",
    "docker": "docker",
    "fastapi": "fastapi",
    "typescript": "typescript",
    "rust": "rust",
}


def project_from_dir(dirname: str) -> str:
    """`-Users-axinvd-projects-demoApp` → `demoApp`.

    Fallback only: the encoding is lossy (`/` and `_` both become `-`), so
    `my_app` would decode as `md`. The authoritative source is the `cwd`
    field on JSONL events — see parse_session."""
    parts = [p for p in dirname.split("-") if p]
    return parts[-1] if parts else "unknown"


def is_subagent_jsonl(path: Path) -> bool:
    """Subagent sessions nest as <parent-uuid>/subagents/agent-<id>.jsonl."""
    return "subagents" in path.parts


def extract_text_from_content(content) -> str:
    """User content is str or list of blocks. Assistant content is list of blocks.
    Returns concatenated text, ignoring tool_use / thinking / tool_result blocks."""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    out = []
    for block in content:
        if not isinstance(block, dict):
            continue
        t = block.get("type")
        if t == "text":
            out.append(block.get("text", ""))
    return "\n".join(out).strip()


def is_real_user_prompt(event: dict) -> bool:
    """User events that came from the human, not as tool results."""
    if event.get("type") != "user":
        return False
    if event.get("toolUseResult") is not None:
        return False
    msg = event.get("message", {}) or {}
    content = msg.get("content")
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_result":
                return False
    text = extract_text_from_content(content)
    return bool(text.strip())


def is_assistant_text(event: dict) -> bool:
    if event.get("type") != "assistant":
        return False
    msg = event.get("message", {}) or {}
    return bool(extract_text_from_content(msg.get("content")).strip())


def parse_session(jsonl_path: Path):
    """Read a session file. Returns dict or None if unreadable.

    `messages` are in file (chronological) order, each carrying enough metadata
    to stitch chains: `is_compact_summary` and `parent_uuid`. `own_uuids` is the
    set of every event uuid in the file — used to resolve cross-file links."""
    events = []
    try:
        with open(jsonl_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return None

    messages = []
    own_uuids = set()
    first_ts = None
    last_ts = None
    cwd = None

    for ev in events:
        u = ev.get("uuid")
        if u:
            own_uuids.add(u)
        if cwd is None and ev.get("cwd"):
            cwd = ev["cwd"]
        ts = ev.get("timestamp")
        if ts:
            if first_ts is None:
                first_ts = ts
            last_ts = ts
        if is_real_user_prompt(ev):
            messages.append({
                "ts": ts or "",
                "role": "user",
                "text": extract_text_from_content(ev.get("message", {}).get("content")),
                "is_compact_summary": bool(ev.get("isCompactSummary")),
                "parent_uuid": ev.get("parentUuid"),
            })
        elif is_assistant_text(ev):
            messages.append({
                "ts": ts or "",
                "role": "assistant",
                "text": extract_text_from_content(ev.get("message", {}).get("content")),
                "is_compact_summary": False,
                "parent_uuid": ev.get("parentUuid"),
            })

    return {
        "uuid": jsonl_path.stem,
        "path": jsonl_path,
        "project": Path(cwd).name if cwd else project_from_dir(jsonl_path.parent.name),
        "first_ts": first_ts,
        "last_ts": last_ts,
        "messages": messages,
        "own_uuids": own_uuids,
    }


# ───────── cross-file continuation graph ─────────

def build_session_graph(jsonls):
    """Scan every JSONL once (lightly) and return (uuid2file, ext_pred):

    - uuid2file: event uuid -> the file it lives in.
    - ext_pred:  file -> the *other* file it continues (its predecessor), or absent.

    A file continues another when its first parented event's `parentUuid`, or any
    `leafUuid` / `isCompactSummary` parent it carries, resolves to a uuid that
    lives in a different file. This is the link the user sees as "the first
    message points to the log before compaction"."""
    uuid2file = {}
    per_file = {}  # file -> (own_uuids:set, cand_pred_uuids:set)
    for f in jsonls:
        own = set()
        cands = set()
        first_parent_seen = False
        try:
            with open(f, "r") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        e = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    u = e.get("uuid")
                    if u:
                        own.add(u)
                        uuid2file[u] = f
                    if not first_parent_seen and e.get("parentUuid"):
                        cands.add(e["parentUuid"])
                        first_parent_seen = True
                    if e.get("leafUuid"):
                        cands.add(e["leafUuid"])
                    if e.get("isCompactSummary") and e.get("parentUuid"):
                        cands.add(e["parentUuid"])
        except OSError:
            continue
        per_file[f] = (own, cands)

    ext_pred = {}
    for f, (own, cands) in per_file.items():
        for c in cands:
            tgt = uuid2file.get(c)
            if tgt is not None and tgt != f:
                ext_pred[f] = tgt
                break
    return uuid2file, ext_pred


def build_chains(jsonls, ext_pred):
    """Group files into predecessor→successor chains. Returns list of chains,
    each an ordered list of files (head = earliest, no external predecessor).

    Continuations are assumed linear; if a session was resumed more than once
    (a fork), successors are ordered by mtime and walked along the earliest —
    rare enough that a deterministic pick beats modelling the tree."""
    succ = {}  # predecessor file -> [successor files]
    for f, p in ext_pred.items():
        succ.setdefault(p, []).append(f)
    for p in succ:
        succ[p].sort(key=lambda x: x.stat().st_mtime if x.exists() else 0)

    chains = []
    for f in jsonls:
        if f in ext_pred:
            continue  # not a head — reached via its predecessor
        chain = []
        cur = f
        visited = set()
        while cur is not None and cur not in visited:
            visited.add(cur)
            chain.append(cur)
            nxts = [s for s in succ.get(cur, []) if s not in visited]
            cur = nxts[0] if nxts else None
        chains.append(chain)
    return chains


def fmt_ts(ts: str) -> str:
    """`2026-04-20T15:08:41.398Z` → `2026-04-20 15:08:41`. Empty in → empty out."""
    if not ts:
        return ""
    s = ts.replace("T", " ")
    if "." in s:
        s = s.split(".", 1)[0]
    return s.rstrip("Z").strip()


def merge_chain_messages(sessions):
    """Flatten a chain's messages in order, dropping synthetic `isCompactSummary`
    messages whose parent is present elsewhere in the chain (the real
    pre-compaction turns are already there); a summary whose predecessor is gone
    is kept and tagged `recovered_summary` — then it's the only record."""
    chain_uuids = set()
    for s in sessions:
        chain_uuids |= s["own_uuids"]
    merged = []
    for s in sessions:
        for m in s["messages"]:
            if m["role"] == "user" and m["is_compact_summary"]:
                if m["parent_uuid"] in chain_uuids:
                    continue  # pre-compaction context already in the chain — dedup
                merged.append({**m, "recovered_summary": True})
                continue
            merged.append(m)
    return merged


def count_messages(merged):
    """(user, assistant) counts — recovered summaries are not real user prompts."""
    n_user = sum(1 for m in merged if m["role"] == "user" and not m.get("recovered_summary"))
    n_asst = sum(1 for m in merged if m["role"] == "assistant")
    return n_user, n_asst


def render_chain(sessions, vault_dir: Path) -> str:
    """Render a chain of parsed sessions (1+ files) into one markdown body."""
    head = sessions[0]
    first_ts = head["first_ts"]
    last_ts = sessions[-1]["last_ts"] or head["last_ts"]
    date = (first_ts or "")[:10] or datetime.now().strftime("%Y-%m-%d")
    started = fmt_ts(first_ts) or date
    ended = fmt_ts(last_ts)

    merged = merge_chain_messages(sessions)
    n_user, n_asst = count_messages(merged)

    lines = []
    lines.append("# Claude Conversation Log")
    lines.append("")
    lines.append(f"Session ID: {head['uuid']}")
    lines.append(f"Project: {head['project']}")
    lines.append(f"Started: {started}")
    if ended and ended != started:
        lines.append(f"Ended: {ended}")
    if len(sessions) > 1:
        cont = ", ".join(s["uuid"] for s in sessions[1:])
        lines.append(f"Continued in: {cont}  ({len(sessions)} merged sessions)")
    lines.append(f"Messages: {n_user} user, {n_asst} assistant")
    lines.append("")
    lines.append("---")
    lines.append("")

    for m in merged:
        if m.get("recovered_summary"):
            lines.append("## 🧷 Compaction summary (earlier context — predecessor log not retained)")
        elif m["role"] == "user":
            lines.append("## 👤 User")
        else:
            lines.append("## 🤖 Claude")
        lines.append("")
        lines.append(m["text"])
        lines.append("")
        lines.append("---")
        lines.append("")

    body = "\n".join(lines)
    return add_wikilinks(body, vault_dir)


def add_wikilinks(content: str, vault_dir: Path) -> str:
    """Wrap mentions of global-node names in [[wikilinks]] — outside fenced code.
    Global nodes live in <repo>/memory (vault_dir is the repo root); the legacy
    Obsidian `permanent/` location is accepted as a fallback."""
    notes_path = vault_dir / "memory"
    if not notes_path.exists():
        notes_path = vault_dir / "permanent"
    if not notes_path.exists():
        return content
    existing = {f.stem for f in notes_path.glob("*.md")}
    if not existing:
        return content
    out = []
    in_fence = False
    for line in content.split("\n"):
        stripped = line.lstrip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
        elif not in_fence:
            for note in existing:
                line = re.sub(rf"\b{re.escape(note)}\b", f"[[{note}]]", line, flags=re.IGNORECASE)
        out.append(line)
    return "\n".join(out)


def keyword_tags(content: str):
    tags = set()
    low = content.lower()
    for kw, tag in KEYWORD_TAG_MAP.items():
        if kw in low:
            tags.add(tag)
    return sorted(tags)


def write_chat(sessions, body: str, vault_dir: Path) -> Path:
    """Write the rendered chain to <vault>/chats/code/, keyed on the chain head."""
    head = sessions[0]
    date = (head["first_ts"] or "")[:10] or datetime.now().strftime("%Y-%m-%d")
    fname = f"{date}-{head['project']}-{head['uuid']}.md"
    dest_dir = vault_dir / "chats" / "code"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / fname

    title = f"{head['project']} {date} ({head['uuid'][:8]})"
    tags = keyword_tags(body)
    tags.append(f"project-{head['project']}")
    tags.append("chat-import")
    tags.append("chat-code")

    last_ts = sessions[-1]["last_ts"] or head["last_ts"] or head["first_ts"] or ""
    last_date = last_ts[:10] or date
    u_msgs, a_msgs = count_messages(merge_chain_messages(sessions))
    tags_yaml = ", ".join('"{}"'.format(t) for t in tags)
    fm_lines = [
        "---",
        f"title: {title}",
        f"tags: [{tags_yaml}]",
        f"created: {date}",
        f"updated: {last_date}",
        f"status: active",
        f"type: chat",
        f"origin: code",
        f"project: {head['project']}",
        f"session_id: {head['uuid']}",
        f"chat_date: {date}",
        f"user_messages: {u_msgs}",
        f"assistant_messages: {a_msgs}",
    ]
    if len(sessions) > 1:
        cont = ", ".join(s["uuid"] for s in sessions[1:])
        fm_lines.append(f"merged_sessions: {len(sessions)}")
        fm_lines.append(f"continued_sessions: [{cont}]")
    fm_lines += ["---", ""]
    dest.write_text("\n".join(fm_lines) + body)
    return dest


def _ppid(pid: int):
    try:
        out = subprocess.run(
            ["ps", "-o", "ppid=", "-p", str(pid)],
            capture_output=True, text=True, timeout=2,
        ).stdout.strip()
        return int(out) if out else None
    except (subprocess.SubprocessError, ValueError):
        return None


def detect_current_session_id():
    """Walk up the parent process tree looking for a Claude Code session marker
    at ~/.claude/sessions/<pid>.json. Returns (session_id, source_description)."""
    sessions_dir = Path.home() / ".claude" / "sessions"
    if not sessions_dir.exists():
        return None, "no ~/.claude/sessions dir"

    pid = os.getppid()
    visited = set()
    while pid and pid != 1 and pid not in visited:
        visited.add(pid)
        sf = sessions_dir / f"{pid}.json"
        if sf.exists():
            try:
                data = json.loads(sf.read_text())
                sid = data.get("sessionId")
                if sid:
                    return sid, f"pid={pid} ({data.get('cwd','?')})"
            except (json.JSONDecodeError, OSError):
                pass
        nxt = _ppid(pid)
        if nxt is None or nxt == pid:
            break
        pid = nxt
    return None, "no Claude Code parent process found in tree"


def find_current_jsonl(projects_dir: Path):
    """Returns (jsonl_path, source_description). Tries deterministic process-tree
    detection first, falls back to most-recently-modified JSONL."""
    sid, src = detect_current_session_id()
    if sid:
        matches = list(projects_dir.rglob(f"{sid}.jsonl"))
        if matches:
            matches.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            return matches[0], f"detected via {src}"
        return None, f"session id {sid} from {src} but JSONL not on disk"

    candidates = [p for p in projects_dir.rglob("*.jsonl") if not is_subagent_jsonl(p)]
    if not candidates:
        return None, "no JSONL files found"
    latest = max(candidates, key=lambda p: p.stat().st_mtime)
    return latest, "fallback: most-recent mtime (NOT guaranteed to be current session)"


def render_and_write_chain(chain, vault_dir: Path):
    """Parse every file in a chain and write the merged markdown. Returns
    (dest_or_None, status)."""
    sessions = [parse_session(f) for f in chain]
    sessions = [s for s in sessions if s is not None]
    if not sessions:
        return None, "unreadable"
    body = render_chain(sessions, vault_dir)
    dest = write_chat(sessions, body, vault_dir)
    return dest, "written"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--projects-dir", default=str(Path.home() / ".claude" / "projects"))
    parser.add_argument("--vault-dir", required=True)
    parser.add_argument(
        "--current",
        action="store_true",
        help="Process only the active session's chain (detected via parent-process tree).",
    )
    parser.add_argument(
        "--session-jsonl",
        help="Path to a specific JSONL file to process (its whole chain is rendered).",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Force full sync of all chains, ignoring the last-sync timestamp. Default is incremental.",
    )
    parser.add_argument(
        "--include-subagents",
        action="store_true",
        help="Also import subagent session JSONLs (skipped by default — tool-call noise).",
    )
    args = parser.parse_args()

    projects_dir = Path(args.projects_dir)
    vault_dir = Path(args.vault_dir)

    found = list(projects_dir.rglob("*.jsonl"))
    if args.include_subagents:
        all_jsonls, skipped_subagents = found, 0
    else:
        all_jsonls = [j for j in found if not is_subagent_jsonl(j)]
        skipped_subagents = len(found) - len(all_jsonls)

    # The continuation graph needs every file to resolve cross-file links.
    _, ext_pred = build_session_graph(all_jsonls)
    chains = build_chains(all_jsonls, ext_pred)
    chain_of = {}  # member file -> its chain (list)
    for ch in chains:
        for f in ch:
            chain_of[f] = ch

    if args.current or args.session_jsonl:
        if args.session_jsonl:
            jsonl = Path(args.session_jsonl)
            source = "explicit --session-jsonl"
            if not jsonl.exists():
                print(f"error: {jsonl} not found")
                return 1
        else:
            jsonl, source = find_current_jsonl(projects_dir)
            if jsonl is None:
                print(f"error: {source}")
                return 1
        chain = chain_of.get(jsonl, [jsonl])
        dest, status = render_and_write_chain(chain, vault_dir)
        print(f"detection: {source}")
        print(f"source: {jsonl} (chain of {len(chain)})")
        if dest:
            print(f"wrote: {dest}")
        else:
            print(f"status: {status}")
        return 0

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    lock_fp = open(LOCK_FILE, "w")
    try:
        fcntl.flock(lock_fp.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("skipped: another sync is running (lock held)")
        return 0

    last_ts = 0.0
    if not args.full and LAST_SYNC_FILE.exists():
        try:
            last_ts = float(LAST_SYNC_FILE.read_text().strip() or 0)
        except ValueError:
            last_ts = 0.0

    if args.full or last_ts == 0.0:
        targets = chains
        mode = "full"
    else:
        # a chain is re-rendered if ANY of its files changed since last sync
        mode = "incremental"
        targets = [
            ch for ch in chains
            if any(f.exists() and f.stat().st_mtime > last_ts for f in ch)
        ]

    if not targets:
        print(
            f"mode={mode} chains={len(chains)} seen={len(all_jsonls)} written=0 "
            f"skipped_unchanged={len(chains)} skipped_subagents={skipped_subagents} "
            f"last_sync={datetime.fromtimestamp(last_ts).isoformat(timespec='seconds')}"
        )
        LAST_SYNC_FILE.write_text(str(time.time()))
        return 0

    written = 0
    skipped_unreadable = 0
    for ch in targets:
        dest, status = render_and_write_chain(ch, vault_dir)
        if dest:
            written += 1
        elif status == "unreadable":
            skipped_unreadable += 1

    LAST_SYNC_FILE.write_text(str(time.time()))

    print(
        f"mode={mode} chains={len(chains)} seen={len(all_jsonls)} processed={len(targets)} "
        f"written={written} skipped_unreadable={skipped_unreadable} "
        f"skipped_subagents={skipped_subagents} unchanged={len(chains) - len(targets)}"
    )


if __name__ == "__main__":
    main()
