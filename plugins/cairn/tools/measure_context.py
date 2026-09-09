"""Measure the real per-session context baseline for a project.

MEASURING A PROJECT RUNS IT. READ THIS BEFORE POINTING IT SOMEWHERE.
--------------------------------------------------------------------
To report what a session start actually costs, this tool starts one: it EXECUTES the target
project's SessionStart hooks (through the shell, as Claude Code does) and it STARTS the MCP
servers that project configures. That is not incidental to the measurement -- a baseline that
skipped them would be the number this tool was written to stop people quoting.

So the blast radius is the target project's own configuration, not this tool's. A repo you have
not opened can carry a `.claude/settings.json` whose SessionStart hook is arbitrary, and running
this is equivalent to opening it. **Do not point it at a repository you would not open.**
On-demand only: it is never wired into a hook, and nothing runs it on your behalf.

Counts tokens with tiktoken o200k_base (a real BPE tokenizer, not a byte estimate) when tiktoken
is installed. It is not Claude's tokenizer -- Anthropic does not publish one -- so treat the
absolute numbers as +/-10-15% and the BEFORE/AFTER deltas as reliable.

tiktoken is OPTIONAL, not a shipped dependency -- the plugin has zero Python dependencies and this
tool preserves that. When tiktoken is absent, every count is a labelled `~N` ESTIMATE (bytes / 4)
instead, clearly marked so it is never mistaken for the real thing; the tool still exits 0. Run
`pip install tiktoken` for exact counts -- see B95 below for why that stays optional rather than
becoming a `requirements.txt` the tool depends on.

    python measure_context.py <project-root>

SHIPPED IN THE PLUGIN since v1.9.0. It used to live only in `code/tools/`, on one machine, which
made every token claim on any other machine a guess -- in a system whose central argument is
that context costs are measured rather than asserted.

WHAT WAS BROKEN (found 2026-08-22)
----------------------------------
It discovered SessionStart hooks by reading `<root>/.claude/settings.json` only. That was correct
until the orientation hook moved into the plugin, after which it reported 0 for the hook and also
omitted the per-project memory index: 3,969 against a true 5,437 for `code\\`, 27% low. It now
looks in all four places a SessionStart hook can actually come from, and counts every file the
session really loads.

WHAT WAS ALSO MISSING (found 2026-08-25, closed 2026-08-27)
-------------------------------------------------------------
It reported no change at all after installing a plugin that costs real tokens every session,
because it never counted the skill/agent listing lines an enabled plugin (or a project/user
skill) adds, nor any MCP tool a server exposes. It now counts skills and agents -- one row per
plugin, rendered as the actual listing line, not raw frontmatter -- and lists configured MCP
servers with both their deferred (name-only) and full-schema token cost, since whichever one a
given session actually loads isn't knowable from outside that session. Only what the user controls
is counted: installed plugins, and project/user skills and agents -- not the fixed harness skills
(`code-review`, `dataviz`, ...) that are identical in every project and can't be changed.

WHAT WAS BROKEN AGAIN -- NO tiktoken ON THE MACHINE (B95, found 2026-09-06)
----------------------------------------------------------------------------
`import tiktoken` used to sit at module level with no guard, so on a machine where the package is
absent this crashed with a bare `ModuleNotFoundError` before printing anything -- and the plugin's
own always-loaded rules file (`rules/CLAUDE.md`) tells every agent, on every machine, to use this
tool instead of quoting a bare token count. A tool the rule points at that cannot run forces the
exact choice the rule forbids: quote a stale number, or silently fall back to bytes.

So the import is now optional. When `tiktoken` is present, output is unchanged -- an exact BPE
count in the `tokens` column, `o200k_base`, as always. When it is absent, every `tokens` column
becomes an `~N` ESTIMATE (bytes / 4, the usual rule-of-thumb ratio for English/code text) and is
never allowed to print as a bare number that could be mistaken for the real count -- that would be
the "one value, two opposite states" defect this repo designs against elsewhere, and it would be
worse than the crash it replaces. A banner at the top of output says which mode is active and, in
estimate mode, prints the one-line install command for exact counts. Exit code is 0 either way --
this is a measurement tool, and degrading gracefully is the correct behaviour, not a failure.
"""
import io
import json
import os
import re
import subprocess
import sys
from pathlib import Path

