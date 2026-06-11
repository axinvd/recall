#!/usr/bin/env python3
"""memory — index / validate / status / dump the triggered markdown memory.

Successor to `memgraph`. Same trigger-indexed flat-markdown model, but vault
resolution is plugin-aware: it discovers vaults from the environment instead of
requiring a hand-maintained global config.

Vault resolution (in order, all that exist are used):
    global   <repo>/memory                 — cross-project memory, lives in this repo
             (override with MEMORY_GLOBAL=/abs/path)
    local    $CLAUDE_PROJECT_DIR/docs       — current project's memory
             (falls back to $PWD/docs when CLAUDE_PROJECT_DIR is unset)
    <extra>  any [vaults] entries in ~/.config/memgraph/config.toml (back-compat)

Commands:
    memory index [vault]      list nodes (path, trigger, outgoing, incoming)
    memory validate [vault]   frontmatter / H1 / dead-link / size checks
    memory status             where memory lives + node counts (single overview)
    memory dump [vault]       JSON of every node (trigger/h1/body/links) — feeds /mem:compact
    memory vaults             list resolved vault name -> folder mappings
"""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

try:
    import tomllib  # py3.11+
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None  # type: ignore

DEFAULT_TRIGGER_MAX = 200
DEFAULT_BODY_MAX_LINES = 150

LINK_RE = re.compile(r"\[([^\]\n]+?)\]\(([^)\n]+?)\)")
TRIGGER_PREFIXES = ("Use when ", "Read when ")


# ───────── config / vault resolution ─────────


@dataclass
class Config:
    vaults: dict[str, Path]  # name -> abs path
    trigger_max: int = DEFAULT_TRIGGER_MAX
    body_max_lines: int = DEFAULT_BODY_MAX_LINES


def repo_root() -> Path:
    """The plugin/repo root: parent of the dir holding this script (src/)."""
    return Path(__file__).resolve().parent.parent


def _add_vault(vaults: dict[str, Path], name: str, path: Path) -> None:
    path = path.expanduser()
    try:
        path = path.resolve()
    except OSError:
        return
    if path.is_dir() and path not in vaults.values():
        vaults[name] = path


def resolve_vaults() -> dict[str, Path]:
    vaults: dict[str, Path] = {}

    # global — cross-project memory inside this repo
    g = os.environ.get("MEMORY_GLOBAL")
    _add_vault(vaults, "global", Path(g) if g else repo_root() / "memory")

    # local — current project's docs/
    proj = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    _add_vault(vaults, "local", Path(proj) / "docs")

    return vaults


def load_config() -> Config:
    vaults = resolve_vaults()
    trigger_max, body_max = DEFAULT_TRIGGER_MAX, DEFAULT_BODY_MAX_LINES
    # config lives in the repo (config.toml at the root), not in ~/.config
    config_path = repo_root() / "config.toml"
    if tomllib and config_path.exists():
        try:
            with config_path.open("rb") as f:
                limits = (tomllib.load(f).get("limits") or {})
            trigger_max = int(limits.get("trigger_max", DEFAULT_TRIGGER_MAX))
            body_max = int(limits.get("body_max_lines", DEFAULT_BODY_MAX_LINES))
        except Exception:
            pass
    if not vaults:
        die(
            "no vaults found.\n"
            f"  expected global memory at {repo_root() / 'memory'}\n"
            "  and/or a docs/ folder in the current project.\n"
            "  (override global with MEMORY_GLOBAL=/abs/path)"
        )
    return Config(vaults=vaults, trigger_max=trigger_max, body_max_lines=body_max)


# ───────── parsing ─────────


@dataclass
class Link:
    label: str
    target: str  # raw href as written
    line: int


@dataclass
class Node:
    vault: str
    abs_path: Path
    rel_path: str
    frontmatter: dict[str, str]
    has_frontmatter: bool
    h1: str | None
    body: str  # body text (frontmatter stripped), trailing blanks trimmed
    body_line_count: int
    links: list[Link]
    outgoing: list[Path] = field(default_factory=list)
    unresolved: list[Link] = field(default_factory=list)
    incoming_count: int = 0


def parse_frontmatter(yaml_lines: list[str]) -> dict[str, str]:
    """Tiny YAML subset: top-level `key: value` only. Quoted strings supported."""
    out: dict[str, str] = {}
    key_re = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*)\s*:\s*(.*)$")
    for raw in yaml_lines:
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith(" "):  # nested → skip silently
            continue
        m = key_re.match(line)
        if not m:
            continue
        k, v = m.group(1), m.group(2)
        if " #" in v:
            v = v.split(" #", 1)[0].rstrip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
            v = v[1:-1]
        out[k] = v
    return out


def is_internal_md(href: str) -> bool:
    if not href or href.startswith("#") or href.startswith("mailto:"):
        return False
    if re.match(r"^[a-z][a-z0-9+.-]*://", href, flags=re.I):
        return False
    bare = href.split("#", 1)[0]
    return bare.endswith(".md")


