"""Convert Claude Code session JSONL files into Obsidian-friendly markdown.

Reads sessions from ~/.claude/projects/<encoded-project-path>/<uuid>.jsonl,
filters out low-value sessions, and writes one markdown file per session
into <vault>/chats/code/.
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
    """Read a session file. Returns dict or None if unreadable."""
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

    user_msgs = []
    assistant_msgs = []
    first_ts = None
    last_ts = None
    cwd = None

    for ev in events:
        if cwd is None and ev.get("cwd"):
            cwd = ev["cwd"]
        ts = ev.get("timestamp")
        if ts:
            if first_ts is None:
                first_ts = ts
            last_ts = ts
        if is_real_user_prompt(ev):
            text = extract_text_from_content(ev.get("message", {}).get("content"))
            user_msgs.append((ts, text))
        elif is_assistant_text(ev):
            text = extract_text_from_content(ev.get("message", {}).get("content"))
            assistant_msgs.append((ts, text))

    return {
        "uuid": jsonl_path.stem,
        "project": Path(cwd).name if cwd else project_from_dir(jsonl_path.parent.name),
        "first_ts": first_ts,
        "last_ts": last_ts,
        "user_msgs": user_msgs,
        "assistant_msgs": assistant_msgs,
        "events": events,
    }


def fmt_ts(ts: str) -> str:
    """`2026-04-20T15:08:41.398Z` → `2026-04-20 15:08:41`. Empty in → empty out."""
    if not ts:
        return ""
    s = ts.replace("T", " ")
    if "." in s:
        s = s.split(".", 1)[0]
    return s.rstrip("Z").strip()


def render_markdown(session, vault_dir: Path) -> str:
    """Build a markdown chat log from a parsed session."""
    date = (session["first_ts"] or "")[:10] or datetime.now().strftime("%Y-%m-%d")
    started = fmt_ts(session["first_ts"]) or date
    ended = fmt_ts(session["last_ts"])

    lines = []
    lines.append("# Claude Conversation Log")
    lines.append("")
    lines.append(f"Session ID: {session['uuid']}")
    lines.append(f"Project: {session['project']}")
    lines.append(f"Started: {started}")
    if ended and ended != started:
        lines.append(f"Ended: {ended}")
    lines.append(f"Messages: {len(session['user_msgs'])} user, {len(session['assistant_msgs'])} assistant")
    lines.append("")
    lines.append("---")
    lines.append("")

    timeline = []
    for ts, text in session["user_msgs"]:
        timeline.append((ts or "", "user", text))
    for ts, text in session["assistant_msgs"]:
        timeline.append((ts or "", "assistant", text))
    timeline.sort(key=lambda x: x[0])

    for _, role, text in timeline:
        if role == "user":
            lines.append("## 👤 User")
        else:
            lines.append("## 🤖 Claude")
        lines.append("")
        lines.append(text)
        lines.append("")
        lines.append("---")
        lines.append("")

    body = "\n".join(lines)
    return add_wikilinks(body, vault_dir)


def add_wikilinks(content: str, vault_dir: Path) -> str:
    """Wrap mentions of permanent-note names in [[wikilinks]] — outside fenced code."""
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


def write_chat(session, body: str, vault_dir: Path) -> Path:
    date = (session["first_ts"] or "")[:10] or datetime.now().strftime("%Y-%m-%d")
    fname = f"{date}-{session['project']}-{session['uuid']}.md"
    dest_dir = vault_dir / "chats" / "code"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / fname

    title = f"{session['project']} {date} ({session['uuid'][:8]})"
    tags = keyword_tags(body)
    tags.append(f"project-{session['project']}")
    tags.append("chat-import")
    tags.append("chat-code")

    last_date = (session["last_ts"] or session["first_ts"] or "")[:10] or date
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
        f"project: {session['project']}",
        f"session_id: {session['uuid']}",
        f"chat_date: {date}",
        f"user_messages: {len(session['user_msgs'])}",
        f"assistant_messages: {len(session['assistant_msgs'])}",
        "---",
        "",
    ]
    dest.write_text("\n".join(fm_lines) + body)
    return dest


def _ppid(pid: int) -> int | None:
    try:
        out = subprocess.run(
            ["ps", "-o", "ppid=", "-p", str(pid)],
            capture_output=True, text=True, timeout=2,
        ).stdout.strip()
        return int(out) if out else None
    except (subprocess.SubprocessError, ValueError):
        return None


def detect_current_session_id() -> tuple[str | None, str]:
    """Walk up the parent process tree looking for a Claude Code session marker
    at ~/.claude/sessions/<pid>.json. Returns (session_id, source_description)."""
    sessions_dir = Path.home() / ".claude" / "sessions"
    if not sessions_dir.exists():
        return None, "no ~/.claude/sessions dir"

    pid = os.getppid()
    visited: set[int] = set()
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


def find_current_jsonl(projects_dir: Path) -> tuple[Path | None, str]:
    """Returns (jsonl_path, source_description). Tries deterministic process-tree
    detection first, falls back to most-recently-modified JSONL."""
    sid, src = detect_current_session_id()
    if sid:
        matches = list(projects_dir.rglob(f"{sid}.jsonl"))
        if matches:
            matches.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            return matches[0], f"detected via {src}"
        return None, f"session id {sid} from {src} but JSONL not on disk"

    # the current interactive session is never a subagent — exclude their JSONLs
    candidates = [p for p in projects_dir.rglob("*.jsonl") if not is_subagent_jsonl(p)]
    if not candidates:
        return None, "no JSONL files found"
    latest = max(candidates, key=lambda p: p.stat().st_mtime)
    return latest, "fallback: most-recent mtime (NOT guaranteed to be current session)"


def process_one(jsonl: Path, vault_dir: Path):
    """Process a single JSONL. Returns (written_path_or_None, status)."""
    session = parse_session(jsonl)
    if session is None:
        return None, "unreadable"
    body = render_markdown(session, vault_dir)
    dest = write_chat(session, body, vault_dir)
    return dest, "written"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--projects-dir", default=str(Path.home() / ".claude" / "projects"))
    parser.add_argument("--vault-dir", required=True)
    parser.add_argument(
        "--current",
        action="store_true",
        help="Process only the active session's JSONL (detected via parent-process tree).",
    )
    parser.add_argument(
        "--session-jsonl",
        help="Path to a specific JSONL file to process.",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Force full sync of all JSONLs, ignoring the last-sync timestamp. Default is incremental.",
    )
    parser.add_argument(
        "--include-subagents",
        action="store_true",
        help="Also import subagent session JSONLs (skipped by default — tool-call noise).",
    )
    args = parser.parse_args()

    projects_dir = Path(args.projects_dir)
    vault_dir = Path(args.vault_dir)

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
        dest, status = process_one(jsonl, vault_dir)
        print(f"detection: {source}")
        print(f"source: {jsonl}")
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

    found = list(projects_dir.rglob("*.jsonl"))
    if args.include_subagents:
        all_jsonls, skipped_subagents = found, 0
    else:
        all_jsonls = [j for j in found if not is_subagent_jsonl(j)]
        skipped_subagents = len(found) - len(all_jsonls)
    if args.full or last_ts == 0.0:
        targets = all_jsonls
        mode = "full"
    else:
        targets = [j for j in all_jsonls if j.stat().st_mtime > last_ts]
        mode = "incremental"

    if not targets:
        print(
            f"mode={mode} seen={len(all_jsonls)} written=0 "
            f"skipped_unchanged={len(all_jsonls)} skipped_subagents={skipped_subagents} "
            f"last_sync={datetime.fromtimestamp(last_ts).isoformat(timespec='seconds')}"
        )
        LAST_SYNC_FILE.write_text(str(time.time()))
        return 0

    written = 0
    skipped_unreadable = 0

    for jsonl in targets:
        dest, status = process_one(jsonl, vault_dir)
        if dest:
            written += 1
        elif status == "unreadable":
            skipped_unreadable += 1

    LAST_SYNC_FILE.write_text(str(time.time()))

    print(
        f"mode={mode} seen={len(all_jsonls)} processed={len(targets)} written={written} "
        f"skipped_unreadable={skipped_unreadable} skipped_subagents={skipped_subagents} "
        f"unchanged={len(all_jsonls) - len(targets)}"
    )


if __name__ == "__main__":
    main()