try:
    import tiktoken
    # NOT `except ImportError` alone: `get_encoding` fetches the BPE vocabulary on first use, so a
    # machine WITH tiktoken and no network raises from here too (URLError, and tiktoken wraps some
    # failures in its own types). Either way the answer is the same -- no tokenizer, fall back to a
    # labelled estimate -- and a measurement tool must not be the thing that breaks a session.
    ENC = tiktoken.get_encoding("o200k_base")
except Exception:
    ENC = None

# True BPE token count via tiktoken, or a labelled `~N` estimate (bytes / 4) when tiktoken is
# absent. Every caller must render this distinction -- see `fmt_tokens` -- never just the number.
TOKENS_ARE_ESTIMATED = ENC is None
TIKTOKEN_INSTALL_HINT = "pip install tiktoken"


def toks(text: str) -> int:
    if ENC is not None:
        return len(ENC.encode(text, disallowed_special=()))
    # No tokenizer available -- fall back to a byte-count-based estimate. Callers must label this
    # as an estimate (see `fmt_tokens`); this function alone cannot carry that label, since it
    # returns a plain int either way.
    return len(text.encode("utf-8")) // 4


def fmt_tokens(n: int) -> str:
    """Render a token count for a table cell -- `1,234` when exact, `~1,234` when estimated.

    The two must never look alike. A number that could be either the real tiktoken count or a
    bytes/4 guess, with no visible marker, is worse than the crash this replaced: it lets a stale
    or approximate figure get quoted as if it were measured.
    """
    return f"{'~' if TOKENS_ARE_ESTIMATED else ''}{n:,}"


def measure_file(path: Path) -> tuple[int, int]:
    if not path.is_file():
        return (0, 0)
    raw = path.read_text(encoding="utf-8", errors="replace")
    return (len(raw.encode("utf-8")), toks(raw))


def config_dir() -> Path:
    override = os.environ.get("CLAUDE_CONFIG_DIR", "").strip()
    return Path(override).expanduser() if override else Path.home() / ".claude"


def project_slug(root: Path) -> str:
    """`C:\\Users\\Example\\code` -> `C--Users-Example-code`, the memory dir's name."""
    return re.sub(r"[^A-Za-z0-9]", "-", str(root))


def run_hook(cmd: str, cwd: Path) -> str:
    payload = json.dumps({"session_id": "measure", "cwd": str(cwd),
                          "hook_event_name": "SessionStart", "source": "startup"})
    try:
        r = subprocess.run(cmd, cwd=cwd, shell=True, input=payload,
                           capture_output=True, text=True, timeout=60,
                           encoding="utf-8", errors="replace")
    except Exception as e:  # noqa: BLE001
        return f"<<hook failed: {e}>>"
    return r.stdout or ""


def _hooks_from_settings(path: Path, plugin_root: Path | None = None):
    """Yield (label, command) for every SessionStart hook declared in a settings-shaped file."""
    if not path.is_file():
        return
    try:
        cfg = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return
    for group in cfg.get("hooks", {}).get("SessionStart", []):
        for h in group.get("hooks", []):
            cmd = h.get("command", "")
            if not cmd:
                continue
            if plugin_root is not None:
                cmd = cmd.replace("${CLAUDE_PLUGIN_ROOT}", str(plugin_root))
            cmd = cmd.replace("${CLAUDE_PROJECT_DIR}", str(path.parent.parent))
            yield cmd