def parse_node(vault_name: str, vault_root: Path, abs_path: Path) -> Node:
    text = abs_path.read_text(encoding="utf-8", errors="replace")
    lines = text.split("\n")

    fm: dict[str, str] = {}
    has_fm = False
    body_start = 0

    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                has_fm = True
                body_start = i + 1
                fm = parse_frontmatter(lines[1:i])
                break

    body_lines = lines[body_start:]
    while body_lines and body_lines[-1] == "":
        body_lines.pop()
    body = "\n".join(body_lines)
    body_line_count = len(body_lines)

    h1: str | None = None
    for ln in body_lines:
        s = ln.strip()
        if not s:
            continue
        if s.startswith("# "):
            h1 = s[2:].strip()
        break

    links: list[Link] = []
    in_fence = False
    for idx, ln in enumerate(lines):
        if idx < body_start:
            continue
        stripped = ln.lstrip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            continue
        if in_fence:  # link syntax inside fenced code is illustrative, not a real edge
            continue
        for m in LINK_RE.finditer(ln):
            href = m.group(2).strip()
            if is_internal_md(href):
                links.append(Link(label=m.group(1), target=href, line=idx + 1))

    rel = abs_path.relative_to(vault_root).as_posix()
    return Node(
        vault=vault_name,
        abs_path=abs_path,
        rel_path=rel,
        frontmatter=fm,
        has_frontmatter=has_fm,
        h1=h1,
        body=body,
        body_line_count=body_line_count,
        links=links,
    )


# ───────── indexing ─────────


def walk_md(root: Path) -> list[Path]:
    out: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for f in filenames:
            if f.endswith(".md"):
                out.append(Path(dirpath) / f)
    out.sort()
    return out


def build_index(cfg: Config) -> list[Node]:
    nodes: list[Node] = []
    for name, root in cfg.vaults.items():
        for abs_path in walk_md(root):
            nodes.append(parse_node(name, root, abs_path))

    by_abs: dict[Path, Node] = {n.abs_path: n for n in nodes}

    for n in nodes:
        for link in n.links:
            bare = link.target.split("#", 1)[0]
            target_path = Path(os.path.expanduser(bare))
            if not target_path.is_absolute():
                target_path = n.abs_path.parent / target_path
            try:
                target_path = target_path.resolve()
            except OSError:
                pass
            if target_path in by_abs:
                n.outgoing.append(target_path)
                by_abs[target_path].incoming_count += 1
            elif target_path.is_file():
                # exists on disk but outside the current index (e.g. another project's
                # docs). A valid cross-reference, not a dead link — don't flag it.
                pass
            else:
                n.unresolved.append(link)
    return nodes


# ───────── validate ─────────


@dataclass
class Issue:
    level: str  # "error" | "warning"
    vault: str
    rel_path: str
    line: int | None
    message: str


def validate(nodes: list[Node], cfg: Config) -> list[Issue]:
    issues: list[Issue] = []

    def add(n: Node, level: str, msg: str, line: int | None = None) -> None:
        issues.append(Issue(level, n.vault, n.rel_path, line, msg))

    all_basenames: dict[str, list[Node]] = {}
    for other in nodes:
        all_basenames.setdefault(other.abs_path.name, []).append(other)

    for n in nodes:
        if not n.has_frontmatter:
            add(n, "error", "missing frontmatter block")
        else:
            trig = n.frontmatter.get("trigger")
            if trig is None:
                add(n, "error", "missing `trigger` field in frontmatter")
            elif not any(trig.startswith(p) for p in TRIGGER_PREFIXES):
                add(n, "error", 'trigger must start with "Use when " or "Read when "', line=1)
            elif len(trig) > cfg.trigger_max:
                add(n, "warning", f"trigger too long ({len(trig)} chars; limit {cfg.trigger_max})", line=1)

        if not n.h1:
            add(n, "error", "missing H1 after frontmatter")

        if n.body_line_count > cfg.body_max_lines:
            add(n, "warning", f"body too long ({n.body_line_count} lines; soft limit {cfg.body_max_lines}) — consider splitting or /mem:compact")

        for link in n.unresolved:
            base = link.target.split("/")[-1].split("#", 1)[0]
            cands = all_basenames.get(base, [])
            hint = f"not found; nearest: {cands[0].vault}:{cands[0].rel_path}" if cands else "not found"
            add(n, "warning", f"dead link → {link.target} ({hint})", line=link.line)

    return issues


# ───────── output ─────────


def short_for(p: Path, cfg: Config) -> str:
    for vname, vroot in cfg.vaults.items():
        try:
            return f"{vname}:{p.relative_to(vroot).as_posix()}"
        except ValueError:
            continue
    return str(p)