def session_start_hooks(root: Path):
    """Every SessionStart hook a real session would fire, from all four sources.

    A hook declared in a plugin is invisible to `<root>/.claude/settings.json`, which is exactly
    the bug this function exists to fix. Plugin hooks live in
    `<config>/plugins/cache/<marketplace>/<plugin>/<version>/hooks/hooks.json` and reference
    `${CLAUDE_PLUGIN_ROOT}`, so the placeholder has to be substituted before running them.
    """
    cfg = config_dir()
    for settings in (root / ".claude" / "settings.json",
                     root / ".claude" / "settings.local.json",
                     cfg / "settings.json"):
        for cmd in _hooks_from_settings(settings):
            yield (f"hook: {cmd}", cmd)

    # ONLY the installed version of each plugin. The cache keeps every version ever fetched --
    # 19 of `reentry` alone on 2026-08-22 -- and globbing the cache counted all of them, turning
    # an 876-token hook into 19,109 tokens of nonsense. `installed_plugins.json` is the authority.
    for plugin_root in _installed_plugin_roots(cfg):
        hooks_json = plugin_root / "hooks" / "hooks.json"
        label = "/".join(plugin_root.parts[-3:])
        for cmd in _hooks_from_settings(hooks_json, plugin_root=plugin_root):
            yield (f"plugin hook [{label}]", cmd)


def _installed_plugin_roots(cfg: Path):
    """The install path of each currently-installed plugin, from `installed_plugins.json`."""
    path = cfg / "plugins" / "installed_plugins.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return
    for installs in (data.get("plugins") or {}).values():
        for install in installs or []:
            location = install.get("installPath")
            if location:
                yield Path(location)


def _plugin_name(plugin_root: Path) -> str:
    manifest = plugin_root / ".claude-plugin" / "plugin.json"
    try:
        return json.loads(manifest.read_text(encoding="utf-8")).get("name", plugin_root.name)
    except Exception:  # noqa: BLE001
        return plugin_root.name


def _read_frontmatter(path: Path) -> dict | None:
    """Parse the flat `key: value` YAML frontmatter of a SKILL.md / agent .md file.

    Not a real YAML parser -- SKILL.md frontmatter is flat scalars, occasionally wrapped onto a
    continuation line, and pulling in a full YAML dependency for that isn't worth requiring on
    every machine this runs on.
    """
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8", errors="replace")
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not m:
        return None
    fm: dict[str, str] = {}
    key = None
    for line in m.group(1).splitlines():
        mm = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if mm:
            key, val = mm.group(1), mm.group(2).strip()
            if len(val) > 1 and val[0] == val[-1] and val[0] in "\"'":
                val = val[1:-1]
            fm[key] = val
        elif key is not None and line.startswith((" ", "\t")):
            fm[key] = f"{fm[key]} {line.strip()}".strip()
    return fm


def _listing_lines(skills_dir: Path, name_prefix: str = "") -> list[str]:
    """The `- name: description` line each skill under `skills_dir` renders as, in a listing."""
    lines = []
    if not skills_dir.is_dir():
        return lines
    for skill_dir in sorted(p for p in skills_dir.iterdir() if p.is_dir()):
        fm = _read_frontmatter(skill_dir / "SKILL.md")
        if fm:
            name = fm.get("name", skill_dir.name)
            lines.append(f"- {name_prefix}{name}: {fm.get('description', '')}")
    return lines


def _agent_lines(agents_dir: Path) -> list[str]:
    """The `- name: description` line each agent under `agents_dir` renders as, in a listing."""
    lines = []
    if not agents_dir.is_dir():
        return lines
    for agent_file in sorted(agents_dir.glob("*.md")):
        fm = _read_frontmatter(agent_file)
        if fm:
            name = fm.get("name", agent_file.stem)
            lines.append(f"- {name}: {fm.get('description', '')}")
    return lines


def skill_and_agent_rows(root: Path, cfg: Path) -> list[tuple[str, int, int]]:
    """One row per plugin (not per skill) plus one row each for project/user skills and agents."""
    rows: list[tuple[str, int, int]] = []
    for plugin_root in _installed_plugin_roots(cfg):
        pname = _plugin_name(plugin_root)
        lines = _listing_lines(plugin_root / "skills", f"{pname}:") + _agent_lines(plugin_root / "agents")
        if lines:
            text = "\n".join(lines)
            rows.append((f"plugin skills+agents [{pname}]", len(text.encode("utf-8")), toks(text)))

    project_lines = _listing_lines(root / ".claude" / "skills") + _agent_lines(root / ".claude" / "agents")
    if project_lines:
        text = "\n".join(project_lines)
        rows.append((f"{root.name}/.claude/skills+agents", len(text.encode("utf-8")), toks(text)))

    user_lines = _listing_lines(cfg / "skills") + _agent_lines(cfg / "agents")
    if user_lines:
        text = "\n".join(user_lines)
        rows.append(("~/.claude/skills+agents", len(text.encode("utf-8")), toks(text)))
    return rows


def _mcp_server_configs(root: Path, cfg: Path) -> dict[str, dict]:
    """Every MCP server the user (not the harness) has configured, by label -> its config dict."""
    servers: dict[str, dict] = {}

    project_mcp = root / ".mcp.json"
    if project_mcp.is_file():
        try:
            data = json.loads(project_mcp.read_text(encoding="utf-8"))
            for name, conf in (data.get("mcpServers") or {}).items():
                servers[f"{root.name}/.mcp.json:{name}"] = conf
        except Exception:  # noqa: BLE001
            pass

    home_config = Path.home() / ".claude.json"
    try:
        data = json.loads(home_config.read_text(encoding="utf-8"))
        proj = (data.get("projects") or {}).get(str(root)) or {}
        for name, conf in (proj.get("mcpServers") or {}).items():
            servers[f"user config:{name}"] = conf
    except Exception:  # noqa: BLE001
        pass

    for plugin_root in _installed_plugin_roots(cfg):
        pm = plugin_root / ".mcp.json"
        if pm.is_file():
            try:
                data = json.loads(pm.read_text(encoding="utf-8"))
                pname = _plugin_name(plugin_root)
                for name, conf in (data.get("mcpServers") or {}).items():
                    servers[f"plugin [{pname}]:{name}"] = conf
            except Exception:  # noqa: BLE001
                pass

    return servers


def _mcp_read_line(proc: subprocess.Popen, timeout: float) -> str | None:
    import queue
    import threading

    q: "queue.Queue[str | None]" = queue.Queue()

    def reader() -> None:
        try:
            q.put(proc.stdout.readline())
        except Exception:  # noqa: BLE001
            q.put(None)

    threading.Thread(target=reader, daemon=True).start()
    try:
        return q.get(timeout=timeout)
    except Exception:  # noqa: BLE001
        return None


def mcp_list_tools(conf: dict, cwd: Path, timeout: float = 10) -> tuple[list[dict] | None, str | None]:
    """Spawn a configured MCP server over stdio and ask it for its tool list.

    Best-effort: many servers need network access, API keys, or an `npx`/`uvx` fetch the first
    time they run. A failure here means "not measured", never a silent zero -- the caller reports
    the reason rather than pretending the server costs nothing.
    """
    command = conf.get("command")
    if not command:
        return None, "no command in config"
    env = {**os.environ, **(conf.get("env") or {})}
    try:
        proc = subprocess.Popen(
            [command, *(conf.get("args") or [])], cwd=cwd, env=env,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, encoding="utf-8", errors="replace", bufsize=1,
        )
    except Exception as e:  # noqa: BLE001
        return None, f"spawn failed: {e}"
    try:
        init_req = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2024-11-05", "capabilities": {},
            "clientInfo": {"name": "measure_context", "version": "0.0.0"}}}
        proc.stdin.write(json.dumps(init_req) + "\n")
        proc.stdin.flush()
        if not _mcp_read_line(proc, timeout):
            return None, "no response to initialize (timeout or missing dependency)"
        proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
        proc.stdin.flush()
        proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}) + "\n")
        proc.stdin.flush()
        line = _mcp_read_line(proc, timeout)
        if not line:
            return None, "no response to tools/list (timeout)"
        resp = json.loads(line)
        return (resp.get("result") or {}).get("tools") or [], None
    except Exception as e:  # noqa: BLE001
        return None, str(e)
    finally:
        try:
            proc.terminate()
        except Exception:  # noqa: BLE001
            pass