def print_index(nodes: list[Node], cfg: Config, only: str | None) -> None:
    by_vault: dict[str, list[Node]] = {}
    for n in nodes:
        by_vault.setdefault(n.vault, []).append(n)

    for vname in cfg.vaults:
        if only and only != vname:
            continue
        vnodes = by_vault.get(vname, [])
        print(f"== {vname} ({cfg.vaults[vname]}) — {len(vnodes)} nodes ==")
        print()
        for n in vnodes:
            print(f"{vname}:{n.rel_path}")
            trig = n.frontmatter.get("trigger")
            print(f"  {trig}" if trig else "  (no trigger)")
            if n.outgoing:
                outs = sorted({short_for(p, cfg) for p in n.outgoing})
                print(f"  → {', '.join(outs)}")
            else:
                print("  → (no outgoing)")
            print(f"  ← {n.incoming_count} incoming")
            print()


def print_validation(issues: list[Issue], total_nodes: int) -> int:
    errors = [i for i in issues if i.level == "error"]
    warns = [i for i in issues if i.level == "warning"]
    print(f"checked {total_nodes} nodes")
    if warns:
        print(f"\nwarnings ({len(warns)}):")
        for w in warns:
            loc = f"{w.vault}:{w.rel_path}" + (f":{w.line}" if w.line else "")
            print(f"  {loc}  {w.message}")
    if errors:
        print(f"\nerrors ({len(errors)}):")
        for e in errors:
            loc = f"{e.vault}:{e.rel_path}" + (f":{e.line}" if e.line else "")
            print(f"  {loc}  {e.message}")
        return 1
    return 0


# ───────── cli ─────────


def die(msg: str, code: int = 2) -> None:
    sys.stderr.write(f"memory: {msg}\n")
    sys.exit(code)


def _filter(nodes: list[Node], only: str | None) -> list[Node]:
    return [n for n in nodes if n.vault == only] if only else nodes


def _check_vault(cfg: Config, only: str | None) -> None:
    if only and only not in cfg.vaults:
        die(f"unknown vault '{only}' (resolved: {', '.join(cfg.vaults) or 'none'})")


def cmd_index(args: list[str]) -> int:
    cfg = load_config()
    only = args[0] if args else None
    _check_vault(cfg, only)
    print_index(build_index(cfg), cfg, only)
    return 0


def cmd_validate(args: list[str]) -> int:
    cfg = load_config()
    only = args[0] if args else None
    _check_vault(cfg, only)
    nodes = build_index(cfg)
    issues = [i for i in validate(nodes, cfg) if not only or i.vault == only]
    return print_validation(issues, len(_filter(nodes, only)))


def cmd_status(_: list[str]) -> int:
    cfg = load_config()
    nodes = build_index(cfg)
    by_vault: dict[str, list[Node]] = {}
    for n in nodes:
        by_vault.setdefault(n.vault, []).append(n)
    issues = validate(nodes, cfg)
    errs = sum(1 for i in issues if i.level == "error")
    warns = sum(1 for i in issues if i.level == "warning")
    print("memory — overview\n")
    for name, root in cfg.vaults.items():
        vn = by_vault.get(name, [])
        print(f"  {name:8} {len(vn):3} nodes   {root}")
    print(f"\n  total {len(nodes)} nodes, {errs} errors, {warns} warnings")
    print(f"  repo  {repo_root()}")
    return 0


def cmd_dump(args: list[str]) -> int:
    """JSON of every node — input for the /mem:compact Pareto pass."""
    cfg = load_config()
    only = args[0] if args else None
    _check_vault(cfg, only)
    nodes = build_index(cfg)
    out = []
    for n in _filter(nodes, only):
        out.append({
            "vault": n.vault,
            "rel_path": n.rel_path,
            "abs_path": str(n.abs_path),
            "trigger": n.frontmatter.get("trigger"),
            "h1": n.h1,
            "body_lines": n.body_line_count,
            "outgoing": sorted({short_for(p, cfg) for p in n.outgoing}),
            "incoming": n.incoming_count,
            "body": n.body,
        })
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


def cmd_vaults(_: list[str]) -> int:
    for name, root in load_config().vaults.items():
        print(f"{name}\t{root}")
    return 0


USAGE = (
    "usage:\n"
    "  memory index [vault]      list nodes (trigger, outgoing, incoming)\n"
    "  memory validate [vault]   frontmatter / H1 / dead-link / size checks\n"
    "  memory status             where memory lives + node counts\n"
    "  memory dump [vault]       JSON of all nodes (feeds /mem:compact)\n"
    "  memory vaults             list resolved vault -> folder mappings\n"
)

COMMANDS = {
    "index": cmd_index,
    "validate": cmd_validate,
    "status": cmd_status,
    "dump": cmd_dump,
    "vaults": cmd_vaults,
}


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help", "help"):
        sys.stdout.write(USAGE)
        return 0
    cmd, rest = argv[0], argv[1:]
    fn = COMMANDS.get(cmd)
    if not fn:
        sys.stderr.write(f"memory: unknown command '{cmd}'\n{USAGE}")
        return 2
    return fn(rest)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