def main() -> None:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    cfg = config_dir()
    rows: list[tuple[str, int, int]] = []

    # Every instruction file a session auto-loads. `.claude/rules/*.md` and `.claude/CLAUDE.md`
    # are loaded alongside the root CLAUDE.md and were never counted before.
    rows.append(("~/.claude/CLAUDE.md", *measure_file(cfg / "CLAUDE.md")))
    rows.append((f"{root.name}/CLAUDE.md", *measure_file(root / "CLAUDE.md")))
    rows.append((f"{root.name}/CLAUDE.local.md", *measure_file(root / "CLAUDE.local.md")))
    rows.append((f"{root.name}/.claude/CLAUDE.md", *measure_file(root / ".claude" / "CLAUDE.md")))
    for rule in sorted((root / ".claude" / "rules").glob("*.md")):
        rows.append((f".claude/rules/{rule.name}", *measure_file(rule)))

    # The per-project memory index, loaded into context every session and previously missed.
    memory = cfg / "projects" / project_slug(root) / "memory" / "MEMORY.md"
    rows.append(("memory/MEMORY.md (index)", *measure_file(memory)))

    for label, cmd in session_start_hooks(root):
        out = run_hook(cmd, root)
        rows.append((label, len(out.encode("utf-8")), toks(out)))

    rows.extend(skill_and_agent_rows(root, cfg))

    if TOKENS_ARE_ESTIMATED:
        print("\n*** tiktoken NOT INSTALLED -- token counts below are ESTIMATES (~N, bytes/4), "
              "not a real BPE count. ***")
        print(f"*** For exact counts: {TIKTOKEN_INSTALL_HINT} ***")
    else:
        print("\n(token counts below are exact -- tiktoken o200k_base)")

    print(f"\n=== per-session baseline: {root} ===")
    print(f"{'source':<52}{'bytes':>10}{'tokens':>10}")
    print("-" * 72)
    tb = tt = 0
    for name, b, t in rows:
        if b == 0 and t == 0:
            continue                                  # absent -- don't pad the table with zeros
        print(f"{name[:52]:<52}{b:>10,}{fmt_tokens(t):>10}")
        tb += b
        tt += t
    print("-" * 72)
    print(f"{'TOTAL':<52}{tb:>10,}{fmt_tokens(tt):>10}")

    # Files that exist but are NOT auto-loaded -- shown for contrast.
    print("\n--- on disk, NOT auto-loaded (read on demand) ---")
    for rel in ("NEXT.md", "INBOX.md", "BACKLOG.md", "CHANGELOG.md", "docs/pending.md",
                "ARCHITECTURE.md", "agent/AGENTS.md"):
        p = root / rel
        if p.is_file():
            b, t = measure_file(p)
            print(f"{rel:<52}{b:>10,}{fmt_tokens(t):>10}")

    # MCP servers the user has configured (project .mcp.json, ~/.claude.json, plugin-bundled).
    # Left out of TOTAL above: whether a given session sees the deferred (name-only) or full
    # schema form of a tool isn't something this script -- run outside a session -- can know.
    mcp_servers = _mcp_server_configs(root, cfg)
    if mcp_servers:
        print("\n--- configured MCP servers (not in TOTAL -- deferred vs. full form is per-session) ---")
        for label, conf in mcp_servers.items():
            tools, err = mcp_list_tools(conf, root)
            if err or tools is None:
                print(f"{label:<52}  unmeasured ({err})")
                continue
            server_name = label.split(":")[-1]
            deferred = "\n".join(f"mcp__{server_name}__{t.get('name', '')}" for t in tools)
            full = json.dumps(tools)
            print(f"{label} -- deferred names: {fmt_tokens(toks(deferred)):>6} tok"
                  f" | full schemas: {fmt_tokens(toks(full)):>6} tok ({len(tools)} tools)")


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    main()
